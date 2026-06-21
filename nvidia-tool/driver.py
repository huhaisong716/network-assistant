"""驱动版本匹配与下载"""

import re

# 驱动索引：显卡前缀 → 最低推荐驱动版本
# 新显卡需要新版驱动
GPU_DRIVER_MIN = [
    (re.compile(r"RTX 50\d{2}", re.I), "570"),
    (re.compile(r"RTX 40\d{2}", re.I), "550"),
    (re.compile(r"RTX 30\d{2}", re.I), "525"),
    (re.compile(r"RTX 20\d{2}", re.I), "470"),
    (re.compile(r"GTX 16\d{2}", re.I), "470"),
    (re.compile(r"GTX 10\d{2}", re.I), "470"),
    (re.compile(r"\bA100\b|\bA\d+\b|\bH100\b|\bH200\b", re.I), "550"),
    (re.compile(r"\bV100\b|\bP100\b|\bK80\b", re.I), "470"),
]

# 驱动列表
ALL_DRIVERS = [
    {"version": "570.133.00", "branch": "stable", "cuda": "12.8",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/570.133.00/NVIDIA-Linux-x86_64-570.133.00.run",
     "notes": "RTX 50xx 系列推荐"},
    {"version": "570.124.06", "branch": "stable", "cuda": "12.8",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/570.124.06/NVIDIA-Linux-x86_64-570.124.06.run",
     "notes": ""},
    {"version": "560.35.03", "branch": "stable", "cuda": "12.7",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/560.35.03/NVIDIA-Linux-x86_64-560.35.03.run",
     "notes": ""},
    {"version": "550.144.03", "branch": "lts", "cuda": "12.6",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/550.144.03/NVIDIA-Linux-x86_64-550.144.03.run",
     "notes": "LTS 分支，推荐生产环境"},
    {"version": "550.142.00", "branch": "lts", "cuda": "12.6",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/550.142.00/NVIDIA-Linux-x86_64-550.142.00.run",
     "notes": ""},
    {"version": "535.216.03", "branch": "lts", "cuda": "12.4",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/535.216.03/NVIDIA-Linux-x86_64-535.216.03.run",
     "notes": "旧版 LTS，兼容性好"},
    {"version": "525.147.05", "branch": "lts", "cuda": "12.2",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/525.147.05/NVIDIA-Linux-x86_64-525.147.05.run",
     "notes": "最后支持 GTX 10xx"},
    {"version": "470.256.02", "branch": "legacy", "cuda": "11.4",
     "url": "https://us.download.nvidia.com/XFree86/Linux-x86_64/470.256.02/NVIDIA-Linux-x86_64-470.256.02.run",
     "notes": "Legacy，仅老显卡"},
]


def recommend_drivers(gpu_model: str) -> list:
    """根据显卡型号推荐驱动版本"""
    min_ver = ""
    for pattern, version in GPU_DRIVER_MIN:
        if pattern.search(gpu_model):
            min_ver = version
            break

    recommended = []
    for d in ALL_DRIVERS:
        if not min_ver or d["version"][:3] >= min_ver:
            recommended.append(d)
    return recommended if recommended else ALL_DRIVERS


def get_driver_url(version: str) -> str:
    """获取指定版本的下载 URL"""
    for d in ALL_DRIVERS:
        if d["version"] == version:
            return d["url"]
    return f"https://us.download.nvidia.com/XFree86/Linux-x86_64/{version}/NVIDIA-Linux-x86_64-{version}.run"
