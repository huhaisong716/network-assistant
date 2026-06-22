"""内置常见错误库"""

COMMON_ERRORS = {
    "no_device": {
        "pattern": "No devices were found",
        "title": "未检测到 NVIDIA 显卡",
        "solution": "请检查服务器是否有 NVIDIA GPU。执行: lspci | grep -i nvidia",
    },
    "nouveau_loaded": {
        "pattern": "Failed to initialize NVML",
        "title": "nouveau 驱动冲突",
        "solution": "nouveau 开源驱动未禁用。请在安装前执行安装流程中的禁用 nouveau 步骤。",
    },
    "kernel_headers_missing": {
        "pattern": "Unable to find the kernel source tree",
        "title": "内核头文件缺失",
        "solution": "执行: sudo apt install linux-headers-$(uname -r) -y",
    },
    "secureboot_enabled": {
        "pattern": "Secure Boot not enabled",
        "title": "Secure Boot 已启用",
        "solution": "需要在 BIOS 中禁用 Secure Boot，或使用 mokutil 签名驱动模块。",
    },
    "gcc_missing": {
        "pattern": "Unable to find a suitable C compiler",
        "title": "GCC 编译器缺失",
        "solution": "执行: sudo apt install build-essential -y",
    },
    "gcc_version": {
        "pattern": "The compiler version is too old",
        "title": "GCC 版本过旧",
        "solution": "安装较新版本 GCC: sudo apt install gcc-12 g++-12 -y",
    },
    "cuda_toolkit_missing": {
        "pattern": "command not found: nvcc",
        "title": "CUDA Toolkit 未安装",
        "solution": "请在 CUDA 页面下载并安装 CUDA Toolkit。",
    },
    "cuda_version_mismatch": {
        "pattern": "CUDA version mismatch",
        "title": "CUDA 版本不匹配",
        "solution": "驱动版本与 CUDA 版本不兼容。请参考 NVIDIA 兼容性矩阵。",
    },
    "dkms_fail": {
        "pattern": "Unable to build the NVIDIA kernel module through DKMS",
        "title": "DKMS 构建失败",
        "solution": "检查内核头文件是否安装完整，尝试手动构建: sudo dkms install -m nvidia -v <version>",
    },
    "permission_denied": {
        "pattern": "Permission denied",
        "title": "权限不足",
        "solution": "请确保使用 sudo 执行或具有 root 权限。",
    },
    "xserver_running": {
        "pattern": "You appear to be running an X server",
        "title": "X Server 正在运行",
        "solution": "请停止 X Server 或进入 runlevel 3: sudo systemctl isolate multi-user.target",
    },
    "disk_full": {
        "pattern": "No space left on device",
        "title": "磁盘空间不足",
        "solution": "清理磁盘空间: sudo apt autoremove && sudo journalctl --vacuum-size=500M",
    },
}


def match_error(text: str) -> dict | None:
    """在输出文本中匹配已知错误"""
    for key, info in COMMON_ERRORS.items():
        if info["pattern"].lower() in text.lower():
            return info
    return None
