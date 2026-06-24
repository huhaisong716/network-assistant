#!/usr/bin/env python3
"""NVIDIA Tools — PyQt5 桌面版（8步向导：GPU勾选→依赖→Nouveau→驱动→CUDA→cuDNN→报告）"""

import sys
import os
import json
import threading
import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QComboBox, QLineEdit,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QCheckBox, QProgressBar, QTextEdit, QMessageBox, QFileDialog,
    QGroupBox, QFormLayout, QSpinBox, QFrame, QHeaderView,
    QDialog, QDialogButtonBox, QScrollArea, QButtonGroup,
    QRadioButton, QSplitter, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor

from config import get_servers, add_server, remove_server, get_deepseek_key, set_deepseek_key
from ssh_client import SSHClient
from gpu import detect_all_gpus, GPUInfo, check_nouveau
from driver import (BUILTIN_DRIVERS, DriverOption, get_runfile_url,
                    version_to_apt_package, merge_ubuntu_drivers)
from envcheck import (
    DRIVER_DEPENDENCIES, CUDA_DEPENDENCIES,
    check_all_deps, get_failed, install_dependency, query_ubuntu_drivers,
    detect_os, get_install_cmd, check_dependency,
)
from installer import NouveauManager, DependencyManager, DriverInstaller, reboot_system, wait_for_reboot
from cuda import get_cuda_versions, get_recommended_cuda, install_cuda, CUDAVersion
from cudnn import get_cudnn_versions, get_recommended_cudnn, install_cudnn, CUDNNVersion
from ai_diagnose import diagnose_with_deepseek

# ── 品牌配色 ──────────────────────────────────────────────
DEEP_BLUE = "#005696"
BRIGHT_BLUE = "#00B0F0"
GOLD = "#FFC000"
WHITE = "#FFFFFF"
LIGHT_GRAY = "#F5F5F5"
DARK_TEXT = "#333333"
GREEN_OK = "#27AE60"
RED_ERR = "#E74C3C"
BG_DARK = "#2C3E50"


# ── 确认对话框 ────────────────────────────────────────────
class ConfirmDialog(QMessageBox):
    def __init__(self, title: str, description: str, detail: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setIcon(QMessageBox.Question)
        self.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        self.button(QMessageBox.Yes).setText("同意")
        self.button(QMessageBox.No).setText("取消")
        self.setDefaultButton(QMessageBox.No)
        text = f"<b style='font-size:14px; color:{DEEP_BLUE};'>{description}</b>"
        if detail:
            text += f"<br><br><span style='font-size:12px; color:{DARK_TEXT};'>{detail}</span>"
        self.setText(text)

    def is_accepted(self) -> bool:
        return self.exec() == QMessageBox.Yes


# ── 信号桥 ────────────────────────────────────────────────
class SignalBridge(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, str)
    done_signal = pyqtSignal(bool, str)
    gpu_signal = pyqtSignal(object)
    deps_signal = pyqtSignal(dict)
    check_signal = pyqtSignal(bool)
    nouveau_signal = pyqtSignal(bool, str, list)
    driver_list_signal = pyqtSignal(list)
    cuda_install_signal = pyqtSignal(bool, list)
    cudnn_install_signal = pyqtSignal(bool, list)
    dep_install_done = pyqtSignal(dict)
    reboot_ready = pyqtSignal()


# ── 页面定义 ──────────────────────────────────────────────
PAGES = ["服务器", "显卡设备", "依赖检测", "屏蔽Nouveau", "驱动安装", "CUDA安装", "cuDNN安装", "报告"]
PAGE_COUNT = len(PAGES)


# ═══════════════════════════════════════════════════════════
# 底部状态栏
# ═══════════════════════════════════════════════════════════
class BottomBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"background-color: {DEEP_BLUE};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        self.btn_prev = QPushButton("← 上一步")
        self.btn_prev.setFixedWidth(110)
        self.btn_prev.setEnabled(False)
        self.btn_prev.setStyleSheet(self._btn_style(WHITE, DEEP_BLUE))
        self.page_label = QLabel("1 / 8")
        self.page_label.setStyleSheet(f"color: {GOLD}; font-weight: bold; font-size: 13px;")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.btn_next = QPushButton("下一步 →")
        self.btn_next.setFixedWidth(110)
        self.btn_next.setStyleSheet(self._btn_style(GOLD, BG_DARK))
        self.server_label = QLabel("未连接")
        self.server_label.setStyleSheet(f"color: {WHITE}; font-size: 12px;")
        self.server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_light = QLabel("●")
        self.status_light.setStyleSheet(f"color: {RED_ERR}; font-size: 18px;")
        self.status_light.setFixedWidth(20)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.page_label)
        layout.addStretch()
        layout.addWidget(self.server_label)
        layout.addWidget(self.status_light)
        layout.addWidget(self.btn_next)

    def _btn_style(self, text_color, bg_color):
        return (f"QPushButton {{ background-color: {bg_color}; color: {text_color}; "
                f"border: 1px solid {WHITE}; border-radius: 4px; padding: 6px 12px; "
                f"font-size: 13px; font-weight: bold; }}"
                f"QPushButton:disabled {{ opacity: 0.5; }}")

    def set_server(self, name: str, connected: bool):
        self.server_label.setText(name or "未连接")
        self.status_light.setStyleSheet(
            f"color: {GREEN_OK}; font-size: 18px;" if connected
            else f"color: {RED_ERR}; font-size: 18px;")

    def set_page(self, idx: int):
        self.page_label.setText(f"{idx + 1} / {PAGE_COUNT}")
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText("完成" if idx == PAGE_COUNT - 1 else "下一步 →")


