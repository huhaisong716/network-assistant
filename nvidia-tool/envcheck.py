"""环境检查 - SSH 远程检查并自动修复"""


def check_env(ssh) -> list:
    """运行所有环境检查"""
    results = []
    results.append(_check_gcc(ssh))
    results.append(_check_nouveau(ssh))
    results.append(_check_secure_boot(ssh))
    results.append(_check_kernel_headers(ssh))
    results.append(_check_build_essential(ssh))
    return results


def _check_gcc(ssh) -> dict:
    out, _, code = ssh.exec("gcc --version 2>/dev/null | head -1")
    if code != 0 or not out.strip():
        return {
            "name": "gcc", "status": "fail", "detail": "未安装",
            "fix_cmd": (
                "apt-get update -qq && apt-get install -y gcc-12 build-essential "
                "&& update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 100 "
                "&& update-alternatives --set gcc /usr/bin/gcc-12"
            ),
        }
    return {"name": "gcc", "status": "ok", "detail": f"已安装: {out.strip()}", "fix_cmd": ""}


def _check_nouveau(ssh) -> dict:
    out, _, _ = ssh.exec("lsmod | grep nouveau 2>/dev/null")
    if out.strip():
        return {
            "name": "nouveau", "status": "fail", "detail": "Nouveau 未禁用",
            "fix_cmd": (
                'echo "blacklist nouveau" | sudo tee /etc/modprobe.d/blacklist-nvidia-nouveau.conf > /dev/null '
                '&& echo "options nouveau modeset=0" | sudo tee -a /etc/modprobe.d/blacklist-nvidia-nouveau.conf > /dev/null '
                "&& sudo update-initramfs -u"
            ),
        }
    out, _, _ = ssh.exec("cat /etc/modprobe.d/blacklist-nvidia-nouveau.conf 2>/dev/null")
    if "blacklist nouveau" in out:
        return {"name": "nouveau", "status": "ok", "detail": "已禁用（需重启生效）", "fix_cmd": ""}
    return {"name": "nouveau", "status": "ok", "detail": "未加载", "fix_cmd": ""}


def _check_secure_boot(ssh) -> dict:
    out, _, code = ssh.exec("mokutil --sb-state 2>/dev/null")
    if code != 0 or not out.strip():
        return {"name": "secureboot", "status": "ok", "detail": "无法检测（mokutil 不可用）", "fix_cmd": ""}
    if "enabled" in out.lower():
        return {
            "name": "secureboot", "status": "fail", "detail": "Secure Boot 已启用",
            "fix_cmd": "重启服务器，进入 BIOS → Security → Secure Boot → Disabled",
        }
    return {"name": "secureboot", "status": "ok", "detail": "已关闭", "fix_cmd": ""}


def _check_kernel_headers(ssh) -> dict:
    out, _, code = ssh.exec("uname -r 2>/dev/null")
    if code != 0 or not out.strip():
        return {"name": "kernel_headers", "status": "skip", "detail": "无法获取内核版本", "fix_cmd": ""}
    kernel = out.strip()
    out, _, _ = ssh.exec(f"dpkg -l | grep linux-headers-{kernel} 2>/dev/null")
    if not out.strip():
        return {
            "name": "kernel_headers", "status": "fail",
            "detail": f"未安装 (内核 {kernel})",
            "fix_cmd": f"apt-get update -qq && apt-get install -y linux-headers-{kernel}",
        }
    return {"name": "kernel_headers", "status": "ok", "detail": f"已安装 ({kernel})", "fix_cmd": ""}


def _check_build_essential(ssh) -> dict:
    out, _, code = ssh.exec("dpkg -l build-essential 2>/dev/null | grep '^ii'")
    if code != 0 or not out.strip():
        return {
            "name": "build_essential", "status": "fail", "detail": "未安装",
            "fix_cmd": "apt-get update -qq && apt-get install -y build-essential",
        }
    return {"name": "build_essential", "status": "ok", "detail": "已安装", "fix_cmd": ""}


def fix_env(ssh, result: dict) -> str:
    """执行环境修复命令"""
    cmd = result.get("fix_cmd", "")
    if not cmd:
        return ""
    print(f"\n  修复 {result['name']}...")
    out, err, code = ssh.exec(cmd, timeout=120)
    output = out + err
    if code != 0:
        print(f"  ❌ 修复失败: {output[:200]}")
    else:
        print(f"  ✅ 修复完成")
    return output
