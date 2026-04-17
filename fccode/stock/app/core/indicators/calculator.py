# -*- coding: utf-8 -*-
"""
统一指标计算器 - 2.0版本

功能:
- 整合所有技术指标计算（15+个指标）
- 提供统一的批量计算接口
- 支持按类别筛选输出

合规声明:
本模块仅提供技术指标的数学计算功能。
所有输出为客观数值，不包含任何投资建议或操作指引。
用户需自主解读数据并做出决策。

使用示例:
    >>> from app.core.indicators import IndicatorCalculatorV2
    >>> calc = IndicatorCalculatorV2()
    >>> result = calc.calculate_all(data)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any

from .trend import TrendIndicators
from .oscillator import OscillatorIndicators
from .volume import VolumeIndicators
from .price import PriceIndicators


class IndicatorCalculatorV2:
    """
    统一技术指标计算器（2.0版）
    
    支持的指标分类:
    - 趋势类: MA/EMA/BOLL/DMI/SAR (5个)
    - 摆动类: RSI/KDJ/WR/CCI/BIAS (5个)
    - 成交量类: VOL/OBV/VR/量比/MAVOL (5个)
    - 价格形态: ATR/TR (2个)
    
    总计: 17个独立指标（含子指标更多）
    """
    
    def __init__(self):
        self.trend_calc = TrendIndicators()
        self.oscillator_calc = OscillatorIndicators()
        self.volume_calc = VolumeIndicators()
        self.price_calc = PriceIndicators()
        
        self.name = "统一指标计算器 V2.0"
        self.version = "2.0.0"
        self.total_indicators = 17
    
    def calculate_all(
        self,
        data: Dict[str, Union[List[float], pd.Series]],
        include_trend: bool = True,
        include_oscillator: bool = True,
        include_volume: bool = True,
        include_price: bool = True
    ) -> Dict[str, Any]:
        """
        批量计算所有技术指标
        
        :param data: 包含open/high/low/close/volume键的字典
        :param include_trend: 是否计算趋势类指标，默认True
        :param include_oscillator: 是否计算摆动类指标，默认True
        :param include_volume: 是否计算成交量类指标，默认True
        :param include_price: 是否计算价格形态类指标，默认True
        :return: 所有指标值的汇总字典
        """
        result = {
            'success': True,
            'indicator_count': 0,
            'data': {}
        }
        
        closes = data.get('close', data.get('closes', []))
        highs = data.get('high', data.get('highs', []))
        lows = data.get('low', data.get('lows', []))
        volumes = data.get('volume', data.get('volumes', []))
        
        if include_trend and len(closes) > 0:
            trend_data = {'close': closes}
            if len(highs) > 0 and len(lows) > 0:
                trend_data.update({'high': highs, 'low': lows})
            result['data']['trend'] = self.trend_calc.calculate_all_trend(trend_data)
            result['indicator_count'] += 5
        
        if include_oscillator and len(closes) > 0 and len(highs) > 0 and len(lows) > 0:
            osc_data = {
                'close': closes,
                'high': highs,
                'low': lows
            }
            result['data']['oscillator'] = self.oscillator_calc.calculate_all_oscillator(osc_data)
            result['indicator_count'] += 5
        
        if include_volume and len(closes) > 0 and len(volumes) > 0:
            vol_data = {'close': closes, 'volume': volumes}
            result['data']['volume'] = self.volume_calc.calculate_all_volume(vol_data)
            result['indicator_count'] += 5
        
        if include_price and len(highs) > 0 and len(lows) > 0 and len(closes) > 0:
            price_data = {'high': highs, 'low': lows, 'close': closes}
            result['data']['price'] = self.price_calc.calculate_all_price(price_data)
            result['indicator_count'] += 2
        
        return result
    
    def calculate_single_indicator(
        self,
        indicator_name: str,
        **params
    ) -> Union[List[float], Dict]:
        """
        计算单个指定指标
        
        :param indicator_name: 指标名称（如'rsi','macd','boll'等）
        :param params: 指标所需的参数
        :return: 指标计算结果
        """
        name_lower = indicator_name.lower()
        
        trend_indicators = ['ma', 'ema', 'boll', 'dmi', 'sar']
        oscillator_indicators = ['rsi', 'kdj', 'wr', 'cci', 'bias']
        volume_indicators = ['volume_ratio', 'obv', 'vr', 'ma_vol']
        price_indicators = ['atr', 'tr']
        
        if name_lower in trend_indicators:
            method = getattr(self.trend_calc, f'calculate_{name_lower}', None)
            if method:
                return method(**params)
        
        elif name_lower in oscillator_indicators:
            method = getattr(self.oscillator_calc, f'calculate_{name_lower}', None)
            if method:
                return method(**params)
        
        elif name_lower in volume_indicators:
            method = getattr(self.volume_calc, f'calculate_{name_lower}', None)
            if method:
                return method(**params)
        
        elif name_lower in price_indicators:
            method = getattr(self.price_calc, f'calculate_{name_lower}', None)
            if method:
                return method(**params)
        
        raise ValueError(f"不支持的指标名称: {indicator_name}")
    
    def get_available_indicators(self) -> Dict[str, List[str]]:
        """
        获取所有可用的指标列表
        
        :return: 按分类组织的指标字典
        """
        return {
            'trend': ['MA', 'EMA', 'BOLL', 'DMI', 'SAR'],
            'oscillator': ['RSI', 'KDJ', 'WR', 'CCI', 'BIAS'],
            'volume': ['Volume_Ratio', 'OBV', 'VR', 'MA_VOL'],
            'price': ['ATR', 'TR']
        }
    
    def get_indicator_info(self, indicator_name: str) -> Optional[Dict]:
        """
        获取单个指标的详细信息
        
        :param indicator_name: 指标名称
        :return: 指标信息字典（包含说明、参数、取值范围等）
        """
        info_map = {
            'rsi': {
                'name': '相对强弱指标',
                'category': 'oscillator',
                'range': [0, 100],
                'default_period': 14,
                'description': '衡量价格变动速度和变化的技术指标',
                'zones': {
                    'overbought': [70, 100],
                    'oversold': [0, 30],
                    'neutral': [30, 70]
                }
            },
            'macd': {
                'name': '指数平滑异同移动平均线',
                'category': 'trend',
                'range': None,
                'default_params': [12, 26, 9],
                'description': '趋势跟踪动量指标'
            },
            'boll': {
                'name': '布林带',
                'category': 'trend',
                'range': None,
                'default_params': [20, 2.0],
                'description': '由三条轨道组成的波动性指标'
            },
            'kdj': {
                'name': '随机指标',
                'category': 'oscillator',
                'range': {'k': [0, 100], 'd': [0, 100], 'j': [-50, 150]},
                'default_params': [9, 3, 3],
                'description': '判断超买超卖状态的震荡指标'
            },
            'atr': {
                'name': '平均真实波幅',
                'category': 'price',
                'range': [0, float('inf')],
                'default_period': 14,
                'description': '衡量市场波动幅度的指标'
            }
        }
        
        return info_map.get(indicator_name.lower())


if __name__ == '__main__':
    print("=" * 60)
    print("统一指标计算器 V2.0 测试")
    print("=" * 60)
    
    calc = IndicatorCalculatorV2()
    
    print(f"\n计算器信息:")
    print(f"  名称: {calc.name}")
    print(f"  版本: {calc.version}")
    print(f"  支持指标数: {calc.total_indicators}")
    
    print(f"\n可用指标列表:")
    indicators = calc.get_available_indicators()
    for category, names in indicators.items():
        print(f"  {category}: {', '.join(names)}")
    
    test_data = {
        'open': [10.1, 11.1, 12.1, 13.1, 14.1, 15.1, 14.1, 13.1, 
                 12.1, 11.1, 12.1, 13.1, 14.1, 15.1, 16.1, 17.1,
                 16.1, 15.1, 14.1, 13.1],
        'high': [10.8, 11.8, 12.8, 13.8, 14.8, 15.8, 14.8, 13.8,
                 12.8, 11.8, 12.8, 13.8, 14.8, 15.8, 16.8, 17.8,
                 16.8, 15.8, 14.8, 13.8],
        'low': [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 13.5, 12.5,
                 11.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5,
                 15.5, 14.5, 13.5, 12.5],
        'close': [10, 11, 12, 13, 14, 15, 14, 13, 12, 11,
                  12, 13, 14, 15, 16, 17, 16, 15, 14, 13],
        'volume': [1000, 1200, 1100, 1300, 1400, 1800, 1600, 1200,
                   900, 800, 950, 1100, 1250, 1350, 1500, 1700, 1400,
                   1150, 900, 850]
    }
    
    print("\n--- 批量计算测试 ---")
    result = calc.calculate_all(test_data)
    
    print(f"\n计算结果:")
    print(f"  成功: {result['success']}")
    print(f"  指标数: {result['indicator_count']}")
    print(f"  分类数: {len(result['data'])}")
    
    for category, indicators in result['data'].items():
        print(f"\n  [{category}] 包含 {len(indicators)} 个子指标:")
        if isinstance(indicators, dict):
            for key in list(indicators.keys())[:3]:
                values = indicators[key]
                if isinstance(values, list):
                    print(f"    - {key}: {values[-3:] if len(values) >= 3 else values}")
        else:
            print(f"    - {indicators[-3:] if len(indicators) >= 3 else indicators}")
    
    print("\n✅ 统一指标计算器 V2.0 正常工作")
