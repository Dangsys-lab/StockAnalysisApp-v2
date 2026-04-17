# -*- coding: utf-8 -*-
"""
统一指标计算器 - 3.0版本（支持自定义参数）

功能:
- 整合所有技术指标计算（17+个指标）
- 支持内购用户自定义参数
- 提供统一的批量计算接口
- 支持按类别筛选输出

合规声明:
本模块仅提供技术指标的数学计算功能。
所有输出为客观数值，不包含任何投资建议或操作指引。
用户需自主解读数据并做出决策。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Any

from app.core.indicators.trend import TrendIndicators
from app.core.indicators.oscillator import OscillatorIndicators
from app.core.indicators.volume import VolumeIndicators
from app.core.indicators.price import PriceIndicators


DEFAULT_PARAMS = {
    'rsi_period': 14,
    'kdj_n': 9,
    'kdj_m1': 3,
    'kdj_m2': 3,
    'wr_period': 14,
    'cci_period': 20,
    'bias_periods': [6, 12, 24],
    'ma_periods': [5, 10, 20, 60],
    'ema_periods': [5, 10, 20, 60],
    'boll_period': 20,
    'boll_std_dev': 2.0,
    'dmi_period': 14,
    'sar_af_start': 0.02,
    'sar_af_step': 0.02,
    'sar_af_max': 0.2,
    'atr_period': 14,
    'volume_ratio_period': 5,
    'vr_period': 26,
    'ma_vol_periods': [5, 10, 20]
}

CUSTOMIZABLE_PARAMS = {
    'rsi_period': {'name': 'RSI周期', 'type': 'int', 'min': 5, 'max': 30, 'default': 14},
    'kdj_n': {'name': 'KDJ-N', 'type': 'int', 'min': 5, 'max': 30, 'default': 9},
    'kdj_m1': {'name': 'KDJ-M1', 'type': 'int', 'min': 1, 'max': 10, 'default': 3},
    'kdj_m2': {'name': 'KDJ-M2', 'type': 'int', 'min': 1, 'max': 10, 'default': 3},
    'wr_period': {'name': 'WR周期', 'type': 'int', 'min': 5, 'max': 30, 'default': 14},
    'cci_period': {'name': 'CCI周期', 'type': 'int', 'min': 10, 'max': 40, 'default': 20},
    'boll_period': {'name': 'BOLL周期', 'type': 'int', 'min': 10, 'max': 30, 'default': 20},
    'boll_std_dev': {'name': 'BOLL标准差', 'type': 'float', 'min': 1.0, 'max': 3.0, 'default': 2.0},
    'atr_period': {'name': 'ATR周期', 'type': 'int', 'min': 5, 'max': 30, 'default': 14},
}


class IndicatorCalculatorV2:
    """
    统一技术指标计算器（3.0版）
    
    支持的指标分类:
    - 趋势类: MA/EMA/BOLL/DMI/SAR (5个)
    - 摆动类: RSI/KDJ/WR/CCI/BIAS (5个)
    - 成交量类: VOL/OBV/VR/量比/MAVOL (5个)
    - 价格形态: ATR/TR (2个)
    
    总计: 17个独立指标
    
    内购用户可自定义参数:
    - RSI周期 (5-30)
    - KDJ参数 (N/M1/M2)
    - WR周期 (5-30)
    - CCI周期 (10-40)
    - BOLL周期和标准差
    - ATR周期 (5-30)
    """
    
    def __init__(self, user_params: Dict = None):
        """
        初始化计算器
        
        :param user_params: 用户自定义参数（仅内购用户有效）
        """
        self.params = {**DEFAULT_PARAMS, **(user_params or {})}
        
        self.trend_calc = TrendIndicators(self.params)
        self.oscillator_calc = OscillatorIndicators(self.params)
        self.volume_calc = VolumeIndicators(self.params)
        self.price_calc = PriceIndicators(self.params)
        
        self.name = "统一指标计算器 V3.0"
        self.version = "3.0.0"
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
        :param include_trend: 是否计算趋势类指标
        :param include_oscillator: 是否计算摆动类指标
        :param include_volume: 是否计算成交量类指标
        :param include_price: 是否计算价格形态类指标
        :return: 所有指标值的汇总字典
        """
        result = {
            'success': True,
            'indicator_count': 0,
            'data': {},
            'params_used': self._get_used_params()
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
    
    def _get_used_params(self) -> Dict[str, Any]:
        """获取实际使用的参数"""
        return {
            'rsi_period': self.params.get('rsi_period'),
            'kdj': {
                'n': self.params.get('kdj_n'),
                'm1': self.params.get('kdj_m1'),
                'm2': self.params.get('kdj_m2')
            },
            'wr_period': self.params.get('wr_period'),
            'cci_period': self.params.get('cci_period'),
            'boll': {
                'period': self.params.get('boll_period'),
                'std_dev': self.params.get('boll_std_dev')
            },
            'atr_period': self.params.get('atr_period')
        }
    
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
    
    @staticmethod
    def get_available_indicators() -> Dict[str, List[str]]:
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
    
    @staticmethod
    def get_customizable_params() -> Dict[str, Dict]:
        """
        获取可自定义的参数列表（内购用户）
        
        :return: 可自定义参数及其约束
        """
        return CUSTOMIZABLE_PARAMS
    
    @staticmethod
    def validate_params(user_params: Dict) -> Dict[str, Any]:
        """
        验证用户参数是否合法
        
        :param user_params: 用户提交的参数
        :return: 验证结果 {'valid': bool, 'errors': [], 'sanitized': {}}
        """
        errors = []
        sanitized = {}
        
        for key, value in user_params.items():
            if key not in CUSTOMIZABLE_PARAMS:
                errors.append(f"未知参数: {key}")
                continue
            
            constraint = CUSTOMIZABLE_PARAMS[key]
            
            if constraint['type'] == 'int':
                if not isinstance(value, int):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        errors.append(f"{constraint['name']}: 必须为整数")
                        continue
            
            elif constraint['type'] == 'float':
                if not isinstance(value, (int, float)):
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        errors.append(f"{constraint['name']}: 必须为数字")
                        continue
            
            if value < constraint['min'] or value > constraint['max']:
                errors.append(
                    f"{constraint['name']}: 取值范围 {constraint['min']}-{constraint['max']}"
                )
                continue
            
            sanitized[key] = value
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'sanitized': sanitized
        }
    
    def get_indicator_info(self, indicator_name: str) -> Optional[Dict]:
        """
        获取单个指标的详细信息
        
        :param indicator_name: 指标名称
        :return: 指标信息字典
        """
        info_map = {
            'rsi': {
                'name': '相对强弱指标',
                'category': 'oscillator',
                'range': [0, 100],
                'default_period': 14,
                'description': '衡量价格变动速度和变化的技术指标',
                'customizable': True,
                'param_key': 'rsi_period'
            },
            'kdj': {
                'name': '随机指标',
                'category': 'oscillator',
                'range': {'k': [0, 100], 'd': [0, 100], 'j': [-50, 150]},
                'default_params': [9, 3, 3],
                'description': '判断超买超卖状态的震荡指标',
                'customizable': True,
                'param_keys': ['kdj_n', 'kdj_m1', 'kdj_m2']
            },
            'boll': {
                'name': '布林带',
                'category': 'trend',
                'range': None,
                'default_params': [20, 2.0],
                'description': '由三条轨道组成的波动性指标',
                'customizable': True,
                'param_keys': ['boll_period', 'boll_std_dev']
            },
            'wr': {
                'name': '威廉指标',
                'category': 'oscillator',
                'range': [-100, 0],
                'default_period': 14,
                'description': '判断超买超卖状态',
                'customizable': True,
                'param_key': 'wr_period'
            },
            'cci': {
                'name': '顺势指标',
                'category': 'oscillator',
                'range': None,
                'default_period': 20,
                'description': '识别价格偏离统计常态的程度',
                'customizable': True,
                'param_key': 'cci_period'
            },
            'atr': {
                'name': '平均真实波幅',
                'category': 'price',
                'range': [0, float('inf')],
                'default_period': 14,
                'description': '衡量市场波动幅度的指标',
                'customizable': True,
                'param_key': 'atr_period'
            }
        }
        
        return info_map.get(indicator_name.lower())


if __name__ == '__main__':
    print("=" * 60)
    print("统一指标计算器 V3.0 测试")
    print("=" * 60)
    
    print("\n--- 可自定义参数列表 ---")
    params = IndicatorCalculatorV2.get_customizable_params()
    for key, info in params.items():
        print(f"  {info['name']}: {info['min']}-{info['max']} (默认{info['default']})")
    
    print("\n--- 测试自定义参数 ---")
    user_params = {
        'rsi_period': 21,
        'kdj_n': 14,
        'boll_period': 15,
        'boll_std_dev': 2.5
    }
    
    validation = IndicatorCalculatorV2.validate_params(user_params)
    print(f"参数验证: {'通过' if validation['valid'] else '失败'}")
    if validation['errors']:
        print(f"错误: {validation['errors']}")
    
    calc = IndicatorCalculatorV2(user_params=validation['sanitized'])
    
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
    
    result = calc.calculate_all(test_data)
    
    print(f"\n--- 计算结果 ---")
    print(f"成功: {result['success']}")
    print(f"指标数: {result['indicator_count']}")
    print(f"使用参数: {result['params_used']}")
    
    print("\n✅ 统一指标计算器 V3.0 正常工作")
