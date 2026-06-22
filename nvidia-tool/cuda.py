"""CUDA Toolkit 安装"""
from ssh_client import SSHClient


CUDA_DOWNLOADS = {
    "12.5": {
        "url": "https://developer.download.nvidia.com/compute/cuda/12.5.0/local_installers/cuda_12.5.0_555.42.02_linux.run",
        "sha256": "6ba6ef3fa0b13d22d17b31a202317bf61339044f5848e5ffe13e6b2a3bda9a7b",
    },
    "12.4": {
        "url": "https://developer.download.nvidia.com/compute/cuda/12.4.0/local_installers/cuda_12.4.0_550.54.14_linux.run",
        "sha256": "54a22c301908ec406abc265e8f150b2caeb0fe646090f427ff11424c5c464f74",
    },
    "12.3": {
        "url": "https://developer.download.nvidia.com/compute/cuda/12.3.0/local_installers/cuda_12.3.0_545.23.06_linux.run",
        "sha256": "a868b31c9e38187e30195811f1198250d3a0bb3b4ba77deaa1377723acc7a851",
    },
    "12.2": {
        "url": "https://developer.download.nvidia.com/compute/cuda/12.2.0/local_installers/cuda_12.2.0_535.54.03_linux.run",
        "sha256": "b0a2e4e3563c53aacaebd9946adc34fbbe4f432970e0cb94e1ba3bc288e40ac4",
    },
    "11.8": {
        "url": "https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run",
        "sha256": "8d5731da47620a3bede0d8e732ae7bd35882ced8e1d6ba9e9dc2c9f444d3c199",
    },
}


def install_cuda(ssh: SSHClient, version: str = "12.4",
                 progress_callback=None) -> tuple[bool, list[str]]:
    """远程安装 CUDA Toolkit"""
    logs = []

    if version not in CUDA_DOWNLOADS:
        logs.append(f"不支持的 CUDA 版本: {version}")
        return False, logs

    info = CUDA_DOWNLOADS[version]
    filename = f"cuda_{version}_linux.run"

    logs.append(f"[1/3] 下载 CUDA Toolkit {version}...")
    ec, out, err = ssh.exec(
        f"cd /tmp && wget -q --show-progress {info['url']} -O {filename} 2>&1", timeout=600
    )
    if ec != 0:
        logs.append(f"  ✗ 下载失败: {err or out}")
        return False, logs
    logs.append("  ✓ 下载完成")
    if progress_callback:
        progress_callback(1, 3, "下载 CUDA Toolkit")

    logs.append("[2/3] 安装 CUDA Toolkit（静默模式，仅驱动）...")
    ec, out, err = ssh.exec(
        f"sh /tmp/{filename} --silent --toolkit --override 2>&1", timeout=600
    )
    if ec != 0:
        logs.append(f"  ✗ 安装失败: {err or out[:300]}")
        return False, logs
    logs.append("  ✓ 安装完成")
    if progress_callback:
        progress_callback(2, 3, "安装 CUDA Toolkit")

    logs.append("[3/3] 配置环境变量...")
    ec, _, _ = ssh.exec(
        "echo 'export PATH=/usr/local/cuda/bin:$PATH' >> /etc/profile.d/cuda.sh && "
        "echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> /etc/profile.d/cuda.sh && "
        "chmod +x /etc/profile.d/cuda.sh", timeout=10
    )
    logs.append("  ✓ 环境变量已配置")

    # 验证
    ec, out, err = ssh.exec("nvcc --version 2>&1")
    if ec == 0:
        logs.append(f"  ✓ 验证通过: {out.strip()}")
    else:
        logs.append("  ⚠ nvcc 未找到，可能需重新登录")
    if progress_callback:
        progress_callback(3, 3, "CUDA 安装完成")

    return True, logs


def get_cuda_versions() -> list[str]:
    return list(CUDA_DOWNLOADS.keys())
