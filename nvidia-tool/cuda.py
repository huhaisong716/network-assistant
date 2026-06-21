"""CUDA 安装模块"""

# CUDA 版本列表
CUDA_ENTRIES = [
    {"version": "12.8.0", "url": "https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/cuda_12.8.0_570.86.10_linux.run", "min_driver": "570"},
    {"version": "12.6.3", "url": "https://developer.download.nvidia.com/compute/cuda/12.6.3/local_installers/cuda_12.6.3_560.35.05_linux.run", "min_driver": "560"},
    {"version": "12.4.1", "url": "https://developer.download.nvidia.com/compute/cuda/12.4.1/local_installers/cuda_12.4.1_550.54.15_linux.run", "min_driver": "550"},
    {"version": "12.2.2", "url": "https://developer.download.nvidia.com/compute/cuda/12.2.2/local_installers/cuda_12.2.2_535.104.05_linux.run", "min_driver": "535"},
    {"version": "11.8.0", "url": "https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run", "min_driver": "525"},
]


def recommend_cuda(driver_version: str) -> dict:
    """根据驱动版本推荐 CUDA"""
    if not driver_version:
        return CUDA_ENTRIES[0]
    driver_major = driver_version[:3]
    for c in CUDA_ENTRIES:
        if driver_major >= c["min_driver"]:
            return c
    return CUDA_ENTRIES[0]


def install_cuda(ssh, cuda: dict) -> str:
    """安装 CUDA Toolkit，返回空字符串表示成功"""
    version = cuda["version"]
    url = cuda["url"]
    remote_path = f"/tmp/cuda_{version}_linux.run"

    print(f"\n  → 下载 CUDA {version}...")
    cmd = f"wget -q --show-progress '{url}' -O {remote_path} 2>&1"
    out, err, code = ssh.exec(cmd, timeout=600)
    if code != 0:
        cmd = f"curl -L -o {remote_path} '{url}' 2>&1"
        out, err, code = ssh.exec(cmd, timeout=600)
        if code != 0:
            return f"下载 CUDA 失败: {err[:200]}"

    print("  → 执行 CUDA 安装（仅 Toolkit）...")
    install_cmd = f"chmod +x {remote_path} && sudo {remote_path} --silent --toolkit 2>&1"
    out, err, code = ssh.exec(install_cmd, timeout=600)
    if code != 0:
        return f"CUDA 安装失败: {(out + err)[:300]}"

    # 配置环境变量
    print("  → 配置 CUDA 环境变量...")
    env_cmd = (
        "echo 'export PATH=/usr/local/cuda/bin:$PATH' | sudo tee /etc/profile.d/cuda.sh > /dev/null "
        "&& echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' | sudo tee -a /etc/profile.d/cuda.sh > /dev/null "
        "&& sudo chmod +x /etc/profile.d/cuda.sh"
    )
    ssh.exec(env_cmd)

    # 验证
    nvcc, _, _ = ssh.exec("source /etc/profile.d/cuda.sh 2>/dev/null; nvcc --version 2>&1 | tail -1")
    if nvcc.strip():
        print(f"  ✓ CUDA {version} 安装完成: {nvcc.strip()}")
    else:
        print(f"  ✓ CUDA {version} 安装完成（请手动验证 nvcc --version）")
    return ""