# ═══════════════════════════════════════════════════════════
# 页面 1: 服务器连接（保留原版逻辑）
# ═══════════════════════════════════════════════════════════
class ServerPage(QWidget):
    def __init__(self, bridge: SignalBridge):
        super().__init__()
        self.bridge = bridge
        self._ssh: SSHClient | None = None
        self._init_ui()
        self._load_servers()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🔧 服务器连接")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("添加或选择要安装驱动的远程服务器"))
        group = QGroupBox("已保存的服务器")
        group.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; border: 1px solid {BRIGHT_BLUE}; border-radius: 6px; "
            f"margin-top: 10px; padding-top: 16px; }} QGroupBox::title {{ color: {DEEP_BLUE}; }}")
        gl = QVBoxLayout(group)
        self.server_combo = QComboBox()
        self.server_combo.setMinimumHeight(32)
        gl.addWidget(self.server_combo)
        br = QHBoxLayout()
        self.btn_add = QPushButton("➕ 新增")
        self.btn_edit = QPushButton("✏️ 编辑")
        self.btn_del = QPushButton("🗑️ 删除")
        btn_style = (f"QPushButton {{ background-color: {WHITE}; border: 1px solid {BRIGHT_BLUE}; "
                     f"border-radius: 4px; padding: 6px 14px; color: {DEEP_BLUE}; }} "
                     f"QPushButton:hover {{ background-color: {BRIGHT_BLUE}; color: white; }}")
        for b in (self.btn_add, self.btn_edit, self.btn_del):
            b.setStyleSheet(btn_style)
        br.addWidget(self.btn_add)
        br.addWidget(self.btn_edit)
        br.addWidget(self.btn_del)
        br.addStretch()
        gl.addLayout(br)
        layout.addWidget(group)
        test_g = QGroupBox("连接测试")
        test_g.setStyleSheet(group.styleSheet())
        tl = QVBoxLayout(test_g)
        self.btn_test = QPushButton("🔌 测试连接")
        self.btn_test.setMinimumHeight(36)
        self.btn_test.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 8px 24px; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: {DEEP_BLUE}; }}")
        tl.addWidget(self.btn_test)
        self.test_result = QLabel("")
        self.test_result.setStyleSheet("font-size: 13px; padding: 4px 0;")
        tl.addWidget(self.test_result)
        layout.addWidget(test_g)
        api_g = QGroupBox("DeepSeek API Key（AI 诊断用，选填）")
        api_g.setStyleSheet(group.styleSheet())
        al = QHBoxLayout(api_g)
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("输入 DeepSeek API Key...")
        self.api_input.setEchoMode(QLineEdit.Password)
        self.btn_save_api = QPushButton("保存")
        self.btn_save_api.setStyleSheet(
            f"QPushButton {{ background-color: {GOLD}; color: {DARK_TEXT}; "
            f"border-radius: 4px; padding: 6px 14px; font-weight: bold; }}")
        al.addWidget(self.api_input)
        al.addWidget(self.btn_save_api)
        layout.addWidget(api_g)
        layout.addStretch()
        self.btn_test.clicked.connect(self._test_connection)
        self.btn_add.clicked.connect(self._add_server)
        self.btn_edit.clicked.connect(self._edit_server)
        self.btn_del.clicked.connect(self._del_server)
        self.btn_save_api.clicked.connect(self._save_api_key)
        self.server_combo.currentIndexChanged.connect(lambda: self.test_result.setText(""))

    def _load_servers(self):
        self.server_combo.blockSignals(True)
        self.server_combo.clear()
        self.server_combo.addItem("-- 选择服务器 --", None)
        for s in get_servers():
            self.server_combo.addItem(f"{s['name']} ({s['host']}:{s['port']})", s)
        self.server_combo.blockSignals(False)
        self.api_input.setText(get_deepseek_key())

    def get_server_info(self) -> dict | None:
        d = self.server_combo.currentData()
        self._ssh = getattr(self, '_ssh', None)
        return d

    def get_ssh(self) -> SSHClient | None:
        return self._ssh

    def _test_connection(self):
        info = self.get_server_info()
        if not info:
            self.test_result.setText("⚠️ 请先选择一个服务器")
            self.test_result.setStyleSheet(f"color: {RED_ERR};")
            self.bridge.check_signal.emit(False)
            return
        self.test_result.setText("🔄 连接中...")
        self.test_result.setStyleSheet(f"color: {GOLD};")
        self.btn_test.setEnabled(False)

        def test():
            ssh = SSHClient(host=info["host"], port=info["port"], user=info["user"],
                            password=info.get("password"), key_path=info.get("key_path"))
            err = ssh.connect()
            if err:
                self.test_result.setText(f"❌ {err}")
                self.test_result.setStyleSheet(f"color: {RED_ERR};")
                self._ssh = None
                self.bridge.check_signal.emit(False)
            else:
                self.test_result.setText(f"✅ 连接成功 → {info['host']}")
                self.test_result.setStyleSheet(f"color: {GREEN_OK};")
                self._ssh = ssh
                self.bridge.check_signal.emit(True)
            self.btn_test.setEnabled(True)
        threading.Thread(target=test, daemon=True).start()

    def _add_server(self):
        self._server_dialog("新增服务器", None)

    def _edit_server(self):
        info = self.get_server_info()
        if info:
            self._server_dialog("编辑服务器", info)
        else:
            QMessageBox.information(self, "提示", "请先选择一个服务器")

    def _del_server(self):
        info = self.get_server_info()
        if info:
            ret = QMessageBox.question(self, "确认删除", f"删除服务器 [{info['name']}]？")
            if ret == QMessageBox.Yes:
                remove_server(info["name"])
                self._load_servers()
        else:
            QMessageBox.information(self, "提示", "请先选择一个服务器")

    def _server_dialog(self, title, existing):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(420, 320)
        layout = QFormLayout(dlg)
        ne = QLineEdit(existing.get("name", "") if existing else "")
        he = QLineEdit(existing.get("host", "") if existing else "")
        pe = QSpinBox(); pe.setRange(1, 65535); pe.setValue(existing.get("port", 22) if existing else 22)
        ue = QLineEdit(existing.get("user", "root") if existing else "root")
        ac = QComboBox(); ac.addItems(["密码认证", "密钥认证"])
        ac.setCurrentIndex(1 if existing and existing.get("key_path") else 0)
        pwe = QLineEdit(); pwe.setEchoMode(QLineEdit.Password)
        ke = QLineEdit(); kb = QPushButton("浏览...")
        kl = QHBoxLayout(); kl.addWidget(ke); kl.addWidget(kb)
        if existing:
            if existing.get("password"): pwe.setText(existing["password"])
            if existing.get("key_path"): ke.setText(existing["key_path"])

        def on_auth(idx):
            pwe.setVisible(idx == 0); ke.setVisible(idx == 1); kb.setVisible(idx == 1)
        ac.currentIndexChanged.connect(on_auth); on_auth(ac.currentIndex())

        def browse():
            p, _ = QFileDialog.getOpenFileName(dlg, "选择 SSH 私钥", str(Path.home()))
            if p: ke.setText(p)
        kb.clicked.connect(browse)
        layout.addRow("名称:", ne); layout.addRow("主机:", he); layout.addRow("端口:", pe)
        layout.addRow("用户:", ue); layout.addRow("认证方式:", ac)
        layout.addRow("密码:", pwe); layout.addRow("密钥文件:", kl)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        layout.addRow(buttons)
        if dlg.exec():
            name, host = ne.text().strip(), he.text().strip()
            if not name or not host:
                QMessageBox.warning(self, "错误", "名称和主机不能为空"); return
            server = {"name": name, "host": host, "port": pe.value(), "user": ue.text().strip()}
            if ac.currentIndex() == 0:
                server.update({"auth_type": "password", "password": pwe.text()})
            else:
                server.update({"auth_type": "key", "key_path": ke.text().strip()})
            add_server(server); self._load_servers()

    def _save_api_key(self):
        set_deepseek_key(self.api_input.text().strip())
        QMessageBox.information(self, "提示", "API Key 已保存")

    def close_ssh(self):
        if self._ssh:
            try: self._ssh.close()
            except Exception: pass
            self._ssh = None


