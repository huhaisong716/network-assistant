#!/usr/bin/env python3
import subprocess, os

# Read token
with open("/tmp/gh_token") as f:
    token = f.read().strip()

# Download artifact
url = "https://api.github.com/repos/huhaisong716/network-assistant/actions/artifacts/7781228848/zip"
cmd = ["curl", "-sL", "-H", f"Authorization: Bearer {token}", url, "-o", "/tmp/nvidia-v3.zip"]
subprocess.run(cmd, check=True)

size = os.path.getsize("/tmp/nvidia-v3.zip")
print(f"Downloaded: {size} bytes")
