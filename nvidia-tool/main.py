#!/usr/bin/env python3
"""NVIDIA Tools — PyQt5 桌面版（7步向导）"""

import sys
import os
import json
import threading
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QComboBox, QLineEdit,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QCheckBox, QProgressBar, QTextEdit, QMessageBox, QFileDialog,
    QGroupBox, QFormLayout, QSpinBox, QFrame, QHeaderView, QStatusBar,
    QSplitter,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon

# ── 后端模块 ──────────────────────────────────────────────
from config import get_servers, add_server, remove_server, get_deepseek_key, set_deepseek_key
from ssh_client import SSHClient
from gpu import detect_gpu
from driver import RECOMMENDED_DRIVERS, get_recommended_for_gpu, get_download_url
from envcheck import EnvChecker, CHECK_LABELS
from installer import Installer
from cuda import install_cuda, get_cuda_versions
from cudnn import install_cudnn, get_cudnn_versions
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

# ── 页面定义 ──────────────────────────────────────────────
PAGES = ["服务器", "显卡检测", "驱动选择", "环境检查", "安装", "CUDA/cuDNN", "报告"]
PAGE_COUNT = len(PAGES)


# ── 信号桥（跨线程更新 UI） ──────────────────────────────
class SignalBridge(QObject):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, str)
    step_signal = pyqtSignal(int)
    done_signal = pyqtSignal(bool, str)
    gpu_signal = pyqtSignal(object)
    env_signal = pyqtSignal(dict)
    check_signal = pyqtSignal(bool)
    verify_signal = pyqtSignal(bool, str)


# ── 底部状态栏部件 ──────────────────────────────────────
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

        self.page_label = QLabel("1 / 7")
        self.page_label.setStyleSheet(f"color: {GOLD}; font-weight: bold; font-size: 13px;")
        self.page_label.setAlignment(Qt.AlignCenter)

        self.btn_next = QPushButton("下一步 →")
        self.btn_next.setFixedWidth(110)
        self.btn_next.setStyleSheet(self._btn_style(GOLD, "#2C3E50"))

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
        return (
            f"QPushButton {{ background-color: {bg_color}; color: {text_color}; "
            f"border: 1px solid {WHITE}; border-radius: 4px; padding: 6px 12px; "
            f"font-size: 13px; font-weight: bold; }}"
            f"QPushButton:disabled {{ opacity: 0.5; }}"
        )

    def set_server(self, name: str, connected: bool):
        self.server_label.setText(name or "未连接")
        self.status_light.setStyleSheet(
            f"color: {GREEN_OK}; font-size: 18px;" if connected
            else f"color: {RED_ERR}; font-size: 18px;"
        )

    def set_page(self, idx: int):
        self.page_label.setText(f"{idx + 1} / {PAGE_COUNT}")
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setText("完成" if idx == PAGE_COUNT - 1 else "下一步 →")


