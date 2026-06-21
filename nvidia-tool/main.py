#!/usr/bin/env python3
"""nvidia-tool PyQt5 桌面版 - GPU 驱动安装向导"""

import sys
import os
import time
import traceback
from datetime import datetime
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QComboBox, QLabel, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem, QProgressBar,
    QTextEdit, QCheckBox, QLineEdit, QMessageBox, QFileDialog,
    QInputDialog, QDialog, QFormLayout, QSpinBox, QFrame, QHeaderView,
    QSizePolicy, QDialogButtonBox, QStatusBar, QGroupBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPalette, QTextCursor

# ── 后端模块 ──────────────────────────────────────────────
from config import load_config, save_config, Server, Config, get_log_dir
from ssh_client import SSHClient
from gpu import detect_gpu
from driver import recommend_drivers, get_driver_url
from envcheck import check_env, fix_env
from installer import disable_nouveau, download_driver, run_installer, verify_installation
from cuda import recommend_cuda, install_cuda
from cudnn import recommend_cudnn, install_cudnn
from ai_diagnose import diagnose
from errors import find_known_error

# ── 品牌配色 ──────────────────────────────────────────────
DEEP_BLUE = "#005696"
BRIGHT_BLUE = "#00B0F0"
GOLD = "#FFC000"
BG_LIGHT = "#F5F7FA"
SUCCESS_GREEN = "#27AE60"
ERROR_RED = "#E74C3C"

