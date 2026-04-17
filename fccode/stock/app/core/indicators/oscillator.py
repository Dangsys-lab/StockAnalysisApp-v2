# -*- coding: utf-8 -*-
"""
摆动类技术指标计算器

包含指标:
- RSI (Relative Strength Index): 相对强弱指标
- KDJ: 随机指标（K/D/J线）
- WR (Williams %R): 威廉指标
- CCI (Commodity Channel Index): 顺势指标
- BIAS: 乖离率

合规说明:
本模块仅计算摆动类技术指标的数学数值。
输出结果用于判断超买超卖状态，不构成任何投资建议。
数值仅反映当前技术形态的客观位置。

使用示例:
    >>> from app.core.indicators.oscillator import OscillatorIndicators
    >>> calc = OscillatorIndicators()
    >>> rsi = calc.calculate_rsi(prices, period=14)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union


class OscillatorIndicators:
    """
    摆动类指标计算器
    
    提供各类震荡和超买超卖判断的技术指标计算功能
    """
    
    def __init__(self):
        self.name = "摆动类指标"
        self.description = "用于判断超买超卖状态和动量变化"
    
    def calculate_rsi(
        self,
        prices: Union[List[float], pd.Series],
        period: int = 14
    ) -> List[float]:
        """
        计算相对强弱指标(RSI)
        
        RSI取值范围0-100:
        - RSI > 70: 超买区域（价格可能偏高）
        - RSI < 30: 超卖区域（价格可能偏低）
        - RSI 30-70: 中性区间
        
        :param prices: 价格序列（通常为收盘价）
        :param period: 计算周期，默认14
        :return: RSI值列表（0-100之间）
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50).tolist()
    
    def calculate_kdj(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        n: int = 9,
        m1: int = 3,
        m2: int = 3
    ) -> Dict[str, List[float]]:
        """
        计算随机指标(KDJ)
        
        KDJ系统包含三条曲线:
        - K线: 快速随机指标
        - D线: 慢速随机指标
        - J线: 附加线（3K-2D），更敏感
        
        常用判断:
        - J > 100: 可能处于超买区
        - J < 0: 可能处于超卖区
        - K上穿D: 金叉信号（多头动能增强）
        - K下穿D: 死叉信号（空头动能增强）
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param n: RSV计算周期，默认9
        :param m1: K值平滑系数，默认3
        :param m2: D值平滑系数，默认3
        :return: 包含k/d/j的字典
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        low_n = lows.rolling(window=n).min()
        high_n = highs.rolling(window=n).max()
        
        rsv = ((closes - low_n) / (high_n - low_n) * 100).fillna(50)
        
        k = rsv.ewm(alpha=1/m1, adjust=False).mean()
        d = k.ewm(alpha=1/m2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return {
            'k': k.tolist(),
            'd': d.tolist(),
            'j': j.tolist(),
            'rsv': rsv.tolist()
        }
    
    def calculate_wr(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        period: int = 14
    ) -> List[float]:
        """
        计算威廉指标(WR/Williams %R)
        
        WR取值范围-100到0:
        - WR > -20: 超买区域
        - WR < -80: 超卖区域
        - 与RSI方向相反（WR越接近0表示越强）
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param period: 计算周期，默认14
        :return: WR值列表（-100到0之间）
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        high_n = highs.rolling(window=period).max()
        low_n = lows.rolling(window=period).min()
        
        wr = -100 * (high_n - closes) / (high_n - low_n + 0.0001)
        
        return wr.fillna(-50).tolist()
    
    def calculate_cci(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        period: int = 20
    ) -> List[float]:
        """
        计算顺势指标(CCI)
        
        CCI用于识别价格偏离统计常态的程度:
        - CCI > 100: 价格可能高于正常水平
        - CCI < -100: 价格可能低于正常水平
        - CCI 0附近: 价格处于正常范围
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param period: 计算周期，默认20
        :return: CCI值列表
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        tp = (highs + lows + closes) / 3
        ma_tp = tp.rolling(window=period).mean()
        md = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        
        cci = (tp - ma_tp) / (0.015 * md + 0.0001)
        
        return cci.fillna(0).tolist()
    
    def calculate_bias(
        self,
        prices: Union[List[float], pd.Series],
        periods: List[int] = [6, 12, 24]
    ) -> Dict[str, List[float]]:
        """
        计算乖离率(BIAS)
        
        BIAS衡量当前价格偏离均线的程度:
        - 正BIAS: 价格在均线之上
        - 负BIAS: 价格在均线之下
        - 绝对值越大，偏离程度越高
        
        :param prices: 价格序列
        :param periods: 计算周期列表，默认[6, 12, 24]
        :return: 各周期BIAS值的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        result = {}
        for period in periods:
            key = f'bias{period}'
            ma = prices.rolling(window=period).mean()
            bias = (prices - ma) / ma * 100
            result[key] = bias.fillna(0).tolist()
        
        return result
    
    def calculate_all_oscillator(
        self,
        data: Dict[str, Union[List[float], pd.Series]]
    ) -> Dict[str, Union[List[float], Dict]]:
        """
        批量计算所有摆动类指标
        
        :param data: 包含high/low/close键的字典
        :return: 所有摆动类指标的汇总字典
        """
        closes = data.get('close', data.get('closes', []))
        highs = data.get('high', data.get('highs', []))
        lows = data.get('low', data.get('lows', []))
        
        result = {}
        
        result['rsi'] = self.calculate_rsi(closes)
        result.update(self.calculate_kdj(highs, lows, closes))
        result['wr'] = self.calculate_wr(highs, lows, closes)
        result['cci'] = self.calculate_cci(highs, lows, closes)
        result.update(self.calculate_bias(closes))
        
        return result


if __name__ == '__main__':
    print("=" * 60)
    print("摆动类指标计算器测试")
    print("=" * 60)
    
    calc = OscillatorIndicators()
    
    test_closes = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11,
                   12, 13, 14, 15, 16, 17, 16, 15, 14, 13]
    test_highs = [x + 0.5 for x in test_closes]
    test_lows = [x - 0.5 for x in test_closes]
    
    print("\n--- RSI 计算 ---")
    rsi = calc.calculate_rsi(test_closes)
    print(f"RSI(14) 最后5个值: {rsi[-5:]}")
    
    print("\n--- KDJ 计算 ---")
    kdj = calc.calculate_kdj(test_highs, test_lows, test_closes)
    print(f"K 最后5个值: {kdj['k'][-5:]}")
    print(f"D 最后5个值: {kdj['d'][-5:]}")
    print(f"J 最后5个值: {kdj['j'][-5:]}")
    
    print("\n--- WR 计算 ---")
    wr = calc.calculate_wr(test_highs, test_lows, test_closes)
    print(f"WR(14) 最后5个值: {wr[-5:]}")
    
    print("\n--- CCI 计算 ---")
    cci = calc.calculate_cci(test_highs, test_lows, test_closes)
    print(f"CCI(20) 最后5个值: {cci[-5:]}")
    
    print("\n--- BIAS 计算 ---")
    bias = calc.calculate_bias(test_closes)
    for key, values in bias.items():
        print(f"{key} 最后5个值: {values[-5:]}")
    
    print("\n✅ 摆动类指标计算器正常工作")