# ── 页面 1: 服务器配置 ──────────────────────────────────
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

        desc = QLabel("添加或选择要安装驱动的远程服务器")
        desc.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; margin-bottom: 12px;")
        layout.addWidget(desc)

        # 已保存服务器列表
        group = QGroupBox("已保存的服务器")
        group.setStyleSheet(f"QGroupBox {{ font-weight: bold; border: 1px solid {BRIGHT_BLUE}; border-radius: 6px; margin-top: 10px; padding-top: 16px; }} QGroupBox::title {{ color: {DEEP_BLUE}; }}")
        glayout = QVBoxLayout(group)

        self.server_combo = QComboBox()
        self.server_combo.setMinimumHeight(32)
        glayout.addWidget(self.server_combo)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("➕ 新增")
        self.btn_edit = QPushButton("✏️ 编辑")
        self.btn_del = QPushButton("🗑️ 删除")
        for b in (self.btn_add, self.btn_edit, self.btn_del):
            b.setStyleSheet(f"QPushButton {{ background-color: {WHITE}; border: 1px solid {BRIGHT_BLUE}; border-radius: 4px; padding: 6px 14px; color: {DEEP_BLUE}; }} QPushButton:hover {{ background-color: {BRIGHT_BLUE}; color: white; }}")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch()
        glayout.addLayout(btn_row)

        layout.addWidget(group)

        # 连接测试
        test_group = QGroupBox("连接测试")
        test_group.setStyleSheet(group.styleSheet())
        tlayout = QVBoxLayout(test_group)
        self.btn_test = QPushButton("🔌 测试连接")
        self.btn_test.setMinimumHeight(36)
        self.btn_test.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 8px 24px; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: {DEEP_BLUE}; }}"
        )
        tlayout.addWidget(self.btn_test)
        self.test_result = QLabel("")
        self.test_result.setStyleSheet(f"font-size: 13px; padding: 4px 0;")
        tlayout.addWidget(self.test_result)
        layout.addWidget(test_group)

        # API Key 设置
        api_group = QGroupBox("DeepSeek API Key（AI 诊断）")
        api_group.setStyleSheet(group.styleSheet())
        alayout = QHBoxLayout(api_group)
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("输入 DeepSeek API Key...")
        self.api_input.setEchoMode(QLineEdit.Password)
        self.api_input.setMinimumHeight(30)
        self.btn_save_api = QPushButton("保存")
        self.btn_save_api.setStyleSheet(f"QPushButton {{ background-color: {GOLD}; color: {DARK_TEXT}; border-radius: 4px; padding: 6px 14px; font-weight: bold; }}")
        alayout.addWidget(self.api_input)
        alayout.addWidget(self.btn_save_api)
        layout.addWidget(api_group)

        layout.addStretch()

        # 信号连接
        self.btn_test.clicked.connect(self._test_connection)
        self.btn_add.clicked.connect(self._add_server)
        self.btn_edit.clicked.connect(self._edit_server)
        self.btn_del.clicked.connect(self._del_server)
        self.btn_save_api.clicked.connect(self._save_api_key)
        self.server_combo.currentIndexChanged.connect(self._on_server_selected)

    def _load_servers(self):
        self.server_combo.blockSignals(True)
        self.server_combo.clear()
        self.server_combo.addItem("-- 选择服务器 --", None)
        for s in get_servers():
            self.server_combo.addItem(f"{s['name']} ({s['host']}:{s['port']})", s)
        self.server_combo.blockSignals(False)
        self.api_input.setText(get_deepseek_key())

    def _on_server_selected(self):
        self.test_result.setText("")

    def get_server_info(self) -> dict | None:
        data = self.server_combo.currentData()
        return data

    def get_ssh(self) -> SSHClient | None:
        return self._ssh

    def _test_connection(self):
        info = self.get_server_info()
        if not info:
            self.test_result.setText("⚠️ 请先选择一个服务器")
            self.test_result.setStyleSheet(f"color: {RED_ERR}; font-size: 13px;")
            self.bridge.check_signal.emit(False)
            return

        self.test_result.setText("🔄 连接中...")
        self.test_result.setStyleSheet(f"color: {GOLD}; font-size: 13px;")
        self.btn_test.setEnabled(False)

        def test():
            ssh = SSHClient(
                host=info["host"], port=info["port"], user=info["user"],
                password=info.get("password"), key_path=info.get("key_path"),
            )
            err = ssh.connect()
            if err:
                self.test_result.setText(f"❌ {err}")
                self.test_result.setStyleSheet(f"color: {RED_ERR}; font-size: 13px;")
                self._ssh = None
                self.bridge.check_signal.emit(False)
            else:
                self.test_result.setText(f"✅ 连接成功 → {info['host']}")
                self.test_result.setStyleSheet(f"color: {GREEN_OK}; font-size: 13px;")
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

    def _server_dialog(self, title: str, existing: dict | None):
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(420, 320)
        layout = QFormLayout(dlg)

        name_edit = QLineEdit(existing.get("name", "") if existing else "")
        host_edit = QLineEdit(existing.get("host", "") if existing else "")
        port_edit = QSpinBox()
        port_edit.setRange(1, 65535)
        port_edit.setValue(existing.get("port", 22) if existing else 22)
        user_edit = QLineEdit(existing.get("user", "root") if existing else "root")

        auth_combo = QComboBox()
        auth_combo.addItems(["密码认证", "密钥认证"])
        auth_combo.setCurrentIndex(1 if existing and existing.get("key_path") else 0)

        pw_edit = QLineEdit()
        pw_edit.setEchoMode(QLineEdit.Password)
        key_edit = QLineEdit()
        key_btn = QPushButton("浏览...")
        key_layout = QHBoxLayout()
        key_layout.addWidget(key_edit)
        key_layout.addWidget(key_btn)

        if existing:
            if existing.get("password"):
                pw_edit.setText(existing["password"])
            if existing.get("key_path"):
                key_edit.setText(existing["key_path"])

        def on_auth_change(idx):
            pw_edit.setVisible(idx == 0)
            key_edit.setVisible(idx == 1)
            key_btn.setVisible(idx == 1)
        auth_combo.currentIndexChanged.connect(on_auth_change)
        on_auth_change(auth_combo.currentIndex())

        def browse_key():
            path, _ = QFileDialog.getOpenFileName(dlg, "选择 SSH 私钥", str(Path.home()))
            if path:
                key_edit.setText(path)
        key_btn.clicked.connect(browse_key)

        layout.addRow("名称:", name_edit)
        layout.addRow("主机:", host_edit)
        layout.addRow("端口:", port_edit)
        layout.addRow("用户:", user_edit)
        layout.addRow("认证方式:", auth_combo)
        layout.addRow("密码:", pw_edit)
        layout.addRow("密钥文件:", key_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addRow(buttons)

        if dlg.exec():
            name, host = name_edit.text().strip(), host_edit.text().strip()
            if not name or not host:
                QMessageBox.warning(self, "错误", "名称和主机不能为空")
                return
            server = {
                "name": name, "host": host, "port": port_edit.value(),
                "user": user_edit.text().strip(),
            }
            if auth_combo.currentIndex() == 0:
                server["auth_type"] = "password"
                server["password"] = pw_edit.text()
            else:
                server["auth_type"] = "key"
                server["key_path"] = key_edit.text().strip()
            add_server(server)
            self._load_servers()

    def _save_api_key(self):
        key = self.api_input.text().strip()
        set_deepseek_key(key)
        QMessageBox.information(self, "提示", "API Key 已保存")

    def close_ssh(self):
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None


# ── 页面 2: 显卡检测 ──────────────────────────────────
class GpuPage(QWidget):
    def __init__(self, bridge: SignalBridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._gpu_info: dict | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🎮 显卡检测")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("检测远程服务器上的 NVIDIA 显卡信息"))

        self.btn_detect = QPushButton("🔍 开始检测")
        self.btn_detect.setMinimumHeight(36)
        self.btn_detect.setStyleSheet(
            f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 8px 24px; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: {DEEP_BLUE}; }}"
        )
        layout.addWidget(self.btn_detect)

        self.info_label = QLabel("点击「开始检测」扫描服务器显卡信息")
        self.info_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; padding: 8px; background: {LIGHT_GRAY}; border-radius: 6px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        layout.addStretch()

        self.btn_detect.clicked.connect(self._detect)

    def _detect(self):
        ssh = self.get_ssh()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面测试连接")
            return
        self.info_label.setText("🔄 检测中...")
        self.btn_detect.setEnabled(False)

        def task():
            result = detect_gpu(ssh)
            self.bridge.gpu_signal.emit(result)
            self.btn_detect.setEnabled(True)
        threading.Thread(target=task, daemon=True).start()

    def on_result(self, result):
        if isinstance(result, str):
            self.info_label.setText(f"❌ {result}")
            self.info_label.setStyleSheet(f"color: {RED_ERR}; font-size: 13px; padding: 8px; background: {LIGHT_GRAY}; border-radius: 6px;")
            self._gpu_info = None
        else:
            text = (
                f"✅ 型号: {result['model']}\n"
                f"驱动: {'已安装: ' + result['driver_version'] if result['driver_installed'] else '未安装'}\n"
                f"CUDA: {result.get('cuda_version', 'N/A')}\n"
                f"架构: {result.get('arch', 'x86_64')}"
            )
            self.info_label.setText(text)
            self.info_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px; padding: 8px; background: {LIGHT_GRAY}; border-radius: 6px;")
            self._gpu_info = result

    def get_gpu_info(self):
        return self._gpu_info