# ═══════════════════════════════════════════════════════════
# 页面 2: 显卡检测 + 勾选设备
# ═══════════════════════════════════════════════════════════
class GpuSelectPage(QWidget):
    """多 GPU 检测 + 勾选要安装的 GPU"""
    gpu_checked = pyqtSignal(list)

    def __init__(self, bridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._gpus: list[GPUInfo] = []
        self._checkboxes: list[QCheckBox] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🎮 显卡检测 & 设备选择")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("检测到的 NVIDIA 显卡，勾选要安装驱动的设备："))

        self.btn_detect = QPushButton("🔍 开始检测")
        self.btn_detect.setMinimumHeight(36)
        self.btn_detect.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 8px 24px; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: {DEEP_BLUE}; }}")
        layout.addWidget(self.btn_detect)

        # 设备列表区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {LIGHT_GRAY}; border-radius: 6px; }}")
        self.device_container = QWidget()
        self.device_layout = QVBoxLayout(self.device_container)
        self.device_layout.setContentsMargins(8, 8, 8, 8)
        self.no_gpu_label = QLabel("点击「开始检测」扫描服务器上的 NVIDIA 显卡")
        self.no_gpu_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px;")
        self.device_layout.addWidget(self.no_gpu_label)
        scroll.setWidget(self.device_container)
        layout.addWidget(scroll, 1)

        # 全选按钮
        self.select_all = QCheckBox("全选")
        self.select_all.setEnabled(False)
        self.select_all.setStyleSheet(f"color: {DEEP_BLUE}; font-weight: bold; font-size: 13px;")
        self.select_all.stateChanged.connect(self._toggle_all)
        layout.addWidget(self.select_all)

        self.btn_detect.clicked.connect(self._detect)

    def _detect(self):
        ssh = self.get_ssh()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面连接")
            return
        self.btn_detect.setEnabled(False)
        self._clear_gpus()
        self.no_gpu_label.setText("🔄 检测中...")

        def task():
            result = detect_all_gpus(ssh)
            self.bridge.gpu_signal.emit(result)
            self.btn_detect.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()

    def _clear_gpus(self):
        for cb in self._checkboxes:
            self.device_layout.removeWidget(cb)
            cb.deleteLater()
        self._checkboxes.clear()
        self._gpus = []

    def on_detect_result(self, result):
        self._clear_gpus()
        if isinstance(result, str):
            self.no_gpu_label.setText(f"❌ {result}")
            self.no_gpu_label.setStyleSheet(f"color: {RED_ERR}; font-size: 13px;")
            self.select_all.setEnabled(False)
            return
        self.no_gpu_label.hide()
        self._gpus = result
        for gpu in result:
            mem_str = f"{gpu.memory_mb}MB" if gpu.memory_mb else "?"
            driver_str = f"驱动v{gpu.driver_version}" if gpu.driver_installed else "未装驱动"
            text = f"[GPU{gpu.index}] {gpu.model}  |  {mem_str}  |  {driver_str}  |  PCI:{gpu.pci_id}"
            cb = QCheckBox(text)
            cb.setStyleSheet(
                f"QCheckBox {{ font-size: 13px; padding: 8px; border: 1px solid {LIGHT_GRAY}; "
                f"border-radius: 4px; margin: 2px; }}"
                f"QCheckBox:checked {{ background-color: #E8F4FD; border-color: {BRIGHT_BLUE}; }}"
                f"QCheckBox:hover {{ background-color: {LIGHT_GRAY}; }}")
            cb.setChecked(True)  # 默认全勾
            self._checkboxes.append(cb)
            self.device_layout.addWidget(cb)
        self.device_layout.addStretch()
        self.select_all.setEnabled(True)
        self.select_all.setChecked(True)

    def _toggle_all(self, state):
        for cb in self._checkboxes:
            cb.setChecked(state == Qt.Checked)

    def get_selected_gpus(self) -> list[GPUInfo]:
        return [gpu for gpu, cb in zip(self._gpus, self._checkboxes) if cb.isChecked()]

    def has_selection(self) -> bool:
        return any(cb.isChecked() for cb in self._checkboxes)


