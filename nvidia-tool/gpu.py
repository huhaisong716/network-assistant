"""远程检测 NVIDIA 显卡信息（支持多 GPU）"""
from ssh_client import SSHClient
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GPUInfo:
    index: int = 0          # GPU 序号
    pci_id: str = ""        # PCI Bus ID
    model: str = ""         # 型号
    driver_installed: bool = False
    driver_version: str = ""
    cuda_version: str = ""
    memory_mb: int = 0
    persistence_m: bool = False


def detect_all_gpus(ssh: SSHClient) -> list[GPUInfo] | str:
    """检测所有 NVIDIA 显卡，返回 GPUInfo 列表或错误字符串"""
    gpus: list[GPUInfo] = []

    # 1. lspci 列出所有 NVIDIA 显卡
    ec, out, err = ssh.exec("lspci -mm | grep -i nvidia 2>/dev/null")
    if ec != 0 or not out.strip():
        ec2, out2, _ = ssh.exec("lspci -mm | grep -i 'vga.*nvidia\\|3d.*nvidia' 2>/dev/null")
        if not out2.strip():
            return "未检测到 NVIDIA 显卡"
        out = out2

    # 解析 lspci 结果
    pci_devices = []
    for line in out.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip('"') for p in line.split('"')]
        pci_id = parts[0].split()[0] if parts else ""
        desc = parts[-2] if len(parts) >= 2 else parts[-1] if parts else ""
        pci_devices.append((pci_id, desc))

    if not pci_devices:
        return "无法解析显卡信息"

    # 2. nvidia-smi 获取详细信息（驱动已装时）
    ec_smi, smi_out, _ = ssh.exec(
        "nvidia-smi --query-gpu=index,name,pci.bus_id,driver_version,memory.total,persistence_mode --format=csv,noheader 2>/dev/null"
    )
    smi_data = {}
    if ec_smi == 0 and smi_out.strip():
        for line in smi_out.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    idx = int(parts[0])
                    smi_data[idx] = {
                        "name": parts[1] if len(parts) > 1 else "",
                        "bus_id": parts[2] if len(parts) > 2 else "",
                        "driver_version": parts[3] if len(parts) > 3 else "",
                        "memory": parts[4] if len(parts) > 4 else "",
                        "persistence": parts[5].lower() == "enabled" if len(parts) > 5 else False,
                    }
                except ValueError:
                    pass

    # 3. nvidia-smi CUDA 版本
    ec_cuda, cuda_out, _ = ssh.exec(
        "nvidia-smi --query-gpu=index,cuda_version --format=csv,noheader 2>/dev/null"
    )
    cuda_data = {}
    if ec_cuda == 0 and cuda_out.strip():
        for line in cuda_out.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                try:
                    cuda_data[int(parts[0])] = parts[1]
                except ValueError:
                    pass

    # 4. 组装结果
    for i, (pci_id, desc) in enumerate(pci_devices):
        gpu = GPUInfo(
            index=i,
            pci_id=pci_id,
            model=desc,
            driver_installed=i in smi_data,
            driver_version=smi_data.get(i, {}).get("driver_version", ""),
            cuda_version=cuda_data.get(i, ""),
            memory_mb=_parse_memory(smi_data.get(i, {}).get("memory", "0 MiB")),
            persistence_m=smi_data.get(i, {}).get("persistence", False),
        )
        gpus.append(gpu)

    return gpus


def _parse_memory(s: str) -> int:
    """从 '15109 MiB' 中提取数字"""
    import re
    m = re.search(r"(\d+)", s.replace(",", ""))
    return int(m.group(1)) if m else 0


def get_compute_capability(model_name: str) -> str | None:
    """根据显卡型号返回计算能力"""
    mapping = {
        "RTX 4090": "8.9", "RTX 4080": "8.9", "RTX 4070": "8.9",
        "RTX 4060": "8.9", "RTX 3090": "8.6", "RTX 3080": "8.6",
        "RTX 3070": "8.6", "RTX 3060": "8.6",
        "RTX 2080": "7.5", "RTX 2070": "7.5", "RTX 2060": "7.5",
        "GTX 1660": "7.5", "GTX 1650": "7.5",
        "GTX 1080": "6.1", "GTX 1070": "6.1", "GTX 1060": "6.1",
        "A100": "8.0", "V100": "7.0", "T4": "7.5", "H100": "9.0",
        "L40": "8.9", "L4": "8.9", "A40": "8.6", "A30": "8.0",
        "A10": "8.6", "A16": "8.6",
    }
    for key, cap in mapping.items():
        if key.lower() in model_name.lower():
            return cap
    return None


def check_nouveau(ssh: SSHClient) -> tuple[bool, str]:
    """检查 nouveau 是否已禁用，返回 (已禁用?, 详情)"""
    ec, out, _ = ssh.exec("lsmod | grep nouveau 2>/dev/null")
    if out.strip():
        return False, "nouveau 模块仍加载中"
    # 再检查 blacklist 配置
    ec2, out2, _ = ssh.exec("cat /etc/modprobe.d/blacklist-nvidia-nouveau.conf 2>/dev/null")
    if "blacklist nouveau" in out2:
        return True, "已禁用（需重启生效）"
    return False, "未配置 nouveau 黑名单"
