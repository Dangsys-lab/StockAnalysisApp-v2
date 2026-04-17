# -*- coding: utf-8 -*-
"""
综合分析报告生成器

功能:
- 汇总所有技术指标数据
- 生成客观的技术面总结
- 多空信号统计与对比
- 综合评分计算（仅反映指标状态）

合规声明（最高优先级）:
本模块仅提供技术指标的客观数据汇总和状态描述。
所有输出严格遵循以下原则：
✅ 只描述"是什么"，不说"该怎么做"
✅ 只呈现技术状态，不给任何操作建议
✅ 只统计信号数量，不做主观判断
❌ 禁止出现：建议/推荐/买入/卖出/持有/观望/抄底/逃顶等词汇
❌ 禁止承诺任何收益或成功率

输出示例（合规）:
"RSI(14)=55，处于中性区间(30-70)"
"当前多空信号对比为4:2，处于震荡格局"

错误示例（违规）:
"建议买入" / "等待突破" / "值得关注"
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


class ReportGenerator:
    """
    技术分析报告生成器
    
    将多个技术指标的数据整合为结构化的客观报告
    仅描述技术形态，不提供任何操作建议
    """
    
    def __init__(self):
        self.name = "综合分析报告生成器"
        self.version = "2.0.0"
        
        self.signal_weights = {
            'trend': 0.30,
            'oscillator': 0.35,
            'volume': 0.20,
            'price_pattern': 0.15
        }
        
        # 单个指标权重 - ADX等趋势指标权重更高
        self.indicator_weights = {
            'ADX': 2.0,
            'DMI': 1.5,
            'MA均线': 1.3,
            'BOLL': 1.3,
            'RSI': 1.0,
            'KDJ-J': 1.0,
            'WR': 1.0,
            'CCI': 1.0,
            '量比': 1.2,
            'default': 1.0
        }
    
    def generate_report(
        self,
        indicators_data: Dict[str, Any],
        thresholds: Dict[str, Any] = None,
        market_env: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        生成技术分析报告
        
        :param indicators_data: 指标数据字典（来自IndicatorCalculatorV2）
        :param thresholds: 自适应阈值配置（可选）
        :param market_env: 市场环境信息（可选）
        :return: 结构化报告字典
        """
        
        trend_data = indicators_data.get('trend', {})
        oscillator_data = indicators_data.get('oscillator', {})
        volume_data = indicators_data.get('volume', {})
        price_data = indicators_data.get('price', {})
        
        signals = self._analyze_all_signals(
            trend_data, oscillator_data, volume_data, price_data,
            thresholds
        )
        
        summary = self._generate_summary(signals, market_env)
        
        score = self._calculate_score(signals)
        
        report = {
            'success': True,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'score': score,
            'signals': signals,
            'summary': summary,
            'market_environment': market_env or {},
            'indicator_count': self._count_indicators(indicators_data),
            'disclaimer': '⚠️ 以上为技术指标客观计算结果，仅供参考，不构成任何投资建议。',
            'compliance_note': '本报告仅描述技术形态的客观状态，不含任何操作建议或方向判断。'
        }
        
        # 合规性检查：确保没有违规词汇（排除免责声明中的合规用法）
        forbidden_words = ['推荐买入', '推荐卖出', '买入', '卖出', '持有', '观望', '抄底', '逃顶']
        report_str = str(report)
        for word in forbidden_words:
            if word in report_str:
                raise ValueError(f"发现违规词汇: '{word}'")
        
        return report
    
    def _analyze_all_signals(
        self,
        trend_data: Dict,
        oscillator_data: Dict,
        volume_data: Dict,
        price_data: Dict,
        thresholds: Dict = None
    ) -> Dict[str, Any]:
        """
        分析所有指标的技术信号
        
        :return: 信号分析结果
        """
        if not thresholds:
            from app.core.adaptive import AdaptiveThresholdManager
            manager = AdaptiveThresholdManager()
            env = 'oscillation'
            thresholds = manager.get_thresholds(env)
            thresholds = thresholds.get('all_thresholds', {})
        
        rsi_thresh = thresholds.get('rsi', {})
        kdj_thresh = thresholds.get('kdj_j', {})
        wr_thresh = thresholds.get('wr', {})
        cci_thresh = thresholds.get('cci', {})
        bias_thresh = thresholds.get('bias', {})
        vol_ratio_thresh = thresholds.get('volume_ratio', {})
        
        signals = {
            'bullish': [],
            'bearish': [],
            'neutral': []
        }
        
        signals['bullish'], signals['bearish'] = self._analyze_rsi(
            oscillator_data.get('rsi', []), 
            rsi_thresh
        )
        
        kdj_bull, kdj_bear = self._analyze_kdj(
            oscillator_data.get('k', []),
            oscillator_data.get('j', []),
            kdj_thresh
        )
        signals['bullish'].extend(kdj_bull)
        signals['bearish'].extend(kdj_bear)
        
        wr_bull, wr_bear = self._analyze_wr(
            oscillator_data.get('wr', []),
            wr_thresh
        )
        signals['bullish'].extend(wr_bull)
        signals['bearish'].extend(wr_bear)
        
        cci_bull, cci_bear = self._analyze_cci(
            oscillator_data.get('cci', []),
            cci_thresh
        )
        signals['bullish'].extend(cci_bull)
        signals['bearish'].extend(cci_bear)
        
        boll_signals = self._analyze_boll(
            trend_data.get('boll_upper', []),
            trend_data.get('boll_middle', []),
            trend_data.get('boll_lower', [])
        )
        signals['bullish'].extend(boll_signals[0])
        signals['bearish'].extend(boll_signals[1])
        
        ma_signals = self._analyze_ma_position(
            trend_data.get('ma5', []),
            trend_data.get('ma10', []),
            trend_data.get('ma20', []),
            trend_data.get('close', trend_data.get('boll_middle', []))
        )
        signals['bullish'].extend(ma_signals[0])
        signals['bearish'].extend(ma_signals[1])
        
        vol_signals = self._analyze_volume(
            volume_data.get('volume_ratio', []),
            vol_ratio_thresh
        )
        signals['bullish'].extend(vol_signals[0])
        signals['bearish'].extend(vol_signals[1])
        
        dmi_signals = self._analyze_dmi(
            trend_data.get('pdi', []),
            trend_data.get('mdi', []),
            trend_data.get('adx', [])
        )
        signals['bullish'].extend(dmi_signals[0])
        signals['bearish'].extend(dmi_signals[1])
        
        return signals
    
    def _get_last_value(self, data_list):
        """获取列表最后一个有效值"""
        if not data_list:
            return None
        for val in reversed(data_list):
            if val is not None and (not isinstance(val, float) or not pd.isna(val)):
                return val
        return data_list[-1] if data_list else None
    
    def _analyze_rsi(self, rsi_values, thresholds) -> Tuple[List, List]:
        """分析RSI信号"""
        bullish = []
        bearish = []
        
        rsi = self._get_last_value(rsi_values)
        if rsi is None:
            return [], []
        
        overbought = thresholds.get('overbought', 70)
        oversold = thresholds.get('oversold', 30)
        
        if rsi > overbought:
            bearish.append({
                'indicator': 'RSI',
                'value': round(rsi, 2),
                'type': 'overbought',
                'description': f'RSI({round(rsi, 2)})处于超买区域(>{overbought})'
            })
        elif rsi < oversold:
            bullish.append({
                'indicator': 'RSI',
                'value': round(rsi, 2),
                'type': 'oversold',
                'description': f'RSI({round(rsi, 2)})处于超卖区域(<{oversold})'
            })
        else:
            neutral_desc = f'RSI({round(rsi, 2)})处于中性区间({oversold}-{overbought})'
        
        return bullish, bearish
    
    def _analyze_kdj(self, k_values, j_values, thresholds) -> Tuple[List, List]:
        """分析KDJ信号"""
        bullish = []
        bearish = []
        
        j_val = self._get_last_value(j_values)
        k_val = self._get_last_value(k_values)
        
        if j_val is None:
            return [], []
        
        overbought = thresholds.get('overbought', 80)
        oversold = thresholds.get('oversold', 20)
        
        if j_val > overbought:
            bearish.append({
                'indicator': 'KDJ-J',
                'value': round(j_val, 2),
                'type': 'overbought',
                'description': f'KDJ的J值({round(j_val, 2)})进入超买区域(>{overbought})'
            })
        elif j_val < oversold:
            bullish.append({
                'indicator': 'KDJ-J',
                'value': round(j_val, 2),
                'type': 'oversold',
                'description': f'KDJ的J值({round(j_val, 2)})进入超卖区域(<{oversold})'
            })
        
        return bullish, bearish
    
    def _analyze_wr(self, wr_values, thresholds) -> Tuple[List, List]:
        """分析WR信号"""
        bullish = []
        bearish = []
        
        wr = self._get_last_value(wr_values)
        if wr is None:
            return [], []
        
        overbought = thresholds.get('overbought', -20)
        oversold = thresholds.get('oversold', -80)
        
        if wr > overbought:
            bearish.append({
                'indicator': 'WR',
                'value': round(wr, 2),
                'type': 'overbought',
                'description': f'WR({round(wr, 2)})处于超买区域(>{overbought})'
            })
        elif wr < oversold:
            bullish.append({
                'indicator': 'WR',
                'value': round(wr, 2),
                'type': 'oversold',
                'description': f'WR({round(wr, 2)})处于超卖区域(<{oversold})'
            })
        
        return bullish, bearish
    
    def _analyze_cci(self, cci_values, thresholds) -> Tuple[List, List]:
        """分析CCI信号"""
        bullish = []
        bearish = []
        
        cci = self._get_last_value(cci_values)
        if cci is None:
            return [], []
        
        overbought = thresholds.get('overbought', 100)
        oversold = thresholds.get('oversold', -100)
        
        if cci > overbought:
            bearish.append({
                'indicator': 'CCI',
                'value': round(cci, 2),
                'type': 'overbought',
                'description': f'CCI({round(cci, 2)})高于正常水平(>{overbought})'
            })
        elif cci < oversold:
            bullish.append({
                'indicator': 'CCI',
                'value': round(cci, 2),
                'type': 'oversold',
                'description': f'CCI({round(cci, 2)})低于正常水平(<{oversold})'
            })
        
        return bullish, bearish
    
    def _analyze_boll(self, upper, middle, lower) -> Tuple[List, List]:
        """分析布林带位置"""
        bullish = []
        bearish = []
        
        close = self._get_last_value(middle)
        upper_val = self._get_last_value(upper)
        lower_val = self._get_last_value(lower)
        
        if close is None or upper_val is None or lower_val is None:
            return [], []
        
        boll_width = upper_val - lower_val
        if boll_width == 0:
            return [], []
        
        position_pct = (close - lower_val) / boll_width * 100
        
        if position_pct > 90:
            bearish.append({
                'indicator': 'BOLL',
                'value': round(position_pct, 1),
                'type': 'near_upper',
                'description': f'价格接近布林带上轨(位置{round(position_pct, 1)}%)'
            })
        elif position_pct < 10:
            bullish.append({
                'indicator': 'BOLL',
                'value': round(position_pct, 1),
                'type': 'near_lower',
                'description': f'价格接近布林带下轨(位置{round(position_pct, 1)}%)'
            })
        
        return bullish, bearish
    
    def _analyze_ma_position(self, ma5, ma10, ma20, prices) -> Tuple[List, List]:
        """分析均线位置关系"""
        bullish = []
        bearish = []
        
        price = self._get_last_value(prices)
        ma5_val = self._get_last_value(ma5)
        ma10_val = self._get_last_value(ma10)
        ma20_val = self._get_last_value(ma20)
        
        if price is None:
            return [], []
        
        above_count = 0
        total_ma = 0
        
        if ma5_val is not None:
            total_ma += 1
            if price > ma5_val:
                above_count += 1
        
        if ma10_val is not None:
            total_ma += 1
            if price > ma10_val:
                above_count += 1
        
        if ma20_val is not None:
            total_ma += 1
            if price > ma20_val:
                above_count += 1
        
        if total_ma == 0:
            return [], []
        
        if above_count == total_ma:
            bullish.append({
                'indicator': 'MA均线',
                'value': f'{above_count}/{total_ma}',
                'type': 'all_above',
                'description': f'价格站上所有观察均线({above_count}/{total_ma})'
            })
        elif above_count == 0:
            bearish.append({
                'indicator': 'MA均线',
                'value': f'{above_count}/{total_ma}',
                'type': 'all_below',
                'description': f'价格位于所有均线下方(0/{total_ma})'
            })
        
        return bullish, bearish
    
    def _analyze_volume(self, vol_ratio_values, thresholds) -> Tuple[List, List]:
        """分析成交量信号"""
        bullish = []
        bearish = []
        
        vr = self._get_last_value(vol_ratio_values)
        if vr is None:
            return [], []
        
        high = thresholds.get('high', 2.0)
        low = thresholds.get('low', 0.6)
        
        if vr > high:
            bullish.append({
                'indicator': '量比',
                'value': round(vr, 2),
                'type': 'high_volume',
                'description': f'量比({round(vr, 2)})明显高于近期均值(>{high})'
            })
        elif vr < low:
            bearish.append({
                'indicator': '量比',
                'value': round(vr, 2),
                'type': 'low_volume',
                'description': f'量比({round(vr, 2)})明显低于近期均值(<{low})'
            })
        
        return bullish, bearish
    
    def _analyze_dmi(self, pdi_values, mdi_values, adx_values) -> Tuple[List, List]:
        """分析DMI趋向指标"""
        bullish = []
        bearish = []
        
        pdi = self._get_last_value(pdi_values)
        mdi = self._get_last_value(mdi_values)
        adx = self._get_last_value(adx_values)
        
        if pdi is None or mdi is None:
            return [], []
        
        if pdi > mdi + 5:
            bullish.append({
                'indicator': 'DMI',
                'value': f'+DI{round(pdi,1)} vs -DI{round(mdi,1)}',
                'type': 'positive_direction',
                'description': f'正方向指标(PDI={round(pdi,1)})强于负方向指标(MDI={round(mdi,1)})'
            })
        elif mdi > pdi + 5:
            bearish.append({
                'indicator': 'DMI',
                'value': f'+DI{round(pdi,1)} vs -DI{round(mdi,1)}',
                'type': 'negative_direction',
                'description': f'负方向指标(MDI={round(mdi,1)})强于正方向指标(PDI={round(pdi,1)})'
            })
        
        if adx is not None and adx > 25:
            direction = '多头' if pdi > mdi else '空头'
            desc = f'ADX({round(adx,1)})>25，存在明确的{direction}趋势'
            
            if pdi > mdi:
                bullish.append({
                    'indicator': 'ADX',
                    'value': round(adx, 1),
                    'type': 'strong_trend',
                    'description': desc
                })
            else:
                bearish.append({
                    'indicator': 'ADX',
                    'value': round(adx, 1),
                    'type': 'strong_trend',
                    'description': desc
                })
        
        return bullish, bearish
    
    def _calculate_score(self, signals: Dict) -> int:
        """
        计算综合评分（0-100）
        
        评分仅反映多空信号的相对数量对比
        不代表任何投资价值判断
        
        使用加权计算：ADX等趋势指标权重更高
        
        :param signals: 信号字典
        :return: 评分整数
        """
        bullish_signals = signals.get('bullish', [])
        bearish_signals = signals.get('bearish', [])
        
        # 计算加权得分
        bull_weighted = 0.0
        bear_weighted = 0.0
        
        for signal in bullish_signals:
            indicator_name = signal.get('indicator', 'default')
            weight = self.indicator_weights.get(indicator_name, self.indicator_weights['default'])
            bull_weighted += weight
        
        for signal in bearish_signals:
            indicator_name = signal.get('indicator', 'default')
            weight = self.indicator_weights.get(indicator_name, self.indicator_weights['default'])
            bear_weighted += weight
        
        total_weighted = bull_weighted + bear_weighted
        
        if total_weighted == 0:
            return 50
        
        raw_score = (bull_weighted / total_weighted) * 100
        
        score = int(round(raw_score, 0))
        score = max(10, min(90, score))
        
        return score
    
    def _generate_summary(self, signals: Dict, market_env: Dict = None) -> Dict:
        """
        生成技术面总结（纯客观描述）
        
        :param signals: 信号字典
        :param market_env: 市场环境信息
        :return: 总结字典
        """
        bull_count = len(signals.get('bullish', []))
        bear_count = len(signals.get('bearish', []))
        
        env_label = market_env.get('label', '震荡格局') if market_env else '震荡格局'
        
        diff = abs(bull_count - bear_count)
        
        if diff <= 1:
            status_label = '均衡'
            pattern_desc = f'当前多空信号数量接近（多{bull_count} vs 空{bear_count}），处于{env_label}'
        elif bull_count > bear_count:
            status_label = '偏多'
            pattern_desc = f'当前多头信号多于空头信号（多{bull_count} vs 空{bear_count}），处于{env_label}'
        else:
            status_label = '偏空'
            pattern_desc = f'当前空头信号多于多头信号（空{bear_count} vs 多{bull_count}），处于{env_label}'
        
        top_bullish = sorted(
            signals.get('bullish', []), 
            key=lambda x: float(x.get('value', 0)) if isinstance(x.get('value', 0), (int, float, str)) and str(x.get('value', 0)).replace('.','',1).replace('-','',1).isdigit() else 0, 
            reverse=True
        )[:3]
        
        top_bearish = sorted(
            signals.get('bearish', []), 
            key=lambda x: float(x.get('value', 0)) if isinstance(x.get('value', 0), (int, float, str)) and str(x.get('value', 0)).replace('.','',1).replace('-','',1).isdigit() else 0, 
            reverse=True
        )[:3]
        
        return {
            'status': status_label,
            'pattern_description': pattern_desc,
            'signal_counts': {
                'bullish': bull_count,
                'bearish': bear_count,
                'total': bull_count + bear_count
            },
            'top_bullish_signals': [s['description'] for s in top_bullish],
            'top_bearish_signals': [s['description'] for s in top_bearish],
            'market_context': env_label
        }
    
    def _count_indicators(self, data: Dict) -> int:
        """统计使用的指标数量"""
        count = 0
        for category, values in data.items():
            if isinstance(values, dict):
                count += len(values.keys())
            elif isinstance(values, list):
                count += 1
        return count


