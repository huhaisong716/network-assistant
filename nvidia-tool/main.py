#!/usr/bin/env python3
"""nvidia-tool 入口 - TUI 主菜单"""

import sys
import time
from datetime import datetime

from config import load_config, save_config, Server
from ssh_client import SSHClient
from gpu import detect_gpu
from driver import recommend_drivers, get_driver_url
from envcheck import check_env, fix_env
from installer import disable_nouveau, download_driver, run_installer, verify_installation
from cuda import recommend_cuda, install_cuda
from cudnn import recommend_cudnn, install_cudnn
from ai_diagnose import diagnose, prompt_fix


def banner():
    print()
    print("╔═══════════════════════════════════════╗")
    print("║        NVIDIA 驱动安装助手            ║")
    print("╚═══════════════════════════════════════╝")
    print()


def main():
    cfg = load_config()
    start_time = time.time()

    while True:
        banner()
        print("[1] 选择目标服务器")
        print("[2] 新增服务器")
        print("[3] 配置（API Key 等）")
        print("[4] 管理服务器列表")
        print("[0] 退出")
        print()

        choice = input("选择 > ").strip()

        if choice == "1":
            select_server(cfg, start_time)
        elif choice == "2":
            add_server(cfg)
        elif choice == "3":
            configure_api(cfg)
        elif choice == "4":
            manage_servers(cfg)
        elif choice == "0":
            print("\n感谢使用！")
            sys.exit(0)


def select_server(cfg, start_time):
    if not cfg.servers:
        print("\n⚠️  还没有保存的服务器，请先新增")
        input("按 Enter 返回...")
        return

    print("\n已保存服务器：")
    for i, s in enumerate(cfg.servers, 1):
        port_info = f":{s.port}" if s.port and s.port != 22 else ""
        print(f"  [{i}] {s.host}{port_info} ({s.user}@{s.name})")
    print("  [0] 返回上一级")
    print()

    try:
        choice = int(input("选择服务器 > ").strip())
    except ValueError:
        return
    if choice <= 0 or choice > len(cfg.servers):
        return

    server = cfg.servers[choice - 1]
    handle_workflow(cfg, server, start_time)


def add_server(cfg):
    print("\n--- 新增服务器 ---")
    s = Server()
    s.name = input("服务器名称（别名）: ").strip()
    s.host = input("IP 地址: ").strip()
    port_str = input("SSH 端口（默认 22）: ").strip()
    s.port = int(port_str) if port_str else 22
    user_str = input("用户名（默认 root）: ").strip()
    s.user = user_str if user_str else "root"
    key_str = input("SSH 私钥路径（默认 ~/.ssh/id_rsa）: ").strip()
    s.key_path = key_str if key_str else "~/.ssh/id_rsa"

    cfg.servers.append(s)
    save_config(cfg)
    print("✅ 服务器已保存")


def manage_servers(cfg):
    if not cfg.servers:
        print("\n暂无服务器")
        input("按 Enter 返回...")
        return

    print("\n--- 管理服务器 ---")
    for i, s in enumerate(cfg.servers, 1):
        print(f"  [{i}] {s.name} ({s.user}@{s.host}:{s.port})")
    print("\n输入序号删除服务器（0 返回）:")
    try:
        idx = int(input().strip())
    except ValueError:
        return
    if 0 < idx <= len(cfg.servers):
        cfg.servers.pop(idx - 1)
        save_config(cfg)
        print("✅ 已删除")


def configure_api(cfg):
    print("\n--- 配置 ---")
    if cfg.api_key:
        print(f"当前 API Key: {cfg.api_key[:8]}...{cfg.api_key[-4:]}")
    else:
        print("当前 API Key: 未配置")
    key = input("输入新的 DeepSeek API Key（留空跳过）: ").strip()
    if key:
        cfg.api_key = key
        save_config(cfg)
        print("✅ API Key 已保存")