APP_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {BG_LIGHT};
    font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
}}
QPushButton {{
    background-color: {DEEP_BLUE};
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 4px;
    font-size: 13px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {BRIGHT_BLUE};
}}
QPushButton:pressed {{
    background-color: #004070;
}}
QPushButton:disabled {{
    background-color: #B0BEC5;
    color: #90A4AE;
}}
QPushButton#btnPrev, QPushButton#btnNext {{
    padding: 10px 30px;
    font-size: 14px;
    min-width: 100px;
}}
QPushButton#btnNext {{
    background-color: {GOLD};
    color: #333;
}}
QPushButton#btnNext:hover {{
    background-color: #FFD54F;
}}
QComboBox {{
    padding: 6px 12px;
    border: 1px solid #CCC;
    border-radius: 4px;
    background: white;
    min-height: 20px;
}}
QComboBox:focus {{
    border-color: {BRIGHT_BLUE};
}}
QLineEdit, QSpinBox {{
    padding: 6px 12px;
    border: 1px solid #CCC;
    border-radius: 4px;
    background: white;
    min-height: 20px;
}}
QLineEdit:focus, QSpinBox:focus {{
    border-color: {BRIGHT_BLUE};
}}
QTableWidget, QListWidget, QTextEdit {{
    border: 1px solid #DDD;
    border-radius: 4px;
    background: white;
    alternate-background-color: #F0F4F8;
}}
QHeaderView::section {{
    background-color: {DEEP_BLUE};
    color: white;
    padding: 6px;
    border: none;
    font-weight: bold;
}}
QProgressBar {{
    border: 1px solid #DDD;
    border-radius: 4px;
    text-align: center;
    height: 24px;
    background: white;
}}
QProgressBar::chunk {{
    background-color: {BRIGHT_BLUE};
    border-radius: 3px;
}}
QGroupBox {{
    font-weight: bold;
    border: 1px solid #DDD;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {DEEP_BLUE};
}}
QStatusBar {{
    background: {DEEP_BLUE};
    color: white;
    font-size: 12px;
}}
QLabel#pageTitle {{
    font-size: 18px;
    font-weight: bold;
    color: {DEEP_BLUE};
    padding: 10px 0;
}}
"""


# ═══════════════════════════════════════════════════════════
# Worker — 后台线程执行长时间任务
# ═══════════════════════════════════════════════════════════
class Worker(QObject):
    """在 QThread 中执行 fn(*args, **kwargs)，通过信号汇报结果"""
    started = pyqtSignal()
    progress = pyqtSignal(int, str)   # (percent, message)
    log = pyqtSignal(str)             # 追加日志行
    finished = pyqtSignal(object)     # 返回值
    error = pyqtSignal(str)           # 错误消息

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.started.emit()
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{e}\n{tb}")

    def stop(self):
        """在子类中可重写以支持取消"""
        pass


def run_in_thread(target, callback, error_callback=None, progress_callback=None,
                  log_callback=None):
    """快捷启动一个 worker 线程"""
    thread = QThread()
    worker = Worker(target)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    if error_callback:
        worker.error.connect(error_callback)
    if progress_callback:
        worker.progress.connect(progress_callback)
    if log_callback:
        worker.log.connect(log_callback)
    if callback:
        worker.finished.connect(callback)
        worker.error.connect(lambda e: callback(None))

    thread.start()
    return thread, worker


# ═══════════════════════════════════════════════════════════
# 新增/编辑服务器对话框
# ═══════════════════════════════════════════════════════════
class ServerDialog(QDialog):
    def __init__(self, parent=None, server: Optional[Server] = None):
        super().__init__(parent)
        self.server = server or Server()
        self.setWindowTitle("编辑服务器" if server else "新增服务器")
        self.setModal(True)
        self.resize(400, 280)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("例如: 办公区 GPU 节点")
        layout.addRow("名称:", self.edit_name)

        self.edit_host = QLineEdit()
        self.edit_host.setPlaceholderText("IP 地址或域名")
        layout.addRow("地址:", self.edit_host)

        self.edit_port = QSpinBox()
        self.edit_port.setRange(1, 65535)
        self.edit_port.setValue(22)
        layout.addRow("端口:", self.edit_port)

        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText("默认: root")
        layout.addRow("用户名:", self.edit_user)

        self.edit_key = QLineEdit()
        self.edit_key.setPlaceholderText("默认: ~/.ssh/id_rsa")
        layout.addRow("私钥路径:", self.edit_key)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_data(self):
        s = self.server
        self.edit_name.setText(s.name)
        self.edit_host.setText(s.host)
        self.edit_port.setValue(s.port)
        self.edit_user.setText(s.user)
        self.edit_key.setText(s.key_path)

    def _accept(self):
        if not self.edit_name.text().strip():
            QMessageBox.warning(self, "提示", "请输入服务器名称")
            return
        if not self.edit_host.text().strip():
            QMessageBox.warning(self, "提示", "请输入服务器地址")
            return

        self.server.name = self.edit_name.text().strip()
        self.server.host = self.edit_host.text().strip()
        self.server.port = self.edit_port.value()
        self.server.user = self.edit_user.text().strip() or "root"
        self.server.key_path = self.edit_key.text().strip() or "~/.ssh/id_rsa"
        self.accept()


# ═══════════════════════════════════════════════════════════
# 页面 1: 服务器选择
# ═══════════════════════════════════════════════════════════
class ServerPage(QWidget):
    connected = pyqtSignal(object)  # 连接成功后发射 SSHClient

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self._build_ui()
        self._refresh_servers()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)

        title = QLabel("选择目标服务器")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel("选择一个已保存的服务器，或新增/编辑服务器列表:"))

        # 服务器下拉
        self.combo_server = QComboBox()
        self.combo_server.setMinimumHeight(32)
        layout.addWidget(self.combo_server)

        # 服务器管理按钮
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("➕ 新增")
        self.btn_add.clicked.connect(self._add_server)
        self.btn_edit = QPushButton("✏️ 编辑")
        self.btn_edit.clicked.connect(self._edit_server)
        self.btn_delete = QPushButton("🗑️ 删除")
        self.btn_delete.clicked.connect(self._delete_server)
        for b in (self.btn_add, self.btn_edit, self.btn_delete):
            b.setMaximumWidth(100)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addSpacing(10)

        # API Key 配置
        key_row = QHBoxLayout()
        self.btn_api = QPushButton("🔑 配置 API Key")
        self.btn_api.clicked.connect(self._configure_api)
        self.label_api_status = QLabel("未配置")
        self.label_api_status.setStyleSheet(f"color: {ERROR_RED};")
        key_row.addWidget(self.btn_api)
        key_row.addWidget(self.label_api_status)
        key_row.addStretch()
        layout.addLayout(key_row)

        layout.addSpacing(15)

        # 连接测试区域
        test_group = QGroupBox("连接测试")
        test_layout = QVBoxLayout(test_group)
        self.btn_test = QPushButton("🔌 测试连接")
        self.btn_test.setMinimumHeight(36)
        self.btn_test.clicked.connect(self._test_connection)
        test_layout.addWidget(self.btn_test)

        self.label_status = QLabel("")
        self.label_status.setAlignment(Qt.AlignCenter)
        self.label_status.setMinimumHeight(30)
        font = QFont()
        font.setPointSize(14)
        self.label_status.setFont(font)
        test_layout.addWidget(self.label_status)

        layout.addWidget(test_group)
        layout.addStretch()

    def _refresh_servers(self):
        self.combo_server.clear()
        self.main.cfg = load_config()
        for s in self.main.cfg.servers:
            label = f"{s.name} ({s.user}@{s.host}:{s.port})"
            self.combo_server.addItem(label, s)
        self.btn_edit.setEnabled(self.combo_server.count() > 0)
        self.btn_delete.setEnabled(self.combo_server.count() > 0)
        self.btn_test.setEnabled(self.combo_server.count() > 0)

        # API Key 状态
        if self.main.cfg.api_key:
            key = self.main.cfg.api_key
            self.label_api_status.setText(f"已配置 ({key[:8]}...{key[-4:]})")
            self.label_api_status.setStyleSheet(f"color: {SUCCESS_GREEN};")
        else:
            self.label_api_status.setText("未配置")
            self.label_api_status.setStyleSheet(f"color: {ERROR_RED};")

    def _add_server(self):
        dlg = ServerDialog(self)
        if dlg.exec_():
            self.main.cfg.servers.append(dlg.server)
            save_config(self.main.cfg)
            self._refresh_servers()
            # 选中刚添加的
            idx = self.combo_server.count() - 1
            self.combo_server.setCurrentIndex(idx)

    def _edit_server(self):
        idx = self.combo_server.currentIndex()
        if idx < 0:
            return
        server = self.main.cfg.servers[idx]
        dlg = ServerDialog(self, server)
        if dlg.exec_():
            self.main.cfg.servers[idx] = dlg.server
            save_config(self.main.cfg)
            self._refresh_servers()
            self.combo_server.setCurrentIndex(idx)

    def _delete_server(self):
        idx = self.combo_server.currentIndex()
        if idx < 0:
            return
        server = self.main.cfg.servers[idx]
        sure = QMessageBox.question(
            self, "确认删除", f"确定删除服务器「{server.name}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if sure == QMessageBox.Yes:
            self.main.cfg.servers.pop(idx)
            save_config(self.main.cfg)
            self._refresh_servers()

    def _configure_api(self):
        key, ok = QInputDialog.getText(
            self, "配置 API Key",
            "输入 DeepSeek API Key (留空清空):",
            text=self.main.cfg.api_key if self.main.cfg.api_key else ""
        )
        if ok:
            self.main.cfg.api_key = key.strip()
            save_config(self.main.cfg)
            self._refresh_servers()

    def _test_connection(self):
        idx = self.combo_server.currentIndex()
        if idx < 0:
            return
        server = self.main.cfg.servers[idx]
        self.btn_test.setEnabled(False)
        self.btn_test.setText("连接中...")
        self.label_status.setText("🔄 正在连接...")
        self.label_status.setStyleSheet(f"color: {BRIGHT_BLUE};")

        def _do_connect():
            ssh = SSHClient(server.host, server.port, server.user, server.key_path)
            err = ssh.connect()
            if err:
                # 尝试密码认证
                return {"ok": False, "ssh": ssh, "error": err}
            return {"ok": True, "ssh": ssh, "error": ""}

        def _on_connect(result):
            self.btn_test.setEnabled(True)
            self.btn_test.setText("🔌 测试连接")
            if result is None:
                self.label_status.setText("❌ 连接失败")
                self.label_status.setStyleSheet(f"color: {ERROR_RED};")
                return
            if result["ok"]:
                self.label_status.setText("✅ 连接成功")
                self.label_status.setStyleSheet(f"color: {SUCCESS_GREEN};")
                QMessageBox.information(self, "连接成功",
                    f"已成功连接到 {server.name}")
                result["ssh"].close()
            else:
                err = result["error"]
                # 检查是否需要密码
                if "密码" in err:
                    # 弹出密码对话框
                    self._retry_with_password(server)
                else:
                    self.label_status.setText(f"❌ {err}")
                    self.label_status.setStyleSheet(f"color: {ERROR_RED};")
                    QMessageBox.warning(self, "连接失败", err)

        run_in_thread(_do_connect, _on_connect)

    def _retry_with_password(self, server):
        """密码认证重试"""
        password, ok = QInputDialog.getText(
            self, "SSH 密码认证",
            f"{server.user}@{server.host} 需要密码:",
            QLineEdit.Password
        )
        if not ok or not password:
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("连接中...")
        self.label_status.setText("🔄 密码认证中...")
        self.label_status.setStyleSheet(f"color: {BRIGHT_BLUE};")

        def _do_auth():
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(server.host, port=server.port,
                           username=server.user, password=password,
                           timeout=10, banner_timeout=30)
            ssh = SSHClient(server.host, server.port, server.user, server.key_path)
            ssh.client = client
            return {"ok": True, "ssh": ssh}

        def _on_auth(result):
            self.btn_test.setEnabled(True)
            self.btn_test.setText("🔌 测试连接")
            if result is None:
                self.label_status.setText("❌ 密码认证失败")
                self.label_status.setStyleSheet(f"color: {ERROR_RED};")
                return
            if result.get("ok"):
                self.label_status.setText("✅ 连接成功 (密码认证)")
                self.label_status.setStyleSheet(f"color: {SUCCESS_GREEN};")
                QMessageBox.information(self, "连接成功",
                    f"已通过密码认证连接到 {server.name}")
                result["ssh"].close()

        run_in_thread(_do_auth, _on_auth)

    def get_selected_server(self) -> Optional[Server]:
        idx = self.combo_server.currentIndex()
        if idx >= 0 and idx < len(self.main.cfg.servers):
            return self.main.cfg.servers[idx]
        return None


# ═══════════════════════════════════════════════════════════
# 页面 2: 显卡检测
# ═══════════════════════════════════════════════════════════
class GpuPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)

        title = QLabel("显卡检测")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel("检测远程服务器的显卡型号和驱动状态:"))

        self.btn_detect = QPushButton("🔍 检测显卡")
        self.btn_detect.setMinimumHeight(36)
        self.btn_detect.clicked.connect(self._detect)
        layout.addWidget(self.btn_detect)

        self.label_model = QLabel("")
        self.label_model.setWordWrap(True)
        self.label_model.setMinimumHeight(80)
        self.label_model.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(13)
        self.label_model.setFont(font)
        layout.addWidget(self.label_model)

        # 状态卡片
        self.card_driver = QLabel("")
        self.card_driver.setMinimumHeight(30)
        self.card_driver.setAlignment(Qt.AlignCenter)
        self.card_driver.setStyleSheet(
            f"background: white; border: 1px solid #DDD; border-radius: 6px; padding: 12px;")
        layout.addWidget(self.card_driver)

        self.card_cuda = QLabel("")
        self.card_cuda.setMinimumHeight(30)
        self.card_cuda.setAlignment(Qt.AlignCenter)
        self.card_cuda.setStyleSheet(
            f"background: white; border: 1px solid #DDD; border-radius: 6px; padding: 12px;")
        layout.addWidget(self.card_cuda)

        layout.addStretch()

    def _detect(self):
        ssh = self.main.ssh
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器选择」页连接服务器")
            return

        self.btn_detect.setEnabled(False)
        self.btn_detect.setText("检测中...")
        self.label_model.setText("🔄 正在检测显卡...")

        def _do_detect():
            return detect_gpu(ssh)

        def _on_detect(result):
            self.btn_detect.setEnabled(True)
            self.btn_detect.setText("🔍 检测显卡")
            if result is None:
                self.label_model.setText("❌ 检测失败")
                return

            self.main.gpu_info = result
            model = result.get("model", "未知")
            has_driver = result.get("has_driver", False)
            driver_ver = result.get("driver_version", "")
            cuda_ver = result.get("cuda_version", "")

            self.label_model.setText(f"🖥️ {model}")

            if has_driver:
                self.card_driver.setText(f"✅ 驱动已安装: {driver_ver}")
                self.card_driver.setStyleSheet(
                    f"background: #E8F5E9; border: 1px solid #A5D6A7; "
                    f"border-radius: 6px; padding: 12px; color: {SUCCESS_GREEN};")
            else:
                self.card_driver.setText("❌ 未安装驱动")
                self.card_driver.setStyleSheet(
                    f"background: #FFEBEE; border: 1px solid #EF9A9A; "
                    f"border-radius: 6px; padding: 12px; color: {ERROR_RED};")

            if cuda_ver:
                self.card_cuda.setText(f"✅ CUDA: {cuda_ver}")
                self.card_cuda.setStyleSheet(
                    f"background: #E8F5E9; border: 1px solid #A5D6A7; "
                    f"border-radius: 6px; padding: 12px; color: {SUCCESS_GREEN};")
            else:
                self.card_cuda.setText("CUDA: 未安装")
                self.card_cuda.setStyleSheet(
                    f"background: white; border: 1px solid #DDD; "
                    f"border-radius: 6px; padding: 12px;")

        run_in_thread(_do_detect, _on_detect)


# ═══════════════════════════════════════════════════════════
# 页面 3: 驱动选择
# ═══════════════════════════════════════════════════════════
class DriverPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)

        title = QLabel("选择驱动版本")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel("选择要安装的 NVIDIA 驱动版本:"))

        self.list_drivers = QListWidget()
        self.list_drivers.setMinimumHeight(150)
        layout.addWidget(self.list_drivers)

        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("或手动输入版本号:"))
        self.edit_version = QLineEdit()
        self.edit_version.setPlaceholderText("例如 570.133.00")
        manual_row.addWidget(self.edit_version)
        self.btn_manual = QPushButton("使用此版本")
        self.btn_manual.clicked.connect(self._use_manual)
        self.btn_manual.setMaximumWidth(120)
        manual_row.addWidget(self.btn_manual)
        layout.addLayout(manual_row)

        layout.addStretch()

    def refresh(self):
        """进入本页时自动刷新驱动列表"""
        if not self.main.gpu_info:
            return
        model = self.main.gpu_info.get("model", "")
        if not model:
            return

        drivers = recommend_drivers(model)
        self.list_drivers.clear()
        for d in drivers:
            labels = {"stable": "⭐ 推荐 - 最新稳定版",
                      "lts": "LTS 分支", "legacy": "旧版"}
            label = labels.get(d.get("branch", ""), d.get("branch", ""))
            if d.get("notes"):
                label += f" - {d['notes']}"
            text = f"{d['version']}  ({label})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, d)
            self.list_drivers.addItem(item)

        if self.list_drivers.count() > 0:
            self.list_drivers.setCurrentRow(0)

    def get_selected_driver(self) -> dict:
        """获取选中的驱动信息"""
        item = self.list_drivers.currentItem()
        if item:
            return item.data(Qt.UserRole)
        ver = self.edit_version.text().strip()
        if ver:
            return {"version": ver, "url": get_driver_url(ver)}
        return None

    def _use_manual(self):
        ver = self.edit_version.text().strip()
        if ver:
            QMessageBox.information(self, "已选择",
                f"将安装驱动版本: {ver}")


# ═══════════════════════════════════════════════════════════
# 页面 4: 环境检查
# ═══════════════════════════════════════════════════════════
class EnvPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.env_results = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)

        title = QLabel("环境检查")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel("检查目标服务器的系统环境:"))

        self.btn_check = QPushButton("🔍 开始检查")
        self.btn_check.setMinimumHeight(36)
        self.btn_check.clicked.connect(self._check)
        layout.addWidget(self.btn_check)

        self.table_env = QTableWidget(0, 2)
        self.table_env.setHorizontalHeaderLabels(["状态", "检查项"])
        self.table_env.horizontalHeader().setStretchLastSection(True)
        self.table_env.setColumnWidth(0, 80)
        self.table_env.verticalHeader().setVisible(False)
        self.table_env.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table_env)

        self.btn_fix = QPushButton("🛠️ 一键修复")
        self.btn_fix.setMinimumHeight(36)
        self.btn_fix.setEnabled(False)
        self.btn_fix.clicked.connect(self._fix_all)
        layout.addWidget(self.btn_fix)

        layout.addStretch()

    def _check(self):
        ssh = self.main.ssh
        if not ssh:
            QMessageBox.warning(self, "提示", "请先连接服务器")
            return

        self.btn_check.setEnabled(False)
        self.btn_check.setText("检查中...")

        def _do_check():
            return check_env(ssh)

        def _on_check(result):
            self.btn_check.setEnabled(True)
            self.btn_check.setText("🔍 开始检查")
            if result is None:
                return
            self.env_results = result
            self._populate_table(result)
            has_fail = any(r["status"] == "fail" for r in result)
            self.btn_fix.setEnabled(has_fail)

        run_in_thread(_do_check, _on_check)

    def _populate_table(self, results):
        self.table_env.setRowCount(len(results))
        for i, r in enumerate(results):
            icon = "✅" if r["status"] == "ok" else "❌" if r["status"] == "fail" else "⚠️"
            item_status = QTableWidgetItem(icon)
            item_status.setTextAlignment(Qt.AlignCenter)
            self.table_env.setItem(i, 0, item_status)

            detail = f"{r['name']}: {r['detail']}"
            item_detail = QTableWidgetItem(detail)
            self.table_env.setItem(i, 1, item_detail)

            if r["status"] == "fail":
                item_detail.setBackground(QColor("#FFEBEE"))

    def _fix_all(self):
        ssh = self.main.ssh
        if not ssh:
            return

        self.btn_fix.setEnabled(False)
        self.btn_fix.setText("修复中...")

        def _do_fix():
            for r in self.env_results:
                if r["status"] == "fail":
                    fix_env(ssh, r)
            return check_env(ssh)  # 重新检查

        def _on_fix(result):
            self.btn_fix.setEnabled(True)
            self.btn_fix.setText("🛠️ 一键修复")
            if result:
                self.env_results = result
                self._populate_table(result)
                has_fail = any(r["status"] == "fail" for r in result)
                self.btn_fix.setEnabled(has_fail)
                if not has_fail:
                    QMessageBox.information(self, "修复完成",
                        "所有环境检查项已通过 ✅")

        run_in_thread(_do_fix, _on_fix)

    def is_all_ok(self) -> bool:
        return all(r["status"] == "ok" for r in self.env_results) \
            if self.env_results else True


# ═══════════════════════════════════════════════════════════
# 页面 5: 安装驱动
# ═══════════════════════════════════════════════════════════
class InstallPage(QWidget):
    install_done = pyqtSignal(object)  # 安装完成后发射更新的 gpu_info

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)

        title = QLabel("安装驱动")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        layout.addWidget(QLabel("正在安装 NVIDIA 驱动，请勿关闭窗口:"))

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        self.log_text.setStyleSheet(
            "font-family: 'Cascadia Code', 'Fira Code', monospace; "
            "font-size: 12px; background: #1E1E2E; color: #CDD6F4;")
        layout.addWidget(self.log_text)

        self.btn_install = QPushButton("🚀 开始安装")
        self.btn_install.setMinimumHeight(40)
        self.btn_install.clicked.connect(self._install)
        layout.addWidget(self.btn_install)

        layout.addStretch()

    def _log(self, msg):
        self.log_text.append(msg)
        # 滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def _install(self):
        ssh = self.main.ssh
        if not ssh:
            QMessageBox.warning(self, "提示", "请先连接服务器")
            return

        driver = self.main.selected_driver
        if not driver:
            QMessageBox.warning(self, "提示", "请先在「驱动选择」页选择驱动")
            return

        ver = driver["version"]
        url = driver["url"]

        self.btn_install.setEnabled(False)
        self.btn_install.setText("安装中...")
        self.progress.setValue(0)
        self.log_text.clear()

        def _do_install(progress_signal, log_signal):
            def log_msg(msg):
                log_signal.emit(msg)

            # 阶段 1: 下载 (0-20%)
            progress_signal.emit(5, "正在下载驱动...")
            log_msg(f"📥 下载驱动 {ver}...")
            err = download_driver(ssh, ver, url)
            if err:
                log_msg(f"❌ 下载失败: {err}")
                raise Exception(err)
            log_msg("✅ 下载完成")
            progress_signal.emit(20, "下载完成")

            # 阶段 2: 禁用 nouveau (20-30%)
            progress_signal.emit(20, "正在禁用 nouveau...")
            log_msg("🔧 禁用 nouveau...")
            disable_nouveau(ssh)
            log_msg("✅ nouveau 已禁用")
            progress_signal.emit(30, "nouveau 已禁用")

            # 阶段 3: 安装 (30-80%)
            progress_signal.emit(30, "正在安装驱动...")
            log_msg("🔨 运行安装程序...")
            known_err, out, err_out = run_installer(ssh, ver)

            if known_err:
                log_msg(f"⚠️ 已知错误: {known_err['title']}")
                # 尝试本地修复
                fix_cmd = known_err.get("fix", "")
                if fix_cmd:
                    log_msg(f"🛠️ 尝试自动修复: {fix_cmd}")
                    ssh.exec(fix_cmd, timeout=120)
                    log_msg("↩️ 重试安装...")
                    known_err2, _, _ = run_installer(ssh, ver)
                    if known_err2:
                        log_msg(f"❌ 重试仍失败: {known_err2['title']}")
                        diag = diagnose("",
                            known_err2['title'], "")
                        if prompt_result(diag, log_msg):
                            if diag.get("fix"):
                                ssh.exec(diag["fix"], timeout=120)

            # 收集所有输出
            combined = out + "\n" + err_out
            if combined.strip():
                log_msg(f"📋 安装日志:\n{combined[:2000]}")
                # AI 诊断
                if self.main.cfg.api_key:
                    log_msg("🤖 AI 诊断中...")
                    diag = diagnose(self.main.cfg.api_key, combined,
                                    self.main.gpu_info.get("model", ""))
                    if prompt_result(diag, log_msg):
                        if diag.get("fix"):
                            ssh.exec(diag["fix"], timeout=120)

            progress_signal.emit(80, "安装完成，验证中...")
            log_msg("✅ 安装流程完成，验证中...")

            # 阶段 4: 验证 (80-100%)
            updated = verify_installation(ssh)
            progress_signal.emit(100, "验证完成")
            return updated

        def prompt_result(diag, log_fn):
            """在桌面环境中显示修复建议并等待用户确认"""
            if diag and diag.get("fix"):
                msg = diag.get("reason", "") or diag.get("title", "")
                fix = diag.get("fix", "")
                log_fn(f"💡 建议修复: {msg}")
                log_fn(f"  命令: {fix}")
                # 自动执行修复（不打断流程）
                return True
            return False

        def _on_progress(percent, msg):
            self.progress.setValue(percent)

        def _on_log(msg):
            self._log(msg)

        def _on_done(result):
            self.btn_install.setEnabled(True)
            self.btn_install.setText("🚀 开始安装")
            self.progress.setValue(100)
            if result and result.get("has_driver"):
                self.main.gpu_info = result
                self._log("🎉 驱动安装成功！")
                QMessageBox.information(self, "安装成功",
                    f"驱动 {result.get('driver_version', ver)} 安装成功！")
            else:
                self._log("⚠️ 安装可能不完整，请检查日志")

        def _do_with_signals():
            return _do_install(_on_progress, _on_log)

        run_in_thread(_do_with_signals, _on_done)


# ═══════════════════════════════════════════════════════════
# 页面 6: CUDA/cuDNN
# ═══════════════════════════════════════════════════════════
class CudaPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)

        title = QLabel("CUDA / cuDNN 安装")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.chk_cuda = QCheckBox("安装 CUDA Toolkit")
        self.chk_cuda.setStyleSheet("font-size: 14px; padding: 8px 0;")
        layout.addWidget(self.chk_cuda)

        self.chk_cudnn = QCheckBox("安装 cuDNN")
        self.chk_cudnn.setStyleSheet("font-size: 14px; padding: 8px 0;")
        layout.addWidget(self.chk_cudnn)

        self.btn_install = QPushButton("开始安装")
        self.btn_install.setMinimumHeight(36)
        self.btn_install.clicked.connect(self._install)
        layout.addWidget(self.btn_install)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        self.log_text.setStyleSheet(
            "font-family: 'Cascadia Code', 'Fira Code', monospace; "
            "font-size: 12px; background: #1E1E2E; color: #CDD6F4;")
        layout.addWidget(self.log_text)

        layout.addStretch()

    def _log(self, msg):
        self.log_text.append(msg)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def _install(self):
        ssh = self.main.ssh
        if not ssh:
            QMessageBox.warning(self, "提示", "请先连接服务器")
            return

        self.btn_install.setEnabled(False)
        self.btn_install.setText("安装中...")
        self.log_text.clear()

        gpu = self.main.gpu_info or {}

        def _do_install():
            logs = []
            if self.chk_cuda.isChecked():
                logs.append("📦 安装 CUDA Toolkit...")
                cuda_entry = recommend_cuda(gpu.get("driver_version", ""))
                logs.append(f"  推荐版本: {cuda_entry['version']}")
                err = install_cuda(ssh, cuda_entry)
                if err:
                    logs.append(f"❌ CUDA 安装失败: {err}")
                else:
                    logs.append("✅ CUDA 安装成功")

            if self.chk_cudnn.isChecked():
                cuda_ver = gpu.get("cuda_version", "12")
                logs.append(f"\n📦 安装 cuDNN (CUDA {cuda_ver})...")
                cudnn_entry = recommend_cudnn(cuda_ver)
                logs.append(f"  推荐版本: {cudnn_entry['version']}")
                err = install_cudnn(ssh, cudnn_entry)
                if err:
                    logs.append(f"❌ cuDNN 安装失败: {err}")
                else:
                    logs.append("✅ cuDNN 安装成功")

            return "\n".join(logs)

        def _on_done(result):
            self.btn_install.setEnabled(True)
            self.btn_install.setText("开始安装")
            if result:
                self.log_text.setPlainText(result)
                if "失败" not in result:
                    QMessageBox.information(self, "安装完成",
                        "CUDA / cuDNN 安装完成！")

        run_in_thread(_do_install, _on_done)


# ═══════════════════════════════════════════════════════════
# 页面 7: 完成报告
# ═══════════════════════════════════════════════════════════
class SummaryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 10, 30, 10)

        title = QLabel("安装报告")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.report_text = QLabel("")
        self.report_text.setWordWrap(True)
        self.report_text.setMinimumHeight(300)
        self.report_text.setStyleSheet(
            "background: white; border: 1px solid #DDD; "
            "border-radius: 6px; padding: 20px; "
            "font-size: 14px; line-height: 1.8;")
        self.report_text.setAlignment(Qt.AlignTop)
        layout.addWidget(self.report_text)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("💾 保存报告")
        self.btn_save.clicked.connect(self._save_report)
        btn_row.addWidget(self.btn_save)
        self.btn_new = QPushButton("🔄 重新开始")
        self.btn_new.clicked.connect(self._restart)
        btn_row.addWidget(self.btn_new)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

    def refresh(self):
        """加载报告内容"""
        ssh = self.main.ssh
        gpu = self.main.gpu_info or {}
        elapsed = time.time() - self.main.start_time

        host = ssh.host if ssh else "未连接"
        model = gpu.get("model", "未检测")
        driver = gpu.get("driver_version", "未安装")
        cuda = gpu.get("cuda_version", "未安装")

        report = (
            f"📋 安装报告\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🖥️ 服务器: {host}\n"
            f"💳 显卡:   {model}\n"
            f"🔧 驱动:   {driver}\n"
            f"📐 CUDA:   {cuda}\n"
            f"⏱️ 耗时:   {int(elapsed // 60)} 分 {int(elapsed % 60)} 秒\n"
            f"📂 日志:   {get_log_dir()}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ 安装完成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.report_text.setText(report)

    def _save_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存报告",
            f"nvidia-install-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.report_text.text())
            QMessageBox.information(self, "已保存", f"报告已保存到:\n{path}")

    def _restart(self):
        """重新开始整个流程"""
        if self.main.ssh:
            self.main.ssh.close()
            self.main.ssh = None
        self.main.start_time = time.time()
        self.main.gpu_info = None
        self.main.selected_driver = None
        self.main.stack.setCurrentIndex(0)


# ═══════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.ssh: Optional[SSHClient] = None
        self.gpu_info: Optional[dict] = None
        self.selected_driver: Optional[dict] = None
        self.start_time = time.time()

        self.setWindowTitle("NVIDIA 驱动安装助手 v2.0")  # 触发重编
        self.resize(800, 600)
        self._center()
        self.setStyleSheet(APP_STYLE)

        self._build_ui()
        self._setup_nav()

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 800) // 2
        y = (screen.height() - 600) // 2
        self.move(x, y)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部标题栏
        header = QFrame()
        header.setStyleSheet(f"background: {DEEP_BLUE}; padding: 10px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 8, 20, 8)

        title_label = QLabel("NVIDIA 驱动安装助手")
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_label)

        # 步骤指示器
        self.step_label = QLabel("步骤 1/7")
        self.step_label.setStyleSheet(
            f"color: {GOLD}; font-size: 14px; font-weight: bold; padding: 0 10px;")
        header_layout.addWidget(self.step_label)
        header_layout.addStretch()

        # 状态指示
        self.connection_label = QLabel("🔴 未连接")
        self.connection_label.setStyleSheet("color: white; font-size: 12px;")
        header_layout.addWidget(self.connection_label)

        main_layout.addWidget(header)

        # 内容区域（QStackedWidget）
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {BG_LIGHT};")

        self.page_servers = ServerPage(self)
        self.page_gpu = GpuPage(self)
        self.page_driver = DriverPage(self)
        self.page_env = EnvPage(self)
        self.page_install = InstallPage(self)
        self.page_cuda = CudaPage(self)
        self.page_summary = SummaryPage(self)

        self.stack.addWidget(self.page_servers)   # 0
        self.stack.addWidget(self.page_gpu)        # 1
        self.stack.addWidget(self.page_driver)     # 2
        self.stack.addWidget(self.page_env)        # 3
        self.stack.addWidget(self.page_install)    # 4
        self.stack.addWidget(self.page_cuda)       # 5
        self.stack.addWidget(self.page_summary)    # 6

        main_layout.addWidget(self.stack, 1)

        # 底部导航栏
        nav_bar = QFrame()
        nav_bar.setStyleSheet(f"background: white; border-top: 1px solid #DDD;")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(20, 10, 20, 10)

        self.btn_prev = QPushButton("← 上一步")
        self.btn_prev.setObjectName("btnPrev")
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_prev.setEnabled(False)

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addStretch()

        self.btn_next = QPushButton("下一步 →")
        self.btn_next.setObjectName("btnNext")
        self.btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self.btn_next)

        main_layout.addWidget(nav_bar)

        # 状态栏
        status_bar = self.statusBar()
        status_bar.showMessage("就绪")

    def _setup_nav(self):
        """设置页面导航逻辑"""
        self.PAGE_NAMES = [
            "服务器选择", "显卡检测", "驱动选择",
            "环境检查", "安装驱动", "CUDA/cuDNN", "完成报告"
        ]
        self._update_nav()

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.step_label.setText(f"步骤 {idx + 1}/7 — {self.PAGE_NAMES[idx]}")
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText("完成 ✓" if idx == 6 else "下一步 →")

    def _go_prev(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _go_next(self):
        idx = self.stack.currentIndex()
        if idx == 0:
            # 服务器选择 → 需要先连接 SSH
            self._connect_and_advance()
            return
        elif idx == 1:
            # 显卡检测 → 如果没有 GPU 信息，阻止前进
            if not self.gpu_info:
                QMessageBox.warning(self, "提示", "请先检测显卡")
                return
        elif idx == 2:
            # 驱动选择 → 保存选中的驱动
            driver = self.page_driver.get_selected_driver()
            if not driver:
                QMessageBox.warning(self, "提示", "请选择一个驱动版本")
                return
            self.selected_driver = driver
        elif idx == 3:
            # 环境检查 → 非必须，可跳过
            pass
        elif idx == 4:
            # 安装后自动刷新 GPU 信息
            pass
        elif idx == 5:
            # CUDA 后到汇总
            pass
        elif idx == 6:
            # 完成
            QMessageBox.information(self, "完成",
                "所有操作已完成！点击「重新开始」可进行下一次安装。")
            return

        # 导航到下一页
        if idx + 1 < self.stack.count():
            # 特殊处理：进入驱动选择页时刷新列表
            if idx + 1 == 2:
                self.page_driver.refresh()
            # 进入汇总页时刷新报告
            if idx + 1 == 6:
                self.page_summary.refresh()
            self.stack.setCurrentIndex(idx + 1)
            self._update_nav()

    def _connect_and_advance(self):
        """从服务器选择页连接到选中服务器，然后前进到下一页"""
        server = self.page_servers.get_selected_server()
        if not server:
            QMessageBox.warning(self, "提示", "请先选择服务器")
            return

        self.btn_next.setEnabled(False)
        self.btn_next.setText("连接中...")

        self.connection_label.setText("🔄 连接中...")
        self.connection_label.setStyleSheet("color: #FFC000; font-size: 12px;")

        def _do_connect():
            ssh = SSHClient(server.host, server.port, server.user, server.key_path)
            err = ssh.connect()
            if err:
                # 尝试密码认证
                if "密码" in err:
                    return {"need_password": True, "server": server}
                return {"ok": False, "error": err}
            return {"ok": True, "ssh": ssh}

        def _on_connect(result):
            self.btn_next.setEnabled(True)
            self.btn_next.setText("下一步 →")

            if result is None:
                self.connection_label.setText("🔴 连接失败")
                QMessageBox.critical(self, "连接失败", "无法连接到服务器")
                return

            if result.get("need_password"):
                self._connect_with_password(server)
                return

            if result.get("ok"):
                self.ssh = result["ssh"]
                self.connection_label.setText(f"🟢 {server.name} ({server.host})")
                self.connection_label.setStyleSheet("color: #27AE60; font-size: 12px;")
                self.statusBar().showMessage(f"已连接: {server.name}")

                # 前进到下一页
                self.stack.setCurrentIndex(1)
                self._update_nav()
            else:
                self.connection_label.setText("🔴 连接失败")
                QMessageBox.critical(self, "连接失败", result.get("error", ""))

        run_in_thread(_do_connect, _on_connect)

    def _connect_with_password(self, server):
        """密码认证连接"""
        password, ok = QInputDialog.getText(
            self, "SSH 密码",
            f"{server.user}@{server.host} 需要密码:",
            QLineEdit.Password
        )
        if not ok or not password:
            self.connection_label.setText("🔴 未连接")
            return

        self.btn_next.setEnabled(False)
        self.btn_next.setText("连接中...")

        def _do_auth():
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(server.host, port=server.port,
                           username=server.user, password=password,
                           timeout=10, banner_timeout=30)
            ssh = SSHClient(server.host, server.port, server.user, server.key_path)
            ssh.client = client
            return {"ok": True, "ssh": ssh}

        def _on_auth(result):
            self.btn_next.setEnabled(True)
            self.btn_next.setText("下一步 →")
            if result and result.get("ok"):
                self.ssh = result["ssh"]
                self.connection_label.setText(f"🟢 {server.name} ({server.host})")
                self.connection_label.setStyleSheet("color: #27AE60; font-size: 12px;")
                self.statusBar().showMessage(f"已连接: {server.name}")
                self.stack.setCurrentIndex(1)
                self._update_nav()
            else:
                self.connection_label.setText("🔴 认证失败")
                QMessageBox.critical(self, "认证失败", "密码认证失败")

        run_in_thread(_do_auth, _on_auth)

    def closeEvent(self, event):
        """关闭时断开 SSH"""
        if self.ssh:
            try:
                self.ssh.close()
            except Exception:
                pass
        event.accept()


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NVIDIA 驱动安装助手")
    app.setOrganizationName("DYC")

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