# ── 页面 3: 驱动选择 ──────────────────────────────────
class DriverPage(QWidget):
    def __init__(self, get_gpu_fn):
        super().__init__()
        self.get_gpu = get_gpu_fn
        self._selected_version: str | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("💿 驱动选择")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("选择要安装的 NVIDIA 驱动版本"))

        self.list_widget = QListWidget()
        for d in RECOMMENDED_DRIVERS:
            item = QListWidgetItem(f"{d.version}  {'★ 推荐' if d.is_recommended else ''}")
            item.setData(Qt.UserRole, d.version)
            if d.is_recommended:
                item.setForeground(QColor(DEEP_BLUE))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("或手动输入版本号:"))
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("例如 550.144.03")
        manual_layout.addWidget(self.manual_input)
        layout.addLayout(manual_layout)

        self.selected_label = QLabel("未选择驱动")
        self.selected_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px;")
        layout.addWidget(self.selected_label)
        layout.addStretch()

        self.list_widget.currentItemChanged.connect(self._on_select)
        self.manual_input.textChanged.connect(self._on_manual)

    def _on_select(self, current, _):
        if current:
            v = current.data(Qt.UserRole)
            self._selected_version = v
            self.selected_label.setText(f"已选择: {v}")

    def _on_manual(self, text):
        if text.strip():
            self._selected_version = text.strip()
            self.selected_label.setText(f"已选择: {text.strip()}")

    def get_selected(self) -> str | None:
        return self._selected_version

    def auto_select_for_gpu(self):
        gpu = self.get_gpu()
        if gpu and isinstance(gpu, dict):
            recommended = get_recommended_for_gpu(gpu.get("model", ""))
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(Qt.UserRole) == recommended.version:
                    self.list_widget.setCurrentItem(item)
                    self._selected_version = recommended.version
                    self.selected_label.setText(f"已选择: {recommended.version} (推荐)")
                    return
            # 手动兜底
            self.manual_input.setText(recommended.version)
            self._selected_version = recommended.version
            self.selected_label.setText(f"已选择: {recommended.version} (推荐)")


