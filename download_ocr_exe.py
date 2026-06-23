#!/usr/bin/env python3
import urllib.request, json, io, zipfile, shutil, os

with open("/tmp/gh_token") as f:
    token = f.read().strip()

headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",
}

REPO = "https://api.github.com/repos/huhaisong716/network-assistant"

# Get the OCR tool build run (workflow_id for build-ocr.yml)
runs_req = urllib.request.Request(f"{REPO}/actions/runs?per_page=1&event=push&status=success", headers=headers)
runs = json.loads(urllib.request.urlopen(runs_req).read())
run = runs["workflow_runs"][0]
print(f"Latest successful run: #{run['run_number']} {run['name']}")

# Get artifact
art_req = urllib.request.Request(f"{REPO}/actions/runs/{run['id']}/artifacts", headers=headers)
arts = json.loads(urllib.request.urlopen(art_req).read())
art = arts["artifacts"][0]
print(f"Artifact: {art['name']} (id={art['id']})")

# Download
dl_req = urllib.request.Request(art["archive_download_url"], headers=headers)
resp = urllib.request.urlopen(dl_req)
zip_data = resp.read()
print(f"Downloaded: {len(zip_data)} bytes")

with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
    for info in zf.infolist():
        if info.filename.endswith(".exe"):
            zf.extract(info, "/tmp/")
            src = f"/tmp/{info.filename}"
            dst = "/home/dytc/network-assistant/OCRDataExtractor.exe"
            shutil.copy2(src, dst)
            size = os.path.getsize(dst)
            print(f"OK OCRDataExtractor.exe ({size} bytes)")
            break
