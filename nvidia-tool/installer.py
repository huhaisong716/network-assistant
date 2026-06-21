"""安装执行 - 禁用 nouveau → 下载 → 安装 → 验证"""

import os
from datetime import datetime

from config import get_log_dir
from errors import find_known_error


def save_log(name: str, stdout: str, stderr: str):
    """保存安装日志"""
    log_dir = get_log_dir()
    path = os.path.join(log_dir, f"{datetime.now():%Y%m%d_%H%M%S}_{name}.log")
    with open(path, "w") as f:
        f.write(f"=== STDOUT ===\n{stdout}\n=== STDERR ===\n{stderr}\n")


def disable_nouveau(ssh) -> str:
    """禁用 Nouveau 驱动"""
    print("\n  → 禁用 Nouveau 驱动...")
    cmd = (
        'echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nvidia-nouveau.conf > /dev/null '
        '&& echo "options nouveau modeset=0" | sudo tee -a /etc/modprobe.d/blacklist-nvidia-nouveau.conf > /dev/null '
        "&& sudo update-initramfs -u"
    )
    out, err, code = ssh.exec(cmd, timeout=120)
    if code != 0:
        return f"禁用 Nouveau 失败: {err[:200]}"
    print("  ✓ Nouveau 已禁用（需重启生效）")
    return ""


def download_driver(ssh, version: str, url: str) -> str:
    """在远程服务器上下载驱动"""
    remote_path = f"/tmp/NVIDIA-Linux-x86_64-{version}.run"
    print(f"\n  → 下载驱动 {version}...")

    # wget 下载
    cmd = f"wget -q --show-progress '{url}' -O {remote_path} 2>&1"
    out, err, code = ssh.exec(cmd, timeout=300)
    if code != 0:
        # 尝试 curl 回退
        cmd = f"curl -L -o {remote_path} '{url}' 2>&1"
        out, err, code = ssh.exec(cmd, timeout=300)
        if code != 0:
            return f"下载失败: {err[:200]}"

    # 验证 + 加执行权限
    ssh.exec(f"chmod +x {remote_path}")
    exists = ssh.file_exists(remote_path)
    if not exists:
        return "驱动文件未找到"
    print(f"  ✓ 下载完成")
    return ""


def run_installer(ssh, version: str) -> tuple:
    """执行驱动安装，返回 (error_info, stdout, stderr)"""
    remote_path = f"/tmp/NVIDIA-Linux-x86_64-{version}.run"
    print("\n  → 执行驱动安装...")

    cmd = f"sudo {remote_path} --silent --disable-nouveau --no-cc-version-check 2>&1"
    out, err, code = ssh.exec(cmd, timeout=300)

    save_log("driver-install", out, err)

    if code != 0:
        combined = out + "\n" + err
        known = find_known_error(combined)
        return known, out, err

    print("  ✓ 驱动安装完成")
    return {}, out, err


def verify_installation(ssh) -> dict:
    """验证驱动安装"""
    print("\n  → 验证安装...")
    from gpu import detect_gpu
    try:
        return detect_gpu(ssh)
    except RuntimeError as e:
        return {"model": str(e), "has_driver": False}
