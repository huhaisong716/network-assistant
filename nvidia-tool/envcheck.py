"""依赖检测：支持 ubuntu-drivers / PPA / 系统依赖 / 多发行版"""

# ── 系统类型检测 ──────────────────────────────────────────
def detect_os(ssh) -> str:
    """检测远程系统类型，返回 'ubuntu' / 'rhel' / 'unknown'"""
    ec, out, _ = ssh.exec("cat /etc/os-release 2>/dev/null | head -5", timeout=5)
    if 'ubuntu' in out.lower() or 'debian' in out.lower():
        return 'ubuntu'
    if 'rhel' in out.lower() or 'centos' in out.lower() or 'rocky' in out.lower() or 'tencentos' in out.lower():
        return 'rhel'
    ec2, out2, _ = ssh.exec("which apt 2>/dev/null && echo apt-found", timeout=5)
    if 'apt-found' in out2:
        return 'ubuntu'
    ec3, out3, _ = ssh.exec("which dnf 2>/dev/null && echo dnf-found || (which yum 2>/dev/null && echo yum-found)", timeout=5)
    if 'dnf-found' in out3 or 'yum-found' in out3:
        return 'rhel'
    return 'unknown'


def pm(ssh) -> str:
    """返回包管理器命令前缀"""
    os_type = detect_os(ssh)
    if os_type == 'rhel':
        ec, out, _ = ssh.exec("which dnf 2>/dev/null && echo dnf", timeout=5)
        return 'dnf' if 'dnf' in out else 'yum'
    return 'apt'


# ── 驱动安装前置依赖检查项 ──────────────────────────────────
DRIVER_DEPENDENCIES = {
    "gcc": {
        "label": "GCC 编译器",
        "check": "gcc --version 2>/dev/null | head -1",
        "ok_match": r"gcc",
        "install_cmd": "apt install -y gcc g++",
        "install_cmd_rhel": "dnf install -y gcc gcc-c++ make",
    },
    "make": {
        "label": "make 工具",
        "check": "make --version 2>/dev/null | head -1",
        "ok_match": r"GNU Make",
        "install_cmd": "apt install -y make",
        "install_cmd_rhel": "dnf install -y make",
    },
    "kernel_headers": {
        "label": "内核头文件",
        "check": "dpkg -l 2>/dev/null | grep -q linux-headers-$(uname -r) && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y linux-headers-$(uname -r)",
        "install_cmd_rhel": "dnf install -y kernel-devel-$(uname -r) kernel-headers-$(uname -r)",
        "check_rhel": "rpm -q kernel-devel-$(uname -r) 2>/dev/null | grep -q kernel-devel && echo installed",
    },
    "build_essential": {
        "label": "基础编译工具",
        "check": "dpkg -l 2>/dev/null | grep -q build-essential && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y build-essential",
        "install_cmd_rhel": "dnf groupinstall -y 'Development Tools'",
        "check_rhel": "rpm -q gcc make 2>/dev/null | wc -l | grep -q 2 && echo installed",
    },
    "dkms": {
        "label": "DKMS",
        "check": "dkms --version 2>/dev/null | head -1",
        "ok_match": r"dkms",
        "install_cmd": "apt install -y dkms",
        "install_cmd_rhel": "dnf install -y dkms",
    },
    "secureboot": {
        "label": "Secure Boot 状态",
        "check": "mokutil --sb-state 2>/dev/null",
        "ok_match": r"disabled|does not support|not enabled",
        "install_cmd": None,
        "install_cmd_rhel": None,
    },
    "epel": {
        "label": "EPEL 源（RHEL 系）",
        "check": "rpm -q epel-release 2>/dev/null | grep -q epel-release && echo installed",
        "ok_match": r"installed",
        "install_cmd": "true",  # apt 系不需要
        "install_cmd_rhel": "dnf install -y epel-release",
    },
}

# ── CUDA 前置依赖 ──────────────────────────────────────────
CUDA_DEPENDENCIES = {
    "freeglut3": {
        "label": "freeglut3-dev",
        "check": "dpkg -l 2>/dev/null | grep -q freeglut3-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y freeglut3-dev",
        "install_cmd_rhel": "dnf install -y freeglut-devel",
        "check_rhel": "rpm -q freeglut-devel 2>/dev/null | grep -q freeglut && echo installed",
    },
    "libx11": {
        "label": "libx11-dev",
        "check": "dpkg -l 2>/dev/null | grep -q libx11-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y libx11-dev",
        "install_cmd_rhel": "dnf install -y libX11-devel",
        "check_rhel": "rpm -q libX11-devel 2>/dev/null | grep -q libX11 && echo installed",
    },
    "libxmu": {
        "label": "libxmu-dev",
        "check": "dpkg -l 2>/dev/null | grep -q libxmu-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y libxmu-dev",
        "install_cmd_rhel": "dnf install -y libXmu-devel",
        "check_rhel": "rpm -q libXmu-devel 2>/dev/null | grep -q libXmu && echo installed",
    },
    "libxi": {
        "label": "libxi-dev",
        "check": "dpkg -l 2>/dev/null | grep -q libxi-dev && echo installed",
        "ok_match": r"installed",
        "install_cmd": "apt install -y libxi-dev",
        "install_cmd_rhel": "dnf install -y libXi-devel",
        "check_rhel": "rpm -q libXi-devel 2>/dev/null | grep -q libXi && echo installed",
    },
}


def get_install_cmd(dep_def: dict, os_type: str) -> str | None:
    """根据系统类型返回安装命令"""
    if os_type == 'rhel':
        return dep_def.get('install_cmd_rhel') or dep_def.get('install_cmd')
    return dep_def.get('install_cmd')


def get_check_cmd(dep_def: dict, os_type: str) -> str:
    """根据系统类型返回检查命令"""
    if os_type == 'rhel':
        return dep_def.get('check_rhel', dep_def['check'])
    return dep_def['check']


def check_dependency(ssh, dep_def: dict, os_type: str = 'ubuntu') -> tuple[bool, str]:
    """执行单条依赖检查，返回 (通过?, 详情)"""
    check_cmd = get_check_cmd(dep_def, os_type)
    ec, out, err = ssh.exec(check_cmd, timeout=10)
    import re
    if re.search(dep_def["ok_match"], out, re.IGNORECASE):
        detail = out.strip().split("\n")[0][:80] if out.strip() else "已安装"
        return True, detail
    return False, err.strip() or "未安装"


def check_all_deps(ssh, dep_dict: dict, os_type: str = 'ubuntu') -> dict[str, tuple[bool, str]]:
    """批量检查依赖，返回 {key: (ok, detail)}"""
    results = {}
    for key, dep_def in dep_dict.items():
        ok, detail = check_dependency(ssh, dep_def, os_type)
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
