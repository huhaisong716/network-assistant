"""安装工作流：禁用 nouveau → 下载 → 安装 → 验证"""
import os
import re
from ssh_client import SSHClient
from errors import match_error


class Installer:
    def __init__(self, ssh: SSHClient, driver_url: str, driver_version: str):
        self.ssh = ssh
        self.driver_url = driver_url
        self.driver_version = driver_version
        self.log_lines: list[str] = []

    def _log(self, msg: str):
        self.log_lines.append(msg)

    def step_disable_nouveau(self) -> bool:
        """禁用 nouveau 驱动"""
        self._log("[1/5] 禁用 nouveau 驱动...")
        ec, out, err = self.ssh.exec(
            "bash -c 'echo \"blacklist nouveau\" > /etc/modprobe.d/blacklist-nvidia-nouveau.conf && "
            "echo \"options nouveau modeset=0\" >> /etc/modprobe.d/blacklist-nvidia-nouveau.conf && "
            "update-initramfs -u 2>&1'", timeout=30
        )
        if ec != 0:
            self._log(f"  ✗ 禁用失败: {err}")
            return False
        self._log("  ✓ nouveau 已禁用（需要重启后生效）")
        return True

    def step_download_driver(self) -> bool:
        """下载驱动安装包"""
        self._log(f"[2/5] 下载驱动: {self.driver_version}...")
        filename = f"NVIDIA-Linux-x86_64-{self.driver_version}.run"
        # 先去 /tmp 检查是否已有
        ec, out, _ = self.ssh.exec(f"ls -la /tmp/{filename} 2>/dev/null && wc -c /tmp/{filename}")
        if ec == 0:
            self._log(f"  ✓ /tmp/{filename} 已存在，跳过下载")
            return True
        ec, out, err = self.ssh.exec(
            f"cd /tmp && wget -q --show-progress {self.driver_url} -O {filename} 2>&1", timeout=300
        )
        if ec != 0:
            self._log(f"  ✗ 下载失败: {err or out}")
            return False
        self._log("  ✓ 下载完成")
        return True

    def step_pre_install(self) -> bool:
        """安装前准备工作"""
        self._log("[3/5] 安装前准备工作...")
        # 停止 X server 和服务
        ec, out, err = self.ssh.exec(
            "systemctl stop gdm 2>/dev/null || systemctl stop lightdm 2>/dev/null || true; "
            "systemctl stop nvidia-persistenced 2>/dev/null || true", timeout=15
        )
        self._log("  ✓ 显示管理器已停止")
        return True

    def step_install_driver(self) -> bool:
        """执行安装"""
        self._log(f"[4/5] 安装驱动 {self.driver_version}...")
        filename = f"NVIDIA-Linux-x86_64-{self.driver_version}.run"
        ec, out, err = self.ssh.exec(
            f"chmod +x /tmp/{filename} && "
            f"sudo /tmp/{filename} --silent --accept-license --no-opengl-files --no-x-check 2>&1",
            timeout=600
        )
        if ec != 0:
            err_info = match_error(err + out)
            if err_info:
                self._log(f"  ✗ 安装失败: {err_info['title']}")
                self._log(f"    建议: {err_info['solution']}")
            else:
                self._log(f"  ✗ 安装失败: {err[:500]}")
            # 检查是否有部分成功
            ec2, out2, _ = self.ssh.exec("nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null")
            if ec2 == 0 and out2.strip():
                self._log(f"  ✓ 但 nvidia-smi 可用，驱动版本: {out2.strip()}")
                return True
            return False
        self._log("  ✓ 安装完成")
        return True

    def step_verify(self) -> bool:
        """验证安装"""
        self._log("[5/5] 验证安装...")
        ec, out, err = self.ssh.exec("nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1")
        if ec != 0:
            self._log(f"  ✗ 验证失败: {err or out}")
            return False
        self._log(f"  ✓ {out.strip()}")
        return True

    def full_install(self) -> tuple[bool, list[str]]:
        """全流程安装，返回 (成功?, 日志)"""
        steps = [
            self.step_disable_nouveau,
            self.step_download_driver,
            self.step_pre_install,
            self.step_install_driver,
            self.step_verify,
        ]
        for step in steps:
            if not step():
                return False, self.log_lines
        return True, self.log_lines

    def get_logs(self) -> list[str]:
        return self.log_lines
