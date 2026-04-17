# -*- coding: utf-8 -*-
"""
技术指标API接口 - 3.0版本

功能:
- 支持内购用户自定义参数
- 多数据源容错
- 请求间隔控制

合规声明:
本接口仅提供技术指标的客观计算结果。
所有输出为纯技术数据，不包含任何投资建议或操作指引。
"""

from flask import request, jsonify
from datetime import datetime, timedelta
from typing import Dict, Any

from app.api import api_bp
from app.services.indicator_service import IndicatorService
from app.core.online_data_source import get_online_data_manager


def clean_nan_for_json(data):
    """清理NaN值"""
    import math
    
    if isinstance(data, list):
        return [None if (isinstance(x, float) and math.isnan(x)) else x for x in data]
    elif isinstance(data, dict):
        return {k: None if (isinstance(v, float) and math.isnan(v)) else v for k, v in data.items()}
    elif isinstance(data, float) and math.isnan(data):
        return None
    else:
        return data


online_manager = get_online_data_manager()


@api_bp.route('/api/indicators/<stock_code>', methods=['GET'])
def get_stock_indicators(stock_code: str):
    """
    获取单只股票的技术指标数据
    
    参数:
    - is_pro: 是否为专业版用户 (true/false)
    - user_params: 用户自定义参数 (JSON字符串，仅专业版有效)
    - type: 指标类型 (all/trend/oscillator/volume/price)
    - start_date: 开始日期 (YYYY-MM-DD)
    - end_date: 结束日期 (YYYY-MM-DD)
    
    :param stock_code: 6位股票代码
    :return: JSON格式的指标数据
    """
    try:
        is_pro = request.args.get('is_pro', 'false').lower() == 'true'
        indicator_type = request.args.get('type', 'all')
        start_date = request.args.get('start_date',
                       (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        
        user_params = None
        if is_pro:
            import json
            params_str = request.args.get('user_params', '')
            if params_str:
                try:
                    user_params = json.loads(params_str)
                except json.JSONDecodeError:
                    pass
        
        service = IndicatorService()
        result = service.calculate_indicators(
            stock_code=stock_code,
            is_pro=is_pro,
            user_params=user_params,
            start_date=start_date,
            end_date=end_date
        )
        
        if not result.get('success'):
            return jsonify({
                'success': False,
                'message': result.get('error', '无法获取数据'),
                'stock_code': stock_code,
                'source_status': online_manager.get_source_health(),
                'suggestion': '请检查网络后重试'
            }), 503
        
        result['disclaimer'] = '以上为技术指标客观计算结果，仅供参考，不构成任何投资建议。'
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取指标数据时发生错误'
        }), 500


@api_bp.route('/api/indicators/params', methods=['GET'])
def get_customizable_params():
    """
    获取可自定义参数列表（内购用户）
    
    :return: 可自定义参数及其约束
    """
    try:
        service = IndicatorService()
        result = service.get_customizable_params()
        result['disclaimer'] = '参数配置仅对专业版用户有效。'
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/api/indicators/params/validate', methods=['POST'])
def validate_user_params():
    """
    验证用户参数是否合法
    
    请求体(JSON):
    {
        "rsi_period": 14,
        "kdj_n": 9,
        ...
    }
    
    :return: 验证结果
    """
    try:
        data = request.json or {}
        
        service = IndicatorService()
        result = service.validate_user_params(data)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/api/indicators/batch', methods=['POST'])
def batch_get_indicators():
    """
    批量获取多只股票的指标摘要
    
    请求体(JSON):
    {
        "codes": ["600519", "000858", "601318"],
        "is_pro": true/false
    }
    
    限制:
    - 单次最多20只股票
    
    :return: 批量查询结果JSON
    """
    try:
        data = request.json or {}
        codes = data.get('codes', [])
        is_pro = data.get('is_pro', False)
        
        if not codes:
            return jsonify({
                'success': False,
                'message': '请提供股票代码列表'
            }), 400
        
        if len(codes) > 20:
            return jsonify({
                'success': False,
                'message': '单次最多查询20只股票'
            }), 400
        
        for code in codes:
            if not code or len(code) != 6 or not code.isdigit():
                return jsonify({
                    'success': False,
                    'message': f'无效的股票代码: {code}'
                }), 400
        
        results = []
        errors = []
        
        service = IndicatorService()
        
        for code in codes:
            try:
                result = service.calculate_indicators(
                    stock_code=code,
                    is_pro=is_pro,
                    start_date=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                    end_date=datetime.now().strftime('%Y-%m-%d')
                )
                
                if result.get('success'):
                    summary = {
                        'code': code,
                        'last_price': result['data']['close'][-1] if result['data'].get('close') else None,
                        'rsi': result['data'].get('rsi', [None])[-1] if result['data'].get('rsi') else None,
                        'ma5': result['data'].get('ma5', [None])[-1] if result['data'].get('ma5') else None,
                        'ma20': result['data'].get('ma20', [None])[-1] if result['data'].get('ma20') else None,
                        'data_source': result.get('data_source')
                    }
                    results.append(summary)
                else:
                    errors.append({'code': code, 'error': result.get('error', '未知错误')})
                
            except Exception as e:
                errors.append({'code': code, 'error': str(e)})
                continue
        
        return jsonify({
            'success': True,
            'total_requested': len(codes),
            'successful': len(results),
            'failed': len(errors),
            'results': results,
            'errors': errors[:5],
            'is_pro': is_pro,
            'disclaimer': '以上为技术指标客观计算结果，仅供参考。'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '批量查询时发生错误'
        }), 500


@api_bp.route('/api/indicators/list', methods=['GET'])
def list_available_indicators():
    """
    获取所有可用的技术指标列表
    
    :return: 指标分类和名称列表
    """
    from app.core.indicators.calculator import IndicatorCalculatorV2
    
    try:
        calc = IndicatorCalculatorV2()
        indicators = calc.get_available_indicators()
        
        free_indicators = {
            'trend': ['MA5', 'MA10', 'MA20', 'BOLL'],
            'oscillator': ['RSI']
        }
        
        pro_indicators = indicators
        
        return jsonify({
            'success': True,
            'free_version': free_indicators,
            'pro_version': pro_indicators,
            'total_free': sum(len(v) for v in free_indicators.values()),
            'total_pro': sum(len(v) for v in pro_indicators.values()),
            'customizable_params': IndicatorCalculatorV2.get_customizable_params(),
            'disclaimer': '所有指标均为客观数值计算，不构成投资建议。'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/api/indicators/sources', methods=['GET'])
def get_data_source_status():
    """
    获取数据源健康状态
    
    :return: 数据源状态信息
    """
    health = online_manager.get_source_health()
    stats = online_manager.get_stats()

    active_count = sum(1 for h in health.values() if h['status'] == 'active')

    return jsonify({
        'success': True,
        'mode': 'online',
        'sources': health,
        'active_count': active_count,
        'total_count': len(health),
        'stats': stats,
        'request_interval': f"{stats.get('min_interval', 1.5)}秒",
        'timestamp': datetime.now().isoformat()
    })
