# -*- coding: utf-8 -*-
"""
App Store 股票分析工具 2.0 - 应用入口

版本: v2.0
定位: 专业级技术分析工具（良心打赏制 + 新用户¥12内购）

合规声明:
- 本应用仅提供技术指标的客观计算与状态描述
- 所有输出均为技术数据呈现，不构成任何投资建议
- 用户需自主做出投资决策，投资有风险入市需谨慎
"""

__version__ = "2.0.0"
__author__ = "Stock Analysis Tool Team"

from flask import Flask, render_template, send_from_directory, jsonify


from app.api import api_bp
from app.api import indicators as indicators_api
from app.api import market as market_api
from app.api import portfolio as portfolio_api
from app.api import report as report_api


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
    
    app.register_blueprint(api_bp)
    
    @app.route('/')
    def index():
        """首页"""
        return render_template('index_v2.html')
    
    @app.route('/health')
    def health():
        """健康检查"""
        return jsonify({
            'status': 'ok',
            'success': True,
            'message': '服务运行正常',
            'version': __version__
        })
    
    @app.route('/portfolio')
    def portfolio_page():
        """自选股页面"""
        return render_template('portfolio.html')
    
    @app.route('/report')
    @app.route('/report/<stock_code>')
    def report_page(stock_code=None):
        """报告页面"""
        if not stock_code:
            from flask import request
            stock_code = request.args.get('code', '')
        return render_template('report.html', stock_code=stock_code)
    
    @app.route('/report_page')
    def report_page_new():
        """报告页面（新版）"""
        return render_template('report_page.html')
    
    @app.route('/preview')
    def preview_page():
        """iPhone模拟预览页面"""
        return render_template('preview.html')
    
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
