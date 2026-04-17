# -*- coding: utf-8 -*-
"""
市场环境与动态阈值API（增强版）

v2.1 更新内容:
✅ 请求频率限制（防止频繁查询）
✅ 响应缓存（市场环境变化慢，适合缓存）
✅ 错误处理增强（备用数据兜底）

合规声明:
本接口仅提供市场技术形态的客观数据分析结果。
所有输出为基于历史数据的计算值，不构成任何投资建议。
"""

from flask import request, jsonify
from datetime import datetime
import pandas as pd
import numpy as np

from . import api_bp
from app.core.adaptive import MarketEnvironmentDetector, AdaptiveThresholdManager
from app.core.api_middleware import rate_limit, cache_response


@api_bp.route('/api/market/environment', methods=['GET'])
@rate_limit('market')
@cache_response('medium')
def get_market_environment():
    """
    获取当前市场环境状态（带缓存，15分钟刷新）

    新增特性:
    - 限流：每分钟最多30次请求
    - 缓存：相同参数15分钟内返回缓存

    :return: 市场环境检测结果JSON
    """
    try:
        lookback = int(request.args.get('lookback', 60))
        index_code = request.args.get('index', 'sh000001')

        data_reader = get_data_reader()

        df = data_reader.get_daily_data(
            index_code,
            start_date=(datetime.now() - pd.Timedelta(days=lookback*2)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        if df.empty:
            return jsonify({
                'success': False,
                'message': f'未找到指数{index_code}的数据',
                'fallback': generate_fallback_environment(),
                '_cached': False,
                'disclaimer': '数据获取失败，使用默认值。'
            }), 200

        data_dict = {
            'close': df['close'].tolist(),
            'high': df['high'].tolist() if 'high' in df.columns else None,
            'low': df['low'].tolist() if 'low' in df.columns else None,
            'volume': df['volume'].tolist() if 'volume' in df.columns else None
        }

        detector = MarketEnvironmentDetector()
        result = detector.detect(data_dict, lookback)

        manager = AdaptiveThresholdManager()
        thresholds = manager.get_thresholds(result['status'])

        result['thresholds'] = thresholds['all_thresholds']
        result['index_code'] = index_code
        result['_cached'] = False

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取市场环境时发生错误',
            'fallback': generate_fallback_environment(),
            'disclaimer': '服务暂时不可用，使用默认值。'
        }), 500


@api_bp.route('/api/market/thresholds', methods=['GET'])
@rate_limit('market')
@cache_response('long')
def get_adaptive_thresholds():
    """
    获取指定指标的自适应阈值配置（长期缓存，1小时刷新）

    阈值配置变化很慢，适合长时间缓存

    :return: 阈值配置JSON
    """
    try:
        market_env = request.args.get('environment', 'auto')
        indicator_name = request.args.get('indicator')

        manager = AdaptiveThresholdManager()

        if market_env == 'auto':
            env_result = get_auto_detected_env()
            market_env = env_result.get('status', 'oscillation')

        result = manager.get_thresholds(market_env, indicator_name)
        result['detection_method'] = 'auto' if request.args.get('environment') == 'auto' else 'manual'
        result['_cached'] = False

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取阈值配置时发生错误',
            'disclaimer': '服务暂时不可用。'
        }), 500


@api_bp.route('/api/market/thermometer', methods=['GET'])
@rate_limit('market')
@cache_response('short')
def get_market_thermometer():
    """
    获取市场温度计数据（前端可视化用）

    短期缓存5分钟，保证一定的实时性

    :return: 温度计数据JSON
    """
    try:
        detector = MarketEnvironmentDetector()
        manager = AdaptiveThresholdManager()

        env_result = get_auto_detected_env()

        status_labels = {
            'strong': {'zh': '强势格局', 'en': 'Strong', 'color': '#FF6B6B', 'icon': '🔴'},
            'oscillation': {'zh': '震荡格局', 'en': 'Oscillation', 'color': '#FFE66D', 'icon': '🟡'},
            'weak': {'zh': '弱势格局', 'en': 'Weak', 'color': '#4ECDC4', 'icon': '🟢'}
        }

        status_info = status_labels.get(env_result['status'], status_labels['oscillation'])

        # 获取指数数据
        index_data = get_index_prices()

        thermometer_data = {
            'success': True,
            'status': env_result['status'],
            'label': status_info['zh'],
            'label_en': status_info['en'],
            'icon': status_info['icon'],
            'color': status_info['color'],
            'score': env_result['score'],
            'score_percent': min(max(env_result['score'], 0), 100),
            'detail_scores': env_result.get('detail_scores', {}),
            'threshold_summary': {
                'rsi_overbought': manager.get_thresholds(
                    env_result['status'], 'rsi'
                )['thresholds']['overbought'],
                'rsi_oversold': manager.get_thresholds(
                    env_result['status'], 'rsi'
                )['thresholds']['oversold']
            },
            'index_data': index_data,
            'update_time': env_result.get('detection_time', ''),
            '_cached': False,
            'disclaimer': '市场温度计基于历史数据客观计算，不构成投资建议。'
        }

        return jsonify(thermometer_data)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取市场温度计数据时发生错误',
            'fallback': {
                'status': 'oscillation',
                'label': '震荡格局',
                'score': 50,
                '_cached': False,
                'disclaimer': '使用默认值，不构成投资建议。'
            }
        }), 200


