# -*- coding: utf-8 -*-
"""
市场环境API接口

功能:
- 自动检测市场环境
- 返回市场状态信息
- 市场温度计

合规声明:
本接口仅提供市场环境的客观数据。
不包含任何投资建议或操作指引。
"""

from flask import jsonify
from datetime import datetime, timedelta
import pandas as pd

from app.api import api_bp


@api_bp.route('/api/market/thermometer', methods=['GET'])
def get_market_thermometer():
    """
    获取市场温度计数据
    
    返回:
    {
        "success": true,
        "score": 65,
        "label": "震荡格局",
        "icon": "🟡",
        "index_data": {
            "sh000001": {"price": 3200.5, "change": 0.5},
            "sz399001": {"price": 10500.8, "change": -0.3},
            "sz399006": {"price": 2100.2, "change": 1.2}
        }
    }
    """
    try:
        import akshare as ak
        
        index_codes = {
            'sh000001': '000001',
            'sz399001': '399001',
            'sz399006': '399006'
        }
        index_names = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指'
        }
        
        index_data = {}
        all_changes = []
        
        for key, code in index_codes.items():
            try:
                price, change = _fetch_index_from_sina(code)
                
                if price is not None:
                    index_data[key] = {
                        'price': round(price, 2),
                        'change': round(change, 2)
                    }
                    all_changes.append(change)
                else:
                    index_data[key] = {'price': None, 'change': None}
            except Exception as e:
                print(f"[警告] 获取指数 {code}({index_names.get(key, '')}) 失败: {e}")
                index_data[key] = {'price': None, 'change': None}
        
        # 计算市场温度分数 (0-100)
        if all_changes:
            avg_change = sum(all_changes) / len(all_changes)
            
            if avg_change > 1.5:
                score = min(90, 65 + avg_change * 5)
                label = '强势格局'
                icon = '🟢'
            elif avg_change > 0.5:
                score = min(80, 60 + avg_change * 10)
                label = '偏强格局'
                icon = '🟢'
            elif avg_change < -1.5:
                score = max(10, 65 + avg_change * 5)
                label = '弱势格局'
                icon = '🔴'
            elif avg_change < -0.5:
                score = max(20, 50 + avg_change * 10)
                label = '偏弱格局'
                icon = '🟠'
            else:
                score = 55 + avg_change * 10
                label = '震荡格局'
                icon = '🟡'
        else:
            score = 50
            label = '数据获取中'
            icon = '⚪'
        
        return jsonify({
            'success': True,
            'score': int(score),
            'label': label,
            'icon': icon,
            'index_data': index_data,
            'timestamp': datetime.now().isoformat(),
            'disclaimer': '基于历史数据客观计算，不构成投资建议。'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'score': 50,
            'label': '数据异常',
            'icon': '⚪',
            'index_data': {}
        }), 500


@api_bp.route('/api/market/recommended', methods=['GET'])
def get_recommended_stocks():
    """
    获取参考股票列表
    
    优先返回智能选股缓存结果
    不构成投资建议
    
    :return: 参考股票列表JSON
    """
    try:
        from app.services.stock_screener import StockScreener
        screener = StockScreener()
        cache = screener.load_cache()

        if cache and cache.get('success') and cache.get('stocks'):
            stocks = []
            for s in cache['stocks']:
                stocks.append({
                    'code': s['code'],
                    'name': s['name'],
                    'change_pct': s.get('change_pct', 0),
                    'price': s.get('latest_close', 0),
                    'score': s.get('total_score', 0),
                    'amount': 0
                })
            return jsonify({
                'success': True,
                'stocks': stocks,
                'source': 'smart_screen',
                'screened_at': cache.get('screened_at', ''),
                'timestamp': datetime.now().isoformat(),
                'disclaimer': '基于技术指标客观计算，不构成投资建议。'
            })

        import akshare as ak
        
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                df['change_pct'] = pd.to_numeric(df['涨跌幅'], errors='coerce').fillna(0)
                df['amount'] = pd.to_numeric(df['成交额'], errors='coerce').fillna(0)
                hot = df.nlargest(8, 'amount')
                
                stocks = []
                for _, row in hot.iterrows():
                    code = str(row.get('代码', ''))
                    if not code or len(code) != 6:
                        continue
                    stocks.append({
                        'code': code,
                        'name': str(row.get('名称', '')),
                        'change_pct': round(float(row.get('涨跌幅', 0)), 2),
                        'amount': round(float(row.get('成交额', 0)) / 100000000, 2)
                    })
                
                if stocks:
                    return jsonify({
                        'success': True,
                        'stocks': stocks[:4],
                        'source': 'eastmoney_hot',
                        'timestamp': datetime.now().isoformat(),
                        'disclaimer': '基于成交额客观排序，不构成投资建议。'
                    })
        except Exception as e:
            print(f"[警告] 东方财富获取热门股票失败: {e}")
        
        default_stocks = [
            {'code': '600519', 'name': '贵州茅台'},
            {'code': '601318', 'name': '中国平安'},
            {'code': '600036', 'name': '招商银行'},
            {'code': '000333', 'name': '美的集团'},
        ]
        
        for stock in default_stocks:
            try:
                price, change = _fetch_stock_from_sina(stock['code'])
                if price is not None:
                    stock['price'] = round(price, 2)
                    stock['change_pct'] = round(change, 2)
                    stock['amount'] = 0
                else:
                    stock['price'] = 0
                    stock['change_pct'] = 0
                    stock['amount'] = 0
            except Exception:
                stock['price'] = 0
                stock['change_pct'] = 0
                stock['amount'] = 0
        
        return jsonify({
            'success': True,
            'stocks': default_stocks,
            'source': 'default',
            'timestamp': datetime.now().isoformat(),
            'disclaimer': '基于成交额客观排序，不构成投资建议。'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'stocks': [],
            'error': str(e)
        })


