# -*- coding: utf-8 -*-
"""
指标计算服务 - 业务编排层

功能:
- 接收用户自定义参数
- 编排数据获取和指标计算
- 返回格式化结果（含前端可直接渲染的指标数组）
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import math

from app.services.base import BaseService
from app.core.indicators.calculator import IndicatorCalculatorV2


FREE_INDICATOR_KEYS = {
    'trend': ['ma5', 'ma10', 'ma20', 'boll_upper', 'boll_middle', 'boll_lower'],
    'oscillator': ['rsi']
}

PRO_INDICATOR_DEFS = [
    {'name': 'EMA12/EMA26', 'key': 'ema12', 'category': 'trend'},
    {'name': 'DMI(PDI/MDI/ADX)', 'key': 'pdi', 'category': 'trend'},
    {'name': 'SAR', 'key': 'sar', 'category': 'trend'},
    {'name': 'KDJ', 'key': 'k', 'category': 'oscillator'},
    {'name': 'WR', 'key': 'wr', 'category': 'oscillator'},
    {'name': 'CCI', 'key': 'cci', 'category': 'oscillator'},
    {'name': 'BIAS', 'key': 'bias', 'category': 'oscillator'},
    {'name': 'OBV', 'key': 'obv', 'category': 'volume'},
    {'name': 'VR', 'key': 'vr', 'category': 'volume'},
    {'name': '量比', 'key': 'volume_ratio', 'category': 'volume'},
    {'name': 'ATR', 'key': 'atr', 'category': 'price'},
    {'name': 'TR', 'key': 'tr', 'category': 'price'},
]


class IndicatorService(BaseService):
    """
    指标计算服务
    
    负责业务编排和数据转换
    """
    
    def calculate_indicators(
        self,
        stock_code: str,
        is_pro: bool = False,
        user_params: Dict = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """
        计算股票技术指标
        
        :param stock_code: 股票代码
        :param is_pro: 是否为专业版用户
        :param user_params: 用户自定义参数（仅专业版有效）
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: 指标计算结果（含格式化指标数组）
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        raw_result = self.data_manager.get_stock_data(stock_code, start_date, end_date)
        
        if not raw_result.get('success'):
            return {
                'success': False,
                'error': raw_result.get('error', '无法获取数据'),
                'stock_code': stock_code,
                'source_status': self.data_manager.get_source_health()
            }
        
        df = raw_result.get('data')
        
        if df is None or (hasattr(df, 'empty') and df.empty):
            return {
                'success': False,
                'error': '未找到该股票的数据',
                'stock_code': stock_code
            }
        
        calc_params = None
        if is_pro and user_params:
            validation = IndicatorCalculatorV2.validate_params(user_params)
            if validation['valid']:
                calc_params = validation['sanitized']
        
        calc = IndicatorCalculatorV2(user_params=calc_params)
        
        data_dict = {
            'open': df['open'].tolist(),
            'high': df['high'].tolist(),
            'low': df['low'].tolist(),
            'close': df['close'].tolist(),
            'volume': df['volume'].tolist()
        }
        
        result = calc.calculate_all(
            data_dict,
            include_trend=True,
            include_oscillator=True,
            include_volume=True,
            include_price=True
        )
        
        response_data = {
            'dates': [idx.strftime('%Y-%m-%d') for idx in df.index],
            'open': self._clean_nan(df['open'].tolist()),
            'high': self._clean_nan(df['high'].tolist()),
            'low': self._clean_nan(df['low'].tolist()),
            'close': self._clean_nan(df['close'].tolist()),
            'volume': self._clean_nan(df['volume'].tolist())
        }
        
        for category, indicators in result['data'].items():
            if isinstance(indicators, dict):
                for key, values in indicators.items():
                    response_data[key] = self._clean_nan(values)
        
        formatted_indicators = self._format_indicators(result['data'], is_pro)
        
        stock_name = self._get_stock_name(stock_code)
        last_close = self._get_last_value(response_data.get('close', []))
        prev_close = self._get_prev_value(response_data.get('close', []))
        change_pct = 0
        if last_close and prev_close and prev_close != 0:
            change_pct = round((last_close - prev_close) / prev_close * 100, 2)
        
        return {
            'success': True,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'name': stock_name,
            'price': last_close,
            'change': change_pct,
            'is_pro': is_pro,
            'indicator_count': result['indicator_count'],
            'data_points': len(response_data['dates']),
            'data': response_data,
            'indicators': formatted_indicators,
            'data_source': raw_result.get('source', '未知'),
            'is_fallback': raw_result.get('is_fallback', False),
            'params_used': result.get('params_used') if is_pro else None
        }
    
    def _format_indicators(self, calc_data: Dict, is_pro: bool) -> List[Dict]:
        """
        将计算结果格式化为前端可渲染的指标数组
        
        :param calc_data: IndicatorCalculatorV2.calculate_all 返回的 data 字典
        :param is_pro: 是否专业版
        :return: 格式化指标列表
        """
        indicators = []
        
        trend_data = calc_data.get('trend', {})
        osc_data = calc_data.get('oscillator', {})
        vol_data = calc_data.get('volume', {})
        price_data = calc_data.get('price', {})
        
        close_list = trend_data.get('close', [])
        last_close = self._get_last_value(close_list)
        
        ma5 = self._get_last_value(trend_data.get('ma5', []))
        ma10 = self._get_last_value(trend_data.get('ma10', []))
        ma20 = self._get_last_value(trend_data.get('ma20', []))
        boll_upper = self._get_last_value(trend_data.get('boll_upper', []))
        boll_middle = self._get_last_value(trend_data.get('boll_middle', []))
        boll_lower = self._get_last_value(trend_data.get('boll_lower', []))
        rsi = self._get_last_value(osc_data.get('rsi', []))
        
        indicators.append({
            'name': 'MA5',
            'value': self._format_value(ma5),
            'category': 'trend',
            'status': self._get_ma_status(last_close, ma5),
            'status_text': self._get_ma_status_text(last_close, ma5),
            'is_pro_only': False
        })
        indicators.append({
            'name': 'MA10',
            'value': self._format_value(ma10),
            'category': 'trend',
            'status': self._get_ma_status(last_close, ma10),
            'status_text': self._get_ma_status_text(last_close, ma10),
            'is_pro_only': False
        })
        indicators.append({
            'name': 'MA20',
            'value': self._format_value(ma20),
            'category': 'trend',
            'status': self._get_ma_status(last_close, ma20),
            'status_text': self._get_ma_status_text(last_close, ma20),
            'is_pro_only': False
        })
        
        boll_pos = self._get_boll_position(last_close, boll_upper, boll_lower)
        indicators.append({
            'name': 'BOLL',
            'value': f'上{self._format_value(boll_upper)} 中{self._format_value(boll_middle)} 下{self._format_value(boll_lower)}' if boll_upper else None,
            'category': 'trend',
            'status': self._get_boll_status(boll_pos),
            'status_text': self._get_boll_status_text(boll_pos),
            'is_pro_only': False
        })
        
        indicators.append({
            'name': 'RSI(14)',
            'value': self._format_value(rsi),
            'category': 'oscillator',
            'status': self._get_rsi_status(rsi),
            'status_text': self._get_rsi_status_text(rsi),
            'is_pro_only': False
        })
        
        if is_pro:
            ema12 = self._get_last_value(trend_data.get('ema12', []))
            ema26 = self._get_last_value(trend_data.get('ema26', []))
            indicators.append({
                'name': 'EMA12/EMA26',
                'value': f'{self._format_value(ema12)}/{self._format_value(ema26)}' if ema12 and ema26 else None,
                'category': 'trend',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
            
            pdi = self._get_last_value(trend_data.get('pdi', []))
            mdi = self._get_last_value(trend_data.get('mdi', []))
            adx = self._get_last_value(trend_data.get('adx', []))
            indicators.append({
                'name': 'DMI(PDI/MDI/ADX)',
                'value': f'+DI{self._format_value(pdi)} -DI{self._format_value(mdi)} ADX{self._format_value(adx)}' if pdi else None,
                'category': 'trend',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
            
            sar = self._get_last_value(trend_data.get('sar', []))
            indicators.append({
                'name': 'SAR',
                'value': self._format_value(sar),
                'category': 'trend',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
            
            k = self._get_last_value(osc_data.get('k', []))
            d = self._get_last_value(osc_data.get('d', []))
            j = self._get_last_value(osc_data.get('j', []))
            indicators.append({
                'name': 'KDJ',
                'value': f'K{self._format_value(k)} D{self._format_value(d)} J{self._format_value(j)}' if k else None,
                'category': 'oscillator',
                'status': self._get_kdj_status(j),
                'status_text': self._get_kdj_status_text(j),
                'is_pro_only': True
            })
            
            wr = self._get_last_value(osc_data.get('wr', []))
            indicators.append({
                'name': 'WR',
                'value': self._format_value(wr),
                'category': 'oscillator',
                'status': self._get_wr_status(wr),
                'status_text': self._get_wr_status_text(wr),
                'is_pro_only': True
            })
            
            cci = self._get_last_value(osc_data.get('cci', []))
            indicators.append({
                'name': 'CCI',
                'value': self._format_value(cci),
                'category': 'oscillator',
                'status': self._get_cci_status(cci),
                'status_text': self._get_cci_status_text(cci),
                'is_pro_only': True
            })
            
            bias = self._get_last_value(osc_data.get('bias', []))
            indicators.append({
                'name': 'BIAS',
                'value': self._format_value(bias),
                'category': 'oscillator',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
            
            obv = self._get_last_value(vol_data.get('obv', []))
            indicators.append({
                'name': 'OBV',
                'value': self._format_value(obv),
                'category': 'volume',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
            
            vr = self._get_last_value(vol_data.get('vr', []))
            indicators.append({
                'name': 'VR',
                'value': self._format_value(vr),
                'category': 'volume',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
            
            vol_ratio = self._get_last_value(vol_data.get('volume_ratio', []))
            indicators.append({
                'name': '量比',
                'value': self._format_value(vol_ratio),
                'category': 'volume',
                'status': self._get_vol_ratio_status(vol_ratio),
                'status_text': self._get_vol_ratio_status_text(vol_ratio),
                'is_pro_only': True
            })
            
            atr = self._get_last_value(price_data.get('atr', []))
            indicators.append({
                'name': 'ATR',
                'value': self._format_value(atr),
                'category': 'price',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
            
            tr = self._get_last_value(price_data.get('tr', []))
            indicators.append({
                'name': 'TR',
                'value': self._format_value(tr),
                'category': 'price',
                'status': 'neutral',
                'status_text': '中性',
                'is_pro_only': True
            })
        else:
            for pro_def in PRO_INDICATOR_DEFS:
                indicators.append({
                    'name': pro_def['name'],
                    'value': None,
                    'category': pro_def['category'],
                    'status': 'locked',
                    'status_text': '专业版',
                    'is_pro_only': True
                })
        
        return indicators
    
    def _get_last_value(self, data_list):
        """
        获取列表最后一个有效值
        
        :param data_list: 数据列表
        :return: 最后一个有效值或None
        """
        if not data_list:
            return None
        for val in reversed(data_list):
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                return val
        return None
    
    def _get_prev_value(self, data_list):
        """
        获取列表倒数第二个有效值
        
        :param data_list: 数据列表
        :return: 倒数第二个有效值或None
        """
        if not data_list or len(data_list) < 2:
            return None
        count = 0
        for val in reversed(data_list):
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                count += 1
                if count == 2:
                    return val
        return None
    
    def _format_value(self, value):
        """
        格式化数值，保留2位小数
        
        :param value: 原始值
        :return: 格式化后的值
        """
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return round(value, 2)
            if isinstance(value, str):
                try:
                    return round(float(value), 2)
                except ValueError:
                    return value
        except:
            pass
        return value
    
    def _get_stock_name(self, stock_code: str) -> str:
        """
        获取股票名称
        
        :param stock_code: 股票代码
        :return: 股票名称
        """
        try:
            from app.services.stock_name_service import StockNameService
            service = StockNameService()
            name = service.get_name(stock_code)
            return name or stock_code
        except Exception:
            return stock_code
    
    def _get_ma_status(self, price, ma_val):
        """
        获取均线状态
        
        :param price: 当前价格
        :param ma_val: 均线值
        :return: 状态字符串
        """
        if price is None or ma_val is None:
            return 'neutral'
        return 'strong' if price > ma_val else 'weak'
    
    def _get_ma_status_text(self, price, ma_val):
        """
        获取均线状态文本
        
        :param price: 当前价格
        :param ma_val: 均线值
        :return: 状态文本
        """
        if price is None or ma_val is None:
            return '数据不足'
        return '上方' if price > ma_val else '下方'
    
    def _get_boll_position(self, price, upper, lower):
        """
        计算布林带位置百分比
        
        :param price: 当前价格
        :param upper: 上轨
        :param lower: 下轨
        :return: 位置百分比(0-100)或None
        """
        if price is None or upper is None or lower is None:
            return None
        width = upper - lower
        if width == 0:
            return 50
        return (price - lower) / width * 100
    
    def _get_boll_status(self, pos):
        """
        获取布林带状态
        
        :param pos: 位置百分比
        :return: 状态字符串
        """
        if pos is None:
            return 'neutral'
        if pos > 80:
            return 'weak'
        if pos < 20:
            return 'strong'
        return 'neutral'
    
    def _get_boll_status_text(self, pos):
        """
        获取布林带状态文本
        
        :param pos: 位置百分比
        :return: 状态文本
        """
        if pos is None:
            return '数据不足'
        if pos > 80:
            return '接近上轨'
        if pos < 20:
            return '接近下轨'
        return '中性区间'
    
    def _get_rsi_status(self, rsi):
        """
        获取RSI状态
        
        :param rsi: RSI值
        :return: 状态字符串
        """
        if rsi is None:
            return 'neutral'
        if rsi > 70:
            return 'weak'
        if rsi < 30:
            return 'strong'
        return 'neutral'
    
    def _get_rsi_status_text(self, rsi):
        """
        获取RSI状态文本
        
        :param rsi: RSI值
        :return: 状态文本
        """
        if rsi is None:
            return '数据不足'
        if rsi > 70:
            return '超买区域'
        if rsi < 30:
            return '超卖区域'
        return '中性区间'
    
    def _get_kdj_status(self, j):
        if j is None:
            return 'neutral'
        if j > 80:
            return 'weak'
        if j < 20:
            return 'strong'
        return 'neutral'
    
    def _get_kdj_status_text(self, j):
        if j is None:
            return '数据不足'
        if j > 80:
            return '超买区域'
        if j < 20:
            return '超卖区域'
        return '中性区间'
    
    def _get_wr_status(self, wr):
        if wr is None:
            return 'neutral'
        if wr > -20:
            return 'weak'
        if wr < -80:
            return 'strong'
        return 'neutral'
    
    def _get_wr_status_text(self, wr):
        if wr is None:
            return '数据不足'
        if wr > -20:
            return '超买区域'
        if wr < -80:
            return '超卖区域'
        return '中性区间'
    
    def _get_cci_status(self, cci):
        if cci is None:
            return 'neutral'
        if cci > 100:
            return 'weak'
        if cci < -100:
            return 'strong'
        return 'neutral'
    
    def _get_cci_status_text(self, cci):
        if cci is None:
            return '数据不足'
        if cci > 100:
            return '偏高'
        if cci < -100:
            return '偏低'
        return '正常区间'
    
    def _get_vol_ratio_status(self, vr):
        if vr is None:
            return 'neutral'
        if vr > 2.0:
            return 'strong'
        if vr < 0.6:
            return 'weak'
        return 'neutral'
    
    def _get_vol_ratio_status_text(self, vr):
        if vr is None:
            return '数据不足'
        if vr > 2.0:
            return '放量'
        if vr < 0.6:
            return '缩量'
        return '正常'
    
    def get_customizable_params(self) -> Dict[str, Any]:
        """
        获取可自定义参数列表
        
        :return: 可自定义参数及其约束
        """
        return {
            'success': True,
            'params': IndicatorCalculatorV2.get_customizable_params(),
            'total': len(IndicatorCalculatorV2.get_customizable_params())
        }
    
    def validate_user_params(self, user_params: Dict) -> Dict[str, Any]:
        """
        验证用户参数
        
        :param user_params: 用户提交的参数
        :return: 验证结果
        """
        return IndicatorCalculatorV2.validate_params(user_params)
