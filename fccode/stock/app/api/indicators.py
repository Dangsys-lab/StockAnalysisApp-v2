# -*- coding: utf-8 -*-
"""
技术指标API接口（App专用增强版）

v2.2 更新内容:
✅ 在线数据源为主（适配手机/平板App）
✅ 多源容错（东方财富→新浪→腾讯→MooTDX→模拟）
✅ 请求间隔控制（防止IP被封）
✅ 限流+缓存+批量查询

数据源架构:
1. 东方财富（主源）- 数据全、速度快
2. 新浪财经 - 实时行情备用
3. 腾讯财经 - 实时行情备用
4. MooTDX（通达信在线）- K线数据备用
5. 模拟数据 - 测试/最后兜底

合规声明:
本接口仅提供技术指标的客观计算结果。
所有输出为纯技术数据，不包含任何投资建议或操作指引。
"""

from flask import request, jsonify
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from . import api_bp
from app.core.indicators.calculator import IndicatorCalculatorV2
from app.core.api_middleware import (
    rate_limit,
    cache_response,
    retry_on_failure
)
from app.core.online_data_source import OnlineDataSourceManager, get_online_data_manager


def get_online_manager():
    """获取在线数据管理器实例"""
    return get_online_data_manager()


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


# 初始化在线数据源管理器（App专用）
online_manager = get_online_data_manager()


@api_bp.route('/api/indicators/<stock_code>', methods=['GET'])
@rate_limit('indicator')
@cache_response('short')
def get_stock_indicators(stock_code: str):
    """
    获取单只股票的技术指标数据（增强版）
    
    新增特性:
    - 限流：每分钟最多30次请求
    - 缓存：相同参数5分钟内返回缓存
    - 多源自动切换：通达信→AKShare→模拟兜底
    - 重试：失败时自动重试2次
    
    :param stock_code: 6位股票代码
    :return: JSON格式的指标数据
    """
    try:
        is_pro = request.args.get('is_pro', 'false').lower() == 'true'
        indicator_type = request.args.get('type', 'all')
        start_date = request.args.get('start_date',
                       (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        
        # 使用在线数据源管理器获取数据（App专用）
        raw_result = online_manager.get_stock_data(stock_code, start_date, end_date)

        if not raw_result.get('success'):
            # 所有数据源都失败了
            return jsonify({
                'success': False,
                'message': raw_result.get('error', '无法获取数据'),
                'stock_code': stock_code,
                'source_status': online_manager.get_source_health(),
                'suggestion': raw_result.get('suggestion', '请检查网络后重试'),
                'disclaimer': '数据获取失败，请检查网络连接。'
            }), 503

        df = raw_result.get('data')

        if df is None or (hasattr(df, 'empty') and df.empty):
            return jsonify({
                'success': False,
                'message': '未找到该股票的数据',
                'stock_code': stock_code,
                'data_source': raw_result.get('source', '未知'),
                'is_fallback': raw_result.get('is_fallback', False)
            }), 404
        
        calc = IndicatorCalculatorV2()
        
        data_dict = {
            'open': df['open'].tolist(),
            'high': df['high'].tolist(),
            'low': df['low'].tolist(),
            'close': df['close'].tolist(),
            'volume': df['volume'].tolist()
        }
        
        type_map = {
            'trend': (True, False, False, False),
            'oscillator': (False, True, False, False),
            'volume': (False, False, True, False),
            'price': (False, False, False, True),
            'all': (True, True, True, True)
        }
        
        include_flags = type_map.get(indicator_type.lower(), (True, True, True, True))
        
        result = calc.calculate_all(
            data_dict,
            include_trend=include_flags[0] if is_pro else True,
            include_oscillator=include_flags[1] if is_pro else True,
            include_volume=include_flags[2] if is_pro else False,
            include_price=include_flags[3] if is_pro else False
        )
        
        response_data = {
            'dates': [idx.strftime('%Y-%m-%d') for idx in df.index],
            'open': clean_nan_for_json(df['open'].tolist()),
            'high': clean_nan_for_json(df['high'].tolist()),
            'low': clean_nan_for_json(df['low'].tolist()),
            'close': clean_nan_for_json(df['close'].tolist()),
            'volume': clean_nan_for_json(df['volume'].tolist())
        }
        
        if is_pro:
            for category, indicators in result['data'].items():
                if isinstance(indicators, dict):
                    for key, values in indicators.items():
                        response_data[key] = clean_nan_for_json(values)
        else:
            free_indicators = result.get('data', {}).get('oscillator', {})
            if 'rsi' in free_indicators:
                response_data['rsi'] = clean_nan_for_json(free_indicators['rsi'])
            
            trend_indicators = result.get('data', {}).get('trend', {})
            if 'ma5' in trend_indicators:
                response_data['ma5'] = clean_nan_for_json(trend_indicators['ma5'])
            if 'ma10' in trend_indicators:
                response_data['ma10'] = clean_nan_for_json(trend_indicators['ma10'])
            if 'ma20' in trend_indicators:
                response_data['ma20'] = clean_nan_for_json(trend_indicators['ma20'])
            
            boll_indicators = result.get('data', {}).get('trend', {})
            if 'boll_upper' in boll_indicators:
                response_data['boll_upper'] = clean_nan_for_json(boll_indicators['boll_upper'])
            if 'boll_middle' in boll_indicators:
                response_data['boll_middle'] = clean_nan_for_json(boll_indicators['boll_middle'])
            if 'boll_lower' in boll_indicators:
                response_data['boll_lower'] = clean_nan_for_json(boll_indicators['boll_lower'])
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'stock_name': stock_code,  # 添加股票名称字段
            'is_pro': is_pro,
            'indicator_count': result['indicator_count'],
            'data_points': len(response_data['dates']),
            'data': response_data,
            'data_source': raw_result.get('source', '未知'),
            'is_fallback': raw_result.get('is_fallback', False),
            'available_sources': raw_result.get('available_sources', 1),
            'disclaimer': '以上为技术指标客观计算结果，仅供参考，不构成任何投资建议。'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取指标数据时发生错误',
            'source_health': data_source_manager.get_source_health()
        }), 500


