# -*- coding: utf-8 -*-
"""
成交量类技术指标计算器

包含指标:
- VOL (Volume): 成交量
- OBV (On Balance Volume): 能量潮
- VR (Volume Ratio): 成交量比率
- Volume Ratio (量比): 当日成交量与近期均量的比值

合规说明:
本模块仅计算成交量相关技术指标的数学数值。
输出结果用于分析量价关系，不构成任何投资建议。

使用示例:
    >>> from app.core.indicators.volume import VolumeIndicators
    >>> calc = VolumeIndicators()
    >>> obv = calc.calculate_obv(closes, volumes)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Union


class VolumeIndicators:
    """
    成交量类指标计算器
    
    提供各类成交量和量价关系分析的指标计算功能
    """
    
    def __init__(self):
        self.name = "成交量类指标"
        self.description = "用于分析成交量和量价关系"
    
    def calculate_volume_ratio(
        self,
        volumes: Union[List[float], pd.Series],
        period: int = 5
    ) -> List[float]:
        """
        计算量比(Volume Ratio)
        
        量比 = 当日成交量 / 过去N日平均成交量
        
        量比含义（仅作数据参考）:
        - 量比 > 1.5: 成交量明显放大
        - 量比 < 0.5: 成交量明显萎缩
        - 量比 ≈ 1.0: 成交量正常
        
        :param volumes: 成交量序列
        :param period: 平均成交量计算周期，默认5
        :return: 量比值列表
        """
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        avg_vol = volumes.rolling(window=period).mean()
        ratio = volumes / avg_vol.replace(0, np.nan)
        
        return ratio.fillna(1.0).tolist()
    
    def calculate_obv(
        self,
        closes: Union[List[float], pd.Series],
        volumes: Union[List[float], pd.Series]
    ) -> List[float]:
        """
        计算能量潮(OBV)
        
        OBV通过累计成交量来衡量资金流向:
        - 今日收盘价 > 昨日收盘价 → OBV增加当日成交量
        - 今日收盘价 < 昨日收盘价 → OBV减少当日成交量
        - 收盘价持平 → OBV不变
        
        OBV趋势可用于判断量价配合程度
        
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
        period: int = 26
    ) -> List[float]:
        """
        计算成交量比率(VR)
        
        VR通过比较上涨日和下跌日的成交量来判断市场活跃度:
        - VR > 450: 成交量过热（可能偏高）
        - VR < 70: 成交量低迷（可能偏低）
        - VR 150-250: 正常范围
        
        :param closes: 收盘价序列
        :param volumes: 成交量序列
        :param period: 计算周期，默认26
        :return: VR值列表
        """
        if isinstance(closes, list):
            closes = pd.Series(closes)
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        price_change = closes.diff()
        
        av = pd.Series(np.where(price_change > 0, volumes, 0))
        bv = pd.Series(np.where(price_change < 0, volumes, 0))
        cv = pd.Series(np.where(price_change == 0, volumes, 0))
        
        av_sum = av.rolling(window=period).sum()
        bv_sum = bv.rolling(window=period).sum()
        cv_sum = cv.rolling(window=period).sum()
        
        vr = (av_sum + cv_sum / 2) / (bv_sum + cv_sum / 2) * 100
        
        return vr.fillna(100).tolist()
    
    def calculate_ma_volume(
        self,
        volumes: Union[List[float], pd.Series],
        periods: List[int] = [5, 10, 20]
    ) -> Dict[str, List[float]]:
        """
        计算成交量均线(MAVOL)
        
        :param volumes: 成交量序列
        :param periods: 均线周期列表
        :return: 各周期成交量均线的字典
        """
        if isinstance(volumes, list):
            volumes = pd.Series(volumes)
        
        result = {}
        for period in periods:
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


if __name__ == '__main__':
    print("=" * 60)
    print("成交量类指标计算器测试")
    print("=" * 60)
    
    calc = VolumeIndicators()
    
    test_closes = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11,
                   12, 13, 14, 15, 16, 17, 16, 15, 14, 13]
    test_volumes = [1000, 1200, 1100, 1300, 1400, 1800, 1600, 1200,
                   900, 800, 950, 1100, 1250, 1350, 1500, 1700, 1400,
                   1150, 900, 850]
    
    print("\n--- 量比 计算 ---")
    vratio = calc.calculate_volume_ratio(test_volumes)
    print(f"量比 最后5个值: {vratio[-5:]}")
    
    print("\n--- OBV 计算 ---")
    obv = calc.calculate_obv(test_closes, test_volumes)
    print(f"OBV 最后5个值: {obv[-5:]}")
    
    print("\n--- VR 计算 ---")
    vr = calc.calculate_vr(test_closes, test_volumes)
    print(f"VR 最后5个值: {vr[-5:]}")
    
    print("\n--- 成交量均线 计算 ---")
    ma_vol = calc.calculate_ma_volume(test_volumes)
    for key, values in ma_vol.items():
        print(f"{key} 最后3个值: {values[-3:]}")
    
    print("\n✅ 成交量类指标计算器正常工作")
