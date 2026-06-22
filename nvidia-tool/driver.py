"""NVIDIA 驱动版本匹配与下载 URL"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DriverInfo:
    version: str
    url: str
    is_recommended: bool = False


# 已知稳定版驱动（Linux x86_64）
RECOMMENDED_DRIVERS = [
    DriverInfo("550.144.03", "https://us.download.nvidia.com/XFree86/Linux-x86_64/550.144.03/NVIDIA-Linux-x86_64-550.144.03.run", True),
    DriverInfo("535.216.03", "https://us.download.nvidia.com/XFree86/Linux-x86_64/535.216.03/NVIDIA-Linux-x86_64-535.216.03.run", True),
    DriverInfo("525.147.05", "https://us.download.nvidia.com/XFree86/Linux-x86_64/525.147.05/NVIDIA-Linux-x86_64-525.147.05.run", True),
    DriverInfo("470.256.02", "https://us.download.nvidia.com/XFree86/Linux-x86_64/470.256.02/NVIDIA-Linux-x86_64-470.256.02.run", False),
    DriverInfo("390.157", "https://us.download.nvidia.com/XFree86/Linux-x86_64/390.157/NVIDIA-Linux-x86_64-390.157.run", False),
]


def get_download_url(version: str) -> Optional[str]:
    """根据版本号构造下载 URL"""
    for d in RECOMMENDED_DRIVERS:
        if d.version == version:
            return d.url
    # 尝试构造通用 URL
    major = version.split(".")[0] if "." in version else version
    return f"https://us.download.nvidia.com/XFree86/Linux-x86_64/{version}/NVIDIA-Linux-x86_64-{version}.run"


def get_recommended_for_gpu(model: str) -> DriverInfo:
    """根据 GPU 型号推荐驱动版本"""
    if any(x in model.upper() for x in ["RTX 40", "RTX 50", "A100", "H100", "A40"]):
        return RECOMMENDED_DRIVERS[0]  # 550
    elif any(x in model.upper() for x in ["RTX 30", "RTX 20", "T4", "RTX A"]):
        return RECOMMENDED_DRIVERS[1]  # 535
    else:
        return RECOMMENDED_DRIVERS[2]  # 525


def parse_latest_stable(html: str) -> Optional[str]:
    """从 NVIDIA 官网页面提取最新稳定版号"""
    m = re.search(r"Latest\s*Production\s*Branch:\s*(\S+)", html, re.I)
    if m:
        return m.group(1)
    m = re.search(r"NVIDIA-Linux-x86_64-([\d.]+)\.run", html)
    if m:
        return m.group(1)
    return None
