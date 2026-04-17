# -*- coding: utf-8 -*-
"""
市场环境感知模块

功能:
- 判断当前市场环境（强势/震荡/弱势）
- 基于多维度数据分析
- 输出客观的环境状态描述

合规声明:
本模块仅提供市场技术形态的客观数据分析。
输出结果用于调整指标阈值参考，不构成任何投资建议。
环境判断基于历史数据计算，不预测未来走势。

使用示例:
    >>> from app.core.adaptive import MarketEnvironmentDetector
    >>> detector = MarketEnvironmentDetector()
    >>> env = detector.detect(index_data)
    >>> print(env['status'])  # 'strong' / 'oscillation' / 'weak'
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta


class MarketEnvironmentDetector:
    """
    市场环境检测器
    
    通过分析指数的多维度数据，判断当前市场所处的技术状态
    
    判断维度:
    1. 趋势强度: MA均线斜率和排列状态
    2. 动量变化: 价格变动幅度和持续性
    3. 波动率水平: ATR或历史波动率
    4. 成交量配合: 量价关系
    """
    
    def __init__(self):
        self.name = "市场环境感知系统"
        self.version = "1.0.0"
        
        self.env_weights = {
            'trend_strength': 0.30,
            'momentum': 0.25,
            'volatility': 0.20,
            'volume_confirm': 0.15,
            'breadth': 0.10
        }
    
    def detect(
        self,
        data: Dict[str, Union[List[float], pd.Series]],
        lookback: int = 60
    ) -> Dict[str, Any]:
        """
        检测当前市场环境
        
        :param data: 包含high/low/close/volume键的字典（通常为指数数据）
        :param lookback: 回看周期（交易日），默认60
        :return: 环境检测结果字典
        """
        closes = data.get('close', data.get('closes', []))
        highs = data.get('high', data.get('highs', []))
        lows = data.get('low', data.get('lows', []))
        volumes = data.get('volume', data.get('volumes', []))
        
        if isinstance(closes, list):
            closes = pd.Series(closes)
        if isinstance(highs, list):
            highs = pd.Series(highs)
        if isinstance(lows, list):
            lows = pd.Series(lows)
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        scores = {}
        
        scores['trend_strength'] = self._calc_trend_score(closes)
        scores['momentum'] = self._calc_momentum_score(closes, lookback)
        scores['volatility'] = self._calc_volatility_score(highs, lows, closes)
        scores['volume_confirm'] = self._calc_volume_score(closes, volumes)
        
        weighted_sum = sum(
            score * self.env_weights.get(key, 0)
            for key, score in scores.items()
        )
        
        if weighted_sum >= 65:
            status = 'strong'
            label = '强势格局'
        elif weighted_sum >= 35:
            status = 'oscillation'
            label = '震荡格局'
        else:
            status = 'weak'
            label = '弱势格局'
        
        return {
            'success': True,
            'status': status,
            'label': label,
            'score': round(weighted_sum, 2),
            'detail_scores': {k: round(v, 2) for k, v in scores.items()},
            'lookback_period': lookback,
            'detection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'disclaimer': '本结果基于历史数据客观计算，不构成任何投资建议。'
        }
    
    def _calc_trend_score(self, closes: pd.Series) -> float:
        """
        计算趋势强度得分(0-100)
        
        :param closes: 收盘价序列
        :return: 趋势得分
        """
        if len(closes) < 20:
            return 50.0
        
        ma5 = closes.rolling(window=5).mean()
        ma10 = closes.rolling(window=10).mean()
        ma20 = closes.rolling(window=20).mean()
        ma60 = closes.rolling(window=60).mean() if len(closes) >= 60 else ma20
        
        last_close = closes.iloc[-1]
        
        alignment_score = 0
        if last_close > ma5.iloc[-1]:
            alignment_score += 25
        if last_close > ma10.iloc[-1]:
            alignment_score += 25
        if last_close > ma20.iloc[-1]:
            alignment_score += 25
        if len(closes) >= 60 and last_close > ma60.iloc[-1]:
            alignment_score += 25
        
        recent_ma5 = ma5.iloc[-5:]
        if len(recent_ma5) > 1:
            ma_slope = (recent_ma5.iloc[-1] - recent_ma5.iloc[0]) / recent_ma5.iloc[0] * 100
            slope_score = min(max(ma_slope * 100 + 50, 0), 100)
        else:
            slope_score = 50
        
        return (alignment_score * 0.6 + slope_score * 0.4)
    
    def _calc_momentum_score(self, closes: pd.Series, lookback: int) -> float:
        """
        计算动量得分(0-100)
        
        :param closes: 收盘价序列
        :param lookback: 回看周期
        :return: 动量得分
        """
        if len(closes) < lookback:
            return 50.0
        
        current_price = closes.iloc[-1]
        price_lookback_ago = closes.iloc[-lookback]
        
        if price_lookback_ago == 0:
            return 50.0
        
        total_return = (current_price - price_lookback_ago) / price_lookback_ago * 100
        
        if total_return > 15:
            momentum_score = 85 + min(total_return - 15, 15)
        elif total_return > 5:
            momentum_score = 70 + (total_return - 5) * 3
        elif total_return > -5:
            momentum_score = 50 + total_return * 4
        elif total_return > -15:
            momentum_score = 30 + (total_return + 5) * 4
        else:
            momentum_score = max(0, 15 + total_return)
        
        return min(max(momentum_score, 0), 100)
    
    def _calc_volatility_score(self, highs, lows, closes) -> float:
        """
        计算波动率得分(0-100)
        
        高波动率在强势市场中可能意味着活跃度提升
        在弱势市场中可能意味着恐慌性抛售
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :return: 波动率得分
        """
        if isinstance(highs, pd.Series) and len(highs) > 20:
            tr_list = []
            for i in range(1, len(highs)):
                tr1 = highs.iloc[i] - lows.iloc[i]
                tr2 = abs(highs.iloc[i] - closes.iloc[i-1])
                tr3 = abs(lows.iloc[i] - closes.iloc[i-1])
                tr_list.append(max(tr1, tr2, tr3))
            
            atr_series = pd.Series(tr_list).rolling(window=14).mean()
            recent_atr = atr_series.iloc[-5:].mean()
            
            if closes.iloc[-1] != 0:
                atr_pct = (recent_atr / closes.iloc[-1]) * 100
            else:
                atr_pct = 5
            
            if atr_pct < 1.5:
                vol_score = 40 + (1.5 - atr_pct) * 20
            elif atr_pct < 3:
                vol_score = 55 + (3 - atr_pct) * 10
            elif atr_pct < 5:
                vol_score = 70 - (atr_pct - 3) * 7.5
            else:
                vol_score = max(20, 55 - (atr_pct - 5) * 5)
            
            return min(max(vol_score, 0), 100)
        
        return 50.0
    
    def _calc_volume_score(self, closes, volumes) -> float:
        """
        计算成交量确认得分(0-100)
        
        :param closes: 收盘价序列
        :param volumes: 成交量序列
        :return: 成交量确认得分
        """
        if isinstance(volumes, pd.Series) and len(volumes) > 6 and isinstance(closes, pd.Series):
            recent_vol = volumes.iloc[-1]
            avg_vol_5d = volumes.iloc[-6:-1].mean()
            
            if avg_vol_5d > 0:
                vol_ratio = recent_vol / avg_vol_5d
            else:
                vol_ratio = 1.0
            
            price_change = closes.iloc[-1] - closes.iloc[-2] if len(closes) > 1 else 0
            
            if price_change > 0 and vol_ratio > 1.2:
                vol_score = 75 + min((vol_ratio - 1.2) * 25, 25)
            elif price_change > 0 and vol_ratio >= 0.8:
                vol_score = 60 + (vol_ratio - 0.8) * 75
            elif price_change <= 0 and vol_ratio > 1.5:
                vol_score = 45 + (vol_ratio - 1.5) * 30
            elif price_change <= 0 and vol_ratio >= 0.8:
                vol_score = 40 + (vol_ratio - 0.8) * 25
            else:
                vol_score = 35
            
            return min(max(vol_score, 0), 100)
        
        return 50.0


class AdaptiveThresholdManager:
    """
    自适应阈值管理器
    
    根据市场环境动态调整各指标的阈值参数
    使指标信号更适应当前市场状态
    """
    
    def __init__(self):
        self.name = "自适应阈值管理系统"
        
        self.base_thresholds = {
            'rsi': {
                'overbought': 70,
                'oversold': 30,
                'neutral_high': 55,
                'neutral_low': 45
            },
            'kdj_j': {
                'overbought': 80,
                'oversold': 20
            },
            'wr': {
                'overbought': -20,
                'oversold': -80
            },
            'cci': {
                'overbought': 100,
                'oversold': -100
            },
            'bias': {
                'high': 5,
                'low': -5
            },
            'volume_ratio': {
                'high': 2.0,
                'low': 0.6
            },
            'gain_20d': {
                'high': 0.30,
                'low': -0.10
            }
        }
    
    def get_thresholds(
        self,
        market_env: str,
        indicator_name: str = None
    ) -> Dict[str, Any]:
        """
        获取当前市场环境下适用的阈值配置
        
        :param market_env: 市场环境 ('strong'/'oscillation'/'weak')
        :param indicator_name: 指定指标名称（可选）
        :return: 阈值配置字典
        """
        adjustments = {
            'strong': {
                'rsi': {'overbought': 80, 'oversold': 25},
                'kdj_j': {'overbought': 90, 'oversold': 10},
                'gain_20d': {'high': 0.50, 'low': -0.15}
            },
            'oscillation': {
                'rsi': {'overbought': 72, 'oversold': 28},
                'kdj_j': {'overbought': 82, 'oversold': 18},
                'gain_20d': {'high': 0.28, 'low': -0.12}
            },
            'weak': {
                'rsi': {'overbought': 62, 'oversold': 38},
                'kdj_j': {'overbought': 72, 'oversold': 28},
                'gain_20d': {'high': 0.18, 'low': -0.05}
            }
        }
        
        base = self.base_thresholds.copy()
        adj = adjustments.get(market_env, {})
        
        for ind, thresh in adj.items():
            if ind in base:
                for key, value in thresh.items():
                    if key in base[ind]:
                        base[ind][key] = value
        
        if indicator_name and indicator_name in base:
            return {
                'success': True,
                'market_environment': market_env,
                'indicator': indicator_name,
                'thresholds': base[indicator_name],
                'disclaimer': '阈值为动态调整的参考值，不构成操作建议。'
            }
        
        return {
            'success': True,
            'market_environment': market_env,
            'all_thresholds': base,
            'adjustment_applied': adj,
            'disclaimer': '所有阈值均为动态调整的参考值，不构成任何投资建议。'
        }


if __name__ == '__main__':
    print("=" * 60)
    print("市场环境感知系统测试")
    print("=" * 60)
    
    detector = MarketEnvironmentDetector()
    
    np.random.seed(42)
    n = 120
    base_price = 3000
    prices = [base_price]
    
    trend = 0.002
    for i in range(n - 1):
        noise = np.random.normal(0, 0.015)
        change = trend + noise
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
    
    test_data = {
        'close': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'volume': [int(np.random.uniform(8000, 15000)) for _ in range(n)]
    }
    
    print("\n--- 市场环境检测 ---")
    result = detector.detect(test_data)
    
    print(f"  检测时间: {result['detection_time']}")
    print(f"  环境状态: {result['label']} ({result['status']})")
    print(f"  综合得分: {result['score']}")
    print(f"\n  各维度得分:")
    for key, value in result['detail_scores'].items():
        print(f"    - {key}: {value}")
    
    print("\n--- 自适应阈值测试 ---")
    manager = AdaptiveThresholdManager()
    
    for env in ['strong', 'oscillation', 'weak']:
        thresholds = manager.get_thresholds(env, 'rsi')
        print(f"\n  [{env.upper()}] RSI阈值:")
        print(f"    超买区: > {thresholds['thresholds']['overbought']}")
        print(f"    超卖区: < {thresholds['thresholds']['oversold']}")
        print(f"    中性高: {thresholds['thresholds'].get('neutral_high', '-')}")
        print(f"    中性低: {thresholds['thresholds'].get('neutral_low', '-')}")
    
    print("\n✅ 市场环境感知系统正常工作")