# ── 页面 4: 环境检查 ──────────────────────────────────
class EnvCheckPage(QWidget):
    def __init__(self, bridge: SignalBridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._env_results: dict = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🔍 环境检查")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("检查远程服务器上的安装环境"))

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["检查项", "状态", "详情"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setStyleSheet(f"QTableWidget {{ border: 1px solid {LIGHT_GRAY}; }} QHeaderView::section {{ background-color: {DEEP_BLUE}; color: white; padding: 6px; }}")
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_check = QPushButton("🔍 执行检查")
        self.btn_check.setStyleSheet(f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_fix = QPushButton("🔧 一键修复")
        self.btn_fix.setStyleSheet(f"QPushButton {{ background-color: {GOLD}; color: {DARK_TEXT}; border-radius: 4px; padding: 8px 20px; font-weight: bold; }}")
        self.btn_fix.setEnabled(False)
        btn_row.addWidget(self.btn_check)
        btn_row.addWidget(self.btn_fix)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 13px;")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.btn_check.clicked.connect(self._run_check)
        self.btn_fix.clicked.connect(self._fix_all)

    def _run_check(self):
        ssh = self.get_ssh()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面测试连接")
            return
        self.status_label.setText("🔄 检查中...")
        self.btn_check.setEnabled(False)

        def task():
            checker = EnvChecker(ssh)
            checker.check_all()
            self._env_results = checker.results
            self.bridge.env_signal.emit(checker.results)

        threading.Thread(target=task, daemon=True).start()

    def on_results(self, results: dict):
        self.btn_check.setEnabled(True)
        self.table.setRowCount(len(results))
        self._env_results = results
        failed = 0
        for i, (key, (ok, detail)) in enumerate(results.items()):
            label = CHECK_LABELS.get(key, key)
            self.table.setItem(i, 0, QTableWidgetItem(label))
            status_item = QTableWidgetItem("✅ 通过" if ok else "❌ 失败")
            status_item.setForeground(QColor(GREEN_OK if ok else RED_ERR))
            self.table.setItem(i, 1, status_item)
            self.table.setItem(i, 2, QTableWidgetItem(detail))
            if not ok:
                failed += 1

        if failed == 0:
            self.status_label.setText("✅ 所有环境检查通过")
            self.status_label.setStyleSheet(f"color: {GREEN_OK}; font-size: 13px;")
            self.btn_fix.setEnabled(False)
        else:
            self.status_label.setText(f"⚠️ {failed} 项检查未通过，可点击「一键修复」")
            self.status_label.setStyleSheet(f"color: {GOLD}; font-size: 13px;")
            self.btn_fix.setEnabled(True)

    def _fix_all(self):
        ssh = self.get_ssh()
        if not ssh:
            return
        self.status_label.setText("🔄 正在修复...")
        self.btn_fix.setEnabled(False)

        from envcheck import EnvChecker
        checker = EnvChecker(ssh)

        def task():
            failed = [k for k, (ok, _) in self._env_results.items() if not ok]
            for key in failed:
                cmd = checker.fix_command(key)
                if cmd and "BIOS" not in cmd:
                    ssh.exec(f"sudo {cmd}", timeout=60)
            # 重新检查
            checker.check_all()
            self._env_results = checker.results
            self.bridge.env_signal.emit(checker.results)

        threading.Thread(target=task, daemon=True).start()


# ── 页面 5: 安装进度 ──────────────────────────────────
class InstallPage(QWidget):
    def __init__(self, bridge: SignalBridge, get_ssh_fn, get_driver_fn, get_gpu_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self.get_driver = get_driver_fn
        self.get_gpu = get_gpu_fn
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("⚙️ 驱动安装")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)
        layout.addWidget(QLabel("安装过程实时显示"))

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setStyleSheet(
            f"QProgressBar {{ border: 1px solid {BRIGHT_BLUE}; border-radius: 6px; height: 24px; text-align: center; }}"
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRIGHT_BLUE}, stop:1 {DEEP_BLUE}); border-radius: 5px; }}"
        )
        layout.addWidget(self.progress)

        self.step_label = QLabel("准备就绪")
        self.step_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 13px;")
        layout.addWidget(self.step_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(f"background-color: #1E1E1E; color: #D4D4D4; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; border-radius: 6px; padding: 8px;")
        layout.addWidget(self.log_view)

        btn_row = QHBoxLayout()
        self.btn_install = QPushButton("▶ 开始安装")
        self.btn_install.setStyleSheet(f"QPushButton {{ background-color: {DEEP_BLUE}; color: white; font-weight: bold; border-radius: 6px; padding: 10px 30px; font-size: 14px; }} QPushButton:hover {{ background-color: {BRIGHT_BLUE}; }}")
        btn_row.addWidget(self.btn_install)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.bridge.log_signal.connect(self.log_view.append)
        self.bridge.progress_signal.connect(self._update_progress)
        self.btn_install.clicked.connect(self._start_install)

    def _update_progress(self, value, total, label):
        if total > 0:
            self.progress.setMaximum(total)
            self.progress.setValue(value)
        self.step_label.setText(label)

    def _start_install(self):
        ssh = self.get_ssh()
        driver_v = self.get_driver()
        gpu = self.get_gpu()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面连接")
            return
        if not driver_v:
            QMessageBox.warning(self, "提示", "请先在「驱动选择」页面选择版本")
            return

        self.log_view.clear()
        self.progress.setValue(0)
        self.btn_install.setEnabled(False)
        download_url = get_download_url(driver_v)
        installer = Installer(ssh, download_url, driver_v)

        def task():
            self.bridge.log_signal.emit(f"🚀 开始安装驱动 {driver_v}...")
            success, logs = installer.full_install()
            for line in logs:
                self.bridge.log_signal.emit(line)
            if success:
                self.bridge.log_signal.emit("✅ 安装完成！")
                self.bridge.done_signal.emit(True, f"驱动 {driver_v} 安装成功")
            else:
                self.bridge.log_signal.emit("❌ 安装失败！")
                # 尝试 AI 诊断
                self.bridge.log_signal.emit("🤖 正在进行 AI 诊断...")
                try:
                    diag = diagnose_with_deepseek("\n".join(logs), f"驱动版本: {driver_v}")
                    self.bridge.log_signal.emit(f"\n--- AI 诊断 ---\n{diag}")
                except Exception:
                    pass
                self.bridge.done_signal.emit(False, "安装失败")
            self.btn_install.setEnabled(True)
            self.progress.setMaximum(1)
            self.progress.setValue(1)

        threading.Thread(target=task, daemon=True).start()


# ── 页面 6: CUDA / cuDNN ────────────────────────────
class CudaPage(QWidget):
    def __init__(self, bridge: SignalBridge, get_ssh_fn):
        super().__init__()
        self.bridge = bridge
        self.get_ssh = get_ssh_fn
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("🧩 CUDA & cuDNN 安装")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)

        # CUDA
        cuda_group = QGroupBox("CUDA Toolkit")
        cuda_group.setStyleSheet(f"QGroupBox {{ font-weight: bold; border: 1px solid {BRIGHT_BLUE}; border-radius: 6px; margin-top: 10px; padding-top: 16px; }} QGroupBox::title {{ color: {DEEP_BLUE}; }}")
        clayout = QVBoxLayout(cuda_group)
        self.cb_cuda = QCheckBox("安装 CUDA Toolkit")
        clayout.addWidget(self.cb_cuda)
        cuda_ver_row = QHBoxLayout()
        cuda_ver_row.addWidget(QLabel("版本:"))
        self.cuda_ver_combo = QComboBox()
        for v in get_cuda_versions():
            self.cuda_ver_combo.addItem(v)
        cuda_ver_row.addWidget(self.cuda_ver_combo)
        cuda_ver_row.addStretch()
        clayout.addLayout(cuda_ver_row)
        layout.addWidget(cuda_group)

        # cuDNN
        cudnn_group = QGroupBox("cuDNN")
        cudnn_group.setStyleSheet(cuda_group.styleSheet())
        nlayout = QVBoxLayout(cudnn_group)
        self.cb_cudnn = QCheckBox("安装 cuDNN")
        nlayout.addWidget(self.cb_cudnn)
        cudnn_ver_row = QHBoxLayout()
        cudnn_ver_row.addWidget(QLabel("版本:"))
        self.cudnn_ver_combo = QComboBox()
        for v in get_cudnn_versions():
            self.cudnn_ver_combo.addItem(v)
        cudnn_ver_row.addWidget(self.cudnn_ver_combo)
        cudnn_ver_row.addStretch()
        nlayout.addLayout(cudnn_ver_row)
        layout.addWidget(cudnn_group)

        self.btn_install = QPushButton("📦 开始安装")
        self.btn_install.setMinimumHeight(36)
        self.btn_install.setStyleSheet(
            f"QPushButton {{ background-color: {DEEP_BLUE}; color: white; font-weight: bold; "
            f"border-radius: 6px; padding: 8px 24px; font-size: 14px; }}"
            f"QPushButton:hover {{ background-color: {BRIGHT_BLUE}; }}"
        )
        layout.addWidget(self.btn_install)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(f"background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas, monospace; font-size: 12px; border-radius: 6px;")
        self.log_view.setMaximumHeight(200)
        layout.addWidget(self.log_view)

        self.bridge.log_signal.connect(self._append_log)
        self.btn_install.clicked.connect(self._start_install)
        layout.addStretch()

    def _append_log(self, msg):
        self.log_view.append(msg)

    def _start_install(self):
        ssh = self.get_ssh()
        if not ssh:
            QMessageBox.warning(self, "提示", "请先在「服务器」页面连接")
            return

        self.log_view.clear()
        self.btn_install.setEnabled(False)

        def task():
            if self.cb_cuda.isChecked():
                cuda_ver = self.cuda_ver_combo.currentText()
                self.bridge.log_signal.emit(f"📦 安装 CUDA Toolkit {cuda_ver}...")
                success, logs = install_cuda(ssh, cuda_ver)
                for l in logs:
                    self.bridge.log_signal.emit(l)
                if not success:
                    self.bridge.log_signal.emit("❌ CUDA 安装失败")

            if self.cb_cudnn.isChecked():
                cudnn_ver = self.cudnn_ver_combo.currentText()
                self.bridge.log_signal.emit(f"📦 安装 cuDNN {cudnn_ver}...")
                success, logs = install_cudnn(ssh, cudnn_ver)
                for l in logs:
                    self.bridge.log_signal.emit(l)
                if not success:
                    self.bridge.log_signal.emit("❌ cuDNN 安装失败")

            self.bridge.log_signal.emit("✅ CUDA/cuDNN 安装完成")
            self.btn_install.setEnabled(True)

        threading.Thread(target=task, daemon=True).start()


