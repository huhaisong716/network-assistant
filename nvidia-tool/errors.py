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
    "pre_install_failed": {
        "pattern": "pre-install script failed",
        "title": "预安装脚本失败",
        "solution": "通常因为 nouveau 未禁用。重新 blacklist nouveau → update-initramfs → reboot → 重试。",
    },
    "kernel_headers_missing": {
        "pattern": "Unable to find the kernel source tree",
        "title": "内核头文件缺失",
        "solution": "执行: sudo apt install linux-headers-$(uname -r) -y（RHEL系: dnf install kernel-devel-$(uname -r)）",
    },
    "kernel_source_tree": {
        "pattern": "kernel source tree",
        "title": "内核源码树未找到",
        "solution": "kernel-devel 版本必须与 `uname -r` 严格一致。执行: sudo apt install linux-headers-$(uname -r) -y",
    },
    "secureboot_enabled": {
        "pattern": "Secure Boot not enabled",
        "title": "Secure Boot 已启用",
        "solution": "需要在 BIOS 中禁用 Secure Boot，或使用 mokutil 签名驱动模块。",
    },
    "gcc_missing": {
        "pattern": "Unable to find a suitable C compiler",
        "title": "GCC 编译器缺失",
        "solution": "执行: sudo apt install build-essential -y（RHEL系: dnf groupinstall 'Development Tools'）",
    },
    "gcc_version": {
        "pattern": "The compiler version is too old",
        "title": "GCC 版本过旧",
        "solution": "安装较新版本 GCC: sudo apt install gcc-12 g++-12 -y",
    },
    "cuda_toolkit_missing": {
        "pattern": "command not found: nvcc",
        "title": "CUDA Toolkit 未安装或 PATH 未配置",
        "solution": "请安装 CUDA Toolkit 或执行 source ~/.bashrc 使环境变量生效。",
    },
    "cuda_version_mismatch": {
        "pattern": "CUDA version mismatch",
        "title": "CUDA 版本不匹配",
        "solution": "驱动版本与 CUDA 版本不兼容。请参考 NVIDIA 兼容性矩阵：CUDA ≤ nvidia-smi 中的 CUDA Version。",
    },
    "cuda_driver_loaded": {
        "pattern": "You appear to already have",
        "title": "CUDA 安装时检测到已有驱动",
        "solution": "安装 CUDA 时必须加 --no-driver 参数，禁止重复安装驱动。",
    },
    "dkms_fail": {
        "pattern": "Unable to build the NVIDIA kernel module through DKMS",
        "title": "DKMS 构建失败",
        "solution": "检查内核头文件是否安装完整，kernel-devel 版本是否等于 `uname -r`。",
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
    "nvidia_smi_failed": {
        "pattern": "Unable to determine the device handle",
        "title": "nvidia-smi 无法获取设备句柄",
        "solution": "驱动安装可能不完整。重启后重试，或检查 lspci | grep nvidia 确认 GPU 是否被正确识别。",
    },
    "libglvnd": {
        "pattern": "libglvnd",
        "title": "libglvnd 缺失",
        "solution": "安装 libglvnd: sudo apt install libglvnd-dev -y（RHEL系: dnf install libglvnd-devel -y）",
    },
}


def match_error(text: str) -> dict | None:
    """在输出文本中匹配已知错误"""
    for key, info in COMMON_ERRORS.items():
        if info["pattern"].lower() in text.lower():
            return info
    return None
