# -*- coding: utf-8 -*-
"""
数据服务 - 提供统一的数据访问接口

职责:
1. 封装在线数据源
2. 提供数据读取器接口
3. 处理数据缓存和容错
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class DataReader:
    """数据读取器 - 使用在线数据源"""
    
    def __init__(self):
        from app.core.online_data_source import OnlineDataSourceManager
        self.manager = OnlineDataSourceManager()
    
    def get_daily_data(self, stock_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取日线数据
        
        :param stock_code: 股票代码
        :param start_date: 开始日期 (YYYY-MM-DD)
        :param end_date: 结束日期 (YYYY-MM-DD)
        :return: DataFrame
        """
        try:
            result = self.manager.get_stock_data(
                stock_code,
                start_date=start_date,
                end_date=end_date,
                period='daily'
            )
            
            if not result or not result.get('success'):
                return pd.DataFrame()
            
            df = result.get('data')
            if df is None or df.empty:
                return pd.DataFrame()
            
            df = df.sort_index()
            
            return df
        except Exception as e:
            print(f"[DataReader] 获取数据失败: {e}")
            return pd.DataFrame()


class DataService:
    """数据服务 - 统一数据访问接口"""
    
    def __init__(self):
        self._reader = None
    
    def get_data_reader(self) -> DataReader:
        """获取数据读取器实例"""
        if self._reader is None:
            self._reader = DataReader()
        return self._reader
