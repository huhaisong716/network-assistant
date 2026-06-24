"""安装管理：Nouveau 禁用 / 依赖安装 / 驱动安装（通过 apt 或 runfile）"""
import re
from ssh_client import SSHClient
from errors import match_error


# ═══════════════════════════════════════════════════════════
# 1. Nouveau Manager
# ═══════════════════════════════════════════════════════════
class NouveauManager:
    """Nouveau 驱动禁用管理"""

    def __init__(self, ssh: SSHClient):
        self.ssh = ssh

    def check_disabled(self) -> tuple[bool, str]:
        """检查 nouveau 是否已禁用"""
        # 方法1：检查模块是否加载
        ec1, out1, _ = self.ssh.exec("lsmod | grep nouveau 2>/dev/null")
        if out1.strip():
            return False, "nouveau 模块仍加载中"

        # 方法2：检查黑名单配置
        ec2, out2, _ = self.ssh.exec(
            "cat /etc/modprobe.d/blacklist-nvidia-nouveau.conf 2>/dev/null || "
            "cat /etc/modprobe.d/blacklist-nouveau.conf 2>/dev/null"
        )
        if "blacklist nouveau" in out2:
            # 模块未加载且有 blacklist → 已禁用（可能需重启）
            ec3, out3, _ = self.ssh.exec("lspci -k | grep -A2 nouveau 2>/dev/null | grep 'Kernel driver in use'")
            if "nouveau" in out3:
                return False, "已配置 blacklist 但内核仍在用 nouveau（需重启）"
            return True, "✓ nouveau 已禁用"
        return False, "未配置 nouveau 黑名单"

    def disable(self) -> tuple[bool, str, list[str]]:
        """禁用 nouveau，返回 (成功?, 消息, 日志)"""
        logs = ["[屏蔽] 正在禁用 nouveau 驱动..."]

        # 创建 blacklist 文件
        cmds = [
            'echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nvidia-nouveau.conf',
            'echo "options nouveau modeset=0" | sudo tee -a /etc/modprobe.d/blacklist-nvidia-nouveau.conf',
            "sudo update-initramfs -u 2>&1",
        ]
        for cmd in cmds:
            ec, out, err = self.ssh.exec(cmd, timeout=60)
            if ec != 0:
                logs.append(f"  ✗ [警告] {err or out[:100]}")
            else:
                logs.append(f"  ✓ {cmd.split('|')[-1].strip()[:60]}")

        # 验证
        ok, msg = self.check_disabled()
        logs.append(f"  {'✓' if ok else '→'} 验证: {msg}")

        if ok:
            return True, "nouveau 已成功禁用", logs
        else:
            return False, msg, logs

    def needs_reboot(self) -> bool:
        """判断是否需要重启才能生效"""
        ok, msg = self.check_disabled()
        if ok:
            return False
        return "需重启" in msg or "加载中" in msg


# ═══════════════════════════════════════════════════════════
# 2. Dependency Manager
# ═══════════════════════════════════════════════════════════
class DependencyManager:
    """依赖安装管理"""

    def __init__(self, ssh: SSHClient):
        self.ssh = ssh

    def install_selected(self, dep_defs: dict[str, dict], selected_keys: list[str],
                         timeout: int = 120) -> dict[str, tuple[bool, str]]:
        """安装选中的依赖项，返回 {key: (成功?, 消息)}"""
        results = {}
        for key in selected_keys:
            dep = dep_defs.get(key)
            if not dep:
                results[key] = (False, "未找到依赖定义")
                continue
            cmd = dep.get("install_cmd")
            if not cmd:
                results[key] = (False, "无自动安装方案")
                continue
            ec, out, err = self.ssh.exec(f"sudo {cmd}", timeout=timeout)
            if ec != 0:
                results[key] = (False, err.strip()[:200])
            else:
                results[key] = (True, "安装完成")
        return results


