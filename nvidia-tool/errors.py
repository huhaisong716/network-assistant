"""内置常见问题库"""

ERROR_FIXES = [
    {
        "keywords": ["nouveau", "Nouveau", "NVIDIA kernel module"],
        "title": "Nouveau 驱动冲突",
        "fix": (
            'echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nvidia-nouveau.conf '
            '&& echo "options nouveau modeset=0" | sudo tee -a /etc/modprobe.d/blacklist-nvidia-nouveau.conf '
            "&& sudo update-initramfs -u && echo '请重启服务器后继续'"
        ),
    },
    {
        "keywords": ["gcc", "compiler", "build-essential"],
        "title": "缺少 GCC 编译环境",
        "fix": (
            "sudo apt-get update && sudo apt-get install -y gcc-12 build-essential "
            "&& sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 100 "
            "&& sudo update-alternatives --set gcc /usr/bin/gcc-12"
        ),
    },
    {
        "keywords": ["kernel header", "linux-headers", "kernel-devel"],
        "title": "缺少内核头文件",
        "fix": "sudo apt-get update && sudo apt-get install -y linux-headers-$(uname -r)",
    },
    {
        "keywords": ["X server", "x server", "display"],
        "title": "X Server 正在运行",
        "fix": "sudo service gdm3 stop || sudo service lightdm stop || sudo init 3",
    },
    {
        "keywords": ["failed to download", "connection timed out", "404 Not Found"],
        "title": "下载失败",
        "fix": "请检查网络连接，或更换镜像源：https://mirror.sjtu.edu.cn/nvidia/",
    },
    {
        "keywords": ["permission denied", "not permitted"],
        "title": "权限不足",
        "fix": "请在命令前加 sudo，或使用 root 用户执行",
    },
    {
        "keywords": ["secure boot", "Secure Boot", "MOK"],
        "title": "Secure Boot 阻止加载模块",
        "fix": "重启进入 BIOS → Security → Secure Boot → Disabled",
    },
    {
        "keywords": ["dkms", "DKMS", "Failed to build"],
        "title": "DKMS 内核模块编译失败",
        "fix": "sudo apt-get install -y dkms && sudo dkms install -m nvidia -v $(ls /usr/src/nvidia-*/ 2>/dev/null | head -1)",
    },
    {
        "keywords": ["already installed", "already exists"],
        "title": "驱动已存在",
        "fix": "sudo nvidia-uninstall && sudo apt-get purge -y '*nvidia*' && sudo apt-get autoremove -y",
    },
    {
        "keywords": ["not supported", "unsupported"],
        "title": "驱动版本不兼容",
        "fix": "请使用 https://www.nvidia.com/Download/Find.aspx 查询兼容版本",
    },
]


def find_known_error(stderr: str) -> dict:
    """在本地查找匹配的错误修复方案"""
    stderr_lower = stderr.lower()
    for ef in ERROR_FIXES:
        for kw in ef["keywords"]:
            if kw.lower() in stderr_lower:
                return ef
    return {}
