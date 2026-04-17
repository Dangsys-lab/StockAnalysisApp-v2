# -*- coding: utf-8 -*-
"""
API 路由层 - 处理HTTP请求和参数验证

职责:
1. 接收并验证请求参数
2. 调用 Service 层处理业务逻辑
3. 返回标准化的 API 响应

合规要求:
- 所有响应文案必须通过合规检查
- 不包含任何投资建议类词汇
"""

from flask import Blueprint

api_bp = Blueprint('api', __name__)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    健康检查接口
    
    :return: 服务状态信息
    """
    return {
        'success': True,
        'status': 'ok',
        'version': '2.0.0',
        'message': '服务运行正常'
    }

@api_bp.route('/debug/report/<stock_code>', methods=['GET'])
def debug_report(stock_code):
    """
    调试报告API - 返回详细错误信息
    """
    import traceback
    from flask import jsonify
    
    try:
        from app.core.online_data_source import get_online_data_manager
        from app.core.indicators.calculator import IndicatorCalculatorV2
        from app.core.report_generator import ReportGenerator
        from datetime import datetime, timedelta
        
        # 步骤1: 获取数据
        manager = get_online_data_manager()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        
        raw_data = manager.get_stock_data(stock_code, start_date=start_date, end_date=end_date)
        
        if not raw_data or not raw_data.get('success'):
            return jsonify({
                'step': 'data_fetch',
                'success': False,
                'error': raw_data.get('error') if raw_data else 'No data',
                'raw_data_keys': list(raw_data.keys()) if raw_data else []
            })
        
        df = raw_data.get('data')
        if df is None or len(df) < 10:
            return jsonify({
                'step': 'data_validation',
                'success': False,
                'error': f'Data insufficient: {len(df) if df is not None else 0} rows',
                'columns': list(df.columns) if df is not None else []
            })
        
        # 步骤2: 计算指标
        calc = IndicatorCalculatorV2()
        data_dict = {
            'open': df['open'].tolist(),
            'high': df['high'].tolist(),
            'low': df['low'].tolist(),
            'close': df['close'].tolist(),
            'volume': df['volume'].tolist()
        }
        
        indicators = calc.calculate_all(data_dict)
        
        if not indicators.get('success'):
            return jsonify({
                'step': 'indicator_calculation',
                'success': False,
                'error': 'Indicator calculation failed',
                'indicators_keys': list(indicators.keys())
            })
        
        # 步骤3: 生成报告
        gen = ReportGenerator()
        report = gen.generate_report(indicators.get('data', {}))
        
        return jsonify({
            'step': 'complete',
            'success': True,
            'score': report.get('score'),
            'signals_count': len(report.get('signals', [])),
            'data_rows': len(df)
        })
        
    except Exception as e:
        return jsonify({
            'step': 'exception',
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })

from . import market
from . import indicators
from . import portfolio
from . import report
from . import iap
