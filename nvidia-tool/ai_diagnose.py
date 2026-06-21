"""AI 诊断 - DeepSeek API 调用"""

import json
import requests

from errors import find_known_error


def diagnose(api_key: str, error_msg: str, gpu_model: str = "") -> dict:
    """诊断错误，先查本地库，再调 API"""
    # 先查本地
    known = find_known_error(error_msg)
    if known:
        return {"reason": known["title"], "fix": known["fix"], "source": "local"}

    # 无 API key 时返回空
    if not api_key:
        return {"reason": "未知错误", "fix": "请查看日志文件 ~/.nvidia-tool/logs/", "source": "none"}

    # 调 DeepSeek API
    return _call_deepseek(api_key, error_msg, gpu_model)


def _call_deepseek(api_key: str, error_msg: str, gpu_model: str) -> dict:
    """调用 DeepSeek API"""
    prompt = f"""你是一个 Linux NVIDIA 驱动安装专家。以下是在 Ubuntu 上安装 NVIDIA 驱动时遇到的错误信息，请给出：
1. 错误原因（一句话）
2. 修复命令（可直接复制执行）

错误信息：
{error_msg[:2000]}

GPU: {gpu_model}

请以 JSON 格式回复：{{"reason": "错误原因", "fix": "修复命令"}}
只返回 JSON，不要其他文字。"""

    try:
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            },
            timeout=30,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # 解析 JSON
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return {**json.loads(content), "source": "ai"}

    except Exception as e:
        return {"reason": f"AI 诊断失败: {e}", "fix": "请查看日志", "source": "error"}


def prompt_fix(diag: dict) -> bool:
    """显示诊断结果并询问是否修复"""
    print(f"\n┌─ {'AI 诊断' if diag.get('source') == 'ai' else '错误诊断'} ─────────────────────┐")
    print(f"│ 原因: {diag.get('reason', '未知')}")
    print(f"│ 修复: {diag.get('fix', '无')}")
    print("└────────────────────────────────────────────┘")

    ans = input("\n是否执行修复？[Y/n]: ").strip().lower()
    return ans != "n"
