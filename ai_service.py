import os
import requests


def build_prompt(log_content, kb_hits):
    ctx = ''
    if kb_hits:
        ctx = '\n\n【参考知识库条目（相关度由高到低）】\n'
        for h in kb_hits[:3]:
            r = h['row']
            ctx += f"[{r['category']}] {r['title']}\n问题：{r['problem']}\n方案：{r['solution']}\n\n"

    return f"""你是一名专业的 DCU/GPU 服务器售后故障诊断专家，专注于 HYGON DCU、HySwitch、驱动（hycu）、DTK、vLLM、分布式训练等领域。\n\n请对以下故障日志进行诊断，给出：\n1. 故障摘要（一句话）\n2. 可能原因（列出 2-3 条）\n3. 排查步骤（分步骤）\n4. 预防建议\n{ctx}--- 故障日志 ---\n{log_content[:4000]}\n--- 结束 ---\n\n请用中文回答，格式清晰。"""


def get_ai_provider():
    provider = os.environ.get('AI_PROVIDER', 'qwen').strip().lower()
    if provider in ('qwen', 'qwenai'):
        return 'qwen', os.environ.get('QWEN_API_KEY', ''), os.environ.get('QWEN_MODEL', 'qwen3.6-plus')
    if provider in ('zhipu', '智谱', 'zhipu'):
        return 'zhipu', os.environ.get('ZHIPU_API_KEY', ''), os.environ.get('ZHIPU_MODEL', 'glm-5')
    if provider in ('anthropic', 'claude'):
        return 'anthropic', os.environ.get('ANTHROPIC_API_KEY', ''), os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')
    return provider, os.environ.get('QWEN_API_KEY', ''), os.environ.get('QWEN_MODEL', 'qwen3.6-plus')


def call_qwen(prompt, api_key, model):
    resp = requests.post(
        'https://api.qwen.ai/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1500,
            'temperature': 0.1,
        },
        timeout=60
    )
    if resp.status_code != 200:
        return f'AI 接口错误 {resp.status_code}: {resp.text[:200]}', 'AI_ERR'
    body = resp.json()
    text = None
    if isinstance(body.get('choices'), list) and body['choices']:
        text = body['choices'][0].get('message', {}).get('content')
    if not text:
        text = body.get('result') or body.get('data', [{}])[0].get('content', '')
    return text or 'AI 返回结果为空', 'AI'


def call_zhipu(prompt, api_key, model):
    resp = requests.post(
        f'https://open.bigmodel.cn/api/paas/v1/model/{model}/invoke',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'input': prompt,
            'parameters': {'max_output_tokens': 1500},
        },
        timeout=60
    )
    if resp.status_code != 200:
        return f'AI 接口错误 {resp.status_code}: {resp.text[:200]}', 'AI_ERR'
    body = resp.json()
    data = body.get('data')
    if isinstance(data, list) and data:
        content = data[0].get('content')
        if isinstance(content, dict):
            return content.get('text', 'AI 返回结果为空'), 'AI'
        return content or 'AI 返回结果为空', 'AI'
    return body.get('result') or body.get('output') or 'AI 返回结果为空', 'AI'


def call_anthropic(prompt, api_key, model):
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': model,
            'max_tokens': 1500,
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=60
    )
    if resp.status_code != 200:
        return f'AI 接口错误 {resp.status_code}: {resp.text[:200]}', 'AI_ERR'
    body = resp.json()
    text = None
    if isinstance(body.get('content'), list) and body['content']:
        text = body['content'][0].get('text')
    return text or 'AI 返回结果为空', 'AI'


def call_ai(log_content, kb_hits):
    provider, api_key, model = get_ai_provider()
    if not api_key:
        return None, 'NO_KEY'

    prompt = build_prompt(log_content, kb_hits)
    try:
        if provider == 'qwen':
            return call_qwen(prompt, api_key, model)
        if provider == 'zhipu':
            return call_zhipu(prompt, api_key, model)
        return call_anthropic(prompt, api_key, model)
    except Exception as e:
        return f'AI 调用异常: {e}', 'AI_ERR'
