"""依赖检测：支持 ubuntu-drivers / PPA / 系统依赖 """

# ── 驱动安装前置依赖检查项 ──────────────────────────────────
DRIVER_DEPENDENCIES = {
    "gcc": {
        "label": "GCC 编译器",
        "check": "gcc --version 2>/dev/null | head -1",
        "ok_match": r"gcc",
        "install_cmd": "apt install -y gcc g++",
    },
    "make": {
        "label": "make 工具",
        "check": "make --version 2>/dev/null | head -1",
        "ok_match": r"GNU Make",
        "install_cmd": "apt install -y make",
    },
    "kernel_headers": {
        "label": "内核头文件",
        "check": "dpkg -l 2>/dev/null | grep -q linux-headers-$(uname -r) && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y linux-headers-$(uname -r)",
    },
    "build_essential": {
        "label": "build-essential",
        "check": "dpkg -l 2>/dev/null | grep -q build-essential && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y build-essential",
    },
    "dkms": {
        "label": "DKMS",
        "check": "dkms --version 2>/dev/null | head -1",
        "ok_match": r"dkms",
        "install_cmd": "apt install -y dkms",
    },
    "secureboot": {
        "label": "Secure Boot 状态",
        "check": "mokutil --sb-state 2>/dev/null",
        "ok_match": r"disabled|does not support|not enabled",
        "install_cmd": None,  # 需 BIOS 手动
    },
}

# ── CUDA 前置依赖 ──────────────────────────────────────────
CUDA_DEPENDENCIES = {
    "freeglut3": {
        "label": "freeglut3-dev",
        "check": "dpkg -l 2>/dev/null | grep -q freeglut3-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y freeglut3-dev",
    },
    "libx11": {
        "label": "libx11-dev",
        "check": "dpkg -l 2>/dev/null | grep -q libx11-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y libx11-dev",
    },
    "libxmu": {
        "label": "libxmu-dev",
        "check": "dpkg -l 2>/dev/null | grep -q libxmu-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y libxmu-dev",
    },
    "libxi": {
        "label": "libxi-dev",
        "check": "dpkg -l 2>/dev/null | grep -q libxi-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y libxi-dev",
    },
}


def check_dependency(ssh, dep_def: dict) -> tuple[bool, str]:
    """执行单条依赖检查，返回 (通过?, 详情)"""
    ec, out, err = ssh.exec(dep_def["check"], timeout=10)
    import re
    if re.search(dep_def["ok_match"], out, re.IGNORECASE):
        detail = out.strip().split("\n")[0][:80] if out.strip() else "已安装"
        return True, detail
    return False, err.strip() or "未安装"


def check_all_deps(ssh, dep_dict: dict) -> dict[str, tuple[bool, str]]:
    """批量检查依赖，返回 {key: (ok, detail)}"""
    results = {}
    for key, dep_def in dep_dict.items():
        ok, detail = check_dependency(ssh, dep_def)
        results[key] = (ok, detail)
    return results


def get_failed(results: dict[str, tuple[bool, str]]) -> list[str]:
    """返回未通过的依赖 key 列表"""
    return [k for k, (ok, _) in results.items() if not ok]


def install_dependency(ssh, dep_def: dict, timeout=120) -> tuple[bool, str]:
    """安装单条依赖"""
    cmd = dep_def.get("install_cmd")
    if not cmd:
        return False, "无自动安装方案（需手动处理）"
    ec, out, err = ssh.exec(f"sudo {cmd}", timeout=timeout)
    if ec != 0:
        return False, err.strip() or out.strip()[:200]
    return True, "安装成功"


def query_ubuntu_drivers(ssh) -> list[dict] | str:
    """通过 ubuntu-drivers devices 查询可用驱动列表"""
    # 先确保 ppa 已添加
    ec1, out1, _ = ssh.exec(
        "apt list --installed 2>/dev/null | grep -q ubuntu-drivers-common && echo installed"
    )
    if "installed" not in out1:
        # 尝试安装 ubuntu-drivers-common
        ssh.exec("sudo apt install -y ubuntu-drivers-common", timeout=60)

    ec, out, err = ssh.exec("ubuntu-drivers devices 2>&1", timeout=30)
    if ec != 0 or not out.strip():
        return f"无法查询驱动列表: {err or out[:200]}"

    drivers = []
    for line in out.strip().split("\n"):
        line = line.strip()
        if "driver" in line and ":" in line:
            parts = [p.strip() for p in line.split(":")]
            if len(parts) >= 2:
                name = parts[1].strip()
                # 提取推荐标记
                recommended = "recommended" in line.lower() or "distro non-free" in line.lower()
                drivers.append({
                    "name": name,
                    "recommended": recommended,
                    "source_line": line.strip(),
                })

    return drivers


def add_graphics_ppa(ssh) -> tuple[bool, str]:
    """添加 graphics-drivers PPA"""
    ec, out, err = ssh.exec(
        "sudo add-apt-repository -y ppa:graphics-drivers/ppa && sudo apt update",
        timeout=120,
    )
    if ec != 0:
        return False, f"添加 PPA 失败: {err or out[:200]}"
    return True, "PPA 已添加，源已更新"
