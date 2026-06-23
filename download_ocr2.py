#!/usr/bin/env python3
"""Download OCR tool zip from Feishu - chunked approach"""
import urllib.request
import json

token = "t-g1046mkl3VMEIC7V6XTPYSLAFZCDIRXELVRYIB2R"
file_key = "file_v3_0012t_b614d788-c049-4187-a5c5-6c790c95907g"
msg_id = "om_x100b6ca6fc84d8a0b22e191d0d7ecdc"

url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/resources/{file_key}?type=file"
headers = {"Authorization": f"Bearer {token}"}

# Try to get size first
req = urllib.request.Request(url, headers={**headers, "Range": "bytes=0-0"})
try:
    resp = urllib.request.urlopen(req)
    print(f"Status: {resp.status}")
    print(f"Headers: {dict(resp.headers)}")
    cr = resp.headers.get("Content-Range", "none")
    cl = resp.headers.get("Content-Length", "none")
    print(f"Content-Range: {cr}")
    print(f"Content-Length: {cl}")
except urllib.error.HTTPError as e:
    print(f"Range header error {e.code}: {e.read().decode()[:200]}")
    # Try wget with curl approach
    print("\nTrying curl with range...")

import subprocess
# Try with curl -r range
cmd = [
    "curl", "-s", "-r", "0-0", "-I",
    "-H", f"Authorization: Bearer ***
    url
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
print(f"curl result: {result.stdout}")
print(f"curl stderr: {result.stderr}")