def get_auto_detected_env():
    """自动检测市场环境"""
    try:
        from app.core.adaptive import MarketEnvironmentDetector
        detector = MarketEnvironmentDetector()

        data_reader = get_data_reader()
        df = data_reader.get_daily_data(
            'sh000001',
            start_date=(datetime.now() - pd.Timedelta(days=120)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        if not df.empty:
            data_dict = {
                'close': df['close'].tolist() if 'close' in df.columns else [],
                'high': df['high'].tolist() if 'high' in df.columns else [c * 1.01 for c in df['close'].tolist()],
                'low': df['low'].tolist() if 'low' in df.columns else [c * 0.99 for c in df['close'].tolist()],
                'volume': df['volume'].tolist() if 'volume' in df.columns else [10000] * len(df)
            }

            # 确保数据有效
            if data_dict['close']:
                return detector.detect(data_dict, 60)

        return generate_fallback_environment()

    except Exception as e:
        print(f"自动检测市场环境失败: {e}")
        return generate_fallback_environment()


def generate_fallback_environment():
    """生成备用环境数据"""
    return {
        'success': True,
        'status': 'oscillation',
        'label': '震荡格局',
        'score': 50.0,
        'detail_scores': {
            'trend_strength': 50.0,
            'momentum': 50.0,
            'volatility': 50.0,
            'volume_confirm': 50.0
        },
        'is_fallback': True,
        'disclaimer': '当前使用默认值，建议稍后刷新获取最新数据。'
    }


def get_data_reader():
    """获取数据读取器实例"""
    try:
        from app.services.data_service import DataService
        return DataService().get_data_reader()
    except ImportError:
        class SimpleDataReader:
            def get_daily_data(self, code, start_date=None, end_date=None):
                import os
                try:
                    from pytdx.reader import TdxDailyBarReader
                    reader = TdxDailyBarReader()

                    market = 'sh' if code.startswith(('6', '9')) else 'sz'
                    prefix = market
                    base_path = r"C:\new_tdx\vipdoc"
                    file_path = os.path.join(base_path, market, 'lday', f"{prefix}{code}.day")

                    if not os.path.exists(file_path):
                        return pd.DataFrame()

                    df = reader.get_df(file_path)
                    df = df.sort_index()

                    if start_date:
                        df = df[df.index >= pd.Timestamp(start_date)]
                    if end_date:
                        df = df[df.index <= pd.Timestamp(end_date)]

                    return df
                except Exception as e:
                    print(f"数据读取失败: {e}")
                    return pd.DataFrame()

        return SimpleDataReader()


def get_index_prices():
    """
    获取主要指数的实时价格
    
    :return: 指数数据字典
    """
    try:
        import requests
        
        # 指数代码（新浪格式需要完整前缀）
        indices = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指'
        }
        
        result = {}
        
        # 批量请求指数数据
        codes = ','.join(indices.keys())
        url = f"http://hq.sinajs.cn/list={codes}"
        headers = {
            'Referer': 'https://finance.sina.com.cn/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'gbk'
            text = response.text
            
            # 解析返回数据
            for line in text.split(';'):
                if not line.strip():
                    continue
                    
                # 提取代码和数据
                if 'var hq_str_' in line:
                    code_part = line.split('hq_str_')[1].split('=')[0]
                    data_part = line.split('"')[1] if '"' in line else ''
                    
                    if code_part in indices and data_part:
                        data = data_part.split(',')
                        if len(data) >= 6:
                            price = float(data[3]) if data[3] else 0
                            prev_close = float(data[2]) if data[2] else price
                            change_pct = ((price / prev_close) - 1) * 100 if prev_close else 0
                            
                            result[code_part] = {
                                'name': indices[code_part],
                                'price': round(price, 2) if price else '--',
                                'change_pct': round(change_pct, 2)
                            }
        except Exception as e:
            print(f"获取指数数据失败: {e}")
        
        # 填充未获取到的数据
        for code, name in indices.items():
            if code not in result:
                result[code] = {
                    'name': name,
                    'price': '--',
                    'change_pct': 0
                }
        
        return result
        
    except Exception as e:
        print(f"获取指数数据失败: {e}")
        return {
            'sh000001': {'name': '上证指数', 'price': '--', 'change_pct': 0},
            'sz399001': {'name': '深证成指', 'price': '--', 'change_pct': 0},
            'sz399006': {'name': '创业板指', 'price': '--', 'change_pct': 0}
        }


if __name__ == '__main__':
    print("市场环境API模块（增强版）已加载")
    print("可用端点:")
    print("  GET /api/market/environment - 获取市场环境（限流+中期缓存）")
    print("  GET /api/market/thresholds - 获取自适应阈值（限流+长期缓存）")
    print("  GET /api/market/thermometer - 获取市场温度计（限流+短期缓存）")
    print("  GET /api/market/recommended - 获取推荐股票（限流+中期缓存）")


@api_bp.route('/api/market/recommended', methods=['GET'])
@rate_limit('market')
@cache_response('medium')
def get_recommended_stocks():
    """
    获取推荐股票列表（中期缓存，15分钟刷新）

    基于技术指标共振筛选股票

    :return: 推荐股票列表JSON
    """
    try:
        from app.core.recommend_stocks import get_recommended_stocks as get_stocks
        
        result = get_stocks(count=4)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取推荐股票失败',
            'stocks': []
        }), 500