if __name__ == '__main__':
    print("=" * 60)
    print("综合分析报告生成器测试")
    print("=" * 60)
    
    generator = ReportGenerator()
    
    test_indicators = {
        'trend': {
            'ma5': [10, 11, 12, 13, 14],
            'ma10': [9.5, 10.5, 11.5, 12.5, 13.5],
            'ma20': [9, 10, 11, 12, 13],
            'boll_upper': [15, 16, 17, 18, 19],
            'boll_middle': [12, 13, 14, 15, 16],
            'boll_lower': [9, 10, 11, 12, 13],
            'pdi': [25, 28, 32, 35, 38],
            'mdi': [20, 18, 15, 14, 12],
            'adx': [22, 24, 26, 28, 30]
        },
        'oscillator': {
            'rsi': [45, 50, 55, 58, 62],
            'k': [50, 55, 60, 65, 72],
            'd': [48, 52, 56, 60, 65],
            'j': [54, 61, 68, 75, 86],
            'wr': [-40, -35, -30, -25, -18],
            'cci': [80, 95, 110, 125, 140]
        },
        'volume': {
            'volume_ratio': [0.8, 0.9, 1.1, 1.3, 1.6]
        },
        'price': {}
    }
    
    test_market_env = {
        'status': 'oscillation',
        'label': '震荡格局',
        'score': 52.3
    }
    
    print("\n--- 生成测试报告 ---")
    report = generator.generate_report(test_indicators, market_env=test_market_env)
    
    print(f"\n  报告生成时间: {report['generated_at']}")
    print(f"  综合评分: {report['score']}")
    print(f"  使用指标数: {report['indicator_count']}")
    
    print(f"\n  --- 信号统计 ---")
    summary = report['summary']
    print(f"  状态: {summary['status']}")
    print(f"  多头信号: {summary['signal_counts']['bullish']}个")
    print(f"  空头信号: {summary['signal_counts']['bearish']}个")
    
    print(f"\n  --- 技术面总结 ---")
    print(f"  {summary['pattern_description']}")
    
    print(f"\n  --- 主要多头信号 ---")
    for i, sig in enumerate(summary['top_bullish_signals'], 1):
        print(f"    {i}. {sig}")
    
    print(f"\n  --- 主要空头信号 ---")
    for i, sig in enumerate(summary['top_bearish_signals'], 1):
        print(f"    {i}. {sig}")
    
    print(f"\n  免责声明: {report['disclaimer']}")
    
    print("\n✅ 综合分析报告生成器正常工作")
