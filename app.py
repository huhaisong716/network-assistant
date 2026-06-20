#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网工助手 - tkinter原生桌面版"""
import os, sys, json, uuid, time, threading, base64, io, urllib.request, subprocess
from datetime import datetime

os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.local/bin")

try: import tkinter as tk
except: os.system("python3 -m pip install tkinter --quiet 2>/dev/null"); import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import paramiko

# ====== 配置 ======
DEVICES_FILE = os.path.expanduser("~/dev-output/开发工具/devices.json")
CONFIG_FILE = os.path.expanduser("~/dev-output/开发工具/config.json")
os.makedirs(os.path.dirname(DEVICES_FILE), exist_ok=True)

def load_json(p, d=None):
    try:
        with open(p) as f: return json.load(f)
    except: return d or {}

def save_json(p, data):
    with open(p, 'w') as f: json.dump(data, f, indent=2, ensure_ascii=False)

# ====== 主应用 ======
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("网工助手 v1.0")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 650)
        # 图标
        try: self.root.iconbitmap(default="")
        except: pass
        
        self.conn = {}  # device_id -> SSHClient
        self.devices = {}
        self.cfg = load_json(CONFIG_FILE, {"url": "https://api.deepseek.com/v1", "key": "", "model": "deepseek-chat"})
        
        self._build_ui()
        self._load_devices()
        self.root.mainloop()
    
    # ====== UI 构建 ======
    def _build_ui(self):
        # 标题
        header = tk.Frame(self.root, bg="#1565C0", height=45)
        header.pack(fill=tk.X)
        tk.Label(header, text="🔧 网工助手 v1.0", fg="white", bg="#1565C0",
                 font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT, padx=15, pady=8)
        tk.Label(header, text="离线版", fg="#FFC107", bg="#1565C0",
                 font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=2)
        
        # 标签页
        self.tab = ttk.Notebook(self.root)
        self.tab.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._build_term_tab()
        self._build_device_tab()
        self._build_ai_tab()
        self._build_patrol_tab()
        self._build_config_tab()
    
    # ====== 终端页 ======
    def _build_term_tab(self):
        f = ttk.Frame(self.tab)
        self.tab.add(f, text="🖥️ 终端")
        
        top = tk.Frame(f); top.pack(fill=tk.X, pady=5)
        tk.Label(top, text="设备:").pack(side=tk.LEFT)
        self.term_dev_cb = ttk.Combobox(top, width=30, state="readonly")
        self.term_dev_cb.pack(side=tk.LEFT, padx=5)
        tk.Button(top, text="🔗 连接", command=self.term_connect).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="断开", command=self.term_disconnect).pack(side=tk.LEFT, padx=2)
        self.term_status = tk.Label(top, text="未连接", fg="gray")
        self.term_status.pack(side=tk.LEFT, padx=10)
        
        # 终端
        self.term_out = scrolledtext.ScrolledText(f, bg="#1a1a2e", fg="#00ff9d",
            font=("Consolas", 11), insertbackground="white", wrap=tk.WORD)
        self.term_out.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.term_out.insert(tk.END, "请先连接设备...\n")
        
        # 命令输入
        bot = tk.Frame(f); bot.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(bot, text="$", font=("Consolas", 14)).pack(side=tk.LEFT)
        self.term_cmd = tk.Entry(bot, font=("Consolas", 12))
        self.term_cmd.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.term_cmd.bind("<Return>", lambda e: self.term_exec())
        tk.Button(bot, text="执行", command=self.term_exec).pack(side=tk.RIGHT)
    
    def term_connect(self):
        did = self.term_dev_cb.get().split("(")[-1].rstrip(")")
        if not did: return
        devs = load_json(DEVICES_FILE, {})
        dev = devs.get(did)
        if not dev: return
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(dev["ip"], int(dev.get("port",22)), dev["user"], dev.get("pass",""), timeout=10)
            self.conn[did] = c
            self.term_status.config(text="已连接", fg="green")
            self.term_out.insert(tk.END, f"✅ 已连接 {dev['name']} ({dev['ip']})\n")
        except Exception as e:
            messagebox.showerror("连接失败", str(e))
    
    def term_disconnect(self):
        did = self.term_dev_cb.get().split("(")[-1].rstrip(")")
        if did and did in self.conn:
            try: self.conn[did].close()
            except: pass
            del self.conn[did]
        self.term_status.config(text="已断开", fg="gray")
    
    def term_exec(self):
        did = self.term_dev_cb.get().split("(")[-1].rstrip(")")
        cmd = self.term_cmd.get()
        if not cmd: return
        self.term_out.insert(tk.END, f"\n$ {cmd}\n")
        self.term_cmd.delete(0, tk.END)
        
        c = self.conn.get(did)
        if not c:
            self.term_out.insert(tk.END, "⛔ 未连接设备\n")
            return
        
        def run():
            try:
                _, o, e = c.exec_command(cmd, timeout=30)
                out = o.read().decode() + e.read().decode()
                self.term_out.insert(tk.END, out)
            except Exception as ex:
                self.term_out.insert(tk.END, f"[错误] {ex}\n")
        
        threading.Thread(target=run, daemon=True).start()
    
    # ====== 设备管理 ======
    def _build_device_tab(self):
        f = ttk.Frame(self.tab)
        self.tab.add(f, text="📋 设备")
        
        # 工具栏
        top = tk.Frame(f); top.pack(fill=tk.X, pady=5)
        tk.Button(top, text="➕ 添加", command=self.dev_add).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="刷新", command=self._load_devices).pack(side=tk.LEFT, padx=2)
        
        # 设备列表
        cols = ("名称", "IP", "端口", "厂商")
        self.dev_tree = ttk.Treeview(f, columns=cols, show="headings", height=15)
        for c in cols:
            self.dev_tree.heading(c, text=c)
            self.dev_tree.column(c, width=150)
        self.dev_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.dev_tree.bind("<Double-1>", lambda e: self.dev_edit())
        
        # 右键菜单
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="编辑", command=self.dev_edit)
        menu.add_command(label="删除", command=self.dev_del)
        self.dev_tree.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))
    
    def _load_devices(self):
        self.devices = load_json(DEVICES_FILE, {})
        self.dev_tree.delete(*self.dev_tree.get_children())
        # 更新下拉
        devs = load_json(DEVICES_FILE, {})
        items = [f"{d['name']} ({did})" for did, d in devs.items()]
        for cb in [self.term_dev_cb, self.pt_dev_cb]:
            cb["values"] = items
            if items: cb.current(0)
        for did, d in devs.items():
            self.dev_tree.insert("", tk.END, values=(d.get("name",""), d.get("ip",""), d.get("port","22"), d.get("vendor","")), iid=did)
    
    def dev_add(self):
        w = tk.Toplevel(self.root); w.title("添加设备"); w.geometry("350x280")
        tk.Label(w, text="设备名称").pack(); e1 = tk.Entry(w); e1.pack(fill=tk.X, padx=20)
        tk.Label(w, text="IP地址").pack(); e2 = tk.Entry(w); e2.pack(fill=tk.X, padx=20)
        tk.Label(w, text="端口").pack(); e3 = tk.Entry(w); e3.insert(0,"22"); e3.pack(fill=tk.X, padx=20)
        tk.Label(w, text="用户名").pack(); e4 = tk.Entry(w); e4.insert(0,"admin"); e4.pack(fill=tk.X, padx=20)
        tk.Label(w, text="密码").pack(); e5 = tk.Entry(w, show="*"); e5.pack(fill=tk.X, padx=20)
        def save():
            did = uuid.uuid4().hex[:8]
            devs = load_json(DEVICES_FILE, {})
            devs[did] = {"name":e1.get(),"ip":e2.get(),"port":e3.get(),"user":e4.get(),"pass":e5.get(),"vendor":"华为"}
            save_json(DEVICES_FILE, devs)
            w.destroy(); self._load_devices()
        tk.Button(w, text="保存", command=save).pack(pady=10)
    
    def dev_edit(self):
        sel = self.dev_tree.selection()
        if not sel: return
        did = sel[0]; d = self.devices.get(did, {})
        w = tk.Toplevel(self.root); w.title("编辑"); w.geometry("350x280")
        tk.Label(w, text="设备名称").pack(); e1 = tk.Entry(w); e1.insert(0,d.get("name","")); e1.pack(fill=tk.X, padx=20)
        tk.Label(w, text="IP地址").pack(); e2 = tk.Entry(w); e2.insert(0,d.get("ip","")); e2.pack(fill=tk.X, padx=20)
        tk.Label(w, text="端口").pack(); e3 = tk.Entry(w); e3.insert(0,d.get("port","22")); e3.pack(fill=tk.X, padx=20)
        tk.Label(w, text="用户名").pack(); e4 = tk.Entry(w); e4.insert(0,d.get("user","")); e4.pack(fill=tk.X, padx=20)
        tk.Label(w, text="密码").pack(); e5 = tk.Entry(w, show="*"); e5.insert(0,d.get("pass","")); e5.pack(fill=tk.X, padx=20)
        def save():
            devs = load_json(DEVICES_FILE, {})
            devs[did] = {"name":e1.get(),"ip":e2.get(),"port":e3.get(),"user":e4.get(),"pass":e5.get(),"vendor":"华为"}
            save_json(DEVICES_FILE, devs)
            w.destroy(); self._load_devices()
        tk.Button(w, text="保存", command=save).pack(pady=10)
    
    def dev_del(self):
        sel = self.dev_tree.selection()
        if not sel: return
        if messagebox.askyesno("确认", "删除此设备？"):
            devs = load_json(DEVICES_FILE, {})
            devs.pop(sel[0], None)
            self.conn.pop(sel[0], None)
            save_json(DEVICES_FILE, devs)
            self._load_devices()
    
    # ====== AI助手 ======
    def _build_ai_tab(self):
        f = ttk.Frame(self.tab)
        self.tab.add(f, text="🤖 AI助手")
        
        tk.Label(f, text="输入配置需求（人话→命令）:").pack(anchor=tk.W, padx=10, pady=5)
        self.ai_input = scrolledtext.ScrolledText(f, height=6, font=("Microsoft YaHei", 10))
        self.ai_input.pack(fill=tk.X, padx=10)
        self.ai_input.insert(tk.END, "示例：配置VLAN 10 名称为 Office\n示例：端口 G0/0/1 设为 Trunk 允许 VLAN 10,20,30")
        
        tk.Button(f, text="🚀 AI生成命令", command=self.ai_gen).pack(pady=5)
        
        self.ai_out = scrolledtext.ScrolledText(f, bg="#f3e5f5", font=("Consolas", 11))
        self.ai_out.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.ai_out.insert(tk.END, "AI生成的命令显示在这里...")
    
    def ai_gen(self):
        prompt = self.ai_input.get(1.0, tk.END).strip()
        if not prompt: return
        self.ai_out.delete(1.0, tk.END); self.ai_out.insert(tk.END, "AI思考中...\n")
        cfg = load_json(CONFIG_FILE, self.cfg)
        
        def run():
            r = self._call_ai("你是网络设备配置专家，精通华为/H3C/锐捷/Cisco命令。", prompt, cfg)
            self.ai_out.delete(1.0, tk.END); self.ai_out.insert(tk.END, r)
        
        threading.Thread(target=run, daemon=True).start()
    
    def _call_ai(self, system, prompt, cfg):
        if not cfg.get("key"): return "⛔ 请先在「设置」配置 API Key"
        body = json.dumps({
            "model": cfg.get("model","deepseek-chat"),
            "messages": [{"role":"system","content":system},{"role":"user","content":prompt}],
            "temperature":0.3,"max_tokens":4096
        }).encode()
        url = cfg["url"].rstrip("/") + "/chat/completions"
        req = urllib.request.Request(url, data=body,
            headers={"Content-Type":"application/json","Authorization":"Bearer "+cfg["key"]})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
            return r["choices"][0]["message"]["content"]
        except Exception as e: return f"[错误] {e}"
    
    # ====== 巡检/诊断 ======
    def _build_patrol_tab(self):
        f = ttk.Frame(self.tab)
        self.tab.add(f, text="🔍 巡检")
        
        top = tk.Frame(f); top.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(top, text="设备:").pack(side=tk.LEFT)
        self.pt_dev_cb = ttk.Combobox(top, width=25, state="readonly")
        self.pt_dev_cb.pack(side=tk.LEFT, padx=5)
        
        n = ttk.Notebook(f); n.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 巡检
        p1 = ttk.Frame(n); n.add(p1, text="设备巡检")
        tk.Button(p1, text="开始巡检", command=self.patrol_run).pack(pady=5)
        self.pt_out = scrolledtext.ScrolledText(p1, font=("Consolas", 10))
        self.pt_out.pack(fill=tk.BOTH, expand=True)
        
        # 日志
        p2 = ttk.Frame(n); n.add(p2, text="日志分析")
        tk.Button(p2, text="获取日志并AI分析", command=self.log_run).pack(pady=5)
        self.lg_out = scrolledtext.ScrolledText(p2, font=("Consolas", 10))
        self.lg_out.pack(fill=tk.BOTH, expand=True)
        
        # 故障诊断
        p3 = ttk.Frame(n); n.add(p3, text="故障诊断")
        tk.Label(p3, text="描述故障现象:").pack(anchor=tk.W)
        self.dg_input = scrolledtext.ScrolledText(p3, height=4, font=("Microsoft YaHei", 10))
        self.dg_input.pack(fill=tk.X)
        tk.Button(p3, text="开始诊断", command=self.diag_run).pack(pady=5)
        self.dg_out = scrolledtext.ScrolledText(p3, bg="#fff3e0", font=("Consolas", 10))
        self.dg_out.pack(fill=tk.BOTH, expand=True)
    
    def patrol_run(self):
        txt = self.pt_dev_cb.get()
        did = txt.split("(")[-1].rstrip(")") if "(" in txt else ""
        if not did: return
        devs = load_json(DEVICES_FILE, {})
        dev = devs.get(did)
        if not dev: return
        cfg = load_json(CONFIG_FILE, self.cfg)
        
        cmds = [("系统版本","display version"),("设备状态","display device"),
                ("接口摘要","display interface brief"),("电源","display power"),
                ("CPU","display cpu-usage"),("内存","display memory")]
        
        def run():
            self.pt_out.delete(1.0, tk.END)
            try:
                c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(dev["ip"], int(dev.get("port",22)), dev["user"], dev.get("pass",""), timeout=10)
                data = ""
                for label, cmd in cmds:
                    _, o, e = c.exec_command(cmd, timeout=20)
                    data += f"【{label}】\n{o.read().decode()}\n"
                c.close()
                self.pt_out.insert(tk.END, data)
                ai = self._call_ai("你是网络巡检专家，分析数据给出评估。", data[:6000], cfg)
                self.pt_out.insert(tk.END, f"\n🧠 AI分析:\n{ai}")
            except Exception as ex:
                self.pt_out.insert(tk.END, f"[错误] {ex}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def log_run(self):
        txt = self.pt_dev_cb.get()
        did = txt.split("(")[-1].rstrip(")") if "(" in txt else ""
        devs = load_json(DEVICES_FILE, {}); dev = devs.get(did)
        if not dev: return
        cfg = load_json(CONFIG_FILE, self.cfg)
        def run():
            self.lg_out.delete(1.0, tk.END); self.lg_out.insert(tk.END, "获取日志...\n")
            try:
                c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(dev["ip"], int(dev.get("port",22)), dev["user"], dev.get("pass",""), timeout=10)
                _, o, _ = c.exec_command("display logbuffer | tail -50", timeout=20)
                logs = o.read().decode(); c.close()
                self.lg_out.insert(tk.END, logs)
                ai = self._call_ai("你是设备日志分析专家。分析日志中的错误和异常。", logs, cfg)
                self.lg_out.insert(tk.END, f"\n🧠 AI分析:\n{ai}")
            except Exception as ex: self.lg_out.insert(tk.END, f"[错误] {ex}")
        threading.Thread(target=run, daemon=True).start()
    
    def diag_run(self):
        prompt = self.dg_input.get(1.0, tk.END).strip()
        if not prompt: return
        cfg = load_json(CONFIG_FILE, self.cfg)
        self.dg_out.delete(1.0, tk.END); self.dg_out.insert(tk.END, "诊断中...\n")
        def run():
            r = self._call_ai("你是网络故障诊断专家，分析原因，给出诊断步骤和建议命令。", prompt, cfg)
            self.dg_out.delete(1.0, tk.END); self.dg_out.insert(tk.END, r)
        threading.Thread(target=run, daemon=True).start()
    
    # ====== 设置 ======
    def _build_config_tab(self):
        f = ttk.Frame(self.tab)
        self.tab.add(f, text="⚙️ 设置")
        
        tk.Label(f, text="API地址:").pack(anchor=tk.W, padx=20, pady=5)
        self.cfg_url = tk.Entry(f, width=60)
        self.cfg_url.insert(0, self.cfg.get("url","https://api.deepseek.com/v1"))
        self.cfg_url.pack(fill=tk.X, padx=20)
        
        tk.Label(f, text="API Key:").pack(anchor=tk.W, padx=20, pady=5)
        self.cfg_key = tk.Entry(f, width=60, show="*")
        if self.cfg.get("key"): self.cfg_key.insert(0, self.cfg["key"][:8]+"***")
        self.cfg_key.pack(fill=tk.X, padx=20)
        
        tk.Label(f, text="模型名称:").pack(anchor=tk.W, padx=20, pady=5)
        self.cfg_model = ttk.Combobox(f, values=["deepseek-chat","gpt-3.5-turbo","moonshot-v1-8k","qwen-plus"])
        self.cfg_model.insert(0, self.cfg.get("model","deepseek-chat"))
        self.cfg_model.pack(fill=tk.X, padx=20)
        
        tk.Button(f, text="💾 保存", command=self.cfg_save).pack(pady=10)
        tk.Button(f, text="🔌 测试连接", command=self.cfg_test).pack(pady=5)
        self.cfg_info = tk.Label(f, text="", fg="green")
        self.cfg_info.pack()
    
    def cfg_save(self):
        key = self.cfg_key.get()
        if "***" in key: key = self.cfg.get("key", "")
        self.cfg = {"url": self.cfg_url.get(), "key": key, "model": self.cfg_model.get()}
        save_json(CONFIG_FILE, self.cfg)
        messagebox.showinfo("成功", "已保存")
    
    def cfg_test(self):
        def run():
            cfg = {"url": self.cfg_url.get(), "key": self.cfg_key.get(), "model": self.cfg_model.get()}
            if "***" in cfg["key"]: cfg["key"] = self.cfg.get("key", "")
            r = self._call_ai("你是一个测试助手，回复'连接成功'", "测试", cfg)
            ok = "成功" in r
            self.cfg_info.config(text="✅ "+r if ok else "❌ "+r, fg="green" if ok else "red")
        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    # 首次使用提示
    if not os.path.exists(CONFIG_FILE) or not load_json(CONFIG_FILE, {}).get("key"):
        print("首次使用请先在「设置」配置 API Key")
    App()