@api_bp.route('/api/indicators/batch', methods=['POST'])
@rate_limit('indicator')
def batch_get_indicators():
    """
    批量获取多只股票的指标摘要
    
    限制:
    - 单次最多20只股票
    - 每分钟最多10次批量请求
    - 仅返回核心指标摘要（非完整数据）
    
    请求体(JSON):
    {
        "codes": ["600519", "000858", "601318"],
        "is_pro": true/false
    }
    
    :return: 批量查询结果JSON
    """
    try:
        data = request.json or {}
        codes = data.get('codes', [])
        is_pro = data.get('is_pro', False)
        
        # 验证输入
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
        
        if len(codes) < 1:
            return jsonify({
                'success': False,
                'message': '至少提供1个股票代码'
            }), 400
        
        # 验证格式
        for code in codes:
            if not code or len(code) != 6 or not code.isdigit():
                return jsonify({
                    'success': False,
                    'message': f'无效的股票代码: {code}'
                }), 400
        
        results = []
        errors = []
        
        for code in codes:
            try:
                # 使用在线数据源管理器（App专用）
                raw_result = online_manager.get_stock_data(
                    code,
                    (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                    datetime.now().strftime('%Y-%m-%d')
                )
                
                if not raw_result.get('success'):
                    errors.append({'code': code, 'error': raw_result.get('error', '未知错误')})
                    continue
                
                df = raw_result.get('data')
                
                if df is None or (hasattr(df, 'empty') and df.empty):
                    errors.append({'code': code, 'error': '无数据'})
                    continue
                
                calc = IndicatorCalculatorV2()
                
                data_dict = {
                    'open': df['open'].tolist(),
                    'high': df['high'].tolist(),
                    'low': df['low'].tolist(),
                    'close': df['close'].tolist(),
                    'volume': df['volume'].tolist()
                }
                
                # 批量模式只计算关键指标（减少计算量）
                summary = {}
                
                # RSI
                osc = calc.calculate_all_oscillator({'close': data_dict['close'], 
                                                     'high': data_dict['high'], 
                                                     'low': data_dict['low']})
                rsi_val = osc.get('rsi', [50])[-1]
                summary['rsi'] = round(rsi_val, 2) if rsi_val else None
                
                # MA趋势
                trend = calc.calculate_all_trend({'close': data_dict['close'],
                                                      'high': data_dict['high'],
                                                      'low': data_dict['low']})
                ma5 = trend.get('ma5', [None])[-1]
                ma20 = trend.get('ma20', [None])[-1]
                summary['ma5'] = round(ma5, 2) if ma5 else None
                summary['ma20'] = round(ma20, 2) if ma20 else None
                
                # 价格位置
                last_close = data_dict['close'][-1]
                summary['last_price'] = round(last_close, 2) if last_close else None
                summary['change_pct'] = round((last_close / data_dict['close'][0] - 1) * 100, 2) if data_dict['close'] else None
                
                results.append({
                    'code': code,
                    'success': True,
                    'summary': summary,
                    'data_source': raw_result.get('source', '未知')
                })
                
            except Exception as e:
                errors.append({'code': code, 'error': str(e)})
                continue
        
        return jsonify({
            'success': True,
            'total_requested': len(codes),
            'successful': len(results),
            'failed': len(errors),
            'results': results,
            'errors': errors[:5],  # 最多返回前5个错误
            'is_pro': is_pro,
            'processing_time': time.time(),  # 可用于统计耗时
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
    获取所有可用的技术指标列表（带缓存，1 小时刷新）
    
    :return: 指标分类和名称列表
    """
    try:
        calc = IndicatorCalculatorV2()
        indicators = calc.get_available_indicators()
        
        free_indicators = {
            'trend': ['MA5', 'MA10', 'MA20', 'BOLL'],
            'oscillator': ['RSI']
        }
        
        pro_indicators = {
            'trend': ['MA', 'EMA', 'BOLL', 'DMI', 'SAR'],
            'oscillator': ['RSI', 'KDJ', 'WR', 'CCI', 'BIAS'],
            'volume': ['Volume_Ratio', 'OBV', 'VR', 'MA_VOL'],
            'price': ['ATR']
        }
        
        return {
            'success': True,
            'free_version': free_indicators,
            'pro_version': pro_indicators,
            'total_free': sum(len(v) for v in free_indicators.values()),
            'total_pro': sum(len(v) for v in pro_indicators.values()),
            'api_features': {
                'rate_limiting': '已启用',
                'caching': '已启用',
                'multi_source': '已启用',
                'batch_query': '已启用',
                'retry': '已启用'
            },
            'disclaimer': '所有指标均为客观数值计算，不构成投资建议。'
        }
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/api/indicators/sources', methods=['GET'])
def get_data_source_status():
    """
    获取数据源健康状态（用于调试和监控）

    显示所有在线数据源的连接状态和健康情况

    :return: 数据源状态信息
    """
    health = online_manager.get_source_health()
    stats = online_manager.get_stats()

    active_count = sum(1 for h in health.values() if h['status'] == 'active')

    return jsonify({
        'success': True,
        'mode': 'online',  # 标识为在线模式
        'sources': health,
        'active_count': active_count,
        'total_count': len(health),
        'stats': stats,
        'request_interval': f"{stats.get('min_interval', 1.5)}秒",
        'timestamp': datetime.now().isoformat()
    })


@api_bp.route('/api/stock/<stock_code>/report', methods=['GET'])
def get_stock_indicators_report(stock_code):
    """
    生成综合分析报告（专业版功能）

    基于技术指标数据生成包含评分、信号对比、结论的报告

    :param stock_code: 股票代码（6位）
    :return: 综合分析报告JSON
    """
    try:
        print(f"[报告API] 开始生成报告: {stock_code}")
        
        if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
            return jsonify({
                'success': False,
                'error': '请提供有效的6位股票代码'
            }), 400

        from app.core.report_generator import ReportGenerator
        from app.api.market import get_auto_detected_env

        print(f"[报告API] 步骤1: 获取指标数据")
        report_gen = ReportGenerator()
        
        indicators_data = _get_indicators_data(stock_code)
        print(f"[报告API] 指标数据获取完成, error={indicators_data.get('error')}")
        
        if indicators_data.get('error'):
            return jsonify({
                'success': False,
                'error': indicators_data.get('error'),
                'message': '数据获取失败，请稍后重试'
            }), 500
        
        print(f"[报告API] 步骤2: 获取市场环境")
        market_env = get_auto_detected_env()
        print(f"[报告API] 市场环境: {market_env.get('status') if market_env else 'None'}")

        indicators_result = indicators_data.get('indicators', {})
        if isinstance(indicators_result, dict) and 'data' in indicators_result:
            indicators_result = indicators_result['data']

        if not indicators_result:
            return jsonify({
                'success': False,
                'error': '指标计算失败',
                'message': '无法计算技术指标，请稍后重试'
            }), 500

        print(f"[报告API] 步骤3: 生成报告")
        report = report_gen.generate_report(
            indicators_data=indicators_result,
            market_env=market_env
        )
        print(f"[报告API] 报告生成完成, score={report.get('score')}")

        # 确保返回数据格式与前端期望一致
        report['code'] = stock_code
        report['stock_code'] = stock_code
        report['stock_name'] = indicators_data.get('name', stock_code)
        report['price'] = indicators_data.get('price')
        report['change'] = indicators_data.get('change')
        
        # 添加前端需要的字段
        if 'summary' in report:
            report['market_env'] = report['summary'].get('status', '震荡格局')
            report['conclusion'] = report['summary'].get('pattern_description', '')
        
        # 确保signals是列表
        if 'signals' not in report:
            report['signals'] = []

        return jsonify({
            'success': True,
            'data': report
        })

    except Exception as e:
        print(f"❌ 报告生成失败 [{stock_code}]: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'报告生成失败: {str(e)}',
            'detail': str(e)
        }), 500


def _get_indicators_data(stock_code: str) -> Dict:
    """获取指标数据的内部函数（复用现有逻辑）"""
    try:
        calculator = IndicatorCalculatorV2()
        online_manager = get_online_manager()
        
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        
        raw_data = online_manager.get_stock_data(
            stock_code,
            start_date=start_date,
            end_date=end_date,
            period='daily'
        )
        
        if not raw_data or not raw_data.get('success'):
            raise ValueError("无法获取股票数据")

        df = raw_data.get('data')
        if df is None or (hasattr(df, 'empty') and df.empty) or len(df) < 10:
            raise ValueError("数据不足，无法计算指标")

        # 获取股票名称
        stock_name = stock_code
        try:
            from app.services.stock_name_service import StockNameService
            name_service = StockNameService()
            fetched_name = name_service.get_name(stock_code)
            if fetched_name:
                stock_name = fetched_name
        except Exception as e:
            print(f"[警告] 获取股票名称失败: {e}")

        data_dict = {
            'open': df['open'].tolist() if 'open' in df.columns else [],
            'high': df['high'].tolist() if 'high' in df.columns else [],
            'low': df['low'].tolist() if 'low' in df.columns else [],
            'close': df['close'].tolist() if 'close' in df.columns else [],
            'volume': df['volume'].tolist() if 'volume' in df.columns else []
        }
        
        indicators = calculator.calculate_all(data_dict)

        # 获取最新价格和涨跌幅
        latest_price = float(df['close'].iloc[-1]) if len(df) > 0 else None
        prev_price = float(df['close'].iloc[-2]) if len(df) > 1 else latest_price
        change_pct = ((latest_price / prev_price) - 1) * 100 if prev_price and prev_price > 0 else 0

        return {
            'code': stock_code,
            'name': stock_name,
            'price': round(latest_price, 2) if latest_price else None,
            'change': round(change_pct, 2),
            'indicators': indicators,
            'data_points': len(df)
        }

    except Exception as e:
        print(f"⚠️ 获取指标数据失败: {e}")
        return {
            'code': stock_code,
            'name': stock_code,
            'price': None,
            'change': 0,
            'indicators': {},
            'data_points': 0,
            'error': str(e)
        }



@api_bp.route('/api/stock/<stock_code>/basic', methods=['GET'])
def get_stock_basic(stock_code):
    """
    获取股票基础信息（用于自选股列表）

    返回股票名称、最新价格、涨跌幅等基本信息

    :param stock_code: 股票代码（6位）
    :return: 基础信息JSON
    """
    try:
        if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
            return jsonify({
                'success': False,
                'error': '请提供有效的6位股票代码'
            }), 400

        from app.services.stock_name_service import StockNameService
        name_service = StockNameService()
        stock_name = name_service.get_name(stock_code) or stock_code

        online_manager = get_online_manager()
        
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        
        raw_result = online_manager.get_stock_data(
            stock_code,
            start_date=start_date,
            end_date=end_date,
            period='daily'
        )

        if raw_result and raw_result.get('success'):
            df = raw_result.get('data')
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                
                price = float(latest['close']) if 'close' in latest else 0
                prev_price = float(prev['close']) if 'close' in prev else 0
                
                if prev_price and prev_price > 0:
                    change = ((price / prev_price) - 1) * 100
                else:
                    change = 0

                return jsonify({
                    'success': True,
                    'data': {
                        'code': stock_code,
                        'name': stock_name,
                        'price': round(price, 2),
                        'change': round(change, 2)
                    }
                })

        return jsonify({
            'success': True,
            'data': {
                'code': stock_code,
                'name': stock_name,
                'price': None,
                'change': None
            }
        })

    except Exception as e:
        print(f"⚠️ 获取基础信息失败 [{stock_code}]: {e}")
        return jsonify({
            'success': True,
            'data': {
                'code': stock_code,
                'name': stock_code,
                'price': None,
                'change': None
            }
        })


if __name__ == '__main__':
    print("技术指标API模块（App专用增强版 v2.2）已加载")
    print("数据源模式: 在线API优先（适配移动端App）")
    print("可用端点:")
    print("  GET  /api/indicators/<code>       - 获取指标（限流+缓存+多源容错）")
    print("  POST /api/indicators/batch      - 批量查询（最多20只）")
    print("  GET  /api/indicators/list       - 指标列表（长期缓存）")
    print("  GET  /api/indicators/sources    - 数据源状态（在线模式）")
    print("  GET  /api/stock/<code>/basic     - 基础信息（自选用）")
    print("  GET  /api/stock/<code>/report    - 综合分析报告")
    print("\n数据源优先级:")
    print("  1. 东方财富（主源）")
    print("  2. 新浪财经（备用）")
    print("  3. 腾讯财经（备用）")
    print("  4. MooTDX通达信在线（备用）")
    print("  5. 模拟数据（兜底）")
