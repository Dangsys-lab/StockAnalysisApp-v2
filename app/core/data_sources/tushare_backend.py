# -*- coding: utf-8 -*-
"""
Tushare API 后端服务

提供 RESTful API 接口，用于访问 Tushare 数据
- 实时行情查询
- 历史数据查询
- 股票信息查询
- 财务指标查询
- F10 资料查询
- 数据源状态管理

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
from tushare_data import TushareDataFetcher, get_fetcher


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


class TushareBackend:
    """
    Tushare 后端服务类
    """
    
    def __init__(self):
        """初始化后端服务"""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.urandom(24)
        self.app.config['JSON_AS_ASCII'] = False  # 支持中文
        
        # 启用 CORS
        CORS(self.app, resources={r"/api/*": {"origins": "*"}})
        
        # 数据获取器
        self.fetcher = TushareDataFetcher(request_interval=0.5)
        
        # 注册路由
        self._register_routes()
    
    def _register_routes(self):
        """注册 API 路由"""
        
        @self.app.route('/api/connect', methods=['POST'])
        def connect():
            """
            连接 Tushare 数据源
            
            Request Body:
                token: Tushare API Token
            
            Returns:
                连接状态
            """
            data = request.json or {}
            token = data.get('token', '').strip()
            
            if not token:
                return jsonify(ApiResponse.validation_error('缺少 token 参数'))
            
            # 设置 token 并测试连接
            self.fetcher.set_token(token)
            
            if self.fetcher.is_connected():
                return jsonify(ApiResponse.success({
                    'connected': True,
                    'message': '连接成功'
                }, '连接成功'))
            else:
                return jsonify(ApiResponse.error('连接失败，请检查 Token 是否正确', code=401))
        
        @self.app.route('/api/status', methods=['GET'])
        def status():
            """
            获取数据源状态
            
            Returns:
                状态信息
            """
            status_info = self.fetcher.get_status()
            return jsonify(ApiResponse.success(status_info, '状态查询成功'))
        
        @self.app.route('/api/realtime', methods=['GET'])
        def get_realtime():
            """
            获取实时行情数据
            
            Query Parameters:
                code: 6 位股票代码
            
            Returns:
                实时行情数据
            """
            code = request.args.get('code', '').strip()
            
            if not code:
                return jsonify(ApiResponse.validation_error('缺少股票代码参数'))
            
            if len(code) != 6 or not code.isdigit():
                return jsonify(ApiResponse.validation_error('股票代码格式错误'))
            
            # 获取实时数据
            result = self.fetcher.get_realtime_data(code)
            
            if result:
                return jsonify(ApiResponse.success(result, '实时数据获取成功'))
            else:
                return jsonify(ApiResponse.error('数据获取失败', code=404))
        
        @self.app.route('/api/history', methods=['GET'])
        def get_history():
            """
            获取历史数据
            
            Query Parameters:
                code: 6 位股票代码
                start_date: 开始日期（YYYYMMDD），可选
                end_date: 结束日期（YYYYMMDD），可选
                period: 周期（daily/weekly/monthly），默认 daily
            
            Returns:
                历史数据
            """
            code = request.args.get('code', '').strip()
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            period = request.args.get('period', 'daily').strip().lower()
            
            if not code:
                return jsonify(ApiResponse.validation_error('缺少股票代码参数'))
            
            if len(code) != 6 or not code.isdigit():
                return jsonify(ApiResponse.validation_error('股票代码格式错误'))
            
            # 验证日期格式
            if start_date:
                try:
                    datetime.strptime(start_date, '%Y%m%d')
                except ValueError:
                    return jsonify(ApiResponse.validation_error('开始日期格式错误，应为 YYYYMMDD'))
            
            if end_date:
                try:
                    datetime.strptime(end_date, '%Y%m%d')
                except ValueError:
                    return jsonify(ApiResponse.validation_error('结束日期格式错误，应为 YYYYMMDD'))
            
            # 获取历史数据
            result = self.fetcher.get_historical_data(
                code=code,
                start_date=start_date,
                end_date=end_date,
                period=period
            )
            
            if result:
                return jsonify(ApiResponse.success(result, '历史数据获取成功'))
            else:
                return jsonify(ApiResponse.error('数据获取失败', code=404))
        
        @self.app.route('/api/stockinfo', methods=['GET'])
        def get_stock_info():
            """
            获取股票基本信息
            
            Query Parameters:
                code: 6 位股票代码
            
            Returns:
                股票基本信息
            """
            code = request.args.get('code', '').strip()
            
            if not code:
                return jsonify(ApiResponse.validation_error('缺少股票代码参数'))
            
            if len(code) != 6 or not code.isdigit():
                return jsonify(ApiResponse.validation_error('股票代码格式错误'))
            
            # 获取股票信息
            result = self.fetcher.get_stock_info(code)
            
            if result:
                return jsonify(ApiResponse.success(result, '股票信息获取成功'))
            else:
                return jsonify(ApiResponse.error('数据获取失败', code=404))
        
        @self.app.route('/api/financial', methods=['GET'])
        def get_financial():
            """
            获取财务指标数据
            
            Query Parameters:
                code: 6 位股票代码
            
            Returns:
                财务指标数据
            """
            code = request.args.get('code', '').strip()
            
            if not code:
                return jsonify(ApiResponse.validation_error('缺少股票代码参数'))
            
            if len(code) != 6 or not code.isdigit():
                return jsonify(ApiResponse.validation_error('股票代码格式错误'))
            
            # 获取财务指标
            result = self.fetcher.get_financial_indicators(code)
            
            if result:
                return jsonify(ApiResponse.success(result, '财务指标获取成功'))
            else:
                return jsonify(ApiResponse.error('数据获取失败', code=404))
        
        @self.app.route('/api/f10', methods=['GET'])
        def get_f10():
            """
            获取 F10 资料
            
            Query Parameters:
                code: 6 位股票代码
            
            Returns:
                F10 资料
            """
            code = request.args.get('code', '').strip()
            
            if not code:
                return jsonify(ApiResponse.validation_error('缺少股票代码参数'))
            
            if len(code) != 6 or not code.isdigit():
                return jsonify(ApiResponse.validation_error('股票代码格式错误'))
            
            # 获取 F10 资料
            result = self.fetcher.get_f10_info(code)
            
            if result:
                return jsonify(ApiResponse.success(result, 'F10 资料获取成功'))
            else:
                return jsonify(ApiResponse.error('数据获取失败', code=404))
        
        @self.app.route('/api/index', methods=['GET'])
        def get_index():
            """
            获取指数数据
            
            Query Parameters:
                code: 指数代码（如 000001）
                start_date: 开始日期（YYYYMMDD），可选
                end_date: 结束日期（YYYYMMDD），可选
            
            Returns:
                指数数据
            """
            code = request.args.get('code', '').strip()
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            
            if not code:
                return jsonify(ApiResponse.validation_error('缺少指数代码参数'))
            
            if len(code) != 6 or not code.isdigit():
                return jsonify(ApiResponse.validation_error('指数代码格式错误'))
            
            # 获取指数数据
            result = self.fetcher.get_market_index_data(
                code=code,
                start_date=start_date,
                end_date=end_date
            )
            
            if result:
                return jsonify(ApiResponse.success(result, '指数数据获取成功'))
            else:
                return jsonify(ApiResponse.error('数据获取失败', code=404))
        
        @self.app.route('/api/stocks', methods=['GET'])
        def get_all_stocks():
            """
            获取所有股票列表
            
            Query Parameters:
                exchange: 交易所代码（SSE/SZSE/BSE），可选
            
            Returns:
                股票列表
            """
            exchange = request.args.get('exchange', '').strip().upper()
            
            # 获取股票列表
            result = self.fetcher.get_all_stocks(exchange=exchange if exchange else '')
            
            if result:
                return jsonify(ApiResponse.success(result, '股票列表获取成功'))
            else:
                return jsonify(ApiResponse.error('数据获取失败', code=404))
        
        @self.app.route('/api/test', methods=['GET'])
        def test_connection():
            """
            测试 API 连接
            
            Returns:
                测试信息
            """
            return jsonify(ApiResponse.success({
                'message': 'Tushare API 服务运行正常',
                'version': '1.0.0',
                'endpoints': [
                    '/api/connect',
                    '/api/status',
                    '/api/realtime',
                    '/api/history',
                    '/api/stockinfo',
                    '/api/financial',
                    '/api/f10',
                    '/api/index',
                    '/api/stocks'
                ]
            }, '服务正常'))
    
    def run(self, host: str = '0.0.0.0', port: int = 5004, debug: bool = False):
        """
        启动 Flask 应用
        
        Args:
            host: 监听地址
            port: 监听端口
            debug: 是否开启调试模式
        """
        print(f"启动 Tushare API 服务...")
        print(f"监听地址：http://{host}:{port}")
        print(f"API 文档：http://{host}:{port}/api/test")
        print(f"按 Ctrl+C 停止服务")
        
        self.app.run(host=host, port=port, debug=debug)


# 便捷函数
def create_app() -> Flask:
    """
    创建 Flask 应用实例
    
    Returns:
        Flask: 应用实例
    """
    backend = TushareBackend()
    return backend.app


def run_server(host: str = '0.0.0.0', port: int = 5004, debug: bool = False):
    """
    启动 Tushare API 服务
    
    Args:
        host: 监听地址
        port: 监听端口
        debug: 是否开启调试模式
    """
    backend = TushareBackend()
    backend.run(host=host, port=port, debug=debug)


# 主程序
if __name__ == '__main__':
    # 从环境变量读取 Token（可选）
    token = os.getenv('TUSHARE_TOKEN', '')
    
    if token:
        print(f"使用环境变量中的 Token")
    else:
        print("警告：未设置 TUSHARE_TOKEN 环境变量")
        print("请在运行时设置：export TUSHARE_TOKEN=your_token_here")
        print("或在代码中直接设置 token")
    
    # 启动服务
    run_server(host='0.0.0.0', port=5004, debug=True)
