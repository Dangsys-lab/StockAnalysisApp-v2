# -*- coding: utf-8 -*-
"""
趋势类技术指标计算器 - 3.0版本（支持自定义参数）

包含指标:
- MA (Moving Average): 移动平均线
- EMA (Exponential MA): 指数移动平均线
- BOLL (Bollinger Bands): 布林带
- DMI (Directional Movement Index): 趋向指标
- SAR (Parabolic SAR): 抛物线转向指标

合规说明:
本模块仅计算趋势类技术指标的数学数值。
输出结果为客观数据，不包含任何投资建议或操作指引。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union


class TrendIndicators:
    """
    趋势类指标计算器
    
    支持自定义参数配置
    """
    
    DEFAULT_MA_PERIODS = [5, 10, 20, 60]
    DEFAULT_BOLL_PERIOD = 20
    DEFAULT_BOLL_STD_DEV = 2.0
    DEFAULT_DMI_PERIOD = 14
    DEFAULT_SAR_AF_START = 0.02
    DEFAULT_SAR_AF_STEP = 0.02
    DEFAULT_SAR_AF_MAX = 0.2
    
    def __init__(self, params: Dict = None):
        """
        初始化趋势类指标计算器
        
        :param params: 用户自定义参数字典
        """
        self.params = params or {}
        self.name = "趋势类指标"
        self.description = "用于识别和跟踪价格趋势方向"
    
    def _get_param(self, key: str, default):
        """获取参数值（优先用户自定义）"""
        return self.params.get(key, default)
    
    def calculate_ma(
        self,
        prices: Union[List[float], pd.Series],
        periods: List[int] = None
    ) -> Dict[str, List[float]]:
        """
        计算简单移动平均线(MA)
        
        :param prices: 价格序列
        :param periods: 计算周期列表（可自定义）
        :return: 各周期MA值的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        use_periods = periods or self._get_param('ma_periods', self.DEFAULT_MA_PERIODS)
        
        result = {}
        for period in use_periods:
            key = f'ma{period}'
            result[key] = prices.rolling(window=period).mean().tolist()
        
        return result
    
    def calculate_ema(
        self,
        prices: Union[List[float], pd.Series],
        periods: List[int] = None
    ) -> Dict[str, List[float]]:
        """
        计算指数移动平均线(EMA)
        
        :param prices: 价格序列
        :param periods: 计算周期列表（可自定义）
        :return: 各周期EMA值的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        use_periods = periods or self._get_param('ema_periods', self.DEFAULT_MA_PERIODS)
        
        result = {}
        for period in use_periods:
            key = f'ema{period}'
            result[key] = prices.ewm(span=period, adjust=False).mean().tolist()
        
        return result
    
    def calculate_boll(
        self,
        prices: Union[List[float], pd.Series],
        period: int = None,
        std_dev: float = None
    ) -> Dict[str, List[float]]:
        """
        计算布林带(BOLL)
        
        :param prices: 价格序列
        :param period: 计算周期（可自定义，默认20）
        :param std_dev: 标准差倍数（可自定义，默认2.0）
        :return: 包含upper/middle/lower的字典
        """
        if isinstance(prices, list):
            prices = pd.Series(prices)
        
        use_period = period or self._get_param('boll_period', self.DEFAULT_BOLL_PERIOD)
        use_std_dev = std_dev or self._get_param('boll_std_dev', self.DEFAULT_BOLL_STD_DEV)
        
        middle = prices.rolling(window=use_period).mean()
        std = prices.rolling(window=use_period).std()
        
        upper = middle + (std * use_std_dev)
        lower = middle - (std * use_std_dev)
        
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
        period: int = None
    ) -> Dict[str, List[float]]:
        """
        计算趋向指标(DMI/ADX)
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param period: 计算周期（可自定义，默认14）
        :return: 包含pdi/mdi/adx的字典
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        use_period = period or self._get_param('dmi_period', self.DEFAULT_DMI_PERIOD)
        
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
        
        atr = tr.rolling(window=use_period).mean()
        plus_di = 100 * (plus_dm.rolling(window=use_period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=use_period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)
        adx = dx.rolling(window=use_period).mean()
        
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
        af_start: float = None,
        af_step: float = None,
        af_max: float = None
    ) -> List[float]:
        """
        计算抛物线转向指标(SAR)
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param af_start: 初始加速因子（可自定义）
        :param af_step: 加速因子步长（可自定义）
        :param af_max: 最大加速因子（可自定义）
        :return: SAR值列表
        """
        if isinstance(highs, list):
            highs = np.array(highs)
            lows = np.array(lows)
            closes = np.array(closes)
        
        use_af_start = af_start or self._get_param('sar_af_start', self.DEFAULT_SAR_AF_START)
        use_af_step = af_step or self._get_param('sar_af_step', self.DEFAULT_SAR_AF_STEP)
        use_af_max = af_max or self._get_param('sar_af_max', self.DEFAULT_SAR_AF_MAX)
        
        n = len(closes)
        sar = np.zeros(n)
        ep = np.zeros(n)
        af = np.zeros(n)
        is_bull = True
        
        sar[0] = lows[0]
        ep[0] = highs[0]
        af[0] = use_af_start
        
        for i in range(1, n):
            if is_bull:
                sar[i] = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
                sar[i] = min(sar[i], lows[i-1])
                sar[i] = min(sar[i], lows[i-2]) if i >= 2 else sar[i]
                
                if highs[i] > ep[i-1]:
                    ep[i] = highs[i]
                    af[i] = min(af[i-1] + use_af_step, use_af_max)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]
                
                if lows[i] < sar[i]:
                    is_bull = False
                    sar[i] = ep[i]
                    ep[i] = lows[i]
                    af[i] = use_af_start
            else:
                sar[i] = sar[i-1] + af[i-1] * (sar[i-1] - ep[i-1])
                sar[i] = max(sar[i], highs[i-1])
                sar[i] = max(sar[i], highs[i-2]) if i >= 2 else sar[i]
                
                if lows[i] < ep[i-1]:
                    ep[i] = lows[i]
                    af[i] = min(af[i-1] + use_af_step, use_af_max)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]
                
                if highs[i] > sar[i]:
                    is_bull = True
                    sar[i] = ep[i]
                    ep[i] = highs[i]
                    af[i] = use_af_start
        
        return sar.tolist()
    
    def calculate_all_trend(
        self,
        data: Dict[str, Union[List[float], pd.Series]],
        ma_periods: List[int] = None
    ) -> Dict[str, Union[List[float], Dict]]:
        """
        批量计算所有趋势类指标
        
        :param data: 包含high/low/close键的字典
        :param ma_periods: MA计算周期（可自定义）
        :return: 所有趋势类指标的汇总字典
        """
        closes = data.get('close', data.get('closes', []))
        highs = data.get('high', data.get('highs', []))
        lows = data.get('low', data.get('lows', []))
        
        result = {}
        
        use_ma_periods = ma_periods or self._get_param('ma_periods', self.DEFAULT_MA_PERIODS)
        
        result.update(self.calculate_ma(closes, use_ma_periods))
        result.update(self.calculate_ema(closes, use_ma_periods))
        result.update(self.calculate_boll(closes))
        
        if len(highs) > 0 and len(lows) > 0:
            result.update(self.calculate_dmi(highs, lows, closes))
            result['sar'] = self.calculate_sar(highs, lows, closes)
        
        return result
