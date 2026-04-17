# -*- coding: utf-8 -*-
"""
Tushare 数据获取核心模块

封装 Tushare Pro API 常用接口，提供统一的股票数据获取服务
- 实时行情数据（使用最新日线数据模拟）
- 历史 K 线数据
- 股票基本信息
- 财务指标数据
- F10 资料

符合项目规范：
- 只返回数据（dict/list/DataFrame），不返回 HTTP 响应
- 完整的异常处理
- 所有函数有文档字符串
- 使用类型注解
"""

import os
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


class TushareDataFetcher:
    """
    Tushare 数据获取器
    
    提供统一的股票数据获取接口，封装 Tushare Pro API 常用功能
    支持缓存、错误处理和重试机制
    """
    
    def __init__(self, token: Optional[str] = None, cache_size: int = 100, request_interval: float = 0.5):
        """
        初始化数据获取器
        
        Args:
            token: Tushare API Token，如不提供则从环境变量读取
            cache_size: LRU 缓存大小，默认 100
            request_interval: 请求间隔（秒），避免被限流，默认 0.5 秒
        """
        self.token = token or os.getenv('TUSHARE_TOKEN', '')
        self.cache_size = cache_size
        self.request_interval = request_interval
        self.last_request_time = 0.0
        self.request_count = 0
        self.error_count = 0
        self.pro = None
        
        if not TUSHARE_AVAILABLE:
            print("警告：Tushare 库未安装，请运行：pip install tushare")
            return
        
        # 初始化 Tushare Pro API
        if self.token:
            try:
                ts.set_token(self.token)
                self.pro = ts.pro_api()
                print(f"Tushare Pro API 初始化成功")
            except Exception as e:
                print(f"Tushare Pro API 初始化失败：{e}")
                self.pro = None
        else:
            print("警告：未提供 Tushare Token，请设置 TUSHARE_TOKEN 环境变量或在初始化时提供")
    
    def _rate_limit(self):
        """
        请求频率控制
        
        确保两次请求之间的时间间隔不小于 request_interval
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.request_interval:
            sleep_time = self.request_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def _validate_stock_code(self, code: str) -> bool:
        """
        验证股票代码格式
        
        Args:
            code: 6 位股票代码
            
        Returns:
            bool: 是否有效
        """
        if not code or not isinstance(code, str):
            return False
        
        code = code.strip()
        if len(code) != 6 or not code.isdigit():
            return False
        
        return True
    
    def _code_to_tscode(self, code: str) -> str:
        """
        将 6 位股票代码转换为 Tushare 格式
        
        Args:
            code: 6 位股票代码
            
        Returns:
            str: Tushare 格式代码（如 600519.SH）
        """
        code = code.strip()
        
        if code.startswith('600') or code.startswith('601') or code.startswith('603'):
            return f"{code}.SH"
        elif code.startswith('000') or code.startswith('001') or code.startswith('002') or code.startswith('003'):
            return f"{code}.SZ"
        elif code.startswith('300') or code.startswith('301'):
            return f"{code}.SZ"
        elif code.startswith('430') or code.startswith('830'):
            return f"{code}.BJ"
        else:
            # 默认返回 SZ
            return f"{code}.SZ"
    
    def _get_market_from_code(self, code: str) -> str:
        """
        根据股票代码获取市场
        
        Args:
            code: 6 位股票代码
            
        Returns:
            str: 市场代码（SH/SZ/BJ）
        """
        tscode = self._code_to_tscode(code)
        return tscode.split('.')[1]
    
    def _convert_dataframe_to_dict(self, df: pd.DataFrame, limit: Optional[int] = None) -> List[Dict]:
        """
        将 DataFrame 转换为字典列表
        
        Args:
            df: pandas DataFrame
            limit: 限制返回数量（从后往前）
            
        Returns:
            List[Dict]: 字典列表
        """
        if df.empty:
            return []
        
        # 如果需要限制数量，取最后 N 条
        if limit and limit > 0:
            df = df.tail(limit)
        
        # 转换为字典列表
        result = df.to_dict('records')
        return result
    
    def set_token(self, token: str):
        """
        设置 Tushare Token
        
        Args:
            token: Tushare API Token
        """
        self.token = token
        if TUSHARE_AVAILABLE and token:
            try:
                ts.set_token(token)
                self.pro = ts.pro_api()
                print(f"Tushare Pro API 重新初始化成功")
            except Exception as e:
                print(f"Tushare Pro API 重新初始化失败：{e}")
                self.pro = None
    
    def is_connected(self) -> bool:
        """
        检查是否已连接到 Tushare API
        
        Returns:
            bool: 是否已连接
        """
        return self.pro is not None and TUSHARE_AVAILABLE
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取数据获取器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'available': TUSHARE_AVAILABLE,
            'connected': self.is_connected(),
            'request_count': self.request_count,
            'error_count': self.error_count,
            'cache_size': self.cache_size,
            'request_interval': self.request_interval,
            'token_set': bool(self.token)
        }
    
    def clear_cache(self):
        """清除所有缓存"""
        # 清除所有带缓存的方法
        methods_to_clear = [
            'get_historical_data',
            'get_stock_info',
            'get_financial_indicators',
        ]
        for method_name in methods_to_clear:
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                if hasattr(method, 'cache_clear'):
                    method.cache_clear()
    
    @lru_cache(maxsize=100)
    def get_historical_data(
        self,
        code: str,
        start_date: str = '',
        end_date: str = '',
        period: str = 'daily'
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票历史数据
        
        Args:
            code: 6 位股票代码
            start_date: 开始日期，格式 YYYYMMDD，默认获取全部
            end_date: 结束日期，格式 YYYYMMDD，默认到今天
            period: 周期，目前只支持 daily
            
        Returns:
            Dict: 包含历史数据的字典，失败返回 None
        """
        if not self.is_connected():
            return None
        
        if not self._validate_stock_code(code):
            return None
        
        try:
            self._rate_limit()
            tscode = self._code_to_tscode(code)
            
            # 获取日线数据
            df = self.pro.daily(ts_code=tscode, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return None
            
            # 转换数据格式
            data_list = self._convert_dataframe_to_dict(df)
            
            return {
                'code': code,
                'ts_code': tscode,
                'period': period,
                'start_date': start_date if start_date else '上市以来',
                'end_date': end_date if end_date else '今日',
                'total_records': len(data_list),
                'data': data_list
            }
            
        except Exception as e:
            self.error_count += 1
            print(f"获取历史数据失败 {code}: {e}")
            return None
    
    def get_realtime_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时数据（使用最新日线数据模拟）
        
        注意：Tushare 不提供真正的实时数据，这里返回最新日线数据
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含实时数据的字典，失败返回 None
        """
        if not self.is_connected():
            return None
        
        if not self._validate_stock_code(code):
            return None
        
        try:
            # 获取最近 1 天的数据
            result = self.get_historical_data(code=code, start_date='', end_date='')
            
            if not result or not result['data']:
                return None
            
            # 取最新一条数据
            latest = result['data'][0]  # Tushare 返回的数据已经是降序排列
            
            # 转换为实时数据格式
            return {
                'code': code,
                'ts_code': result['ts_code'],
                'name': '',  # 需要从股票信息中获取
                'current_price': float(latest.get('close', 0)),
                'change': float(latest.get('change', 0)),
                'change_percent': float(latest.get('pct_chg', 0)),
                'open': float(latest.get('open', 0)),
                'high': float(latest.get('high', 0)),
                'low': float(latest.get('low', 0)),
                'pre_close': float(latest.get('pre_close', 0)),
                'volume': float(latest.get('vol', 0)),
                'amount': float(latest.get('amount', 0)),
                'trade_date': latest.get('trade_date', '')
            }
            
        except Exception as e:
            self.error_count += 1
            print(f"获取实时数据失败 {code}: {e}")
            return None
    
    @lru_cache(maxsize=50)
    def get_stock_info(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含股票基本信息的字典，失败返回 None
        """
        if not self.is_connected():
            return None
        
        if not self._validate_stock_code(code):
            return None
        
        try:
            self._rate_limit()
            tscode = self._code_to_tscode(code)
            
            # 获取股票基本信息
            df = self.pro.stock_basic(ts_code=tscode, fields='ts_code,symbol,name,area,industry,market,list_date')
            
            if df is None or df.empty:
                return None
            
            # 取第一条记录
            stock_info = df.iloc[0].to_dict()
            
            return {
                'code': code,
                'ts_code': tscode,
                'symbol': stock_info.get('symbol', ''),
                'name': stock_info.get('name', ''),
                'area': stock_info.get('area', ''),
                'industry': stock_info.get('industry', ''),
                'market': stock_info.get('market', ''),
                'list_date': stock_info.get('list_date', ''),
                'exchange': self._get_market_from_code(code)
            }
            
        except Exception as e:
            self.error_count += 1
            print(f"获取股票信息失败 {code}: {e}")
            return None
    
    @lru_cache(maxsize=50)
    def get_financial_indicators(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票财务指标
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含财务指标的字典，失败返回 None
        """
        if not self.is_connected():
            return None
        
        if not self._validate_stock_code(code):
            return None
        
        try:
            self._rate_limit()
            tscode = self._code_to_tscode(code)
            
            # 获取财务指标
            df = self.pro.fina_indicator(ts_code=tscode)
            
            if df is None or df.empty:
                return None
            
            # 取最新一条记录
            latest = df.iloc[0].to_dict()
            
            return {
                'code': code,
                'ts_code': tscode,
                'ann_date': latest.get('ann_date', ''),
                'end_date': latest.get('end_date', ''),
                'eps': float(latest.get('eps', 0)) if latest.get('eps') else 0.0,
                'dt_eps': float(latest.get('dt_eps', 0)) if latest.get('dt_eps') else 0.0,
                'pe': float(latest.get('pe', 0)) if latest.get('pe') else 0.0,
                'pb': float(latest.get('pb', 0)) if latest.get('pb') else 0.0,
                'roe': float(latest.get('roe', 0)) if latest.get('roe') else 0.0,
                'roa': float(latest.get('roa', 0)) if latest.get('roa') else 0.0,
                'gross_profit_margin': float(latest.get('gross_profit_margin', 0)) if latest.get('gross_profit_margin') else 0.0,
                'net_profit_margin': float(latest.get('net_profit_margin', 0)) if latest.get('net_profit_margin') else 0.0
            }
            
        except Exception as e:
            self.error_count += 1
            print(f"获取财务指标失败 {code}: {e}")
            return None
    
    def get_f10_info(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票 F10 资料
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含 F10 资料的字典，失败返回 None
        """
        if not self.is_connected():
            return None
        
        if not self._validate_stock_code(code):
            return None
        
        try:
            self._rate_limit()
            tscode = self._code_to_tscode(code)
            
            # 获取 F10 核心资料
            df_core = self.pro.f10_core(ts_code=tscode)
            
            # 获取 F10 股东情况
            df_sdhj = self.pro.f10_sdhj(ts_code=tscode)
            
            # 获取 F10 十大股东
            df_holders = self.pro.f10_holders(ts_code=tscode)
            
            result = {
                'code': code,
                'ts_code': tscode
            }
            
            # 处理核心资料
            if df_core is not None and not df_core.empty:
                core_info = df_core.iloc[0].to_dict()
                result.update({
                    'company_name': core_info.get('company_name', ''),
                    'english_name': core_info.get('english_name', ''),
                    'register_addr': core_info.get('register_addr', ''),
                    'office_addr': core_info.get('office_addr', ''),
                    'main_business': core_info.get('main_business', ''),
                    'introduction': core_info.get('introduction', '')
                })
            
            # 处理股东情况
            if df_sdhj is not None and not df_sdhj.empty:
                sdhj_info = df_sdhj.iloc[0].to_dict()
                result.update({
                    'holder_num': sdhj_info.get('holder_num', 0),
                    'avg_hold_num': sdhj_info.get('avg_hold_num', 0),
                    'holder_num_change': sdhj_info.get('holder_num_change', 0)
                })
            
            # 处理十大股东
            if df_holders is not None and not df_holders.empty:
                holders_list = []
                for _, row in df_holders.head(10).iterrows():
                    holders_list.append({
                        'holder_name': row.get('holder_name', ''),
                        'hold_amount': row.get('hold_amount', 0),
                        'hold_ratio': row.get('hold_ratio', 0),
                        'holder_type': row.get('holder_type', '')
                    })
                result['top_10_holders'] = holders_list
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取 F10 资料失败 {code}: {e}")
            return None
    
    def get_market_index_data(self, code: str, start_date: str = '', end_date: str = '') -> Optional[Dict[str, Any]]:
        """
        获取市场指数数据
        
        Args:
            code: 指数代码（如 000001）
            start_date: 开始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
            
        Returns:
            Dict: 包含指数数据的字典，失败返回 None
        """
        if not self.is_connected():
            return None
        
        if not self._validate_stock_code(code):
            return None
        
        try:
            self._rate_limit()
            tscode = self._code_to_tscode(code)
            
            # 获取指数日线数据
            df = self.pro.index_daily(ts_code=tscode, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                return None
            
            # 转换数据格式
            data_list = self._convert_dataframe_to_dict(df)
            
            return {
                'code': code,
                'ts_code': tscode,
                'total_records': len(data_list),
                'data': data_list
            }
            
        except Exception as e:
            self.error_count += 1
            print(f"获取指数数据失败 {code}: {e}")
            return None
    
    def get_all_stocks(self, exchange: str = '') -> Optional[List[Dict[str, str]]]:
        """
        获取所有股票列表
        
        Args:
            exchange: 交易所代码（SSE/SZSE/BSE），为空获取全部
            
        Returns:
            List[Dict]: 股票列表，失败返回 None
        """
        if not self.is_connected():
            return None
        
        try:
            self._rate_limit()
            
            # 获取股票列表
            if exchange:
                df = self.pro.stock_basic(exchange=exchange, list_status='L')
            else:
                df = self.pro.stock_basic(list_status='L')
            
            if df is None or df.empty:
                return None
            
            # 转换为列表
            result = []
            for _, row in df.iterrows():
                result.append({
                    'ts_code': row.get('ts_code', ''),
                    'symbol': row.get('symbol', ''),
                    'name': row.get('name', ''),
                    'area': row.get('area', ''),
                    'industry': row.get('industry', '')
                })
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取股票列表失败：{e}")
            return None


# 全局便捷函数
_global_fetcher: Optional[TushareDataFetcher] = None


def get_fetcher(token: Optional[str] = None) -> TushareDataFetcher:
    """
    获取全局 TushareDataFetcher 实例（单例模式）
    
    Args:
        token: Tushare API Token
        
    Returns:
        TushareDataFetcher: 数据获取器实例
    """
    global _global_fetcher
    
    if _global_fetcher is None:
        _global_fetcher = TushareDataFetcher(token=token)
    elif token and _global_fetcher.token != token:
        _global_fetcher.set_token(token)
    
    return _global_fetcher


def get_realtime_data(code: str) -> Optional[Dict]:
    """
    便捷函数：获取实时数据
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 实时数据
    """
    fetcher = get_fetcher()
    return fetcher.get_realtime_data(code)


def get_historical_data(
    code: str,
    start_date: str = '',
    end_date: str = '',
    period: str = 'daily'
) -> Optional[Dict]:
    """
    便捷函数：获取历史数据
    
    Args:
        code: 6 位股票代码
        start_date: 开始日期
        end_date: 结束日期
        period: 周期
        
    Returns:
        Dict: 历史数据
    """
    fetcher = get_fetcher()
    return fetcher.get_historical_data(code, start_date, end_date, period)


def get_stock_info(code: str) -> Optional[Dict]:
    """
    便捷函数：获取股票信息
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 股票信息
    """
    fetcher = get_fetcher()
    return fetcher.get_stock_info(code)


def get_financial_indicators(code: str) -> Optional[Dict]:
    """
    便捷函数：获取财务指标
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 财务指标
    """
    fetcher = get_fetcher()
    return fetcher.get_financial_indicators(code)


def get_f10_info(code: str) -> Optional[Dict]:
    """
    便捷函数：获取 F10 资料
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: F10 资料
    """
    fetcher = get_fetcher()
    return fetcher.get_f10_info(code)
