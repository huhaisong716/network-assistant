#!/usr/bin/env python3
"""简易文件上传服务器 - Python标准库实现"""
import os
import sys
import json
import cgi
import io
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

UPLOAD_DIR = "/home/dytc/uploaded-files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>文件上传</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f5f5f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.card { background: white; border-radius: 12px; padding: 40px; box-shadow: 0 2px 20px rgba(0,0,0,0.1); width: 480px; }
h1 { font-size: 22px; color: #005696; margin-bottom: 8px; }
p { color: #666; font-size: 13px; margin-bottom: 24px; }
.upload-area { border: 2px dashed #00B0F0; border-radius: 8px; padding: 40px 20px; text-align: center; cursor: pointer; transition: all 0.3s; background: #f8fbff; }
.upload-area:hover { background: #eef6ff; border-color: #005696; }
.upload-area.dragover { background: #e0f0ff; border-color: #005696; }
.upload-area .icon { font-size: 48px; margin-bottom: 12px; }
.upload-area .text { color: #333; font-size: 15px; }
.upload-area .hint { color: #999; font-size: 12px; margin-top: 8px; }
input[type="file"] { display: none; }
#file-info { margin-top: 16px; padding: 12px; background: #f0f8ff; border-radius: 6px; display: none; font-size: 13px; color: #333; }
#file-info .name { font-weight: bold; }
#file-info .size { color: #666; margin-left: 8px; }
.btn { display: none; margin-top: 16px; width: 100%; padding: 12px; background: #005696; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; }
.btn:hover { background: #003d6b; }
.btn:disabled { background: #ccc; cursor: not-allowed; }
#status { margin-top: 12px; padding: 12px; border-radius: 6px; display: none; font-size: 14px; text-align: center; }
#status.success { background: #e8f5e9; color: #2e7d32; display: block; }
#status.error { background: #ffebee; color: #c62828; display: block; }
.uploaded-list { margin-top: 20px; }
.uploaded-list h3 { font-size: 14px; color: #333; margin-bottom: 8px; }
.uploaded-list .item { padding: 6px 10px; background: #f9f9f9; border-radius: 4px; margin-bottom: 4px; font-size: 12px; color: #666; }
</style>
</head>
<body>
<div class="card">
<h1>📤 上传文件</h1>
<p>把你电脑上的压缩包/源码拖进来</p>
<div class="upload-area" id="dropZone">
<div class="icon">📁</div>
<div class="text">点击选择文件，或拖拽到此处</div>
<div class="hint">支持任意格式，无大小限制</div>
</div>
<input type="file" id="fileInput">
<div id="file-info">
<span class="name" id="fileName"></span>
<span class="size" id="fileSize"></span>
</div>
<button class="btn" id="uploadBtn">⬆ 开始上传</button>
<div id="status"></div>
<div class="uploaded-list" id="fileList">
<h3>已上传的文件</h3>
<div id="listItems"></div>
</div>
</div>
<script>
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('file-info');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const uploadBtn = document.getElementById('uploadBtn');
const status = document.getElementById('status');
let selectedFile = null;

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFiles(e.dataTransfer.files); });
fileInput.addEventListener('change', () => handleFiles(fileInput.files));

function handleFiles(files) {
if (!files.length) return;
selectedFile = files[0];
fileName.textContent = selectedFile.name;
fileSize.textContent = (selectedFile.size / 1024 / 1024).toFixed(2) + ' MB';
fileInfo.style.display = 'block';
uploadBtn.style.display = 'block';
status.style.display = 'none';
}

uploadBtn.addEventListener('click', () => {
if (!selectedFile) return;
uploadBtn.disabled = true;
uploadBtn.textContent = '上传中...';
status.className = '';
status.textContent = '上传中，请稍候...';
status.style.display = 'block';

const formData = new FormData();
formData.append('file', selectedFile);

fetch('/upload', { method: 'POST', body: formData })
.then(r => r.json())
.then(d => {
if (d.ok) {
status.className = 'success';
status.textContent = '✅ 上传成功！' + d.filename;
uploadBtn.style.display = 'none';
fileInfo.style.display = 'none';
loadFileList();
} else {
status.className = 'error';
status.textContent = '❌ 上传失败: ' + (d.error || '未知错误');
}
})
.catch(e => {
status.className = 'error';
status.textContent = '❌ 上传失败: ' + e.message;
})
.finally(() => { uploadBtn.disabled = false; uploadBtn.textContent = '⬆ 开始上传'; selectedFile = null; });
});

function loadFileList() {
fetch('/files').then(r => r.json()).then(d => {
const el = document.getElementById('listItems');
if (!d.files || !d.files.length) { el.innerHTML = '<div class="item">暂无文件</div>'; return; }
el.innerHTML = d.files.map(f =>
'<div class="item">📄 ' + f.name + ' (' + f.size + ') — ' + f.time + '</div>'
).join('');
});
}
loadFileList();
</script>
</body>
</html>"""


class UploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/files":
            files = []
            for f in sorted(os.listdir(UPLOAD_DIR), reverse=True)[:20]:
                fpath = os.path.join(UPLOAD_DIR, f)
                if os.path.isfile(fpath):
                    size = os.path.getsize(fpath)
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
                    files.append({
                        "name": f,
                        "size": f"{size/1024/1024:.1f} MB" if size > 1024*1024 else f"{size/1024:.1f} KB",
                        "time": mtime.strftime("%m-%d %H:%M"),
                    })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"files": files}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/upload":
            self._json({"ok": False, "error": "not found"}, 404)
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._json({"ok": False, "error": "need multipart/form-data"}, 400)
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
            )
            file_item = form["file"]
            if not file_item.filename:
                self._json({"ok": False, "error": "no file selected"})
                return

            # Save with timestamp prefix
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{ts}___{file_item.filename}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            with open(filepath, "wb") as f:
                f.write(file_item.file.read())

            size = os.path.getsize(filepath)
            self._json({"ok": True, "filename": f"{file_item.filename} ({size/1024/1024:.1f} MB)", "path": filepath})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        print(f"[Upload] {args[0]} - {args[1]}", flush=True)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    server = HTTPServer(("0.0.0.0", port), UploadHandler)
    print(f"📤 上传服务已启动: http://0.0.0.0:{port}")
    print(f"📂 文件保存到: {UPLOAD_DIR}")
    print(f"💡 在浏览器中打开 http://你的IP:{port}")
    server.serve_forever()