# ═══════════════════════════════════════════════════════════
# 3. Driver Installer
# ═══════════════════════════════════════════════════════════
class DriverInstaller:
    """显卡驱动安装（支持 apt 和 runfile 两种方式）"""

    def __init__(self, ssh: SSHClient):
        self.ssh = ssh
        self.log_lines: list[str] = []

    def install_via_apt(self, driver_package: str) -> tuple[bool, list[str]]:
        """通过 apt 安装驱动 (例如 nvidia-driver-550)"""
        self.log_lines = [f"[APT 安装] 正在安装 {driver_package}..."]
        ec, out, err = self.ssh.exec(
            f"sudo apt install -y {driver_package} 2>&1",
            timeout=600,
        )
        self.log_lines.append(out.strip()[-500:])
        if ec != 0:
            self.log_lines.append(f"✗ 安装失败: {err[:200]}")
            return False, self.log_lines
        # 验证
        ec2, out2, _ = self.ssh.exec("nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null")
        if ec2 == 0 and out2.strip():
            self.log_lines.append(f"✓ nvidia-smi 可用，版本: {out2.strip()}")
        else:
            self.log_lines.append("→ 安装完成，需重启后验证")
        return True, self.log_lines

    def install_via_runfile(self, driver_version: str, download_url: str) -> tuple[bool, list[str]]:
        """通过 .run 文件安装驱动"""
        self.log_lines = [f"[Runfile] 安装驱动 {driver_version}..."]
        filename = f"NVIDIA-Linux-x86_64-{driver_version}.run"

        # 下载
        self.log_lines.append(f"  下载 {filename}...")
        ec, out, err = self.ssh.exec(
            f"cd /tmp && wget -q --show-progress {download_url} -O {filename} 2>&1",
            timeout=300,
        )
        if ec != 0:
            self.log_lines.append(f"  ✗ 下载失败: {err[:200]}")
            return False, self.log_lines
        self.log_lines.append("  ✓ 下载完成")

        # 停止显示管理器
        self.ssh.exec(
            "systemctl stop gdm 2>/dev/null || systemctl stop lightdm 2>/dev/null || true; "
            "systemctl stop nvidia-persistenced 2>/dev/null || true",
            timeout=15,
        )

        # 安装
        self.log_lines.append(f"  执行安装（安装期间可能有弹窗）...")
        ec, out, err = self.ssh.exec(
            f"chmod +x /tmp/{filename} && "
            f"sudo /tmp/{filename} --silent --accept-license --no-opengl-files --no-x-check 2>&1",
            timeout=600,
        )
        if ec != 0:
            err_info = match_error(err + out)
            if err_info:
                self.log_lines.append(f"  ✗ 安装失败: {err_info['title']}")
                self.log_lines.append(f"    建议: {err_info['solution']}")
            else:
                self.log_lines.append(f"  ✗ 安装失败: {err[:200]}")
            # 检查部分成功
            ec2, out2, _ = self.ssh.exec(
                "nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null"
            )
            if ec2 == 0 and out2.strip():
                self.log_lines.append(f"  但 nvidia-smi 可用，版本: {out2.strip()}")
                return True, self.log_lines
            return False, self.log_lines

        self.log_lines.append("  ✓ 安装完成")
        return True, self.log_lines

    def verify(self) -> tuple[bool, str]:
        """验证驱动安装"""
        ec, out, err = self.ssh.exec(
            "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1",
            timeout=15,
        )
        if ec != 0:
            return False, err or out
        return True, out.strip()

    def get_logs(self) -> list[str]:
        return self.log_lines


# ═══════════════════════════════════════════════════════════
# 4. System Helper
# ═══════════════════════════════════════════════════════════
def reboot_system(ssh: SSHClient) -> tuple[bool, str]:
    """远程重启系统"""
    ec, out, err = ssh.exec("sudo reboot 2>&1", timeout=10)
    if ec != 0 and "not found" in err.lower():
        ec, out, err = ssh.exec("sudo shutdown -r now 2>&1", timeout=10)
    if ec != 0:
        return False, f"重启失败: {err[:100]}"
    return True, "系统正在重启（约 1-2 分钟后可重新连接）"


def wait_for_reboot(ssh: SSHClient, host: str, port: int, user: str,
                    password: str = None, key_path: str = None,
                    max_wait: int = 180) -> tuple[bool, SSHClient | None]:
    """等待系统重启完成后重新连接"""
    import time
    import socket
    from ssh_client import SSHClient as SC

    ssh.close()
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            # SSH 端口已开，尝试连接
            new_ssh = SC(host=host, port=port, user=user,
                         password=password, key_path=key_path)
            err = new_ssh.connect()
            if not err:
                return True, new_ssh
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
        time.sleep(5)
    return False, None