def handle_workflow(cfg, server, start_time):
    print(f"\n🔗 正在连接 {server.user}@{server.host}:{server.port}...")

    ssh = SSHClient(server.host, server.port, server.user, server.key_path)
    err = ssh.connect()
    if err:
        print(f"❌ 连接失败: {err}")
        input("按 Enter 返回...")
        return
    print("✅ SSH 连接成功\n")

    try:
        # Step 1: 检测显卡
        print("🔍 检测显卡...")
        gpu = detect_gpu(ssh)
        model_str = f"  → {gpu['model']}"
        if gpu["has_driver"]:
            model_str += f" (已安装驱动: {gpu['driver_version']}"
            if gpu["cuda_version"]:
                model_str += f", CUDA: {gpu['cuda_version']}"
            model_str += ")"
        else:
            model_str += " (未安装驱动)"
        print(model_str)

        # 如果已安装驱动，跳到 CUDA/cuDNN
        if gpu["has_driver"]:
            print("\n✅ 驱动已安装，跳过安装步骤")
            install_cuda_prompt(gpu, ssh)
            install_cudnn_prompt(gpu, ssh)
            report(ssh, gpu, start_time)
            return

        # Step 2: 选择驱动版本
        drivers = recommend_drivers(gpu["model"])
        print("\n📦 可用驱动版本：")
        for i, d in enumerate(drivers, 1):
            labels = {"stable": "推荐 - 最新稳定版", "lts": "LTS 分支", "legacy": "旧版"}
            label = labels.get(d["branch"], d["branch"])
            if d.get("notes"):
                label += f" - {d['notes']}"
            print(f"  [{i}] {d['version']} ({label})")
        print("  [0] 手动输入版本号")

        try:
            dc = int(input("\n选择 > ").strip())
        except ValueError:
            dc = 0

        if dc <= 0 or dc > len(drivers):
            ver = input("输入驱动版本号（如 570.133.00）: ").strip()
            selected = {"version": ver, "url": get_driver_url(ver)}
        else:
            selected = drivers[dc - 1]

        # Step 3: 环境检查
        print("\n┌─ 环境检查 ───────────────────────────┐")
        env_results = check_env(ssh)
        needs_fix = False
        for r in env_results:
            icon = "✓" if r["status"] == "ok" else "✗" if r["status"] == "fail" else "?"
            print(f"│ {icon} {r['name']}: {r['detail']}")
            if r["status"] == "fail":
                needs_fix = True
        print("└───────────────────────────────────────┘")

        if needs_fix:
            ans = input("\n是否自动修复？[Y/n]: ").strip().lower()
            if ans != "n":
                for r in env_results:
                    if r["status"] == "fail":
                        fix_env(ssh, r)

        # Step 4: 确认安装
        ans = input("\n是否继续安装驱动？[Y/n]: ").strip().lower()
        if ans == "n":
            print("安装已取消")
            return

        # Step 5: 安装驱动
        ver = selected["version"]
        url = selected["url"]

        # 下载
        err = download_driver(ssh, ver, url)
        if err:
            print(f"❌ {err}")
            input("按 Enter 返回...")
            return

        # 禁用 nouveau
        disable_nouveau(ssh)

        # 安装
        known, out, err = run_installer(ssh, ver)
        if known:
            print(f"\n  ⚠️ 错误: {known['title']}")
            diag = {"reason": known["title"], "fix": known["fix"], "source": "local"}
            if prompt_fix(diag):
                ssh.exec(known["fix"], timeout=120)
                print("  → 修复完成，重试安装...")
                known2, _, _ = run_installer(ssh, ver)
                if known2:
                    print(f"❌ 重试仍失败: {known2['title']}")
        else:
            # AI 诊断
            combined = out + "\n" + err
            if combined.strip():
                diag = diagnose(cfg.api_key, combined, gpu["model"])
                if prompt_fix(diag):
                    ssh.exec(diag["fix"], timeout=120)

        # 验证
        updated = verify_installation(ssh)
        if updated and updated["has_driver"]:
            gpu = updated

        # Step 6: CUDA/cuDNN
        install_cuda_prompt(gpu, ssh)
        install_cudnn_prompt(gpu, ssh)

        # 报告
        report(ssh, gpu, start_time)

    finally:
        ssh.close()


def install_cuda_prompt(gpu, ssh):
    ans = input("\n安装 CUDA Toolkit？[y/N]: ").strip().lower()
    if ans == "y":
        cuda = recommend_cuda(gpu.get("driver_version", ""))
        print(f"推荐的 CUDA 版本: {cuda['version']}")
        err = install_cuda(ssh, cuda)
        if err:
            print(f"❌ {err}")
            diag = diagnose("", err, gpu.get("model", ""))
            if prompt_fix(diag):
                ssh.exec(diag["fix"], timeout=120)


def install_cudnn_prompt(gpu, ssh):
    ans = input("安装 cuDNN？[y/N]: ").strip().lower()
    if ans == "y":
        cuda_ver = gpu.get("cuda_version", "12")
        cudnn_entry = recommend_cudnn(cuda_ver)
        print(f"推荐的 cuDNN 版本: {cudnn_entry['version']} (CUDA {cudnn_entry['cuda']})")
        err = install_cudnn(ssh, cudnn_entry)
        if err:
            print(f"❌ {err}")


def report(ssh, gpu, start_time):
    elapsed = time.time() - start_time
    from config import get_log_dir
    print(f"\n┌─ 安装报告 ───────────────────────────┐")
    print(f"│ 服务器: {ssh.host}")
    print(f"│ 显卡:   {gpu['model']}")
    if gpu["has_driver"]:
        print(f"│ 驱动:   {gpu['driver_version']} ✅")
    if gpu.get("cuda_version"):
        print(f"│ CUDA:   {gpu['cuda_version']} ✅")
    print(f"│ 耗时:   {int(elapsed // 60)}分{int(elapsed % 60)}秒")
    print(f"│ 日志:   {get_log_dir()}")
    print("└────────────────────────────────────────")
    print()
    input("按 Enter 返回主菜单...")


if __name__ == "__main__":
    main()
