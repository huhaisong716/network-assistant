#!/bin/bash
TOKEN=*** /tmp/gh_token)
URL="https://api.github.com/repos/huhaisong716/network-assistant/actions/artifacts/7781228848/zip"
curl -sL -H "Authorization: Bearer *** "$URL" -o /tmp/nvidia-v3.zip
ls -la /tmp/nvidia-v3.zip