# ═══════════════════════════════════════════════════════════
# 页面 3: 依赖检测 + 安装
# ═══════════════════════════════════════════════════════════
class DependencyPage(QWidget):
    """检测系统依赖 → 列出缺失 → 手动勾选 → 安装 → 重新检测"""
    def __init__(self, bridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._dep_results: dict[str, tuple[bool, str]] = {}
        self._dep_checkboxes: dict[str, QCheckBox] = {}
        self._install_buttons: list[QPushButton] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("📦 依赖检测 & 安装")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("检测系统是否缺少安装驱动所需的依赖，勾选后批量安装："))

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["", "依赖项", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setStyleSheet(
            f"QTableWidget {{ border: 1px solid {LIGHT_GRAY}; }} "
            f"QHeaderView::section {{ background-color: {DEEP_BLUE}; color: white; padding: 6px; }}")
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        # 按钮行
        br = QHBoxLayout()
        self.btn_check = QPushButton("🔍 检测依赖")
        self.btn_check.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; "
            f"border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_install = QPushButton("📦 安装选中项")
        self.btn_install.setStyleSheet(
            f"QPushButton {{ background-color: {GOLD}; color: {DARK_TEXT}; "
            f"border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_install.setEnabled(False)
        self.btn_recheck = QPushButton("🔄 重新检测")
        self.btn_recheck.setStyleSheet(
            f"QPushButton {{ background-color: {WHITE}; color: {DEEP_BLUE}; "
            f"border: 1px solid {BRIGHT_BLUE}; border-radius: 4px; padding: 8px 20px; }}")
        self.btn_recheck.setEnabled(False)
        br.addWidget(self.btn_check)
        br.addWidget(self.btn_install)
        br.addWidget(self.btn_recheck)
        br.addStretch()
        layout.addLayout(br)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.status_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas, monospace; "
            "font-size: 11px; border-radius: 4px;")
        layout.addWidget(self.log_view)

        self.bridge.log_signal.connect(self.log_view.append)
        self.bridge.dep_install_done.connect(self._on_install_done)
        self.btn_check.clicked.connect(self._run_check)
        self.btn_install.clicked.connect(self._install_selected)
        self.btn_recheck.clicked.connect(self._run_check)

    def _run_check(self):
        ssh = self.get_ssh()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面连接"); return
        self.status_label.setText("🔄 检测系统类型和依赖..."); self.btn_check.setEnabled(False)

        def task():
            os_type = detect_os(ssh)
            self._os_type = os_type
            results = check_all_deps(ssh, DRIVER_DEPENDENCIES, os_type)
            self.bridge.deps_signal.emit(results)
            self.btn_check.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()

    def on_deps_result(self, results: dict):
        self._dep_results = results
        self.table.setRowCount(len(results))
        failed = 0
        self._dep_checkboxes.clear()
        for i, (key, (ok, detail)) in enumerate(results.items()):
            dep = DRIVER_DEPENDENCIES.get(key, {})
            label = dep.get("label", key)
            cb = QCheckBox()
            cb.setChecked(not ok)  # 缺的默认勾选
            cb.setEnabled(not ok)
            self._dep_checkboxes[key] = cb
            self.table.setCellWidget(i, 0, cb)
            self.table.setItem(i, 1, QTableWidgetItem(label))
            item = QTableWidgetItem(f"✅ {detail[:50]}" if ok else f"❌ {detail[:50]}")
            item.setForeground(QColor(GREEN_OK if ok else RED_ERR))
            self.table.setItem(i, 2, item)
            if not ok: failed += 1

        if failed == 0:
            self.status_label.setText("✅ 所有依赖已满足")
            self.status_label.setStyleSheet(f"color: {GREEN_OK}; font-size: 13px;")
            self.btn_install.setEnabled(False)
            self.btn_recheck.setEnabled(False)
        else:
            self.status_label.setText(f"⚠️ {failed} 项依赖缺失，已自动勾选")
            self.status_label.setStyleSheet(f"color: {GOLD}; font-size: 13px;")
            self.btn_install.setEnabled(True)
            self.btn_recheck.setEnabled(False)

    def _install_selected(self):
        ssh = self.get_ssh()
        if not ssh: return
        selected = [k for k, cb in self._dep_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "提示", "请至少勾选一项依赖"); return
        self.btn_install.setEnabled(False)
        self.log_view.clear()
        self.bridge.log_signal.emit(f"📦 开始安装 {len(selected)} 项依赖...")

        def task():
            os_type = getattr(self, '_os_type', detect_os(ssh))
            _dep_defs = DRIVER_DEPENDENCIES
            for key in selected:
                dep = _dep_defs.get(key, {})
                install_cmd = get_install_cmd(dep, os_type)
                self.bridge.log_signal.emit(f"  安装 {dep.get('label', key)}...")
                ec, out, err = ssh.exec(f"sudo {install_cmd}", timeout=120)
                if ec != 0:
                    self.bridge.log_signal.emit(f"  ✗ {err[:100]}")
                else:
                    self.bridge.log_signal.emit(f"  ✓ 完成")
            # 重新检测
            self.bridge.log_signal.emit(f"🔄 重新检测依赖...")
            results = check_all_deps(ssh, DRIVER_DEPENDENCIES, os_type)
            self.bridge.dep_install_done.emit(results)
        threading.Thread(target=task, daemon=True).start()

    def _on_install_done(self, results):
        self.on_deps_result(results)
        btn_text = self.btn_install.text()
        self.btn_recheck.setEnabled(True)
        if all(ok for ok, _ in results.values()):
            self.status_label.setText("✅ 所有依赖已满足，可以继续")
            self.status_label.setStyleSheet(f"color: {GREEN_OK}; font-size: 13px;")
        else:
            self.status_label.setText("⚠️ 仍有依赖未安装，可重新勾选安装")
            self.status_label.setStyleSheet(f"color: {GOLD}; font-size: 13px;")
            self.btn_install.setEnabled(True)

    def all_deps_ok(self) -> bool:
        return all(ok for ok, _ in self._dep_results.values())


# ═══════════════════════════════════════════════════════════
# 页面 4: 屏蔽 Nouveau
# ═══════════════════════════════════════════════════════════
class NouveauPage(QWidget):
    def __init__(self, bridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._nouveau_disabled = False
        self._needs_reboot = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🚫 屏蔽 Nouveau 驱动")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("Nouveau 开源驱动与 NVIDIA 官方驱动冲突，需要先禁用它"))

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 13px; padding: 8px; border-radius: 4px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas, monospace; "
            "font-size: 11px; border-radius: 4px;")
        layout.addWidget(self.log_view, 1)

        br = QHBoxLayout()
        self.btn_check = QPushButton("🔍 检测状态")
        self.btn_check.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; "
            f"border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_disable = QPushButton("🚫 禁用 Nouveau")
        self.btn_disable.setStyleSheet(
            f"QPushButton {{ background-color: {GOLD}; color: {DARK_TEXT}; "
            f"border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_disable.setEnabled(False)
        self.btn_reboot = QPushButton("🔄 重启系统")
        self.btn_reboot.setStyleSheet(
            f"QPushButton {{ background-color: {RED_ERR}; color: white; "
            f"border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_reboot.setEnabled(False)
        br.addWidget(self.btn_check)
        br.addWidget(self.btn_disable)
        br.addWidget(self.btn_reboot)
        br.addStretch()
        layout.addLayout(br)

        self.bridge.log_signal.connect(self.log_view.append)
        self.btn_check.clicked.connect(self._check_status)
        self.btn_disable.clicked.connect(self._disable_nouveau)
        self.btn_reboot.clicked.connect(self._do_reboot)

    def _check_status(self):
        ssh = self.get_ssh()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面连接"); return
        self.status_label.setStyleSheet("font-size: 13px; padding: 8px;")
        self.log_view.clear()

        def task():
            mgr = NouveauManager(ssh)
            ok, msg = mgr.check_disabled()
            if ok:
                self._nouveau_disabled = True
                self.status_label.setStyleSheet(
                    f"font-size: 13px; padding: 8px; color: {GREEN_OK}; "
                    f"background-color: #E8F8E8; border-radius: 4px;")
                self.status_label.setText(f"✅ {msg}")
                self.btn_disable.setEnabled(False)
                self.btn_reboot.setEnabled(False)
            else:
                self._nouveau_disabled = False
                self.status_label.setStyleSheet(
                    f"font-size: 13px; padding: 8px; color: {RED_ERR}; "
                    f"background-color: #FFE8E8; border-radius: 4px;")
                self.status_label.setText(f"❌ {msg}")
                self.btn_disable.setEnabled(True)
                self.btn_reboot.setEnabled("需重启" in msg)
            self.bridge.nouveau_signal.emit(ok, msg, [])
        threading.Thread(target=task, daemon=True).start()

    def _disable_nouveau(self):
        ssh = self.get_ssh()
        if not ssh: return
        dlg = ConfirmDialog("屏蔽 Nouveau",
                           "即将禁用 Nouveau 开源驱动？\n禁用后需要重启系统才能生效。",
                           "此操作会修改 /etc/modprobe.d/ 配置并更新 initramfs")
        if not dlg.is_accepted(): return
        self.log_view.clear()
        self.btn_disable.setEnabled(False)

        def task():
            mgr = NouveauManager(ssh)
            ok, msg, logs = mgr.disable()
            for l in logs: self.bridge.log_signal.emit(l)
            if ok:
                self._nouveau_disabled = True
                self.status_label.setStyleSheet(
                    f"font-size: 13px; padding: 8px; color: {GREEN_OK}; background: #E8F8E8;")
                self.status_label.setText(f"✅ {msg}")
                self.btn_reboot.setEnabled(True)
            else:
                if "需重启" in msg:
                    self._needs_reboot = True
                    self.btn_reboot.setEnabled(True)
                else:
                    self.status_label.setStyleSheet(
                        f"font-size: 13px; padding: 8px; color: {RED_ERR}; background: #FFE8E8;")
                    self.status_label.setText(f"❌ 禁用失败: {msg}")
        threading.Thread(target=task, daemon=True).start()

    def _do_reboot(self):
        ssh = self.get_ssh()
        if not ssh: return
        dlg = ConfirmDialog("重启系统",
                           "即将重启远程服务器？\n重启后系统会断开连接约 1-2 分钟。",
                           "请确认远程服务器上的工作已保存。重启后本工具会自动重新连接并验证 nouveau 状态。")
        if not dlg.is_accepted(): return
        self.btn_reboot.setEnabled(False)
        self.log_view.clear()
        self.bridge.log_signal.emit("🔄 正在重启服务器...")

        def task():
            ok, msg = reboot_system(ssh)
            self.bridge.log_signal.emit(f"  {msg}")
            if ok:
                info = self.get_ssh()
                # Wait and reconnect
                host = ssh.host; port = ssh.port; user = ssh.user
                pw = ssh.password if hasattr(ssh, 'password') else None
                import socket, time
                deadline = time.time() + 180
                while time.time() < deadline:
                    try:
                        sock = socket.create_connection((host, port), timeout=5)
                        sock.close()
                        new_ssh = SSHClient(host=host, port=port, user=user,
                                            password=pw)
                        err = new_ssh.connect()
                        if not err:
                            self.bridge.log_signal.emit("✅ 服务器已重启，重新连接成功")
                            # 重新检测 nouveau
                            mgr = NouveauManager(new_ssh)
                            ok2, msg2 = mgr.check_disabled()
                            if ok2:
                                self._nouveau_disabled = True
                                self.bridge.log_signal.emit(f"✅ {msg2}")
                                self.status_label.setText(f"✅ {msg2}")
                            else:
                                self.bridge.log_signal.emit(f"⚠️ {msg2}")
                            return
                    except: pass
                    time.sleep(5)
                self.bridge.log_signal.emit("❌ 重启后连接超时，请手动检查")
            else:
                self.bridge.log_signal.emit("❌ 重启指令发送失败")
        threading.Thread(target=task, daemon=True).start()

    def is_disabled(self) -> bool:
        return self._nouveau_disabled


# ═══════════════════════════════════════════════════════════
# 页面 5: 驱动安装
# ═══════════════════════════════════════════════════════════
class DriverInstallPage(QWidget):
    def __init__(self, bridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._drivers: list[DriverOption] = []
        self._selected_version: str | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("💿 显卡驱动安装")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("选择要安装的驱动版本："))

        # 驱动列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            f"QListWidget {{ border: 1px solid {LIGHT_GRAY}; border-radius: 6px; }}"
            f"QListWidget::item {{ padding: 8px; }}"
            f"QListWidget::item:selected {{ background-color: #E8F4FD; color: {DEEP_BLUE}; }}")
        layout.addWidget(self.list_widget, 1)

        # 选择信息
        self.sel_label = QLabel("未选择驱动版本")
        self.sel_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px;")
        layout.addWidget(self.sel_label)

        # 安装方式
        method_g = QGroupBox("安装方式")
        method_g.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; border: 1px solid {BRIGHT_BLUE}; border-radius: 6px; "
            f"margin-top: 10px; padding-top: 16px; }} QGroupBox::title {{ color: {DEEP_BLUE}; }}")
        ml = QVBoxLayout(method_g)
        self.rb_apt = QRadioButton("apt 安装（推荐，自动处理依赖）")
        self.rb_runfile = QRadioButton(".run 文件安装（版本可控）")
        self.rb_apt.setChecked(True)
        ml.addWidget(self.rb_apt); ml.addWidget(self.rb_runfile)
        layout.addWidget(method_g)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.status_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.log_view)

        br = QHBoxLayout()
        self.btn_query = QPushButton("🔍 查询可用驱动")
        self.btn_query.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; "
            f"border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_install = QPushButton("▶ 安装选中驱动")
        self.btn_install.setStyleSheet(
            f"QPushButton {{ background-color: {DEEP_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 10px 30px; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: {BRIGHT_BLUE}; }}")
        self.btn_install.setEnabled(False)
        br.addWidget(self.btn_query)
        br.addWidget(self.btn_install)
        br.addStretch()
        layout.addLayout(br)

        self.bridge.log_signal.connect(self.log_view.append)
        self.bridge.driver_list_signal.connect(self._on_driver_list)
        self.btn_query.clicked.connect(self._query_drivers)
        self.btn_install.clicked.connect(self._install)
        self.list_widget.currentItemChanged.connect(self._on_select)

    def _query_drivers(self):
        ssh = self.get_ssh()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面连接"); return
        self.btn_query.setEnabled(False)
        self.list_widget.clear()
        self.status_label.setText("🔄 查询可用驱动...")

        def task():
            # 先用内置列表
            drivers = list(BUILTIN_DRIVERS)
            # 尝试 ubuntu-drivers
            try:
                ubuntu_drivers = query_ubuntu_drivers(ssh)
                if isinstance(ubuntu_drivers, list) and ubuntu_drivers:
                    drivers = merge_ubuntu_drivers(drivers, ubuntu_drivers)
            except Exception:
                pass
            self._drivers = drivers
            self.bridge.driver_list_signal.emit(drivers)
            self.btn_query.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()

    def _on_driver_list(self, drivers: list):
        self.list_widget.clear()
        for d in drivers:
            text = f"{d.apt_package} ({d.version})"
            if d.is_recommended:
                text += "  ★ 推荐"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, d.version)
            if d.is_recommended:
                item.setForeground(QColor(DEEP_BLUE))
                f = item.font(); f.setBold(True); item.setFont(f)
            self.list_widget.addItem(item)
        self.status_label.setText(f"共 {len(drivers)} 个可用驱动版本")

    def _on_select(self, cur, _):
        if cur:
            self._selected_version = cur.data(Qt.UserRole)
            self.sel_label.setText(f"已选择: {cur.text()}")
            self.btn_install.setEnabled(True)

    def _install(self):
        ssh = self.get_ssh()
        if not ssh or not self._selected_version: return
        dlg = ConfirmDialog("安装驱动",
                           f"即将安装驱动 {self._selected_version}？",
                           "安装过程耗时较长，请勿中断连接。安装时 SSH 终端可能有弹窗，请自行选择。")
        if not dlg.is_accepted(): return
        self.log_view.clear()
        self.btn_install.setEnabled(False)

        def task():
            inst = DriverInstaller(ssh)
            if self.rb_apt.isChecked():
                apt_pkg = version_to_apt_package(self._selected_version)
                self.bridge.log_signal.emit(f"📦 通过 apt 安装 {apt_pkg}...")
                success, logs = inst.install_via_apt(apt_pkg)
            else:
                url = get_runfile_url(self._selected_version)
                self.bridge.log_signal.emit(f"📦 通过 runfile 安装 {self._selected_version}...")
                success, logs = inst.install_via_runfile(self._selected_version, url)
            for l in logs: self.bridge.log_signal.emit(l)
            if success:
                self.status_label.setText("✅ 驱动安装成功")
                self.status_label.setStyleSheet(f"color: {GREEN_OK}; font-size: 13px;")
                self.bridge.done_signal.emit(True, f"驱动 {self._selected_version} 安装成功")
            else:
                self.status_label.setText("❌ 安装失败")
                self.status_label.setStyleSheet(f"color: {RED_ERR}; font-size: 13px;")
                self.bridge.done_signal.emit(False, "安装失败")
            self.btn_install.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()


