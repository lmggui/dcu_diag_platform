import json
import traceback
from flask import jsonify, render_template, request

from ai_service import call_ai
from db import KB_THRESHOLD, get_db, search_kb


def register_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/analyze', methods=['POST'])
    def analyze():
        try:
            filename = '手动输入'
            if 'file' in request.files and request.files['file'].filename:
                f = request.files['file']
                filename = f.filename
                content = f.read().decode('utf-8', errors='replace')
            else:
                content = (request.form.get('content') or '').strip()
                if not content:
                    data = request.get_json(silent=True) or {}
                    content = data.get('content', '').strip()

            if not content:
                return jsonify({'error': '日志内容为空'}), 400

            hits = search_kb(content, top_k=5)
            top_score = hits[0]['score'] if hits else 0

            if top_score >= KB_THRESHOLD:
                match_type = 'KB'
                top = hits[0]['row']
                result = (
                    f"【知识库匹配】相关度 {top_score:.0%}\n\n"
                    f"▌ 分类：{top['category']}\n"
                    f"▌ 标题：{top['title']}\n\n"
                    f"🔍 问题描述\n{top['problem']}\n\n"
                    f"✅ 解决方案\n{top['solution']}"
                )
                kb_ids = ','.join(str(h['row']['id']) for h in hits if h['score'] > 0)
            else:
                ai_text, match_type = call_ai(content, hits)
                if ai_text:
                    result = f"【AI 智能分析】（知识库相关度 {top_score:.0%}，转入 AI 分析）\n\n{ai_text}"
                elif match_type == 'NO_KEY':
                    if hits and hits[0]['score'] > 0:
                        top = hits[0]['row']
                        result = (
                            f"【知识库参考】相关度 {top_score:.0%}（未配置 AI Key，仅返回最相关条目）\n\n"
                            f"▌ 分类：{top['category']}\n▌ 标题：{top['title']}\n\n"
                            f"🔍 问题描述\n{top['problem']}\n\n"
                            f"✅ 解决方案\n{top['solution']}"
                        )
                    else:
                        result = '未在知识库中找到相关条目，且未配置 ANTHROPIC_API_KEY，无法进行 AI 分析。'
                    match_type = 'KB_LOW'
                else:
                    result = ai_text or 'AI 分析失败'
                kb_ids = ','.join(str(h['row']['id']) for h in hits if h['score'] > 0)

            conn = get_db()
            conn.execute(
                'INSERT INTO fault_logs(filename,content,result,match_type,kb_ids,score) VALUES(?,?,?,?,?,?)',
                (filename, content[:5000], result, match_type, kb_ids, top_score)
            )
            conn.commit()
            conn.close()

            return jsonify({
                'match_type': match_type,
                'score': top_score,
                'result': result,
                'matched_key_info': bool(hits and hits[0].get('matched_key_info')),
                'matched_key_info_content': hits[0].get('matched_key_info_content') if hits else '',
                'kb_hits': [{'id': h['row']['id'], 'title': h['row']['title'],
                             'category': h['row']['category'], 'score': h['score']}
                            for h in hits[:3] if h['score'] > 0]
            })
        except Exception:
            return jsonify({'error': traceback.format_exc()}), 500


    @app.route('/api/kb/search', methods=['GET'])
    def kb_search():
        q = request.args.get('q', '')
        cat = request.args.get('category', 'all')
        if not q and cat == 'all':
            conn = get_db()
            rows = conn.execute(
                'SELECT id,category,title,problem,solution,keywords,key_info,source,created_at FROM knowledge_base ORDER BY id DESC'
            ).fetchall()
            conn.close()
            return jsonify([dict(r) for r in rows])
        hits = search_kb(q, cat, top_k=20)
        return jsonify([{**h['row'], 'score': h['score']} for h in hits])


    @app.route('/api/kb', methods=['POST'])
    def kb_add():
        data = request.get_json(silent=True) or {}
        required = ['category', 'title', 'problem', 'solution']
        for f in required:
            if not data.get(f):
                return jsonify({'error': f'字段 {f} 不能为空'}), 400
        conn = get_db()
        conn.execute(
            'INSERT INTO knowledge_base(category,title,problem,solution,keywords,key_info,source) VALUES(?,?,?,?,?,?,?)',
            (data['category'], data['title'], data['problem'], data['solution'],
             data.get('keywords',''), data.get('key_info',''), data.get('source','手动录入'))
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})


    @app.route('/api/kb/<int:kid>', methods=['PUT'])
    def kb_update(kid):
        data = request.get_json(silent=True) or {}
        required = ['category', 'title', 'problem', 'solution']
        for f in required:
            if not data.get(f):
                return jsonify({'error': f'字段 {f} 不能为空'}), 400
        conn = get_db()
        cur = conn.execute(
            "UPDATE knowledge_base SET category=?, title=?, problem=?, solution=?, keywords=?, key_info=?, source=?, updated_at=(datetime('now','localtime')) WHERE id=?",
            (data['category'], data['title'], data['problem'], data['solution'],
             data.get('keywords',''), data.get('key_info',''), data.get('source','手动录入'), kid)
        )
        conn.commit()
        if cur.rowcount == 0:
            conn.close()
            return jsonify({'error': '未找到该条目'}), 404
        conn.close()
        return jsonify({'ok': True})


    @app.route('/api/kb/<int:kid>', methods=['DELETE'])
    def kb_delete(kid):
        conn = get_db()
        conn.execute('DELETE FROM knowledge_base WHERE id=?', (kid,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})


    @app.route('/api/kb/import', methods=['POST'])
    def kb_import():
        try:
            if 'file' in request.files:
                f = request.files['file']
                raw = f.read().decode('utf-8', errors='replace')
                items = json.loads(raw)
            else:
                data = request.get_json(silent=True) or {}
                items = data.get('items', [])

            conn = get_db()
            count = 0
            for item in items:
                if not all(item.get(k) for k in ['category','title','problem','solution']):
                    continue
                conn.execute(
                    'INSERT INTO knowledge_base(category,title,problem,solution,keywords,key_info,source) VALUES(?,?,?,?,?,?,?)',
                    (item['category'],item['title'],item['problem'],item['solution'],
                     item.get('keywords',''), item.get('key_info',''), item.get('source','批量导入'))
                )
                count += 1
            conn.commit()
            conn.close()
            return jsonify({'ok': True, 'imported': count})
        except Exception:
            return jsonify({'error': traceback.format_exc()}), 500


    @app.route('/api/logs', methods=['GET'])
    def get_logs():
        conn = get_db()
        rows = conn.execute(
            'SELECT id,filename,match_type,score,created_at,result FROM fault_logs ORDER BY id DESC LIMIT 50'
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])


    @app.route('/api/stats', methods=['GET'])
    def stats():
        conn = get_db()
        kb_count = conn.execute('SELECT COUNT(*) as n FROM knowledge_base').fetchone()['n']
        log_count = conn.execute('SELECT COUNT(*) as n FROM fault_logs').fetchone()['n']
        cats = conn.execute(
            'SELECT category, COUNT(*) as n FROM knowledge_base GROUP BY category'
        ).fetchall()
        conn.close()
        return jsonify({
            'kb_count': kb_count,
            'log_count': log_count,
            'categories': [dict(r) for r in cats]
        })
