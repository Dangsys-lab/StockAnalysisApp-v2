# -*- coding: utf-8 -*-
"""
趋势类技术指标计算器

包含指标:
- MA (Moving Average): 移动平均线
- EMA (Exponential MA): 指数移动平均线
- BOLL (Bollinger Bands): 布林带
- DMI (Directional Movement Index): 趋向指标
- SAR (Parabolic SAR): 抛物线转向指标

合规说明:
本模块仅计算趋势类技术指标的数学数值。
输出结果为客观数据，不包含任何投资建议或操作指引。

使用示例:
    >>> from app.core.indicators.trend import TrendIndicators
    >>> calc = TrendIndicators()
    >>> result = calc.calculate_boll(prices, period=20, std_dev=2)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union


class TrendIndicators:
    """
    趋势类指标计算器
    
    提供各类趋势跟踪和方向判断的技术指标计算功能
    """
    
    def __init__(self):
        self.name = "趋势类指标"
        self.description = "用于识别和跟踪价格趋势方向"
    
    def calculate_ma(
        self,
        prices: Union[List[float], pd.Series],
        periods: List[int] = [5, 10, 20, 60]
    ) -> Dict[str, List[float]]:
        """
        计算简单移动平均线(MA)
        
        :param prices: 价格序列
        :param periods: 计算周期列表，默认[5, 10, 20, 60]
        :return: 各周期MA值的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        result = {}
        for period in periods:
            key = f'ma{period}'
            result[key] = prices.rolling(window=period).mean().tolist()
        
        return result
    
    def calculate_ema(
        self,
        prices: Union[List[float], pd.Series],
        periods: List[int] = [5, 10, 20, 60]
    ) -> Dict[str, List[float]]:
        """
        计算指数移动平均线(EMA)
        
        EMA对近期价格赋予更高权重，比MA更灵敏
        
        :param prices: 价格序列
        :param periods: 计算周期列表
        :return: 各周期EMA值的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        result = {}
        for period in periods:
            key = f'ema{period}'
            result[key] = prices.ewm(span=period, adjust=False).mean().tolist()
        
        return result
    
    def calculate_boll(
        self,
        prices: Union[List[float], pd.Series],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, List[float]]:
        """
        计算布林带(BOLL)
        
        布林带由三条轨道组成:
        - 上轨(Upper): 中轨 + K倍标准差
        - 中轨(Middle): MA(period)
        - 下轨(Lower): 中轨 - K倍标准差
        
        :param prices: 价格序列（通常为收盘价）
        :param period: 计算周期，默认20
        :param std_dev: 标准差倍数，默认2.0
        :return: 包含upper/middle/lower的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {
            'boll_upper': upper.tolist(),
            'boll_middle': middle.tolist(),
            'boll_lower': lower.tolist(),
            'boll_std': std.tolist()
        }
    
    def calculate_dmi(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        period: int = 14
    ) -> Dict[str, List[float]]:
        """
        计算趋向指标(DMI/ADX)
        
        DMI系统包含三个指标:
        - PDI(+DI): 正方向指标
        - MDI(-DI): 负方向指标
        - ADX: 平均趋向指标，衡量趋势强度
        
        ADX > 25 通常表示存在明确趋势
        ADX < 20 表示市场处于震荡状态
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param period: 计算周期，默认14
        :return: 包含pdi/mdi/adx的字典
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        high_diff = highs.diff()
        low_diff = lows.diff()
        
        plus_dm = pd.Series(np.where(
            (high_diff > low_diff) & (high_diff > 0),
            high_diff,
            0.0
        ))
        
        minus_dm = pd.Series(np.where(
            (low_diff > high_diff) & (low_diff > 0),
            low_diff,
            0.0
        ))
        
        tr = pd.concat([
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs()
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)
        adx = dx.rolling(window=period).mean()
        
        return {
            'pdi': plus_di.fillna(0).tolist(),
            'mdi': minus_di.fillna(0).tolist(),
            'adx': adx.fillna(0).tolist()
        }
    
    def calculate_sar(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        af_start: float = 0.02,
        af_step: float = 0.02,
        af_max: float = 0.2
    ) -> List[float]:
        """
        计算抛物线转向指标(SAR)
        
        SAR是一种跟随趋势的止损转向指标:
        - 价格在SAR上方 → 多头信号
        - 价格在SAR下方 → 空头信号
        - 价格穿越SAR → 可能发生趋势反转
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param af_start: 初始加速因子，默认0.02
        :param af_step: 加速因子步长，默认0.02
        :param af_max: 最大加速因子，默认0.2
        :return: SAR值列表
        """
        if isinstance(highs, list):
            highs = np.array(highs)
            lows = np.array(lows)
            closes = np.array(closes)
        
        n = len(closes)
        sar = np.zeros(n)
        ep = np.zeros(n)
        af = np.zeros(n)
        is_bull = True
        
        sar[0] = lows[0]
        ep[0] = highs[0]
        af[0] = af_start
        
        for i in range(1, n):
            if is_bull:
                sar[i] = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
                sar[i] = min(sar[i], lows[i-1])
                sar[i] = min(sar[i], lows[i-2]) if i >= 2 else sar[i]
                
                if highs[i] > ep[i-1]:
                    ep[i] = highs[i]
                    af[i] = min(af[i-1] + af_step, af_max)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]
                
                if lows[i] < sar[i]:
                    is_bull = False
                    sar[i] = ep[i]
                    ep[i] = lows[i]
                    af[i] = af_start
            else:
                sar[i] = sar[i-1] + af[i-1] * (sar[i-1] - ep[i-1])
                sar[i] = max(sar[i], highs[i-1])
                sar[i] = max(sar[i], highs[i-2]) if i >= 2 else sar[i]
                
                if lows[i] < ep[i-1]:
                    ep[i] = lows[i]
                    af[i] = min(af[i-1] + af_step, af_max)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]
                
                if highs[i] > sar[i]:
                    is_bull = True
                    sar[i] = ep[i]
                    ep[i] = highs[i]
                    af[i] = af_start
        
        return sar.tolist()
    
    def calculate_all_trend(
        self,
        data: Dict[str, Union[List[float], pd.Series]],
        ma_periods: List[int] = [5, 10, 20, 60]
    ) -> Dict[str, Union[List[float], Dict]]:
        """
        批量计算所有趋势类指标
        
        :param data: 包含high/low/close键的字典或DataFrame
        :param ma_periods: MA计算周期
        :return: 所有趋势类指标的汇总字典
        """
        closes = data.get('close', data.get('closes', []))
        highs = data.get('high', data.get('highs', []))
        lows = data.get('low', data.get('lows', []))
        
        result = {}
        
        result.update(self.calculate_ma(closes, ma_periods))
        result.update(self.calculate_ema(closes, ma_periods))
        result.update(self.calculate_boll(closes))
        
        if len(highs) > 0 and len(lows) > 0:
            result.update(self.calculate_dmi(highs, lows, closes))
            result['sar'] = self.calculate_sar(highs, lows, closes)
        
        return result


if __name__ == '__main__':
    import sys
    
    print("=" * 60)
    print("趋势类指标计算器测试")
    print("=" * 60)
    
    calc = TrendIndicators()
    
    test_data = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 
                 12, 13, 14, 15, 16, 17, 16, 15, 14, 13]
    
    print("\n测试数据:", test_data[:5], "...")
    
    print("\n--- MA 计算 ---")
    ma_result = calc.calculate_ma(test_data, [5, 10])
    for key, values in ma_result.items():
        print(f"{key}: {values[-3:]}")
    
    print("\n--- BOLL 计算 ---")
    boll_result = calc.calculate_boll(test_data)
    print(f"上轨最后3个值: {boll_result['boll_upper'][-3:]}")
    print(f"中轨最后3个值: {boll_result['boll_middle'][-3:]}")
    print(f"下轨最后3个值: {boll_result['boll_lower'][-3:]}")
    
    print("\n✅ 趋势类指标计算器正常工作")