# ═══════════════════════════════════════════════════════════
# 页面 6: CUDA 安装
# ═══════════════════════════════════════════════════════════
class CudaInstallPage(QWidget):
    def __init__(self, bridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🧩 CUDA Toolkit 安装")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)

        self.cb_install = QCheckBox("安装 CUDA Toolkit")
        self.cb_install.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.cb_install)

        ver_g = QGroupBox("版本选择")
        ver_g.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; border: 1px solid {BRIGHT_BLUE}; border-radius: 6px; "
            f"margin-top: 10px; padding-top: 16px; }} QGroupBox::title {{ color: {DEEP_BLUE}; }}")
        vl = QVBoxLayout(ver_g)
        self.ver_list = QListWidget()
        for v in get_cuda_versions():
            text = f"CUDA {v.version} ({v.full_version})"
            if v.recommended: text += "  ★ 推荐"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, v.full_version)
            if v.recommended:
                item.setForeground(QColor(DEEP_BLUE))
                f = item.font(); f.setBold(True); item.setFont(f)
            self.ver_list.addItem(item)
        vl.addWidget(self.ver_list)
        layout.addWidget(ver_g)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(200)
        self.log_view.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.log_view)

        self.btn_install = QPushButton("📦 安装 CUDA")
        self.btn_install.setStyleSheet(
            f"QPushButton {{ background-color: {DEEP_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 10px 30px; font-size: 14px; }}")
        self.btn_install.setEnabled(False)
        layout.addWidget(self.btn_install)
        layout.addStretch()

        self.bridge.log_signal.connect(self.log_view.append)
        self.ver_list.currentItemChanged.connect(lambda: self.btn_install.setEnabled(
            self.cb_install.isChecked() and self.ver_list.currentItem() is not None))
        self.cb_install.stateChanged.connect(
            lambda: self.btn_install.setEnabled(self.cb_install.isChecked()))
        self.btn_install.clicked.connect(self._install)

    def _install(self):
        ssh = self.get_ssh()
        if not ssh: return
        item = self.ver_list.currentItem()
        if not item: return
        ver_str = item.data(Qt.UserRole)
        dlg = ConfirmDialog("安装 CUDA Toolkit",
                           f"即将安装 CUDA Toolkit {ver_str}？",
                           "安装包约 3-4GB，下载耗时较长。安装后会自动配置环境变量和CUDA软链接。")
        if not dlg.is_accepted(): return
        self.log_view.clear()
        self.btn_install.setEnabled(False)

        def task():
            # 获取已安装的驱动版本
            driver_version = ""
            ec, out, _ = ssh.exec("nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null", timeout=10)
            if ec == 0 and out.strip():
                driver_version = out.strip().split("\n")[0].strip()
                self.bridge.log_signal.emit(f"  检测到驱动版本: {driver_version}")
            success, logs = install_cuda(ssh, ver_str, driver_version=driver_version)
            for l in logs: self.bridge.log_signal.emit(l)
            self.bridge.cuda_install_signal.emit(success, logs)
            self.btn_install.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()


