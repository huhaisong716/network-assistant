#!/bin/bash
# Download latest nvidia-tool artifact from GitHub Actions
cd /home/dytc/network-assistant

# Extract token from git remote
GIT_URL=$(git config --get remote.origin.url)
TOKEN=$(echo "$GIT_URL" | sed 's|https://[^:]*:\(.*\)@github.com.*|\1|')

# Get latest successful run for commit 604ba79
RUN_ID=$(curl -sL "https://api.github.com/repos/huhaisong716/network-assistant/actions/runs?per_page=1&event=push&status=success" | python3 -c "import sys,json; print(json.load(sys.stdin)['workflow_runs'][0]['id'])")

# Get artifact ID
ARTIFACT_ID=$(curl -sL -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/huhaisong716/network-assistant/actions/runs/$RUN_ID/artifacts" | python3 -c "import sys,json; print(json.load(sys.stdin)['artifacts'][0]['id'])")

# Download
curl -sL -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/huhaisong716/network-assistant/actions/artifacts/$ARTIFACT_ID/zip" -o /tmp/nvidia-tool-v2.zip

# Extract
cd /tmp && unzip -o nvidia-tool-v2.zip
ls -lh nvidia-tool.exe
file nvidia-tool.exe
