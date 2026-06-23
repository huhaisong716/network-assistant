#!/usr/bin/env python3
"""Test GitHub token and download artifact"""
import urllib.request
import json
import os
import zipfile
import io
import shutil

with open("/tmp/gh_token") as f:
    token = f.read().strip()

print(f"Token length: {len(token)}")

# Test token
req = urllib.request.Request("https://api.github.com/user")
req.add_header("Authorization", f"token {token}")
resp = urllib.request.urlopen(req)
user = json.loads(resp.read())
print(f"User: {user.get('login')}")

# Get latest run
REPO = "https://api.github.com/repos/huhaisong716/network-assistant"
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",
}

req = urllib.request.Request(f"{REPO}/actions/runs?per_page=1&event=push&status=success", headers=headers)
resp = urllib.request.urlopen(req)
runs = json.loads(resp.read())
run = runs["workflow_runs"][0]
print(f"Run #{run['run_number']} - {run['head_sha'][:7]}")

# Get artifact
req = urllib.request.Request(f"{REPO}/actions/runs/{run['id']}/artifacts", headers=headers)
resp = urllib.request.urlopen(req)
artifacts = json.loads(resp.read())
artifact = artifacts["artifacts"][0]
print(f"Artifact: {artifact['name']} (id={artifact['id']})")

# Download
req = urllib.request.Request(artifact["archive_download_url"], headers=headers)
resp = urllib.request.urlopen(req)
zip_data = resp.read()
print(f"Downloaded: {len(zip_data)} bytes")

with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
    for info in zf.infolist():
        if info.filename.endswith(".exe"):
            zf.extract(info, "/tmp/")
            shutil.copy2(f"/tmp/{info.filename}", "/home/dytc/network-assistant/nvidia-tool.exe")
            size = os.path.getsize("/home/dytc/network-assistant/nvidia-tool.exe")
            print(f"OK nvidia-tool.exe ({size} bytes)")
            break