# ═══════════════════════════════════════════════════════════
# 页面 7: cuDNN 安装
# ═══════════════════════════════════════════════════════════
class CudnnInstallPage(QWidget):
    def __init__(self, bridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🧩 cuDNN 安装")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)

        self.cb_install = QCheckBox("安装 cuDNN")
        self.cb_install.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.cb_install)

        ver_g = QGroupBox("版本选择")
        ver_g.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; border: 1px solid {BRIGHT_BLUE}; border-radius: 6px; "
            f"margin-top: 10px; padding-top: 16px; }} QGroupBox::title {{ color: {DEEP_BLUE}; }}")
        vl = QVBoxLayout(ver_g)
        self.ver_list = QListWidget()
        for v in get_cudnn_versions():
            text = f"cuDNN {v.version}（兼容 CUDA {v.cuda_compat}）"
            if v.recommend: text += "  ★ 推荐"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, v.version)
            if v.recommend:
                item.setForeground(QColor(DEEP_BLUE))
                f = item.font(); f.setBold(True); item.setFont(f)
            self.ver_list.addItem(item)
        vl.addWidget(self.ver_list)
        layout.addWidget(ver_g)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(200)
        self.log_view.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.log_view)

        self.btn_install = QPushButton("📦 安装 cuDNN")
        self.btn_install.setStyleSheet(
            f"QPushButton {{ background-color: {DEEP_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 10px 30px; font-size: 14px; }}")
        self.btn_install.setEnabled(False)
        layout.addWidget(self.btn_install)
        layout.addStretch()

        self.bridge.log_signal.connect(self.log_view.append)
        self.ver_list.currentItemChanged.connect(
            lambda: self.btn_install.setEnabled(self.cb_install.isChecked()))
        self.cb_install.stateChanged.connect(
            lambda: self.btn_install.setEnabled(self.cb_install.isChecked()))
        self.btn_install.clicked.connect(self._install)

    def _install(self):
        ssh = self.get_ssh()
        if not ssh: return
        item = self.ver_list.currentItem()
        if not item: return
        ver_str = item.data(Qt.UserRole)
        dlg = ConfirmDialog("安装 cuDNN",
                           f"即将安装 cuDNN {ver_str}？",
                           "cuDNN 安装包约 1-2GB，下载后会自动复制到 CUDA 目录。")
        if not dlg.is_accepted(): return
        self.log_view.clear()
        self.btn_install.setEnabled(False)

        def task():
            success, logs = install_cudnn(ssh, ver_str)
            for l in logs: self.bridge.log_signal.emit(l)
            self.bridge.cudnn_install_signal.emit(success, logs)
            self.btn_install.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()


