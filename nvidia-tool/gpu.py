"""远程检测 NVIDIA 显卡信息"""
from ssh_client import SSHClient


def detect_gpu(ssh: SSHClient) -> dict | str:
    """检测显卡信息，返回 dict 或错误字符串"""
    # 1. lspci 判断显卡型号
    ec, out, err = ssh.exec("lspci | grep -i nvidia 2>/dev/null")
    if ec != 0 or not out.strip():
        ec2, out2, _ = ssh.exec("lspci | grep -i vga 2>/dev/null")
        if "nvidia" not in out2.lower():
            return "未检测到 NVIDIA 显卡"
        out = out2

    model = out.strip().split(": ", 1)[-1] if ": " in out else out.strip()

    # 2. nvidia-smi 检测驱动信息
    ec2, smi_out, smi_err = ssh.exec("nvidia-smi --query-gpu=name,driver_version,cuda_version --format=csv,noheader 2>/dev/null")
    has_driver = ec2 == 0 and smi_out.strip()

    result = {
        "model": model,
        "driver_installed": has_driver,
    }

    if has_driver:
        parts = [p.strip() for p in smi_out.strip().split(", ")]
        result["driver_version"] = parts[1] if len(parts) > 1 else ""
        result["cuda_version"] = parts[2] if len(parts) > 2 else ""
    else:
        result["driver_version"] = ""
        result["cuda_version"] = ""

    # 3. 系统信息
    ec3, arch_out, _ = ssh.exec("uname -m")
    result["arch"] = arch_out.strip() if ec3 == 0 else "x86_64"

    return result


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
    }
    for key, cap in mapping.items():
        if key.lower() in model_name.lower():
            return cap
    return None
