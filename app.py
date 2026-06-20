#!/usr/bin/env python3
"""网工助手 - Flask 后端"""
import os, json, uuid, time, threading
from pathlib import Path
import paramiko
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
BASE = Path(__file__).parent

DEVICES_FILE = BASE / "devices.json"
CONFIG_FILE = BASE / "config.json"
_conns = {}

def load_json(p, d=None):
    try: return json.loads(open(p).read()) if p.exists() else (d or {})
    except: return d or {}

def save_json(p, d):
    open(p, 'w').write(json.dumps(d, indent=2, ensure_ascii=False))

@app.route('/')
def index():
    return render_template_string(open(BASE/'templates/index.html').read())

@app.route('/api/devices', methods=['GET','POST'])
def api_devices():
    devs = load_json(DEVICES_FILE, {})
    if request.method == 'POST':
        d = request.get_json()
        did = uuid.uuid4().hex[:8]
        d['id'] = did
        devs[did] = d
        save_json(DEVICES_FILE, devs)
        return jsonify({'ok': True, 'id': did})
    return jsonify([{**v, 'Pass': '***'} for v in devs.values()])

@app.route('/api/devices/<did>', methods=['DELETE'])
def api_dev_del(did):
    devs = load_json(DEVICES_FILE, {})
    devs.pop(did, None)
    _conns.pop(did, None)
    save_json(DEVICES_FILE, devs)
    return jsonify({'ok': True})

@app.route('/api/connect/<did>', methods=['POST'])
def api_connect(did):
    devs = load_json(DEVICES_FILE, {})
    d = devs.get(did)
    if not d: return jsonify({'err': '设备不存在'}), 404
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(d['IP'], int(d.get('Port',22)), d['User'], d['Pass'], timeout=10)
        _conns[did] = c
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'err': str(e)}), 500

@app.route('/api/exec/<did>', methods=['POST'])
def api_exec(did):
    c = _conns.get(did)
    if not c: return jsonify({'err': '未连接'}), 400
    cmd = request.get_json().get('cmd','')
    try:
        _, o, e = c.exec_command(cmd, timeout=30)
        return jsonify({'out': o.read().decode() + e.read().decode()})
    except Exception as ex:
        return jsonify({'err': str(ex)}), 500

@app.route('/api/config', methods=['GET','POST'])
def api_config():
    cfg = load_json(CONFIG_FILE, {'url':'https://api.deepseek.com/v1','key':'','model':'deepseek-chat'})
    if request.method == 'POST':
        d = request.get_json()
        for k in ('url','model'): cfg[k] = d.get(k, cfg[k])
        if d.get('key') and '***' not in d['key']: cfg['key'] = d['key']
        save_json(CONFIG_FILE, cfg)
        return jsonify({'ok': True})
    return jsonify({**cfg, 'key': (cfg['key'][:6]+'***') if cfg['key'] else ''})

@app.route('/api/ai', methods=['POST'])
def api_ai():
    cfg = load_json(CONFIG_FILE, {})
    if not cfg.get('key'): return jsonify({'err': '请先配置API Key'})
    import urllib.request
    p = request.get_json().get('prompt','')
    sys_p = '你是网络设备配置专家，精通华为/H3C/锐捷/Cisco。给出准确的配置命令。'
    body = json.dumps({'model': cfg['model'], 'messages': [
        {'role':'system','content':sys_p},{'role':'user','content':p}
    ], 'temperature':0.3, 'max_tokens':4096}).encode()
    req = urllib.request.Request(
        cfg['url'].rstrip('/')+'/chat/completions', data=body,
        headers={'Content-Type':'application/json','Authorization':'Bearer '+cfg['key']})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return jsonify({'out': r['choices'][0]['message']['content']})
    except Exception as e:
        return jsonify({'err': str(e)})

if __name__ == '__main__':
    print('网工助手 → http://localhost:5003')
    app.run(host='0.0.0.0', port=5003, debug=False)
