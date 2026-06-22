"""5 项环境检查：gcc/nouveau/secureboot/内核头文件/build-essential"""

CHECK_ITEMS = [
    "gcc",
    "nouveau_disabled",
    "secureboot_disabled",
    "kernel_headers",
    "build_essential",
]

CHECK_LABELS = {
    "gcc": "GCC 编译器",
    "nouveau_disabled": "nouveau 驱动已禁用",
    "secureboot_disabled": "Secure Boot 已禁用",
    "kernel_headers": "内核头文件已安装",
    "build_essential": "build-essential 已安装",
}


class EnvChecker:
    def __init__(self, ssh):
        self.ssh = ssh
        self.results: dict[str, tuple[bool, str]] = {}  # key -> (ok, detail)

    def check_gcc(self):
        ec, out, _ = self.ssh.exec("gcc --version 2>/dev/null | head -1")
        if ec == 0 and out.strip():
            self.results["gcc"] = (True, out.strip())
        else:
            self.results["gcc"] = (False, "未安装")

    def check_nouveau(self):
        ec, out, _ = self.ssh.exec("lsmod | grep nouveau 2>/dev/null")
        if out.strip():
            self.results["nouveau_disabled"] = (False, "nouveau 模块已加载")
        else:
            self.results["nouveau_disabled"] = (True, "已禁用")

    def check_secureboot(self):
        ec, out, _ = self.ssh.exec("mokutil --sb-state 2>/dev/null")
        if "enabled" in out.lower():
            self.results["secureboot_disabled"] = (False, "Secure Boot 已启用")
        else:
            self.results["secureboot_disabled"] = (True, "已禁用或 mokutil 未安装")

    def check_kernel_headers(self):
        ec, out, _ = self.ssh.exec("dpkg -l | grep linux-headers-$(uname -r) 2>/dev/null")
        if ec == 0 and out.strip():
            self.results["kernel_headers"] = (True, "已安装")
        else:
            self.results["kernel_headers"] = (False, "未安装")

    def check_build_essential(self):
        ec, out, _ = self.ssh.exec("dpkg -l | grep build-essential 2>/dev/null")
        if ec == 0 and out.strip():
            self.results["build_essential"] = (True, "已安装")
        else:
            self.results["build_essential"] = (False, "未安装")

    def check_all(self, progress_callback=None):
        total = len(CHECK_ITEMS)
        for i, name in enumerate(CHECK_ITEMS):
            getattr(self, f"check_{name}")()
            if progress_callback:
                progress_callback(i + 1, total, CHECK_LABELS.get(name, name))

    def all_pass(self) -> bool:
        return all(ok for ok, _ in self.results.values())

    def fix_command(self, name: str) -> str | None:
        """返回修复命令"""
        cmds = {
            "gcc": "apt install -y gcc g++",
            "nouveau_disabled": "bash -c 'echo \"blacklist nouveau\" > /etc/modprobe.d/blacklist-nvidia-nouveau.conf && update-initramfs -u'",
            "secureboot_disabled": "echo '请在 BIOS 中禁用 Secure Boot（无法通过命令行修复）'",
            "kernel_headers": "apt install -y linux-headers-$(uname -r)",
            "build_essential": "apt install -y build-essential",
        }
        return cmds.get(name)

    def get_failed_items(self) -> list[str]:
        return [k for k, (ok, _) in self.results.items() if not ok]
