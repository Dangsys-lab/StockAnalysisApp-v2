# -*- coding: utf-8 -*-
"""
股票过滤器 - 固定条件预筛选

功能:
- ST板块过滤
- 停牌股票过滤
- 涨跌幅过大过滤
- 成交额过低过滤
- 北交所过滤
"""

import pandas as pd
from typing import List, Dict


class StockFilter:
    """
    股票过滤器
    
    基于当日行情数据进行固定条件预筛选，减少后续计算量
    """

    def __init__(self):
        self.filter_log = []

    def filter_all(
        self,
        df: pd.DataFrame,
        min_amount: float = 1000,
        max_change_pct: float = 8.0,
        min_change_pct: float = -8.0
    ) -> pd.DataFrame:
        """
        执行所有固定条件过滤

        :param df: 当日行情DataFrame，需包含列: 代码, 名称, 涨跌幅, 成交额
        :param min_amount: 最低成交额（万元），默认2000万
        :param max_change_pct: 最大涨跌幅（%），默认5%
        :param min_change_pct: 最小涨跌幅（%），默认-5%
        :return: 过滤后的DataFrame
        """
        self.filter_log = []
        original_count = len(df)

        df = self._filter_st(df)
        df = self._filter_suspended(df)
        df = self._filter_extreme_change(df, max_change_pct, min_change_pct)
        df = self._filter_low_amount(df, min_amount)
        df = self._filter_bse(df)

        self.filter_log.append(
            f"过滤完成: {original_count} → {len(df)} ({len(df)/original_count*100:.1f}%)"
        )

        return df

    def _filter_st(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤ST板块

        :param df: 行情DataFrame
        :return: 过滤后的DataFrame
        """
        before = len(df)
        mask = ~df['名称'].str.contains('ST|\\*ST|SST', case=False, na=False)
        result = df[mask].copy()
        removed = before - len(result)
        if removed > 0:
            self.filter_log.append(f"ST过滤: 移除 {removed} 只")
        return result

    def _filter_suspended(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤停牌股票（成交量为0）

        :param df: 行情DataFrame
        :return: 过滤后的DataFrame
        """
        before = len(df)
        if '成交额' in df.columns:
            mask = pd.to_numeric(df['成交额'], errors='coerce').fillna(0) > 0
            result = df[mask].copy()
        else:
            result = df.copy()
        removed = before - len(result)
        if removed > 0:
            self.filter_log.append(f"停牌过滤: 移除 {removed} 只")
        return result

    def _filter_extreme_change(
        self,
        df: pd.DataFrame,
        max_pct: float,
        min_pct: float
    ) -> pd.DataFrame:
        """
        过滤涨跌幅过大的股票

        :param df: 行情DataFrame
        :param max_pct: 最大涨跌幅
        :param min_pct: 最小涨跌幅
        :return: 过滤后的DataFrame
        """
        before = len(df)
        if '涨跌幅' in df.columns:
            change = pd.to_numeric(df['涨跌幅'], errors='coerce').fillna(0)
            mask = (change >= min_pct) & (change <= max_pct)
            result = df[mask].copy()
        else:
            result = df.copy()
        removed = before - len(result)
        if removed > 0:
            self.filter_log.append(f"涨跌幅过滤: 移除 {removed} 只")
        return result

    def _filter_low_amount(self, df: pd.DataFrame, min_amount: float) -> pd.DataFrame:
        """
        过滤成交额过低的股票

        :param df: 行情DataFrame
        :param min_amount: 最低成交额（万元）
        :return: 过滤后的DataFrame
        """
        before = len(df)
        if '成交额' in df.columns:
            amount = pd.to_numeric(df['成交额'], errors='coerce').fillna(0)
            mask = amount >= min_amount
            result = df[mask].copy()
        else:
            result = df.copy()
        removed = before - len(result)
        if removed > 0:
            self.filter_log.append(f"成交额过滤(<{min_amount}万): 移除 {removed} 只")
        return result

    def _filter_bse(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        过滤北交所股票（代码以8或4开头）

        :param df: 行情DataFrame
        :return: 过滤后的DataFrame
        """
        before = len(df)
        if '代码' in df.columns:
            mask = ~df['代码'].astype(str).str.match(r'^[84]')
            result = df[mask].copy()
        else:
            result = df.copy()
        removed = before - len(result)
        if removed > 0:
            self.filter_log.append(f"北交所过滤: 移除 {removed} 只")
        return result

    def get_log(self) -> List[str]:
        """
        获取过滤日志

        :return: 过滤日志列表
        """
        return self.filter_log
