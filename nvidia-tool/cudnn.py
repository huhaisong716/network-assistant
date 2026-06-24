"""cuDNN 安装管理（复制头文件和库文件）"""
from ssh_client import SSHClient
from dataclasses import dataclass


@dataclass
class CUDNNVersion:
    version: str      # 如 "9.3"
    cuda_compat: str  # 兼容的 CUDA 版本
    archive_url: str  # NVIDIA cuDNN archive 地址
    recommend: bool = False


# ── cuDNN 版本 ────────────────────────────────────────────
CUDNN_VERSIONS = [
    CUDNNVersion("9.3", "12.x",
                 "https://developer.download.nvidia.com/compute/cudnn/9.3.0/local_installers/"
                 "cudnn-linux-x86_64-9.3.0.75_cuda12-archive.tar.xz",
                 True),
    CUDNNVersion("9.2", "12.x",
                 "https://developer.download.nvidia.com/compute/cudnn/9.2.1/local_installers/"
                 "cudnn-linux-x86_64-9.2.1.18_cuda12-archive.tar.xz",
                 False),
    CUDNNVersion("8.9", "11.x/12.x",
                 "https://developer.download.nvidia.com/compute/cudnn/8.9.7/local_installers/"
                 "cudnn-linux-x86_64-8.9.7.29_cuda12-archive.tar.xz",
                 False),
]


def get_cudnn_versions() -> list[CUDNNVersion]:
    return CUDNN_VERSIONS


def get_recommended_cudnn(cuda_version: str) -> CUDNNVersion:
    """根据 CUDA 版本推荐 cuDNN 版本"""
    major = cuda_version.split(".")[0]
    if major == "12":
        return CUDNN_VERSIONS[0]  # 9.3
    elif major == "11":
        return CUDNN_VERSIONS[2]  # 8.9
    return CUDNN_VERSIONS[0]


def install_cudnn(ssh: SSHClient, version: CUDNNVersion | str) -> tuple[bool, list[str]]:
    """安装 cuDNN，返回 (成功?, 日志)"""
    if isinstance(version, str):
        for c in CUDNN_VERSIONS:
            if str(version) in c.version or str(version) in c.archive_url:
                version = c
                break
        else:
            return False, [f"[cuDNN] 未知版本: {version}"]

    logs = [f"[cuDNN] 安装 cuDNN {version.version} (兼容 CUDA {version.cuda_compat})..."]

    # 下载
    ec, out, err = ssh.exec("ls /tmp/cudnn_download/ 2>/dev/null | head -5")
    has_download = ec == 0 and out.strip()

    if not has_download:
        logs.append(f"  下载 cuDNN...")
        ec, out, err = ssh.exec(
            f"mkdir -p /tmp/cudnn_download && "
            f"cd /tmp/cudnn_download && "
            f"wget -q --show-progress {version.archive_url} -O cudnn.tar.xz 2>&1",
            timeout=600,
        )
        if ec != 0:
            logs.append(f"  ✗ 下载失败: {err[:200]}")
            return False, logs
        logs.append("  ✓ 下载完成")

    # 解压
    logs.append("  解压...")
    ec, out, err = ssh.exec(
        "cd /tmp/cudnn_download && "
        "tar xf cudnn.tar.xz 2>&1 && "
        "ls -d */ | head -3",
        timeout=30,
    )
    if ec != 0:
        logs.append(f"  ✗ 解压失败: {err[:200]}")
        return False, logs
    dir_name = out.strip().split("\n")[0] if out.strip() else "cudnn-linux-*/"
    logs.append(f"  ✓ 解压完成: {dir_name}")

    # 复制到 CUDA 目录
    logs.append("  复制文件到 CUDA 目录...")
    ec, out, err = ssh.exec(
        f"cd /tmp/cudnn_download && "
        f"CUDNN_DIR=$(ls -d cudnn-*/ 2>/dev/null | head -1) && "
        f"sudo cp -r $CUDNN_DIR/include/* /usr/local/cuda/include/ && "
        f"sudo cp -r $CUDNN_DIR/lib/* /usr/local/cuda/lib64/ 2>/dev/null || "
        f"sudo cp -r $CUDNN_DIR/lib64/* /usr/local/cuda/lib64/ && "
        f"sudo chmod a+r /usr/local/cuda/include/cudnn*.h /usr/local/cuda/lib64/libcudnn* 2>&1",
        timeout=30,
    )
    if ec != 0:
        logs.append(f"  ✗ 复制失败: {err[:200]}")
        return False, logs
    logs.append("  ✓ 文件已复制")

    # 验证
    ec, out, err = ssh.exec(
        "cat /usr/local/cuda/include/cudnn_version.h 2>/dev/null | "
        "grep '#define CUDNN_MAJOR' | head -1 || "
        "cat /usr/local/cuda/include/cudnn.h 2>/dev/null | "
        "grep '#define CUDNN_MAJOR' | head -1",
        timeout=10,
    )
    if ec == 0 and out.strip():
        logs.append(f"  ✓ cuDNN 版本确认: {out.strip()}")
    else:
        logs.append("  ✓ 文件复制完成")
    return True, logs
