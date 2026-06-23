#!/usr/bin/env python3
"""Download OCR tool zip from Feishu"""
import urllib.request
import json
import os
import zipfile

token = "t-g1046mkl3VMEIC7V6XTPYSLAFZCDIRXELVRYIB2R"
file_key = "file_v3_0012t_b614d788-c049-4187-a5c5-6c790c95907g"
msg_id = "om_x100b6ca6fc84d8a0b22e191d0d7ecdc"

headers = {
    "Authorization": f"Bearer {token}",
}

# Try the file info endpoint
url = f"https://open.feishu.cn/open-apis/im/v1/files/{file_key}"
req = urllib.request.Request(url, headers=headers)
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print("File info:", json.dumps(data, indent=2, ensure_ascii=False)[:500])
except Exception as e:
    print(f"File info error: {e}")

# Try download with the full response body
download_url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/resources/{file_key}?type=file"
print(f"\nDownload URL: {download_url}")
req2 = urllib.request.Request(download_url, headers=headers)
try:
    resp2 = urllib.request.urlopen(req2)
    content = resp2.read()
    print(f"Downloaded: {len(content)} bytes")
    save = "/tmp/ocr_tool.zip"
    with open(save, "wb") as f:
        f.write(content)
    # Check if it's a valid zip
    try:
        with zipfile.ZipFile(save) as zf:
            for info in zf.infolist()[:15]:
                print(f"  {info.filename} ({info.file_size})")
            print(f"  Total: {len(zf.infolist())} files")
    except:
        print(f"  Not a valid zip. First bytes: {content[:50].hex()}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"Download error {e.code}: {body[:300]}")