# ── 页面 7: 报告 ──────────────────────────────────
class ReportPage(QWidget):
    def __init__(self, get_server_fn, get_gpu_fn, get_driver_fn):
        super().__init__()
        self.get_server = get_server_fn
        self.get_gpu = get_gpu_fn
        self.get_driver = get_driver_fn
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("📋 安装报告")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DEEP_BLUE};")
        layout.addWidget(title)

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet(f"background-color: {LIGHT_GRAY}; border-radius: 6px; padding: 12px; font-size: 13px;")
        layout.addWidget(self.report_text)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("💾 保存报告")
        self.btn_save.setStyleSheet(f"QPushButton {{ background-color: {GOLD}; color: {DARK_TEXT}; font-weight: bold; border-radius: 6px; padding: 10px 24px; font-size: 14px; }}")
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setStyleSheet(f"QPushButton {{ background-color: {BRIGHT_BLUE}; color: white; border-radius: 6px; padding: 10px 24px; }}")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        self.btn_save.clicked.connect(self._save_report)
        self.btn_refresh.clicked.connect(self._generate)

    def _generate(self):
        server = self.get_server()
        gpu = self.get_gpu()
        driver = self.get_driver()

        lines = []
        lines.append("=" * 50)
        lines.append("  NVIDIA 驱动安装报告")
        lines.append("=" * 50)
        lines.append("")

        lines.append("【服务器信息】")
        if server:
            lines.append(f"  名称: {server.get('name', 'N/A')}")
            lines.append(f"  主机: {server.get('host', 'N/A')}:{server.get('port', 22)}")
            lines.append(f"  用户: {server.get('user', 'root')}")
        else:
            lines.append("  未选择服务器")
        lines.append("")

        lines.append("【显卡信息】")
        if gpu and isinstance(gpu, dict):
            lines.append(f"  型号: {gpu.get('model', 'N/A')}")
            lines.append(f"  当前驱动: {gpu.get('driver_version', '未安装')}")
            lines.append(f"  CUDA 版本: {gpu.get('cuda_version', 'N/A')}")
        else:
            lines.append("  未检测")
        lines.append("")

        lines.append("【驱动安装】")
        lines.append(f"  选择版本: {driver or '未选择'}")
        lines.append("")

        lines.append(f"  生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 50)

        self.report_text.setText("\n".join(lines))

    def _save_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存报告", str(Path.home() / "nvidia-install-report.txt"),
            "文本文件 (*.txt)")
        if path:
            with open(path, "w") as f:
                f.write(self.report_text.toPlainText())
            QMessageBox.information(self, "提示", f"报告已保存到:\n{path}")


