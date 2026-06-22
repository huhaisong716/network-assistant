"""DeepSeek API AI 错误诊断"""
import json
import urllib.request
import urllib.error
from config import get_deepseek_key


def diagnose_with_deepseek(error_text: str, context: str = "") -> str:
    """使用 DeepSeek API 诊断错误"""
    api_key = get_deepseek_key()
    if not api_key:
        return "请先在设置中配置 DeepSeek API Key"

    prompt = f"""你是一个 NVIDIA 驱动安装专家。分析以下错误信息，给出：
1. 问题原因（中文，一句话）
2. 解决方案（可执行的命令行步骤）

错误信息：
{error_text}

上下文：
{context}
"""

    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1000,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        return f"API 请求失败 (HTTP {e.code}): {e.reason}"
    except Exception as e:
        return f"诊断失败: {e}"
