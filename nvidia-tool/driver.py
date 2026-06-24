"""NVIDIA 驱动版本管理：支持 apt 包名 / .run 文件 / ubuntu-drivers 集成"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DriverOption:
    """一个驱动选项"""
    version: str              # 版本号，如 "550.144.03"
    apt_package: str          # apt 包名，如 "nvidia-driver-550"
    runfile_url: str = ""     # .run 文件下载 URL
    is_recommended: bool = False
    branch: str = ""          # "production" / "new-feature"


# ── 预置驱动列表（兜底用，联网查询失败时使用） ────────────
BUILTIN_DRIVERS = [
    DriverOption("550.144.03", "nvidia-driver-550",
                 "https://us.download.nvidia.com/XFree86/Linux-x86_64/550.144.03/NVIDIA-Linux-x86_64-550.144.03.run",
                 True, "production"),
    DriverOption("535.216.03", "nvidia-driver-535",
                 "https://us.download.nvidia.com/XFree86/Linux-x86_64/535.216.03/NVIDIA-Linux-x86_64-535.216.03.run",
                 True, "production"),
    DriverOption("525.147.05", "nvidia-driver-525",
                 "https://us.download.nvidia.com/XFree86/Linux-x86_64/525.147.05/NVIDIA-Linux-x86_64-525.147.05.run",
                 False, "production"),
    DriverOption("470.256.02", "nvidia-driver-470",
                 "https://us.download.nvidia.com/XFree86/Linux-x86_64/470.256.02/NVIDIA-Linux-x86_64-470.256.02.run",
                 False, "legacy"),
    DriverOption("390.157", "nvidia-driver-390",
                 "https://us.download.nvidia.com/XFree86/Linux-x86_64/390.157/NVIDIA-Linux-x86_64-390.157.run",
                 False, "legacy"),
]


def get_runfile_url(version: str) -> str:
    """根据版本号构造 .run 下载 URL"""
    for d in BUILTIN_DRIVERS:
        if d.version == version:
            return d.runfile_url
    return f"https://us.download.nvidia.com/XFree86/Linux-x86_64/{version}/NVIDIA-Linux-x86_64-{version}.run"


def version_to_apt_package(version: str) -> str:
    """从版本号推断 apt 包名，如 550.144.03 → nvidia-driver-550"""
    major = version.split(".")[0]
    return f"nvidia-driver-{major}"


def get_recommended_for_gpu(model: str) -> DriverOption:
    """根据 GPU 型号推荐驱动版本"""
    if any(x in model.upper() for x in ["RTX 40", "RTX 50", "A100", "H100", "A40", "L40", "L4"]):
        return BUILTIN_DRIVERS[0]  # 550
    elif any(x in model.upper() for x in ["RTX 30", "RTX 20", "T4", "RTX A", "A10", "A16"]):
        return BUILTIN_DRIVERS[1]  # 535
    else:
        return BUILTIN_DRIVERS[2]  # 525


def parse_latest_stable(html: str) -> Optional[str]:
    """从 NVIDIA 官网页面提取最新稳定版号"""
    m = re.search(r"Latest\s*Production\s*Branch:\s*(\S+)", html, re.I)
    if m:
        return m.group(1)
    m = re.search(r"NVIDIA-Linux-x86_64-([\d.]+)\.run", html)
    if m:
        return m.group(1)
    return None


def merge_ubuntu_drivers(builtin: list[DriverOption],
                         ubuntu_list: list[dict]) -> list[DriverOption]:
    """将 ubuntu-drivers 查询结果合并到内置列表中"""
    seen_versions = set(d.version for d in builtin)
    result = list(builtin)

    for item in ubuntu_list:
        name = item["name"]
        recommended = item["recommended"]
        # 提取版本号
        m = re.search(r"nvidia-driver-(\d+)", name)
        if m:
            major = m.group(1)
            if major not in seen_versions:
                result.append(DriverOption(
                    version=f"{major}.0.0",
                    apt_package=name,
                    is_recommended=recommended,
                    branch="ubuntu-recommended",
                ))
                seen_versions.add(major)
            elif recommended:
                # 更新推荐标记
                for d in result:
                    if d.version.startswith(major + "."):
                        d.is_recommended = True
    return result
