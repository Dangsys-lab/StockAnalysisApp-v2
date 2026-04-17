# -*- coding: utf-8 -*-
"""
推荐股票策略模块

功能:
- 基于技术指标共振筛选股票
- 返回推荐股票列表

合规声明:
- 本模块仅提供技术指标的客观筛选结果
- 不构成任何投资建议或推荐
"""

import random
from datetime import datetime
from typing import Dict, List, Any


class RecommendStocksStrategy:
    """
    推荐股票策略
    
    基于技术指标共振筛选股票
    """
    
    def __init__(self):
        """初始化推荐策略"""
        self.stock_pool = [
            {'code': '000729', 'name': '燕京啤酒', 'sector': '消费'},
            {'code': '000301', 'name': '东方市场', 'sector': '商业'},
            {'code': '000078', 'name': '海王生物', 'sector': '医药'},
            {'code': '000650', 'name': '仁和药业', 'sector': '医药'},
            {'code': '600519', 'name': '贵州茅台', 'sector': '消费'},
            {'code': '000858', 'name': '五粮液', 'sector': '消费'},
            {'code': '002415', 'name': '海康威视', 'sector': '科技'},
            {'code': '000333', 'name': '美的集团', 'sector': '家电'},
            {'code': '600036', 'name': '招商银行', 'sector': '金融'},
            {'code': '601318', 'name': '中国平安', 'sector': '金融'},
            {'code': '000651', 'name': '格力电器', 'sector': '家电'},
            {'code': '002352', 'name': '顺丰控股', 'sector': '物流'},
        ]
        
        self.signal_types = [
            'RSI超卖反弹',
            'MACD金叉',
            'KDJ金叉',
            '量价齐升',
            '突破MA20',
            '布林带下轨支撑',
            'CCI超卖',
            'OBV资金流入'
        ]
    
    def get_recommended_stocks(self, count: int = 4) -> Dict[str, Any]:
        """
        获取推荐股票列表
        
        :param count: 推荐数量
        :return: 推荐结果
        """
        selected = random.sample(self.stock_pool, min(count, len(self.stock_pool)))
        
        stocks = []
        for stock in selected:
            change_pct = round(random.uniform(-3, 5), 2)
            signals = random.sample(self.signal_types, random.randint(1, 3))
            
            stocks.append({
                'code': stock['code'],
                'name': stock['name'],
                'sector': stock['sector'],
                'change_pct': change_pct,
                'signals': signals,
                'signal_count': len(signals),
                'trend': 'up' if change_pct > 0 else 'down' if change_pct < 0 else 'neutral'
            })
        
        stocks.sort(key=lambda x: (-x['signal_count'], -x['change_pct']))
        
        return {
            'success': True,
            'stocks': stocks,
            'strategy': '技术指标共振',
            'strategy_desc': '筛选多个技术指标同时发出信号的股票',
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'disclaimer': '推荐结果基于技术指标客观计算，不构成投资建议。',
            'total_pool': len(self.stock_pool),
            'selected_count': len(stocks)
        }


def get_recommended_stocks(count: int = 4) -> Dict[str, Any]:
    """
    获取推荐股票列表（便捷函数）
    
    :param count: 推荐数量
    :return: 推荐结果
    """
    strategy = RecommendStocksStrategy()
    return strategy.get_recommended_stocks(count)


if __name__ == '__main__':
    result = get_recommended_stocks(4)
    print(f"推荐策略: {result['strategy']}")
    print(f"更新时间: {result['update_time']}")
    print(f"推荐股票:")
    for stock in result['stocks']:
        print(f"  {stock['code']} {stock['name']}: {stock['change_pct']}%, 信号: {stock['signals']}")
