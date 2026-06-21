"""cuDNN 安装模块"""

CUDNN_ENTRIES = [
    {"version": "9.8.2", "cuda": "12",
     "url": "https://developer.download.nvidia.com/compute/cudnn/9.8.2/local_installers/cudnn_9.8.2_linux-x64.tar.xz",
     "package": "cudnn-linux-x86_64"},
    {"version": "9.5.1", "cuda": "12",
     "url": "https://developer.download.nvidia.com/compute/cudnn/9.5.1/local_installers/cudnn_9.5.1_linux-x64.tar.xz",
     "package": "cudnn-linux-x86_64"},
    {"version": "9.3.0", "cuda": "12",
     "url": "https://developer.download.nvidia.com/compute/cudnn/9.3.0/local_installers/cudnn_9.3.0_linux-x64.tar.xz",
     "package": "cudnn-linux-x86_64"},
    {"version": "8.9.7", "cuda": "11",
     "url": "https://developer.download.nvidia.com/compute/cudnn/8.9.7/local_installers/cudnn-linux-x86_64-8.9.7.29_cuda11-archive.tar.xz",
     "package": "cudnn-linux-x86_64"},
]


def recommend_cudnn(cuda_version: str) -> dict:
    """根据 CUDA 版本推荐 cuDNN"""
    cuda_major = cuda_version.split(".")[0] if cuda_version else "12"
    for c in CUDNN_ENTRIES:
        if c["cuda"] == cuda_major:
            return c
    return CUDNN_ENTRIES[0]


def install_cudnn(ssh, cudnn: dict) -> str:
    """安装 cuDNN，返回空字符串表示成功"""
    version = cudnn["version"]
    url = cudnn["url"]
    package = cudnn["package"]
    remote_tar = f"/tmp/cudnn-{version}.tar.xz"

    print(f"\n  → 下载 cuDNN {version} (CUDA {cudnn['cuda']})...")
    cmd = f"wget -q --show-progress '{url}' -O {remote_tar} 2>&1"
    out, err, code = ssh.exec(cmd, timeout=600)
    if code != 0:
        cmd = f"curl -L -o {remote_tar} '{url}' 2>&1"
        out, err, code = ssh.exec(cmd, timeout=600)
        if code != 0:
            return f"下载 cuDNN 失败: {err[:200]}"

    print("  → 解压并配置...")
    extract_cmd = (
        f"cd /tmp && tar -xf {remote_tar} "
        f"&& sudo cp -r {package}*/include/cudnn*.h /usr/local/cuda/include/ "
        f"&& sudo cp -r {package}*/lib/libcudnn* /usr/local/cuda/lib64/ "
        f"&& sudo chmod a+r /usr/local/cuda/include/cudnn*.h /usr/local/cuda/lib64/libcudnn*"
    )
    out, err, code = ssh.exec(extract_cmd, timeout=60)
    if code != 0:
        return f"cuDNN 配置失败: {(out + err)[:200]}"

    print(f"  ✓ cuDNN {version} 安装完成")
    return ""
