"""cuDNN 安装"""
import re
from ssh_client import SSHClient


CUDNN_VERSIONS = {
    "9.3": {
        "url": "https://developer.download.nvidia.com/compute/cudnn/9.3.0/local_installers/cudnn-linux-x86_64-9.3.0.82_cuda12-archive.tar.xz",
        "sha256": "5f0a2ee8e0f2aa914a18ca30696b68dc9e6bc197f655ef97d08ac7f34b2438ca",
    },
    "9.2": {
        "url": "https://developer.download.nvidia.com/compute/cudnn/9.2.1/local_installers/cudnn-linux-x86_64-9.2.1.18_cuda12-archive.tar.xz",
        "sha256": "a7b880ce38c8de818cfe42d33bf1f66958c6e4c4b7a2a6f3344ac2e82adae904",
    },
    "8.9": {
        "url": "https://developer.download.nvidia.com/compute/cudnn/8.9.7/local_installers/cudnn-linux-x86_64-8.9.7.29_cuda12-archive.tar.xz",
        "sha256": "2b18cb3713a0f46078a77e0223cd94738b05074729d7951e3a488e04cb2ebc36",
    },
}


def install_cudnn(ssh: SSHClient, version: str = "9.3",
                  progress_callback=None) -> tuple[bool, list[str]]:
    """远程安装 cuDNN"""
    logs = []

    if version not in CUDNN_VERSIONS:
        logs.append(f"不支持的 cuDNN 版本: {version}")
        return False, logs

    info = CUDNN_VERSIONS[version]
    filename = f"cudnn-linux-x86_64-{version}-archive.tar.xz"
    extract_dir = f"cudnn-linux-x86_64-{version}-archive"

    logs.append(f"[1/3] 下载 cuDNN {version}...")
    ec, out, err = ssh.exec(
        f"cd /tmp && wget -q --show-progress {info['url']} -O {filename} 2>&1", timeout=600
    )
    if ec != 0:
        logs.append(f"  ✗ 下载失败: {err or out}")
        return False, logs
    logs.append("  ✓ 下载完成")
    if progress_callback:
        progress_callback(1, 3, "下载 cuDNN")

    logs.append("[2/3] 解压并复制到 CUDA 目录...")
    cmds = (
        f"cd /tmp && tar -xf {filename} 2>&1 && "
        f"sudo cp {extract_dir}/include/cudnn*.h /usr/local/cuda/include/ 2>&1 && "
        f"sudo cp -P {extract_dir}/lib/libcudnn* /usr/local/cuda/lib64/ 2>&1 && "
        f"sudo chmod a+r /usr/local/cuda/include/cudnn*.h /usr/local/cuda/lib64/libcudnn* 2>&1"
    )
    ec, out, err = ssh.exec(cmds, timeout=60)
    if ec != 0:
        logs.append(f"  ✗ 安装失败: {err or out[:300]}")
        return False, logs
    logs.append("  ✓ 文件已复制")
    if progress_callback:
        progress_callback(2, 3, "安装 cuDNN 文件")

    logs.append("[3/3] 验证...")
    ec, out, err = ssh.exec(
        "cat /usr/local/cuda/include/cudnn_version.h 2>/dev/null | grep CUDNN_MAJOR -A 2 | head -3 || "
        "cat /usr/local/cuda/include/cudnn.h 2>/dev/null | grep CUDNN_MAJOR -A 2 | head -3", timeout=10
    )
    if ec == 0 and out.strip():
        logs.append(f"  ✓ cuDNN 版本: {out.strip()}")
    else:
        logs.append("  ⚠ 版本信息未找到，但文件已复制")
    if progress_callback:
        progress_callback(3, 3, "cuDNN 安装完成")

    return True, logs


def get_cudnn_versions() -> list[str]:
    return list(CUDNN_VERSIONS.keys())
