# -*- coding: utf-8 -*-
"""
摆动类技术指标计算器 - 3.0版本（支持自定义参数）

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
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union


class OscillatorIndicators:
    """
    摆动类指标计算器
    
    支持自定义参数配置
    """
    
    DEFAULT_RSI_PERIOD = 14
    DEFAULT_KDJ_N = 9
    DEFAULT_KDJ_M1 = 3
    DEFAULT_KDJ_M2 = 3
    DEFAULT_WR_PERIOD = 14
    DEFAULT_CCI_PERIOD = 20
    DEFAULT_BIAS_PERIODS = [6, 12, 24]
    
    def __init__(self, params: Dict = None):
        """
        初始化摆动类指标计算器
        
        :param params: 用户自定义参数字典
        """
        self.params = params or {}
        self.name = "摆动类指标"
        self.description = "用于判断超买超卖状态和动量变化"
    
    def _get_param(self, key: str, default):
        """获取参数值（优先用户自定义）"""
        return self.params.get(key, default)
    
    def calculate_rsi(
        self,
        prices: Union[List[float], pd.Series],
        period: int = None
    ) -> List[float]:
        """
        计算相对强弱指标(RSI)
        
        RSI取值范围0-100:
        - RSI > 70: 超买区域
        - RSI < 30: 超卖区域
        - RSI 30-70: 中性区间
        
        :param prices: 价格序列（通常为收盘价）
        :param period: 计算周期（可自定义，默认14）
        :return: RSI值列表（0-100之间）
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        use_period = period or self._get_param('rsi_period', self.DEFAULT_RSI_PERIOD)
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=use_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=use_period).mean()
        
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50).tolist()
    
    def calculate_kdj(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        n: int = None,
        m1: int = None,
        m2: int = None
    ) -> Dict[str, List[float]]:
        """
        计算随机指标(KDJ)
        
        KDJ系统包含三条曲线:
        - K线: 快速随机指标
        - D线: 慢速随机指标
        - J线: 附加线（3K-2D），更敏感
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param n: RSV计算周期（可自定义，默认9）
        :param m1: K值平滑系数（可自定义，默认3）
        :param m2: D值平滑系数（可自定义，默认3）
        :return: 包含k/d/j的字典
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        use_n = n or self._get_param('kdj_n', self.DEFAULT_KDJ_N)
        use_m1 = m1 or self._get_param('kdj_m1', self.DEFAULT_KDJ_M1)
        use_m2 = m2 or self._get_param('kdj_m2', self.DEFAULT_KDJ_M2)
        
        low_n = lows.rolling(window=use_n).min()
        high_n = highs.rolling(window=use_n).max()
        
        rsv = ((closes - low_n) / (high_n - low_n) * 100).fillna(50)
        
        k = rsv.ewm(alpha=1/use_m1, adjust=False).mean()
        d = k.ewm(alpha=1/use_m2, adjust=False).mean()
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
        period: int = None
    ) -> List[float]:
        """
        计算威廉指标(WR/Williams %R)
        
        WR取值范围-100到0:
        - WR > -20: 超买区域
        - WR < -80: 超卖区域
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param period: 计算周期（可自定义，默认14）
        :return: WR值列表（-100到0之间）
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        use_period = period or self._get_param('wr_period', self.DEFAULT_WR_PERIOD)
        
        high_n = highs.rolling(window=use_period).max()
        low_n = lows.rolling(window=use_period).min()
        
        wr = -100 * (high_n - closes) / (high_n - low_n + 0.0001)
        
        return wr.fillna(-50).tolist()
    
    def calculate_cci(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        period: int = None
    ) -> List[float]:
        """
        计算顺势指标(CCI)
        
        CCI用于识别价格偏离统计常态的程度:
        - CCI > 100: 价格可能高于正常水平
        - CCI < -100: 价格可能低于正常水平
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param period: 计算周期（可自定义，默认20）
        :return: CCI值列表
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        use_period = period or self._get_param('cci_period', self.DEFAULT_CCI_PERIOD)
        
        tp = (highs + lows + closes) / 3
        ma_tp = tp.rolling(window=use_period).mean()
        md = tp.rolling(window=use_period).apply(lambda x: np.abs(x - x.mean()).mean())
        
        cci = (tp - ma_tp) / (0.015 * md + 0.0001)
        
        return cci.fillna(0).tolist()
    
    def calculate_bias(
        self,
        prices: Union[List[float], pd.Series],
        periods: List[int] = None
    ) -> Dict[str, List[float]]:
        """
        计算乖离率(BIAS)
        
        BIAS衡量当前价格偏离均线的程度:
        - 正BIAS: 价格在均线之上
        - 负BIAS: 价格在均线之下
        
        :param prices: 价格序列
        :param periods: 计算周期列表（可自定义）
        :return: 各周期BIAS值的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        use_periods = periods or self._get_param('bias_periods', self.DEFAULT_BIAS_PERIODS)
        
        result = {}
        for period in use_periods:
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
