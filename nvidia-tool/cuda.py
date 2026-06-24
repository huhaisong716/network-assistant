"""CUDA Toolkit 远程安装管理"""
from ssh_client import SSHClient
from dataclasses import dataclass


@dataclass
class CUDAVersion:
    version: str          # 如 "12.5"
    full_version: str     # 如 "12.5.0"
    url: str = ""
    recommended: bool = False


# ── 预置 CUDA 版本 ────────────────────────────────────────
CUDA_VERSIONS = [
    CUDAVersion("12.5", "12.5.0",
                "https://developer.download.nvidia.com/compute/cuda/12.5.0/local_installers/"
                "cuda_12.5.0_555.42.02_linux.run",
                True),
    CUDAVersion("12.4", "12.4.1",
                "https://developer.download.nvidia.com/compute/cuda/12.4.1/local_installers/"
                "cuda_12.4.1_550.54.15_linux.run",
                False),
    CUDAVersion("12.3", "12.3.2",
                "https://developer.download.nvidia.com/compute/cuda/12.3.2/local_installers/"
                "cuda_12.3.2_545.23.08_linux.run",
                False),
    CUDAVersion("11.8", "11.8.0",
                "https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/"
                "cuda_11.8.0_520.61.05_linux.run",
                False),
]


def get_cuda_versions() -> list[CUDAVersion]:
    return CUDA_VERSIONS


def get_recommended_cuda(driver_version: str) -> CUDAVersion | None:
    """根据驱动版本推荐 CUDA 版本"""
    major = driver_version.split(".")[0]
    mapping = {
        "550": "12.5", "545": "12.3", "535": "12.2",
        "525": "12.0", "520": "11.8",
        "470": "11.4", "390": "10.0",
    }
    ver = mapping.get(major, "12.5")
    for c in CUDA_VERSIONS:
        if c.version == ver:
            return c
    return CUDA_VERSIONS[0]


def install_cuda(ssh: SSHClient, version: CUDAVersion | str,
                 install_deps: bool = True) -> tuple[bool, list[str]]:
    """远程安装 CUDA Toolkit，返回 (成功?, 日志)"""
    logs = [f"[CUDA] 安装 CUDA Toolkit {version if isinstance(version, str) else version.version}..."]

    if isinstance(version, str):
        for c in CUDA_VERSIONS:
            if str(version) in c.version or str(version) in c.full_version:
                version = c
                break
        else:
            logs.append(f"  ✗ 未知版本: {version}")
            return False, logs

    # 1. 安装依赖
    if install_deps:
        logs.append("  安装 CUDA 前置依赖...")
        deps = "freeglut3-dev build-essential libx11-dev libxmu-dev libxi-dev"
        ec, out, err = ssh.exec(f"sudo apt install -y {deps} 2>&1", timeout=120)
        logs.append(out.strip()[-300:])
        if ec != 0:
            logs.append(f"  ✗ 依赖安装失败: {err[:200]}")

    # 2. 下载
    filename = f"cuda_{version.full_version}_linux.run"
    logs.append(f"  下载 {filename}...")
    ec, out, err = ssh.exec(
        f"cd /tmp && wget -q --show-progress {version.url} -O {filename} 2>&1",
        timeout=600,
    )
    if ec != 0:
        logs.append(f"  ✗ 下载失败: {err[:200]}")
        return False, logs
    logs.append("  ✓ 下载完成")

    # 3. 安装（不装驱动，只装 CUDA Toolkit）
    logs.append("  执行安装（安装期间可能有弹窗）...")
    # --toolkit 只装 CUDA Toolkit，不装驱动
    # --silent 静默安装
    ec, out, err = ssh.exec(
        f"chmod +x /tmp/{filename} && "
        f"sudo /tmp/{filename} --silent --toolkit --override 2>&1",
        timeout=600,
    )
    logs.append(out.strip()[-300:])
    if ec != 0:
        logs.append(f"  ✗ 安装失败: {err[:200]}")
        # 尝试不带 --silent（让用户交互）
        logs.append("  → 尝试交互式安装...")
        return False, logs

    logs.append("  ✓ CUDA Toolkit 安装完成")

    # 4. 配置环境变量
    logs.append("  配置环境变量...")
    env_lines = [
        'export PATH=/usr/local/cuda/bin:$PATH',
        'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH',
    ]
    for env_line in env_lines:
        ec, out, err = ssh.exec(
            f'grep -q "cuda" ~/.bashrc 2>/dev/null || echo \'{env_line}\' >> ~/.bashrc',
            timeout=10,
        )

    # 立即生效
    ec, out, err = ssh.exec(
        "export PATH=/usr/local/cuda/bin:$PATH && "
        "sudo ldconfig 2>/dev/null",
        timeout=10,
    )
    logs.append("  ✓ 环境变量已配置")

    # 5. 验证
    ec, out, err = ssh.exec(
        "export PATH=/usr/local/cuda/bin:$PATH && nvcc -V 2>&1 | tail -1",
        timeout=10,
    )
    if ec == 0 and out.strip():
        logs.append(f"  ✓ nvcc: {out.strip()}")
    else:
        logs.append("  ⚠ 重新登录后 nvcc 才可用")

    return True, logs