# ═══════════════════════════════════════════════════════════
# 页面 8: 报告
# ═══════════════════════════════════════════════════════════
class ReportPage(QWidget):
    def __init__(self, get_server_fn, get_gpu_page, get_driver_page):
        super().__init__()
        self.get_server = get_server_fn
        self.get_gpu_page = get_gpu_page
        self.get_driver_page = get_driver_page
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("📋 安装报告")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet(
            f"background-color: {LIGHT_GRAY}; border-radius: 6px; padding: 12px; font-size: 13px;")
        layout.addWidget(self.report_text, 1)

        br = QHBoxLayout()
        self.btn_save = QPushButton("💾 保存报告")
        self.btn_save.setStyleSheet(
            f"QPushButton {{ background-color: {GOLD}; color: {DARK_TEXT}; font-weight: bold; "
            f"border-radius: 6px; padding: 10px 24px; font-size: 14px; }}")
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; "
            f"border-radius: 6px; padding: 10px 24px; }}")
        br.addWidget(self.btn_save)
        br.addWidget(self.btn_refresh)
        br.addStretch()
        layout.addLayout(br)

        self.btn_save.clicked.connect(self._save_report)
        self.btn_refresh.clicked.connect(self._generate)

    def _generate(self):
        server = self.get_server()
        gpu_page = self.get_gpu_page()
        driver_page = self.get_driver_page()
        import datetime

        lines = []
        lines.append("=" * 55)
        lines.append("  NVIDIA 驱动安装报告")
        lines.append("=" * 55)
        lines.append(f"  生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append("\n【服务器】")
        if server:
            lines.append(f"  名称: {server.get('name', 'N/A')}")
            lines.append(f"  地址: {server.get('host', 'N/A')}:{server.get('port', 22)}")
        else:
            lines.append("  未连接")

        lines.append("\n【GPU 设备】")
        selected = gpu_page.get_selected_gpus() if hasattr(gpu_page, 'get_selected_gpus') else []
        if selected:
            for gpu in selected:
                lines.append(f"  GPU{gpu.index}: {gpu.model}")
                lines.append(f"    驱动: {gpu.driver_version or '未安装'}")
                lines.append(f"    显存: {gpu.memory_mb}MB")
        else:
            lines.append("  未选择 GPU")

        drv = driver_page._selected_version if hasattr(driver_page, '_selected_version') else None
        lines.append("\n【驱动安装】")
        lines.append(f"  版本: {drv or '未安装'}")

        lines.append("\n" + "=" * 55)
        self.report_text.setText("\n".join(lines))

    def _save_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存报告", str(Path.home() / "nvidia-install-report.txt"),
            "文本文件 (*.txt)")
        if path:
            with open(path, "w") as f:
                f.write(self.report_text.toPlainText())
            QMessageBox.information(self, "提示", f"报告已保存到:\n{path}")


