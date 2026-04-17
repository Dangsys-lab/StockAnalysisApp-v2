# -*- coding: utf-8 -*-
"""
yfinance API 后端服务

提供 RESTful API 接口，用于访问 yfinance 数据
- 支持美股/港股实时行情
- 历史 K 线数据
- 股票基本信息
- 财务指标数据
- 分析师评级
- 新闻资讯

符合项目规范：
- 遵循分层架构（API → Service → Core）
- 使用 ApiResponse 格式返回
- 完整的参数验证
- 添加 CORS 支持
"""

import os
from datetime import datetime
from typing import Dict, Any
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

# 导入数据获取模块
from yfinance_data import YFinanceDataFetcher, get_fetcher


class ApiResponse:
    """
    API 响应格式化工具类
    """
    
    @staticmethod
    def success(data: Any = None, message: str = '成功') -> Dict:
        """
        成功响应
        
        Args:
            data: 响应数据
            message: 成功消息
            
        Returns:
            Dict: 响应字典
        """
        return {
            'code': 200,
            'success': True,
            'message': message,
            'data': data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    @staticmethod
    def error(message: str = '失败', code: int = 500) -> Dict:
        """
        错误响应
        
        Args:
            message: 错误消息
            code: 错误码
            
        Returns:
            Dict: 响应字典
        """
        return {
            'code': code,
            'success': False,
            'message': message,
            'data': None,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    @staticmethod
    def validation_error(message: str = '参数验证失败') -> Dict:
        """
        参数验证错误响应
        
        Args:
            message: 错误消息
            
        Returns:
            Dict: 响应字典
        """
        return ApiResponse.error(message, code=400)


class YFinanceBackend:
    """
    yfinance 后端服务类
    """
    
    def __init__(self):
        """初始化后端服务"""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.urandom(24)
        self.app.config['JSON_AS_ASCII'] = False  # 支持中文
        
        # 启用 CORS
        CORS(self.app, resources={r"/api/*": {"origins": "*"}})
        
        # 数据获取器
        self.fetcher = YFinanceDataFetcher(request_interval=1.0)
        
        # 连接状态
        self.connected = False
        self.connection_info = {}
        
        # 注册路由
        self._register_routes()
    
    def _register_routes(self):
        """注册 API 路由"""
        
        # 健康检查
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """健康检查接口"""
            return jsonify(ApiResponse.success({
                'status': 'ok',
                'service': 'yfinance Backend',
                'version': '1.0.0'
            }))
        
        # 获取实时数据
        @self.app.route('/api/realtime', methods=['GET'])
        def get_realtime():
            """
            获取股票实时行情数据
            
            Query Parameters:
                code: 股票代码（必填，如 AAPL 或 0700）
                market: 市场类型，US/HK（可选，默认 US）
            
            Returns:
                JSON: 实时行情数据
            """
            # 参数验证
            code = request.args.get('code', '').strip()
            if not code:
                return jsonify(ApiResponse.validation_error('缺少参数：code'))
            
            market = request.args.get('market', 'US').strip().upper()
            if market not in ['US', 'HK']:
                return jsonify(ApiResponse.validation_error('无效的市场类型，可选值：US/HK'))
            
            try:
                # 获取数据
                data = self.fetcher.get_realtime_data(code, market)
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取股票 {code} 数据失败', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取历史数据
        @self.app.route('/api/history', methods=['GET'])
        def get_history():
            """
            获取股票历史 K 线数据
            
            Query Parameters:
                code: 股票代码（必填）
                market: 市场类型，US/HK（可选，默认 US）
                period: 周期，如 1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max（可选，默认 1y）
                start_date: 开始日期 YYYY-MM-DD（可选）
                end_date: 结束日期 YYYY-MM-DD（可选）
                interval: 时间间隔，如 1m/5m/15m/30m/60m/90m/1h/1d/5d/1wk/1mo/3mo（可选，默认 1d）
            
            Returns:
                JSON: 历史 K 线数据
            """
            # 参数验证
            code = request.args.get('code', '').strip()
            if not code:
                return jsonify(ApiResponse.validation_error('缺少参数：code'))
            
            market = request.args.get('market', 'US').strip().upper()
            if market not in ['US', 'HK']:
                return jsonify(ApiResponse.validation_error('无效的市场类型，可选值：US/HK'))
            
            period = request.args.get('period', '1y').strip()
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            interval = request.args.get('interval', '1d').strip()
            
            try:
                # 获取数据
                data = self.fetcher.get_historical_data(
                    code=code,
                    market=market,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取股票 {code} 历史数据失败', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取股票信息
        @self.app.route('/api/stockinfo', methods=['GET'])
        def get_stock_info():
            """
            获取股票基本信息
            
            Query Parameters:
                code: 股票代码（必填）
                market: 市场类型，US/HK（可选，默认 US）
            
            Returns:
                JSON: 股票基本信息
            """
            # 参数验证
            code = request.args.get('code', '').strip()
            if not code:
                return jsonify(ApiResponse.validation_error('缺少参数：code'))
            
            market = request.args.get('market', 'US').strip().upper()
            if market not in ['US', 'HK']:
                return jsonify(ApiResponse.validation_error('无效的市场类型，可选值：US/HK'))
            
            try:
                # 获取数据
                data = self.fetcher.get_stock_info(code, market)
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取股票 {code} 信息失败', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取财务指标
        @self.app.route('/api/financial', methods=['GET'])
        def get_financial():
            """
            获取股票财务指标
            
            Query Parameters:
                code: 股票代码（必填）
                market: 市场类型，US/HK（可选，默认 US）
            
            Returns:
                JSON: 财务指标数据
            """
            # 参数验证
            code = request.args.get('code', '').strip()
            if not code:
                return jsonify(ApiResponse.validation_error('缺少参数：code'))
            
            market = request.args.get('market', 'US').strip().upper()
            if market not in ['US', 'HK']:
                return jsonify(ApiResponse.validation_error('无效的市场类型，可选值：US/HK'))
            
            try:
                # 获取数据
                data = self.fetcher.get_financial_data(code, market)
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取股票 {code} 财务指标失败', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取分析师评级
        @self.app.route('/api/ratings', methods=['GET'])
        def get_ratings():
            """
            获取分析师评级
            
            Query Parameters:
                code: 股票代码（必填）
                market: 市场类型，US/HK（可选，默认 US）
            
            Returns:
                JSON: 分析师评级数据
            """
            # 参数验证
            code = request.args.get('code', '').strip()
            if not code:
                return jsonify(ApiResponse.validation_error('缺少参数：code'))
            
            market = request.args.get('market', 'US').strip().upper()
            if market not in ['US', 'HK']:
                return jsonify(ApiResponse.validation_error('无效的市场类型，可选值：US/HK'))
            
            try:
                # 获取数据
                data = self.fetcher.get_analyst_ratings(code, market)
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取股票 {code} 分析师评级失败', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取新闻
        @self.app.route('/api/news', methods=['GET'])
        def get_news():
            """
            获取股票相关新闻
            
            Query Parameters:
                code: 股票代码（必填）
                market: 市场类型，US/HK（可选，默认 US）
            
            Returns:
                JSON: 新闻列表
            """
            # 参数验证
            code = request.args.get('code', '').strip()
            if not code:
                return jsonify(ApiResponse.validation_error('缺少参数：code'))
            
            market = request.args.get('market', 'US').strip().upper()
            if market not in ['US', 'HK']:
                return jsonify(ApiResponse.validation_error('无效的市场类型，可选值：US/HK'))
            
            try:
                # 获取数据
                data = self.fetcher.get_news(code, market)
                
                # 新闻可能为空列表
                return jsonify(ApiResponse.success(data if data is not None else []))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取数据源状态
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """
            获取数据源状态
            
            Returns:
                JSON: 状态信息
            """
            try:
                status = self.fetcher.get_status()
                status['connected'] = self.connected
                status['connection_info'] = self.connection_info
                
                return jsonify(ApiResponse.success(status))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取状态失败：{str(e)}', code=500))
        
        # 连接数据源
        @self.app.route('/api/connect', methods=['POST'])
        def connect():
            """
            连接 yfinance 数据源
            
            Returns:
                JSON: 连接结果
            """
            try:
                # 检查 yfinance 是否可用
                if not self.fetcher.get_status()['available']:
                    return jsonify(ApiResponse.error('yfinance 库未安装', code=500))
                
                # 连接成功
                self.connected = True
                self.connection_info = {
                    'type': 'yfinance',
                    'version': 'latest',
                    'url': 'https://finance.yahoo.com/'
                }
                
                return jsonify(ApiResponse.success({
                    'connected': True,
                    'info': self.connection_info
                }, 'yfinance 连接成功'))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'连接失败：{str(e)}', code=500))
        
        # 断开连接
        @self.app.route('/api/disconnect', methods=['POST'])
        def disconnect():
            """
            断开数据源连接
            
            Returns:
                JSON: 断开结果
            """
            try:
                self.connected = False
                self.connection_info = {}
                
                return jsonify(ApiResponse.success({
                    'connected': False
                }, '已断开连接'))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'断开连接失败：{str(e)}', code=500))
        
        # 清除缓存
        @self.app.route('/api/cache/clear', methods=['POST'])
        def clear_cache():
            """
            清除数据缓存
            
            Returns:
                JSON: 操作结果
            """
            try:
                self.fetcher.clear_cache()
                
                return jsonify(ApiResponse.success(None, '缓存已清除'))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'清除缓存失败：{str(e)}', code=500))
    
    def run(self, host: str = '0.0.0.0', port: int = 5005, debug: bool = True):
        """
        启动 Flask 应用
        
        Args:
            host: 监听地址，默认 0.0.0.0
            port: 监听端口，默认 5005
            debug: 是否开启调试模式，默认 True
        """
        print("=" * 60)
        print("yfinance Backend 服务启动")
        print("=" * 60)
        print(f"监听地址：http://{host}:{port}")
        print(f"调试模式：{'开启' if debug else '关闭'}")
        print("\n可用 API 端点:")
        print("  GET  /api/health          - 健康检查")
        print("  GET  /api/realtime        - 获取实时数据")
        print("  GET  /api/history         - 获取历史数据")
        print("  GET  /api/stockinfo       - 获取股票信息")
        print("  GET  /api/financial       - 获取财务指标")
        print("  GET  /api/ratings         - 获取分析师评级")
        print("  GET  /api/news            - 获取新闻")
        print("  GET  /api/status          - 获取状态")
        print("  POST /api/connect         - 连接数据源")
        print("  POST /api/disconnect      - 断开连接")
        print("  POST /api/cache/clear     - 清除缓存")
        print("=" * 60)
        
        self.app.run(host=host, port=port, debug=debug)


# 创建全局应用实例
app = YFinanceBackend()


# 直接运行入口
if __name__ == '__main__':
    app.run()