# ── 主窗口 ──────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NVIDIA Tools — 驱动安装助手")
        self.setFixedSize(800, 620)
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
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 页面提示
        self.page_title = QLabel(PAGES[0])
        self.page_title.setStyleSheet(
            f"background-color: {DEEP_BLUE}; color: white; font-size: 16px; font-weight: bold; "
            f"padding: 12px 24px;"
        )
        main_layout.addWidget(self.page_title)

        # Stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {WHITE};")

        self.server_page = ServerPage(self.bridge)
        self.gpu_page = GpuPage(self.bridge, self._get_ssh)
        self.driver_page = DriverPage(self.gpu_page.get_gpu_info)
        self.env_page = EnvCheckPage(self.bridge, self._get_ssh)
        self.install_page = InstallPage(self.bridge, self._get_ssh,
                                        self.driver_page.get_selected,
                                        self.gpu_page.get_gpu_info)
        self.cuda_page = CudaPage(self.bridge, self._get_ssh)
        self.report_page = ReportPage(self.server_page.get_server_info,
                                      self.gpu_page.get_gpu_info,
                                      self.driver_page.get_selected)

        for page in [self.server_page, self.gpu_page, self.driver_page,
                     self.env_page, self.install_page, self.cuda_page,
                     self.report_page]:
            self.stack.addWidget(page)

        main_layout.addWidget(self.stack, 1)

        # Bottom bar
        self.bottom_bar = BottomBar()
        main_layout.addWidget(self.bottom_bar)

        # 按钮事件
        self.bottom_bar.btn_prev.clicked.connect(self._prev_page)
        self.bottom_bar.btn_next.clicked.connect(self._next_page)

    def _connect_signals(self):
        self.bridge.check_signal.connect(self._on_connection_check)
        self.bridge.gpu_signal.connect(self.gpu_page.on_result)
        self.bridge.env_signal.connect(self.env_page.on_results)
        self.bridge.done_signal.connect(self._on_install_done)

        # 显卡检测完成后自动推荐驱动
        self.bridge.gpu_signal.connect(lambda r: self.driver_page.auto_select_for_gpu())

    def _get_ssh(self):
        return self.server_page.get_ssh()

    def _on_connection_check(self, ok: bool):
        self._connected = ok
        info = self.server_page.get_server_info()
        name = info.get("name", "") if info else ""
        self.bottom_bar.set_server(name, ok)

    def _on_install_done(self, success: bool, msg: str):
        if success:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._update_page()

    def _next_page(self):
        if self._current_page == PAGE_COUNT - 1:
            return  # 最后一页无下一步
        # 页面检查
        if self._current_page == 0:
            if not self._connected:
                QMessageBox.warning(self, "提示", "请先测试并连接服务器")
                return
        if self._current_page == 1:
            if not self.gpu_page.get_gpu_info():
                QMessageBox.warning(self, "提示", "请先检测显卡")
                return
        if self._current_page == 2:
            if not self.driver_page.get_selected():
                QMessageBox.warning(self, "提示", "请选择驱动版本")
                return

        self._current_page += 1
        self._update_page()

    def _update_page(self):
        self.stack.setCurrentIndex(self._current_page)
        self.page_title.setText(PAGES[self._current_page])
        self.bottom_bar.set_page(self._current_page)

        # 进入报告页自动生成
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
