# -*- coding: utf-8 -*-
"""
pandas_datareader API 后端服务

提供 RESTful API 接口，用于访问 pandas_datareader 数据
- FRED 经济数据查询
- 世界银行数据查询
- 外汇汇率查询
- 美国国债收益率查询
- OECD/Eurostat 数据查询
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
from pandas_data import PandasDataFetcher, get_fetcher


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


class PandasBackend:
    """
    pandas_datareader 后端服务类
    """
    
    def __init__(self):
        """初始化后端服务"""
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.urandom(24)
        self.app.config['JSON_AS_ASCII'] = False  # 支持中文
        
        # 启用 CORS
        CORS(self.app, resources={r"/api/*": {"origins": "*"}})
        
        # 数据获取器
        fred_api_key = os.environ.get('FRED_API_KEY', '')
        self.fetcher = PandasDataFetcher(request_interval=1.0, fred_api_key=fred_api_key)
        
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
                'service': 'pandas_datareader Backend',
                'version': '1.0.0'
            }))
        
        # 获取 FRED 数据
        @self.app.route('/api/fred', methods=['GET'])
        def get_fred():
            """
            获取 FRED（美联储经济数据）
            
            Query Parameters:
                series_id: 数据系列 ID（必填，如 "GDP", "CPIAUCSL"）
                start_date: 开始日期 YYYY-MM-DD（可选）
                end_date: 结束日期 YYYY-MM-DD（可选）
                limit: 限制返回记录数（可选）
            
            Returns:
                JSON: FRED 数据
            """
            # 参数验证
            series_id = request.args.get('series_id', '').strip()
            if not series_id:
                return jsonify(ApiResponse.validation_error('缺少参数：series_id'))
            
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            limit_str = request.args.get('limit', '').strip()
            
            limit = int(limit_str) if limit_str else None
            
            try:
                # 获取数据
                data = self.fetcher.get_fred_data(
                    series_id=series_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取 FRED 数据失败：{series_id}', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取世界银行数据
        @self.app.route('/api/worldbank', methods=['GET'])
        def get_world_bank():
            """
            获取世界银行数据
            
            Query Parameters:
                indicator: 指标代码（必填，如 "NY.GDP.MKTP.CD"）
                countries: 国家代码（可选，如 "CN,US"）
                start_year: 开始年份（可选，默认 2010）
                end_year: 结束年份（可选）
                limit: 限制返回记录数（可选）
            
            Returns:
                JSON: 世界银行数据
            """
            # 参数验证
            indicator = request.args.get('indicator', '').strip()
            if not indicator:
                return jsonify(ApiResponse.validation_error('缺少参数：indicator'))
            
            countries = request.args.get('countries', '').strip()
            start_year = request.args.get('start_year', '2010').strip()
            end_year = request.args.get('end_year', '').strip()
            limit_str = request.args.get('limit', '').strip()
            
            limit = int(limit_str) if limit_str else None
            
            # 解析国家代码
            country_list = [c.strip() for c in countries.split(',')] if countries else None
            
            try:
                # 获取数据
                data = self.fetcher.get_world_bank_data(
                    indicator=indicator,
                    countries=country_list,
                    start_year=start_year,
                    end_year=end_year,
                    limit=limit
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取世界银行数据失败：{indicator}', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取外汇汇率
        @self.app.route('/api/exchange', methods=['GET'])
        def get_exchange():
            """
            获取外汇汇率数据
            
            Query Parameters:
                currency_pairs: 货币对（必填，如 "DEXUSCN,DEXUSEU"）
                start_date: 开始日期 YYYY-MM-DD（可选）
                end_date: 结束日期 YYYY-MM-DD（可选）
                limit: 限制返回记录数（可选）
            
            Returns:
                JSON: 外汇汇率数据
            
            常用货币对:
                - DEXUSEU: USD/EUR
                - DEXUSUK: USD/GBP
                - DEXUSJP: USD/JPY
                - DEXUSCN: USD/CNY
                - DEXUSCA: USD/CAD
                - DEXUSMX: USD/MXN
            """
            # 参数验证
            currency_pairs = request.args.get('currency_pairs', '').strip()
            if not currency_pairs:
                return jsonify(ApiResponse.validation_error('缺少参数：currency_pairs'))
            
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            limit_str = request.args.get('limit', '').strip()
            
            limit = int(limit_str) if limit_str else None
            
            # 解析货币对
            pairs_list = [p.strip() for p in currency_pairs.split(',')]
            if len(pairs_list) == 1:
                pairs_list = pairs_list[0]
            
            try:
                # 获取数据
                data = self.fetcher.get_exchange_rates(
                    currency_pairs=pairs_list,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取外汇汇率失败：{currency_pairs}', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取国债收益率
        @self.app.route('/api/treasury', methods=['GET'])
        def get_treasury():
            """
            获取美国国债收益率数据
            
            Query Parameters:
                maturities: 期限（可选，如 "DGS10,DGS2"，默认获取所有主要期限）
                start_date: 开始日期 YYYY-MM-DD（可选）
                end_date: 结束日期 YYYY-MM-DD（可选）
                limit: 限制返回记录数（可选）
            
            Returns:
                JSON: 国债收益率数据
            
            常用期限:
                - DGS3MO: 3 个月期
                - DGS6MO: 6 个月期
                - DGS1: 1 年期
                - DGS2: 2 年期
                - DGS5: 5 年期
                - DGS10: 10 年期
                - DGS30: 30 年期
            """
            # 参数验证
            maturities = request.args.get('maturities', '').strip()
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            limit_str = request.args.get('limit', '').strip()
            
            limit = int(limit_str) if limit_str else None
            
            # 解析期限
            if maturities:
                maturities_list = [m.strip() for m in maturities.split(',')]
                if len(maturities_list) == 1:
                    maturities_list = maturities_list[0]
            else:
                maturities_list = None
            
            try:
                # 获取数据
                data = self.fetcher.get_treasury_yields(
                    maturities=maturities_list,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error('获取国债收益率失败', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取 OECD 数据
        @self.app.route('/api/oecd', methods=['GET'])
        def get_oecd():
            """
            获取 OECD（经合组织）数据
            
            Query Parameters:
                indicator: 指标代码（必填，如 "UNRATE", "GDP"）
                countries: 国家代码（可选，如 "USA,CHN"）
                start_date: 开始日期 YYYY-MM-DD（可选）
                end_date: 结束日期 YYYY-MM-DD（可选）
                limit: 限制返回记录数（可选）
            
            Returns:
                JSON: OECD 数据
            """
            # 参数验证
            indicator = request.args.get('indicator', '').strip()
            if not indicator:
                return jsonify(ApiResponse.validation_error('缺少参数：indicator'))
            
            countries = request.args.get('countries', '').strip()
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            limit_str = request.args.get('limit', '').strip()
            
            limit = int(limit_str) if limit_str else None
            
            # 解析国家代码
            country_list = [c.strip() for c in countries.split(',')] if countries else None
            
            try:
                # 获取数据
                data = self.fetcher.get_oecd_data(
                    indicator=indicator,
                    countries=country_list,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取 OECD 数据失败：{indicator}', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 获取 Eurostat 数据
        @self.app.route('/api/eurostat', methods=['GET'])
        def get_eurostat():
            """
            获取 Eurostat（欧盟统计局）数据
            
            Query Parameters:
                indicator: 指标代码（必填，如 "PRC_HICP_MIDX"）
                start_date: 开始日期 YYYY-MM-DD（可选）
                end_date: 结束日期 YYYY-MM-DD（可选）
                limit: 限制返回记录数（可选）
            
            Returns:
                JSON: Eurostat 数据
            """
            # 参数验证
            indicator = request.args.get('indicator', '').strip()
            if not indicator:
                return jsonify(ApiResponse.validation_error('缺少参数：indicator'))
            
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            limit_str = request.args.get('limit', '').strip()
            
            limit = int(limit_str) if limit_str else None
            
            try:
                # 获取数据
                data = self.fetcher.get_eurostat_data(
                    indicator=indicator,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取 Eurostat 数据失败：{indicator}', code=404))
                    
            except Exception as e:
                return jsonify(ApiResponse.error(f'获取数据失败：{str(e)}', code=500))
        
        # 通用数据接口
        @self.app.route('/api/data', methods=['GET'])
        def get_data():
            """
            通用数据获取接口
            
            Query Parameters:
                name: 数据系列名称（必填）
                data_source: 数据源（必填，fred/wb/oecd/eurostat）
                start_date: 开始日期 YYYY-MM-DD（可选）
                end_date: 结束日期 YYYY-MM-DD（可选）
            
            Returns:
                JSON: 数据
            """
            # 参数验证
            name = request.args.get('name', '').strip()
            if not name:
                return jsonify(ApiResponse.validation_error('缺少参数：name'))
            
            data_source = request.args.get('data_source', '').strip().lower()
            if not data_source:
                return jsonify(ApiResponse.validation_error('缺少参数：data_source'))
            
            if data_source not in ['fred', 'wb', 'oecd', 'eurostat']:
                return jsonify(ApiResponse.validation_error('无效的数据源，可选值：fred/wb/oecd/eurostat'))
            
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()
            
            try:
                # 获取数据
                data = self.fetcher.get_data(
                    name=name,
                    data_source=data_source,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if data:
                    return jsonify(ApiResponse.success(data))
                else:
                    return jsonify(ApiResponse.error(f'获取数据失败：{name}', code=404))
                    
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
            连接 pandas_datareader 数据源
            
            Returns:
                JSON: 连接结果
            """
            try:
                # 检查 pandas_datareader 是否可用
                if not self.fetcher.get_status()['available']:
                    return jsonify(ApiResponse.error('pandas_datareader 库未安装', code=500))
                
                # 连接成功
                self.connected = True
                self.connection_info = {
                    'type': 'pandas_datareader',
                    'version': 'latest',
                    'url': 'https://pydata.github.io/pandas-datareader/',
                    'fred_api_key_configured': bool(self.fetcher.fred_api_key)
                }
                
                return jsonify(ApiResponse.success({
                    'connected': True,
                    'info': self.connection_info
                }, 'pandas_datareader 连接成功'))
                    
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
    
    def run(self, host: str = '0.0.0.0', port: int = 5006, debug: bool = True):
        """
        启动 Flask 应用
        
        Args:
            host: 监听地址，默认 0.0.0.0
            port: 监听端口，默认 5006
            debug: 是否开启调试模式，默认 True
        """
        print("=" * 60)
        print("pandas_datareader Backend 服务启动")
        print("=" * 60)
        print(f"监听地址：http://{host}:{port}")
        print(f"调试模式：{'开启' if debug else '关闭'}")
        print(f"FRED API Key 配置：{'是' if self.fetcher.fred_api_key else '否'}")
        print("\n可用 API 端点:")
        print("  GET  /api/health          - 健康检查")
        print("  GET  /api/fred            - 获取 FRED 经济数据")
        print("  GET  /api/worldbank       - 获取世界银行数据")
        print("  GET  /api/exchange        - 获取外汇汇率")
        print("  GET  /api/treasury        - 获取国债收益率")
        print("  GET  /api/oecd            - 获取 OECD 数据")
        print("  GET  /api/eurostat        - 获取 Eurostat 数据")
        print("  GET  /api/data            - 通用数据接口")
        print("  GET  /api/status          - 获取状态")
        print("  POST /api/connect         - 连接数据源")
        print("  POST /api/disconnect      - 断开连接")
        print("  POST /api/cache/clear     - 清除缓存")
        print("=" * 60)
        
        self.app.run(host=host, port=port, debug=debug)


# 创建全局应用实例
app = PandasBackend()


# 直接运行入口
if __name__ == '__main__':
    app.run()
