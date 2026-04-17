# -*- coding: utf-8 -*-
"""
本地调试启动脚本

使用方法:
    python run_local.py
    
访问:
    http://localhost:9100
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

if __name__ == '__main__':
    app = create_app()
    
    print("=" * 60)
    print("股票技术分析App - 本地调试模式")
    print("=" * 60)
    print()
    print("可用API端点:")
    print("  GET  /health                        - 健康检查")
    print("  GET  /api/indicators/<code>         - 获取指标")
    print("  GET  /api/indicators/params         - 可自定义参数列表")
    print("  POST /api/indicators/params/validate - 验证参数")
    print("  POST /api/indicators/batch          - 批量查询")
    print("  GET  /api/indicators/list           - 指标列表")
    print("  GET  /api/indicators/sources        - 数据源状态")
    print("  POST /api/iap/verify                - 内购验证")
    print("  GET  /api/iap/status                - 内购状态")
    print("  GET  /api/market/environment        - 市场环境")
    print()
    print("示例请求:")
    print("  http://localhost:9100/api/indicators/600519?is_pro=true")
    print("  http://localhost:9100/api/indicators/600519?is_pro=true&user_params={\"rsi_period\":21}")
    print()
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=9100, debug=True)
