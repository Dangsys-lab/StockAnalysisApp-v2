# -*- coding: utf-8 -*-
"""
App Store 股票分析工具 2.0 - 应用入口

版本: v2.0
定位: 专业级技术分析工具（良心打赏制 + 新用户¥15内购）

合规声明:
- 本应用仅提供技术指标的客观计算与状态描述
- 所有输出均为技术数据呈现，不构成任何投资建议
- 用户需自主做出投资决策，投资有风险入市需谨慎
"""

__version__ = "2.0.0"
__author__ = "Stock Analysis Tool Team"

from flask import Flask, render_template, jsonify, request, Response

from app.api import api_bp


def _add_cors_headers(response):
    """
    添加CORS跨域头

    允许所有来源访问，支持阿里云函数计算跨域请求
    """
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept, Origin'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response


def create_app():
    """
    创建并配置Flask应用实例
    
    :return: 配置好的Flask应用
    """
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static'
    )
    
    import os
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    if not app.config['SECRET_KEY']:
        raise RuntimeError('SECRET_KEY environment variable is required')
    app.config['JSON_AS_ASCII'] = False
    
    @app.after_request
    def after_request(response):
        """每个请求后添加CORS头"""
        # 确保API响应有正确的Content-Type
        if request.path.startswith('/api/') or request.path.startswith('/debug/'):
            if 'application/json' not in response.headers.get('Content-Type', ''):
                response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return _add_cors_headers(response)
    
    @app.before_request
    def handle_options():
        """处理OPTIONS预检请求"""
        if request.method == 'OPTIONS':
            response = Response()
            return _add_cors_headers(response)
        return None
    
    app.register_blueprint(api_bp)
    
    @app.route('/')
    def index():
        """首页"""
        return render_template('index_v2.html')
    
    @app.route('/portfolio')
    def portfolio_page():
        """自选股页面"""
        return render_template('portfolio.html')
    
    @app.route('/report')
    def report_page():
        """报告页面（通过URL参数传递股票代码）"""
        return render_template('report_page.html')
    
    @app.route('/privacy')
    def privacy_page():
        """隐私政策页面"""
        return render_template('privacy.html')
    
    @app.route('/support')
    def support_page():
        """技术支持页面"""
        return render_template('support.html')
    
    @app.errorhandler(404)
    def not_found(error):
        """404错误处理"""
        return render_template('error.html', error=error), 404
    
    @app.errorhandler(500)
    def server_error(error):
        """500错误处理"""
        return render_template('error.html', error=error), 500
    
    return app


__all__ = ['create_app']