# ═══════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NVIDIA Tools — 驱动安装助手 v2.0")
        self.setFixedSize(850, 680)
        self.setStyleSheet(f"QMainWindow {{ background-color: {WHITE}; }}")

        self.bridge = SignalBridge()
        self._current_page = 0
        self._ssh: SSHClient | None = None
        self._connected = False
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.page_title = QLabel(PAGES[0])
        self.page_title.setStyleSheet(
            f"background-color: {DEEP_BLUE}; color: white; font-size: 16px; "
            f"font-weight: bold; padding: 12px 24px;")
        ml.addWidget(self.page_title)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {WHITE};")

        self.server_page = ServerPage(self.bridge)
        self.gpu_page = GpuSelectPage(self.bridge, self._get_ssh)
        self.dep_page = DependencyPage(self.bridge, self._get_ssh)
        self.nouveau_page = NouveauPage(self.bridge, self._get_ssh)
        self.driver_page = DriverInstallPage(self.bridge, self._get_ssh)
        self.cuda_page = CudaInstallPage(self.bridge, self._get_ssh)
        self.cudnn_page = CudnnInstallPage(self.bridge, self._get_ssh)
        self.report_page = ReportPage(self.server_page.get_server_info,
                                      self.gpu_page, self.driver_page)

        for page in [self.server_page, self.gpu_page, self.dep_page,
                     self.nouveau_page, self.driver_page, self.cuda_page,
                     self.cudnn_page, self.report_page]:
            self.stack.addWidget(page)

        ml.addWidget(self.stack, 1)

        self.bottom_bar = BottomBar()
        ml.addWidget(self.bottom_bar)

        self.bottom_bar.btn_prev.clicked.connect(self._prev_page)
        self.bottom_bar.btn_next.clicked.connect(self._next_page)

    def _connect_signals(self):
        self.bridge.check_signal.connect(self._on_connection_check)
        self.bridge.gpu_signal.connect(self.gpu_page.on_detect_result)
        self.bridge.deps_signal.connect(self.dep_page.on_deps_result)

    def _get_ssh(self):
        return self.server_page._ssh if hasattr(self.server_page, '_ssh') else None

    def _on_connection_check(self, ok: bool):
        self._connected = ok
        info = self.server_page.get_server_info()
        name = info.get("name", "") if info else ""
        self.bottom_bar.set_server(name, ok)

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._update_page()

    def _next_page(self):
        if self._current_page == PAGE_COUNT - 1:
            return
        # 前置条件检查
        if self._current_page == 0 and not self._connected:
            QMessageBox.warning(self, "提示", "请先测试并连接服务器"); return
        if self._current_page == 1:
            selected = self.gpu_page.get_selected_gpus()
            if not selected:
                QMessageBox.warning(self, "提示", "请先检测显卡并至少勾选一个设备"); return
        if self._current_page == 2:
            if not self.dep_page.all_deps_ok():
                ret = QMessageBox.question(self, "确认", "仍有依赖未安装，是否继续？",
                                          QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.No: return
        if self._current_page == 3:
            if not self.nouveau_page.is_disabled():
                ret = QMessageBox.question(self, "确认", "Nouveau 尚未禁用，是否继续？",
                                          QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.No: return
        self._current_page += 1
        self._update_page()

    def _update_page(self):
        self.stack.setCurrentIndex(self._current_page)
        self.page_title.setText(PAGES[self._current_page])
        self.bottom_bar.set_page(self._current_page)
        if self._current_page == PAGE_COUNT - 1:
            self.report_page._generate()

    def closeEvent(self, event):
        self.server_page.close_ssh()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
