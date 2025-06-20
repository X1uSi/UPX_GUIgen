import sys
import os
import subprocess
import configparser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
    QFileDialog, QLineEdit, QLabel, QDialog, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QTextCursor


class DropLineEdit(QLineEdit):
    """支持拖拽的自定义输入框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()

            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    self.setText(file_path)
                    # 触发文本改变信号
                    self.textChanged.emit(file_path)
                    break
        else:
            event.ignore()


class ConfigDialog(QDialog):
    def __init__(self, current_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置UPX路径")
        self.setGeometry(300, 300, 500, 200)

        layout = QVBoxLayout()

        # UPX路径设置
        path_layout = QHBoxLayout()
        self.path_edit = DropLineEdit()  # 使用支持拖拽的自定义输入框
        self.path_edit.setText(current_path)
        self.path_edit.setPlaceholderText("拖拽UPX程序到这里或点击浏览...")
        path_layout.addWidget(self.path_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_upx)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        # 拖拽提示
        drag_label = QLabel("支持拖拽UPX程序到此输入框")
        drag_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(drag_label)

        # 官网链接
        link_label = QLabel(
            '<a href="https://upx.github.io/" style="color: blue; text-decoration: underline;">'
            '访问UPX官网下载最新版本</a>'
        )
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)

        # 按钮区域
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def browse_upx(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择UPX程序", "", "Executable Files (*.exe);;All Files (*)"
        )
        if file_path:
            self.path_edit.setText(file_path)

    def get_path(self):
        return self.path_edit.text()


class UPXGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UPX命令构造工具")
        self.setGeometry(100, 100, 900, 700)  # 增大窗口尺寸

        # 加载配置
        self.config_file = "upx_config.ini"
        self.upx_path = self.load_config()

        # 创建主部件和布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # 使用分割器使结果区域更大
        splitter = QSplitter(Qt.Vertical)

        # 上半部分：参数和文件选择
        top_widget = QWidget()
        top_layout = QVBoxLayout()

        # 1. 参数选择区域
        param_group = QGroupBox("参数选项")
        param_layout = QVBoxLayout()

        # 压缩级别 (单选但可取消)
        level_group = QGroupBox("压缩级别 (默认为:-6，再次点击按钮可取消)")
        level_layout = QHBoxLayout()
        self.level_btns = []
        self.level_btn_group = QButtonGroup(self)
        self.level_btn_group.setExclusive(False)  # 允许取消选择

        for i in range(1, 10):
            btn = QRadioButton(f"-{i}")
            btn.setCheckable(True)
            btn.toggled.connect(self.update_preview)
            level_layout.addWidget(btn)
            self.level_btns.append(btn)
            self.level_btn_group.addButton(btn, i)

        # 添加重置按钮
        reset_btn = QPushButton("重置所有参数")
        reset_btn.setFixedWidth(120)
        reset_btn.setToolTip("清除所有选择的参数")
        reset_btn.clicked.connect(self.reset_parameters)
        level_layout.addWidget(reset_btn)

        level_group.setLayout(level_layout)
        param_layout.addWidget(level_group)

        # 命令选项 (多选)
        cmd_layout = QHBoxLayout()
        self.cmd_options = {
            "-d": QCheckBox("解压缩 (-d)"),
            "-l": QCheckBox("列出信息 (-l)"),
            "-t": QCheckBox("测试文件 (-t)"),
            "-V": QCheckBox("显示版本 (-V)"),
            "-h": QCheckBox("显示帮助 (-h)"),
            "-L": QCheckBox("软件许可 (-L)")
        }
        for option in self.cmd_options.values():
            option.stateChanged.connect(self.update_preview)
            cmd_layout.addWidget(option)
        param_layout.addLayout(cmd_layout)

        # 其他选项 (多选)
        opt_layout = QHBoxLayout()
        self.opt_options = {
            "-q": QCheckBox("静默模式 (-q)"),
            "-v": QCheckBox("详细输出 (-v)"),
            "-f": QCheckBox("强制压缩 (-f)"),
            "-k": QCheckBox("保留备份 (-k)")
        }
        for option in self.opt_options.values():
            option.stateChanged.connect(self.update_preview)
            opt_layout.addWidget(option)
        param_layout.addLayout(opt_layout)

        # 输出文件选项
        out_layout = QHBoxLayout()
        self.out_check = QCheckBox("输出文件 (-o)")
        self.out_check.stateChanged.connect(self.update_preview)
        self.out_edit = DropLineEdit()  # 使用支持拖拽的自定义输入框
        self.out_edit.setPlaceholderText("输出文件路径...")
        self.out_edit.textChanged.connect(self.update_preview)
        out_layout.addWidget(self.out_check)
        out_layout.addWidget(self.out_edit)
        param_layout.addLayout(out_layout)

        param_group.setLayout(param_layout)
        top_layout.addWidget(param_group)

        # 2. 文件选择区域 - 改为单文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout()

        # 文件路径输入框
        file_path_layout = QHBoxLayout()
        file_label = QLabel("文件路径:")
        self.file_path_edit = DropLineEdit()
        self.file_path_edit.setPlaceholderText("拖拽文件到这里或点击浏览...")
        self.file_path_edit.textChanged.connect(self.update_preview)
        file_path_layout.addWidget(file_label)
        file_path_layout.addWidget(self.file_path_edit)

        # 浏览按钮
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_file)
        file_path_layout.addWidget(browse_btn)

        file_layout.addLayout(file_path_layout)

        # 拖拽提示
        # drag_label = QLabel("支持拖拽单个文件到此输入框")
        # drag_label.setStyleSheet("color: gray; font-style: italic;")
        # file_layout.addWidget(drag_label)

        file_group.setLayout(file_layout)
        top_layout.addWidget(file_group)

        top_widget.setLayout(top_layout)
        splitter.addWidget(top_widget)

        # 下半部分：命令预览和执行结果
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout()

        # 3. 命令预览区域
        cmd_group = QGroupBox("命令预览")
        cmd_layout = QVBoxLayout()
        self.cmd_preview = QTextEdit()
        self.cmd_preview.setReadOnly(True)
        self.cmd_preview.setFont(QFont("Courier New", 10))
        cmd_layout.addWidget(self.cmd_preview)
        cmd_group.setLayout(cmd_layout)
        bottom_layout.addWidget(cmd_group)

        # 4. 执行结果区域 - 增大高度
        result_group = QGroupBox("执行结果")
        result_layout = QVBoxLayout()
        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setFont(QFont("Courier New", 9))
        # 设置最小高度为300像素
        self.result_output.setMinimumHeight(300)
        result_layout.addWidget(self.result_output)
        result_group.setLayout(result_layout)
        bottom_layout.addWidget(result_group)

        bottom_widget.setLayout(bottom_layout)
        splitter.addWidget(bottom_widget)

        # 设置分割器比例 (上半部分40%，下半部分60%)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter)

        # 底部按钮
        btn_layout = QHBoxLayout()
        config_btn = QPushButton("配置UPX")
        config_btn.clicked.connect(self.config_upx)
        execute_btn = QPushButton("执行命令")
        execute_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        execute_btn.clicked.connect(self.execute_command)
        btn_layout.addWidget(config_btn)
        btn_layout.addWidget(execute_btn)

        main_layout.addLayout(btn_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 初始更新
        self.update_preview()

    def load_config(self):
        """加载配置文件，如果不存在则创建默认配置"""
        config = configparser.ConfigParser()

        # 默认路径
        default_path = "upx.exe" if sys.platform == "win32" else "upx"

        if os.path.exists(self.config_file):
            config.read(self.config_file)
            return config.get('DEFAULT', 'upx_path', fallback=default_path)
        else:
            # 创建默认配置文件
            config['DEFAULT'] = {'upx_path': default_path}
            with open(self.config_file, 'w') as configfile:
                config.write(configfile)
            return default_path

    def save_config(self, path):
        """保存配置到文件"""
        config = configparser.ConfigParser()
        config['DEFAULT'] = {'upx_path': path}
        with open(self.config_file, 'w') as configfile:
            config.write(configfile)

    def browse_file(self):
        """浏览选择单个文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", "All Files (*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def reset_parameters(self):
        """重置所有参数选项"""
        # 清除压缩级别选择
        for btn in self.level_btns:
            btn.setChecked(False)

        # 清除命令选项
        for cb in self.cmd_options.values():
            cb.setChecked(False)

        # 清除其他选项
        for cb in self.opt_options.values():
            cb.setChecked(False)

        # 清除输出文件设置
        self.out_check.setChecked(False)
        self.out_edit.clear()

        self.update_preview()

    def config_upx(self):
        dialog = ConfigDialog(self.upx_path, self)
        if dialog.exec_() == QDialog.Accepted:
            path = dialog.get_path()
            if path:
                self.upx_path = path
                self.save_config(path)
                self.update_preview()

    def update_preview(self):
        # 构建命令
        cmd_parts = [f'"{self.upx_path}"']  # 添加引号处理路径中的空格

        # 添加压缩级别
        for btn in self.level_btns:
            if btn.isChecked():
                cmd_parts.append(btn.text())

        # 添加命令选项
        for opt, cb in self.cmd_options.items():
            if cb.isChecked():
                cmd_parts.append(opt)

        # 添加其他选项 - 修复错误
        for opt, cb in self.opt_options.items():  # 使用items()而不是values()
            if cb.isChecked():
                cmd_parts.append(opt)

        # 添加输出文件
        if self.out_check.isChecked() and self.out_edit.text():
            cmd_parts.append(f"-o\"{self.out_edit.text()}\"")

        # 添加文件路径
        if self.file_path_edit.text():
            cmd_parts.append(f'"{self.file_path_edit.text()}"')

        # 更新预览
        self.cmd_preview.setPlainText(" ".join(cmd_parts))

    def execute_command(self):
        command = self.cmd_preview.toPlainText()
        if not command:
            QMessageBox.warning(self, "错误", "没有可执行的命令")
            return

        # 检查UPX是否存在
        if not os.path.exists(self.upx_path.strip('"')):
            QMessageBox.critical(
                self, "错误",
                f"找不到UPX程序: {self.upx_path}\n请通过配置按钮设置正确的路径"
            )
            return

        # 检查输入文件是否存在
        input_file = self.file_path_edit.text().strip('"')
        if input_file and not os.path.exists(input_file):
            QMessageBox.critical(
                self, "错误",
                f"找不到输入文件: {input_file}"
            )
            return

        self.result_output.clear()
        self.result_output.append(f"执行命令: {command}")
        self.result_output.append("-" * 50)

        try:
            # 执行命令并捕获输出
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            # 显示输出
            self.result_output.append(result.stdout)
            if result.returncode != 0:
                self.result_output.append(f"\n命令执行失败 (退出码: {result.returncode})")
            else:
                self.result_output.append("\n命令执行成功")

            # 滚动到底部
            self.result_output.moveCursor(QTextCursor.End)
        except Exception as e:
            self.result_output.append(f"执行错误: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UPXGUI()
    window.show()
    sys.exit(app.exec_())
