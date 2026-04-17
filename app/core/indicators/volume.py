# -*- coding: utf-8 -*-
"""
成交量类技术指标计算器 - 3.0版本（支持自定义参数）

包含指标:
- VOL (Volume): 成交量
- OBV (On Balance Volume): 能量潮
- VR (Volume Ratio): 成交量比率
- Volume Ratio (量比): 当日成交量与近期均量的比值

合规说明:
本模块仅计算成交量相关技术指标的数学数值。
输出结果用于分析量价关系，不构成任何投资建议。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Union


class VolumeIndicators:
    """
    成交量类指标计算器
    
    支持自定义参数配置
    """
    
    DEFAULT_VOLUME_RATIO_PERIOD = 5
    DEFAULT_VR_PERIOD = 26
    DEFAULT_MA_VOL_PERIODS = [5, 10, 20]
    
    def __init__(self, params: Dict = None):
        """
        初始化成交量类指标计算器
        
        :param params: 用户自定义参数字典
        """
        self.params = params or {}
        self.name = "成交量类指标"
        self.description = "用于分析成交量和量价关系"
    
    def _get_param(self, key: str, default):
        """获取参数值（优先用户自定义）"""
        return self.params.get(key, default)
    
    def calculate_volume_ratio(
        self,
        volumes: Union[List[float], pd.Series],
        period: int = None
    ) -> List[float]:
        """
        计算量比(Volume Ratio)
        
        量比 = 当日成交量 / 过去N日平均成交量
        
        :param volumes: 成交量序列
        :param period: 平均成交量计算周期（可自定义，默认5）
        :return: 量比值列表
        """
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        use_period = period or self._get_param('volume_ratio_period', self.DEFAULT_VOLUME_RATIO_PERIOD)
        
        avg_vol = volumes.rolling(window=use_period).mean()
        ratio = volumes / avg_vol.replace(0, np.nan)
        
        return ratio.fillna(1.0).tolist()
    
    def calculate_obv(
        self,
        closes: Union[List[float], pd.Series],
        volumes: Union[List[float], pd.Series]
    ) -> List[float]:
        """
        计算能量潮(OBV)
        
        OBV通过累计成交量来衡量资金流向
        
        :param closes: 收盘价序列
        :param volumes: 成交量序列
        :return: OBV值列表
        """
        if isinstance(closes, list):
            closes = pd.Series(closes)
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        direction = closes.diff().apply(
            lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
        )
        
        obv = (direction * volumes).cumsum()
        
        return obv.tolist()
    
    def calculate_vr(
        self,
        closes: Union[List[float], pd.Series],
        volumes: Union[List[float], pd.Series],
        period: int = None
    ) -> List[float]:
        """
        计算成交量比率(VR)
        
        :param closes: 收盘价序列
        :param volumes: 成交量序列
        :param period: 计算周期（可自定义，默认26）
        :return: VR值列表
        """
        if isinstance(closes, list):
            closes = pd.Series(closes)
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        use_period = period or self._get_param('vr_period', self.DEFAULT_VR_PERIOD)
        
        price_change = closes.diff()
        
        av = pd.Series(np.where(price_change > 0, volumes, 0))
        bv = pd.Series(np.where(price_change < 0, volumes, 0))
        cv = pd.Series(np.where(price_change == 0, volumes, 0))
        
        av_sum = av.rolling(window=use_period).sum()
        bv_sum = bv.rolling(window=use_period).sum()
        cv_sum = cv.rolling(window=use_period).sum()
        
        vr = (av_sum + cv_sum / 2) / (bv_sum + cv_sum / 2) * 100
        
        return vr.fillna(100).tolist()
    
    def calculate_ma_volume(
        self,
        volumes: Union[List[float], pd.Series],
        periods: List[int] = None
    ) -> Dict[str, List[float]]:
        """
        计算成交量均线(MAVOL)
        
        :param volumes: 成交量序列
        :param periods: 均线周期列表（可自定义）
        :return: 各周期成交量均线的字典
        """
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        use_periods = periods or self._get_param('ma_vol_periods', self.DEFAULT_MA_VOL_PERIODS)
        
        result = {}
        for period in use_periods:
            key = f'ma_vol{period}'
            result[key] = volumes.rolling(window=period).mean().tolist()
        
        return result
    
    def calculate_all_volume(
        self,
        data: Dict[str, Union[List[float], pd.Series]]
    ) -> Dict[str, Union[List[float], Dict]]:
        """
        批量计算所有成交量类指标
        
        :param data: 包含close/volume键的字典
        :return: 所有成交量类指标的汇总字典
        """
        closes = data.get('close', data.get('closes', []))
        volumes = data.get('volume', data.get('volumes', []))
        
        result = {}
        
        result['volume_ratio'] = self.calculate_volume_ratio(volumes)
        result['obv'] = self.calculate_obv(closes, volumes)
        result['vr'] = self.calculate_vr(closes, volumes)
        result.update(self.calculate_ma_volume(volumes))
        
        return result
