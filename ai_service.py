import os
import requests


def call_ai(log_content, kb_hits):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None, 'NO_KEY'

    ctx = ''
    if kb_hits:
        ctx = '\n\n【参考知识库条目（相关度由高到低）】\n'
        for h in kb_hits[:3]:
            r = h['row']
            ctx += f"[{r['category']}] {r['title']}\n问题：{r['problem']}\n方案：{r['solution']}\n\n"

    prompt = f"""你是一名专业的 DCU/GPU 服务器售后故障诊断专家，专注于 HYGON DCU、HySwitch、驱动（hydcu-dkms）、DTK、vLLM、分布式训练等领域。\n\n请对以下故障日志进行诊断，给出：\n1. 故障摘要（一句话）\n2. 可能原因（列出 2-3 条）\n3. 排查步骤（分步骤）\n4. 预防建议\n{ctx}--- 故障日志 ---\n{log_content[:4000]}\n--- 结束 ---\n\n请用中文回答，格式清晰。"""

    try:
        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 1500,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        if resp.status_code == 200:
            return resp.json()['content'][0]['text'], 'AI'
        return f'AI 接口错误 {resp.status_code}: {resp.text[:200]}', 'AI_ERR'
    except Exception as e:
        return f'AI 调用异常: {e}', 'AI_ERR'