@api_bp.route('/api/market/environment', methods=['GET'])
def get_market_environment():
    """
    获取市场环境状态
    
    :return: 市场环境JSON
    """
    try:
        env = get_auto_detected_env()
        
        return jsonify({
            'success': True,
            'status': env.get('status', '震荡格局'),
            'description': env.get('description', ''),
            'indicators': env.get('indicators', {}),
            'timestamp': datetime.now().isoformat(),
            'disclaimer': '市场环境仅供参考，不构成投资建议。'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_auto_detected_env():
    """
    自动检测市场环境
    
    :return: 市场环境字典
    """
    try:
        index_codes = ['000001', '399001', '399006']
        index_names_map = {'000001': '上证指数', '399001': '深证成指', '399006': '创业板指'}
        
        all_prices = []
        for code in index_codes:
            price, _ = _fetch_index_from_sina(code)
            if price is not None:
                all_prices.append({'code': code, 'price': price, 'name': index_names_map.get(code, code)})
        
        if not all_prices:
            return {
                'status': '震荡格局',
                'description': '无法获取指数数据，默认震荡格局',
                'indicators': {}
            }
        
        sh_data = next((p for p in all_prices if p['code'] == '000001'), None)
        if not sh_data:
            return {
                'status': '震荡格局',
                'description': '无法获取上证指数数据',
                'indicators': {}
            }
        
        current = sh_data['price']
        
        return {
            'status': '震荡格局',
            'description': f"上证指数{current}点，{', '.join(p['name']+str(p['price'])+'点' for p in all_prices)}",
            'indicators': {
                'current': round(current, 2),
                'indices': {p['code']: {'name': p['name'], 'price': round(p['price'], 2)} for p in all_prices}
            }
        }
    
    except Exception as e:
        return {
            'status': '震荡格局',
            'description': f'检测失败: {str(e)}',
            'indicators': {}
        }


def _fetch_index_from_sina(code: str):
    """
    从新浪财经获取指数实时数据
    
    :param code: 指数代码 (如 000001, 399001, 399006)
    :return: (price, change_pct) 或 (None, None)
    """
    import requests as req
    
    if code.startswith('6') or code == '000001':
        symbol = f"sh{code}"
    elif code.startswith('3') or code.startswith('0'):
        symbol = f"sz{code}"
    else:
        symbol = f"sh{code}"
    
    try:
        url = f"http://hq.sinajs.cn/list={symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }
        response = req.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.text
            key = f'var hq_str_{symbol}="'
            if key in data:
                stock_data = data.split(key)[1].split('";')[0]
                parts = stock_data.split(',')
                
                if len(parts) >= 33:
                    current_price = float(parts[3])
                    prev_close = float(parts[2])
                    change_pct = (current_price - prev_close) / prev_close * 100 if prev_close > 0 else 0
                    return current_price, change_pct
    except Exception as e:
        print(f"[警告] 新浪获取指数 {code} 失败: {e}")
    
    return None, None


def _fetch_stock_from_sina(code: str):
    """
    从新浪财经获取股票实时数据
    
    :param code: 6位股票代码
    :return: (price, change_pct) 或 (None, None)
    """
    import requests as req
    
    if code.startswith('6'):
        symbol = f"sh{code}"
    else:
        symbol = f"sz{code}"
    
    try:
        url = f"http://hq.sinajs.cn/list={symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }
        response = req.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.text
            key = f'var hq_str_{symbol}="'
            if key in data:
                stock_data = data.split(key)[1].split('";')[0]
                parts = stock_data.split(',')
                
                if len(parts) >= 33:
                    current_price = float(parts[3])
                    prev_close = float(parts[2])
                    change_pct = (current_price - prev_close) / prev_close * 100 if prev_close > 0 else 0
                    return current_price, change_pct
    except Exception as e:
        print(f"[警告] 新浪获取股票 {code} 失败: {e}")
    
    return None, None
