# -*- coding: utf-8 -*-
"""
价格形态类技术指标计算器 - 3.0版本（支持自定义参数）

包含指标:
- ATR (Average True Range): 平均真实波幅
- TR (True Range): 真实波幅

合规说明:
本模块仅计算价格波动性相关技术指标的数学数值。
输出结果用于衡量市场波动程度，不构成任何投资建议。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Union


class PriceIndicators:
    """
    价格形态类指标计算器
    
    支持自定义参数配置
    """
    
    DEFAULT_ATR_PERIOD = 14
    
    def __init__(self, params: Dict = None):
        """
        初始化价格形态类指标计算器
        
        :param params: 用户自定义参数字典
        """
        self.params = params or {}
        self.name = "价格形态类指标"
        self.description = "用于衡量价格波动性和形态特征"
    
    def _get_param(self, key: str, default):
        """获取参数值（优先用户自定义）"""
        return self.params.get(key, default)
    
    def calculate_tr(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series]
    ) -> List[float]:
        """
        计算真实波幅(TR)
        
        TR取以下三者的最大值:
        1. 当日最高 - 当日最低
        2. |当日最高 - 昨日收盘|
        3. |当日最低 - 昨日收盘|
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :return: TR值列表
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        tr1 = highs - lows
        tr2 = (highs - closes.shift(1)).abs()
        tr3 = (lows - closes.shift(1)).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.tolist()
    
    def calculate_atr(
        self,
        highs: Union[List[float], pd.Series],
        lows: Union[List[float], pd.Series],
        closes: Union[List[float], pd.Series],
        period: int = None
    ) -> List[float]:
        """
        计算平均真实波幅(ATR)
        
        ATR用于衡量价格波动幅度:
        - ATR升高: 市场波动性增大
        - ATR降低: 市场趋于平稳
        
        :param highs: 最高价序列
        :param lows: 最低价序列
        :param closes: 收盘价序列
        :param period: 计算周期（可自定义，默认14）
        :return: ATR值列表
        """
        if isinstance(highs, list):
            highs = pd.Series(highs)
            lows = pd.Series(lows)
            closes = pd.Series(closes)
        
        use_period = period or self._get_param('atr_period', self.DEFAULT_ATR_PERIOD)
        
        tr = self.calculate_tr(highs, lows, closes)
        tr_series = pd.Series(tr)
        atr = tr_series.rolling(window=use_period).mean()
        
        return atr.fillna(0).tolist()
    
    def calculate_all_price(
        self,
        data: Dict[str, Union[List[float], pd.Series]]
    ) -> Dict[str, List[float]]:
        """
        批量计算所有价格形态类指标
        
        :param data: 包含high/low/close键的字典
        :return: 所有价格形态类指标的汇总字典
        """
        highs = data.get('high', data.get('highs', []))
        lows = data.get('low', data.get('lows', []))
        closes = data.get('close', data.get('closes', []))
        
        result = {}
        result['atr'] = self.calculate_atr(highs, lows, closes)
        result['tr'] = self.calculate_tr(highs, lows, closes)
        
        return result
