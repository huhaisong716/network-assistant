"""显卡检测 - 远程 lspci + nvidia-smi"""

import re


# 常见 NVIDIA 显卡型号匹配列表
GPU_MODELS = [
    (re.compile(r"RTX 5090", re.I), "NVIDIA RTX 5090"),
    (re.compile(r"RTX 5080", re.I), "NVIDIA RTX 5080"),
    (re.compile(r"RTX 5070", re.I), "NVIDIA RTX 5070"),
    (re.compile(r"RTX 5060", re.I), "NVIDIA RTX 5060"),
    (re.compile(r"RTX 4090", re.I), "NVIDIA RTX 4090"),
    (re.compile(r"RTX 4080", re.I), "NVIDIA RTX 4080"),
    (re.compile(r"RTX 4070", re.I), "NVIDIA RTX 4070"),
    (re.compile(r"RTX 4060", re.I), "NVIDIA RTX 4060"),
    (re.compile(r"RTX 3090", re.I), "NVIDIA RTX 3090"),
    (re.compile(r"RTX 3080", re.I), "NVIDIA RTX 3080"),
    (re.compile(r"RTX 3070", re.I), "NVIDIA RTX 3070"),
    (re.compile(r"RTX 3060", re.I), "NVIDIA RTX 3060"),
    (re.compile(r"PRO 6000", re.I), "NVIDIA PRO 6000"),
    (re.compile(r"PRO 5000", re.I), "NVIDIA PRO 5000"),
    (re.compile(r"\bA100\b", re.I), "NVIDIA A100"),
    (re.compile(r"\bA6000\b", re.I), "NVIDIA A6000"),
    (re.compile(r"\bA5000\b", re.I), "NVIDIA A5000"),
    (re.compile(r"\bA4000\b", re.I), "NVIDIA A4000"),
    (re.compile(r"\bH100\b", re.I), "NVIDIA H100"),
    (re.compile(r"\bH200\b", re.I), "NVIDIA H200"),
    (re.compile(r"\bB100\b", re.I), "NVIDIA B100"),
    (re.compile(r"\bB200\b", re.I), "NVIDIA B200"),
    (re.compile(r"GTX 1080", re.I), "NVIDIA GTX 1080"),
    (re.compile(r"GTX 1070", re.I), "NVIDIA GTX 1070"),
    (re.compile(r"GTX 1060", re.I), "NVIDIA GTX 1060"),
    (re.compile(r"\bT4\b", re.I), "NVIDIA T4"),
    (re.compile(r"\bV100\b", re.I), "NVIDIA V100"),
    (re.compile(r"\bP100\b", re.I), "NVIDIA P100"),
    (re.compile(r"\bK80\b", re.I), "NVIDIA K80"),
]


def detect_gpu(ssh):
    """远程检测显卡型号和驱动状态"""
    gpu = {"model": "", "has_driver": False, "driver_version": "", "cuda_version": ""}

    # Step 1: lspci 检测显卡型号
    out, err, code = ssh.exec("lspci -nn | grep -i nvidia")
    if code != 0 or not out.strip():
        out, err, code = ssh.exec("sudo lspci -nn | grep -i nvidia")
    if code != 0 or not out.strip():
        raise RuntimeError("未检测到 NVIDIA 显卡")

    gpu["model"] = _parse_model(out)

    # Step 2: 检查是否已安装驱动
    out, _, code = ssh.exec("nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null")
    if code == 0 and out.strip():
        gpu["has_driver"] = True
        gpu["driver_version"] = out.strip()

        # 检测 CUDA 版本
        out, _, _ = ssh.exec("nvcc --version 2>/dev/null | grep 'release'")
        m = re.search(r"release (\S+),", out)
        if m:
            gpu["cuda_version"] = m.group(1)

    return gpu


def _parse_model(lspci_output: str) -> str:
    """从 lspci 输出中提取显卡型号"""
    for pattern, name in GPU_MODELS:
        if pattern.search(lspci_output):
            return name

    # 回退：从方括号提取设备名
    m = re.search(r"\[([A-Za-z0-9 /]+)\]", lspci_output)
    if m:
        return f"NVIDIA {m.group(1).strip()}"
    return lspci_output.strip().split("\n")[0][:60]
