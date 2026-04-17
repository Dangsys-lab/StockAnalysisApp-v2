# -*- coding: utf-8 -*-
"""
阿里云函数计算 FC 3.0 - Serverless 部署入口 (v2.0)

v2.0 更新:
- 使用Flask应用工厂模式
- 9个API端点完整支持
- 在线数据源管理器

运行环境说明:
- 事件函数 + Python 3.9 标准运行时
- 依赖由FC自动安装（requirements.txt）
- Handler格式: server.app
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("Stock Analyzer v2.0 - Serverless Mode")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"CWD: {os.getcwd()}")
    print()
    
    port = int(os.environ.get('PORT', 9000))
    
    print("API Endpoints:")
    print("  GET  /api/market/thermometer")
    print("  GET  /api/market/environment")
    print("  GET  /api/indicators/<code>")
    print("  POST /api/indicators/batch")
    print("  GET  /api/indicators/list")
    print("  GET  /api/stock/<code>/basic")
    print("  GET  /api/stock/<code>/report")
    print("  GET  /portfolio")
    print("  POST /portfolio")
    print()
    print(f"Starting server on port {port}...")
    
    app.run(host='0.0.0.0', port=port, debug=False)
