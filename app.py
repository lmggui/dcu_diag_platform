#!/usr/bin/env python3
"""
DCU 售后故障诊断平台  v1.0
After-sales Fault Diagnosis Platform
"""

from flask import Flask
from db import init_db
from routes import register_routes

app = Flask(__name__)
init_db()
register_routes(app)

if __name__ == '__main__':
    print('\n' + '='*60)
    print('  DCU 售后故障诊断平台  v1.0')
    print('  http://127.0.0.1:5000')
    print('='*60)
    print('  AI 分析功能需设置环境变量：')
    print('  export ANTHROPIC_API_KEY=sk-ant-...')
    print('='*60 + '\n')
    app.run(host='0.0.0.0', port=5000, debug=False)
