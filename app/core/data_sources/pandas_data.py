# -*- coding: utf-8 -*-
"""
pandas_datareader 数据获取核心模块

封装 pandas_datareader API，提供统一的宏观经济数据获取服务
- 支持美联储 FRED 经济数据
- 支持世界银行数据
- 支持外汇汇率
- 支持美国国债收益率
- 支持 OECD、Eurostat 数据

符合项目规范：
- 只返回数据（dict/list/DataFrame），不返回 HTTP 响应
- 完整的异常处理
- 所有函数有文档字符串
- 使用类型注解
"""

import os
import time
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Any, Union

try:
    import pandas_datareader as pdr
    import pandas as pd
    PANDAS_DATAREADER_AVAILABLE = True
except ImportError:
    PANDAS_DATAREADER_AVAILABLE = False
    pdr = None
    pd = None


class PandasDataFetcher:
    """
    pandas_datareader 数据获取器
    
    提供统一的宏观经济数据获取接口，封装 pandas_datareader 常用功能
    支持缓存、错误处理和重试机制
    """
    
    def __init__(self, cache_size: int = 100, request_interval: float = 1.0, fred_api_key: Optional[str] = None):
        """
        初始化数据获取器
        
        Args:
            cache_size: LRU 缓存大小，默认 100
            request_interval: 请求间隔（秒），避免被限流，默认 1.0 秒
            fred_api_key: FRED API Key，可从 https://fred.stlouisfed.org/docs/api/api_key.html 获取
        """
        self.cache_size = cache_size
        self.request_interval = request_interval
        self.last_request_time = 0.0
        self.request_count = 0
        self.error_count = 0
        
        # 设置 FRED API Key
        self.fred_api_key = fred_api_key or os.environ.get('FRED_API_KEY', '')
        if self.fred_api_key:
            os.environ['FRED_API_KEY'] = self.fred_api_key
        
        if not PANDAS_DATAREADER_AVAILABLE:
            print("警告：pandas_datareader 库未安装，请运行：pip install pandas-datareader")
    
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
    
    def _validate_date(self, date_str: str) -> bool:
        """
        验证日期格式
        
        Args:
            date_str: 日期字符串，格式应为 "YYYY-MM-DD"
            
        Returns:
            bool: 是否有效
        """
        if not date_str or not isinstance(date_str, str):
            return False
        
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _validate_year(self, year: Union[str, int]) -> bool:
        """
        验证年份格式
        
        Args:
            year: 年份字符串或整数
            
        Returns:
            bool: 是否有效
        """
        try:
            year_int = int(year)
            return 1900 <= year_int <= 2100
        except (ValueError, TypeError):
            return False
    
    def _convert_dataframe_to_dict(
        self, 
        df: Any, 
        limit: Optional[int] = None,
        include_index: bool = True
    ) -> List[Dict]:
        """
        将 DataFrame 转换为字典列表
        
        Args:
            df: pandas DataFrame
            limit: 限制返回的记录数（从最新开始）
            include_index: 是否包含索引列
            
        Returns:
            List[Dict]: 字典列表
        """
        if df is None or (hasattr(df, 'empty') and df.empty):
            return []
        
        try:
            # 限制记录数
            if limit:
                df = df.tail(limit)
            
            # 重置索引（如果需要包含索引）
            if include_index:
                df_reset = df.reset_index()
                records = df_reset.to_dict('records')
            else:
                records = df.to_dict('records')
            
            # 处理 datetime 类型和 numpy 类型
            for record in records:
                for key, value in record.items():
                    if hasattr(value, 'strftime'):  # datetime 类型
                        record[key] = value.strftime('%Y-%m-%d')
                    elif hasattr(value, 'item'):  # numpy 类型
                        record[key] = value.item()
                    elif pd.isna(value):  # NaN 值处理
                        record[key] = None
            
            return records
        except Exception as e:
            print(f"DataFrame 转换失败：{e}")
            return []
    
    def _get_dataframe_summary(self, df: Any) -> Dict[str, Any]:
        """
        获取 DataFrame 摘要信息
        
        Args:
            df: pandas DataFrame
            
        Returns:
            Dict: 摘要信息
        """
        if df is None or (hasattr(df, 'empty') and df.empty):
            return {
                'total_records': 0,
                'columns': [],
                'start_date': None,
                'end_date': None
            }
        
        try:
            # 获取日期范围
            if len(df) > 0:
                if hasattr(df.index, 'min') and hasattr(df.index, 'max'):
                    start_date = df.index.min().strftime('%Y-%m-%d') if hasattr(df.index.min(), 'strftime') else str(df.index.min())
                    end_date = df.index.max().strftime('%Y-%m-%d') if hasattr(df.index.max(), 'strftime') else str(df.index.max())
                else:
                    start_date = str(df.index[0])
                    end_date = str(df.index[-1])
            else:
                start_date = None
                end_date = None
            
            return {
                'total_records': len(df),
                'columns': list(df.columns),
                'start_date': start_date,
                'end_date': end_date
            }
        except Exception as e:
            print(f"获取 DataFrame 摘要失败：{e}")
            return {
                'total_records': 0,
                'columns': [],
                'start_date': None,
                'end_date': None
            }
    
    def get_fred_data(
        self,
        series_id: Union[str, List[str]],
        start_date: str = '',
        end_date: str = '',
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取 FRED（美联储经济数据）
        
        Args:
            series_id: 数据系列 ID（如 "GDP", "CPIAUCSL"），支持单个或多个
            start_date: 开始日期，格式 "YYYY-MM-DD"，默认空（获取全部）
            end_date: 结束日期，格式 "YYYY-MM-DD"，默认空（到今天）
            limit: 限制返回记录数，默认 None（不限制）
            
        Returns:
            Dict: 包含 FRED 数据的字典
            {
                'series_id': str/list,      # 数据系列 ID
                'source': 'FRED',           # 数据源
                'total_records': int,       # 总记录数
                'start_date': str,          # 开始日期
                'end_date': str,            # 结束日期
                'columns': list,            # 列名
                'data': List[Dict],         # 数据列表
                'timestamp': str            # 数据时间戳
            }
        """
        if not PANDAS_DATAREADER_AVAILABLE:
            print("pandas_datareader 不可用")
            return None
        
        try:
            self._rate_limit()
            
            # 参数验证
            if not series_id:
                print("数据系列 ID 不能为空")
                return None
            
            # 日期验证
            if start_date and not self._validate_date(start_date):
                print(f"无效的开始日期格式：{start_date}")
                return None
            
            if end_date and not self._validate_date(end_date):
                print(f"无效的结束日期格式：{end_date}")
                return None
            
            # 获取数据
            if start_date and end_date:
                df = pdr.DataReader(
                    series_id, 
                    'fred', 
                    start=start_date, 
                    end=end_date
                )
            elif start_date:
                df = pdr.DataReader(series_id, 'fred', start=start_date)
            elif end_date:
                df = pdr.DataReader(series_id, 'fred', end=end_date)
            else:
                df = pdr.DataReader(series_id, 'fred')
            
            if df is None or (hasattr(df, 'empty') and df.empty):
                print(f"获取 FRED 数据失败：{series_id}")
                return None
            
            # 获取摘要信息
            summary = self._get_dataframe_summary(df)
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(df, limit=limit)
            
            # 系列 ID 转字符串（如果是列表）
            series_id_str = series_id if isinstance(series_id, str) else ', '.join(series_id)
            
            result = {
                'series_id': series_id_str,
                'source': 'FRED',
                'total_records': summary['total_records'],
                'start_date': summary['start_date'],
                'end_date': summary['end_date'],
                'columns': summary['columns'],
                'data': data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取 FRED 数据失败 [{series_id}]: {e}")
            return None
    
    def get_world_bank_data(
        self,
        indicator: str,
        countries: Optional[Union[str, List[str]]] = None,
        start_year: Union[str, int] = '2010',
        end_year: Union[str, int] = '',
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取世界银行数据
        
        Args:
            indicator: 指标代码（如 "NY.GDP.MKTP.CD"）
            countries: 国家代码（如 "CN", "US"），默认 None（所有国家）
            start_year: 开始年份，默认 '2010'
            end_year: 结束年份，默认空（最新）
            limit: 限制返回记录数，默认 None（不限制）
            
        Returns:
            Dict: 包含世界银行数据的字典
            {
                'indicator': str,           # 指标代码
                'countries': str/list,      # 国家代码
                'source': 'World Bank',     # 数据源
                'total_records': int,       # 总记录数
                'start_year': str,          # 开始年份
                'end_year': str,            # 结束年份
                'data': List[Dict],         # 数据列表
                'timestamp': str            # 数据时间戳
            }
        """
        if not PANDAS_DATAREADER_AVAILABLE:
            print("pandas_datareader 不可用")
            return None
        
        try:
            self._rate_limit()
            
            # 参数验证
            if not indicator:
                print("指标代码不能为空")
                return None
            
            # 年份验证
            if start_year and not self._validate_year(start_year):
                print(f"无效的开始年份：{start_year}")
                return None
            
            if end_year and not self._validate_year(end_year):
                print(f"无效的结束年份：{end_year}")
                return None
            
            # 获取数据
            if countries:
                if end_year:
                    df = pdr.DataReader(
                        indicator, 
                        'wb', 
                        countries=countries,
                        start=start_year, 
                        end=end_year
                    )
                else:
                    df = pdr.DataReader(
                        indicator, 
                        'wb', 
                        countries=countries,
                        start=start_year
                    )
            else:
                if end_year:
                    df = pdr.DataReader(
                        indicator, 
                        'wb', 
                        start=start_year, 
                        end=end_year
                    )
                else:
                    df = pdr.DataReader(
                        indicator, 
                        'wb', 
                        start=start_year
                    )
            
            if df is None or (hasattr(df, 'empty') and df.empty):
                print(f"获取世界银行数据失败：{indicator}")
                return None
            
            # 获取摘要信息
            summary = self._get_dataframe_summary(df)
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(df, limit=limit)
            
            # 国家代码转字符串（如果是列表）
            countries_str = countries if isinstance(countries, str) else ', '.join(countries) if countries else 'All'
            
            result = {
                'indicator': indicator,
                'countries': countries_str,
                'source': 'World Bank',
                'total_records': summary['total_records'],
                'start_year': str(start_year),
                'end_year': str(end_year) if end_year else '最新',
                'data': data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取世界银行数据失败 [{indicator}]: {e}")
            return None
    
    def get_exchange_rates(
        self,
        currency_pairs: Union[str, List[str]],
        start_date: str = '',
        end_date: str = '',
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取外汇汇率数据（通过 FRED）
        
        Args:
            currency_pairs: 货币对（如 "DEXUSEU", "DEXUSCN"），支持单个或多个
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"
            limit: 限制返回记录数，默认 None（不限制）
            
        Returns:
            Dict: 包含外汇汇率数据的字典
            
        常用货币对代码:
            - DEXUSEU: USD/EUR
            - DEXUSUK: USD/GBP
            - DEXUSJP: USD/JPY
            - DEXUSCN: USD/CNY
            - DEXUSCA: USD/CAD
            - DEXUSMX: USD/MXN
        """
        # 直接调用 FRED 数据接口
        return self.get_fred_data(
            series_id=currency_pairs,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    def get_treasury_yields(
        self,
        maturities: Optional[Union[str, List[str]]] = None,
        start_date: str = '',
        end_date: str = '',
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取美国国债收益率数据
        
        Args:
            maturities: 期限（如 "DGS10", "DGS2"），支持单个或多个
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"
            limit: 限制返回记录数，默认 None（不限制）
            
        Returns:
            Dict: 包含国债收益率数据的字典
            
        常用期限代码:
            - DGS3MO: 3 个月期
            - DGS6MO: 6 个月期
            - DGS1: 1 年期
            - DGS2: 2 年期
            - DGS5: 5 年期
            - DGS10: 10 年期
            - DGS30: 30 年期
        """
        # 默认获取所有主要期限
        if maturities is None:
            maturities = ['DGS3MO', 'DGS6MO', 'DGS1', 'DGS2', 'DGS5', 'DGS10', 'DGS30']
        
        # 直接调用 FRED 数据接口
        return self.get_fred_data(
            series_id=maturities,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    def get_oecd_data(
        self,
        indicator: str,
        countries: Optional[Union[str, List[str]]] = None,
        start_date: str = '',
        end_date: str = '',
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取 OECD（经合组织）数据
        
        Args:
            indicator: 指标代码（如 "UNRATE", "GDP"）
            countries: 国家代码（如 "USA", "CHN"），默认 None（所有国家）
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"
            limit: 限制返回记录数，默认 None（不限制）
            
        Returns:
            Dict: 包含 OECD 数据的字典
        """
        if not PANDAS_DATAREADER_AVAILABLE:
            print("pandas_datareader 不可用")
            return None
        
        try:
            self._rate_limit()
            
            # 参数验证
            if not indicator:
                print("指标代码不能为空")
                return None
            
            # 获取数据
            if countries:
                series_id = f"{countries}.{indicator}" if isinstance(countries, str) else f"{countries[0]}.{indicator}"
            else:
                series_id = indicator
            
            df = pdr.DataReader(
                series_id,
                'oecd',
                start=start_date if start_date else None,
                end=end_date if end_date else None
            )
            
            if df is None or (hasattr(df, 'empty') and df.empty):
                print(f"获取 OECD 数据失败：{indicator}")
                return None
            
            # 获取摘要信息
            summary = self._get_dataframe_summary(df)
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(df, limit=limit)
            
            result = {
                'indicator': indicator,
                'countries': countries if countries else 'All',
                'source': 'OECD',
                'total_records': summary['total_records'],
                'start_date': summary['start_date'],
                'end_date': summary['end_date'],
                'data': data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取 OECD 数据失败 [{indicator}]: {e}")
            return None
    
    def get_eurostat_data(
        self,
        indicator: str,
        start_date: str = '',
        end_date: str = '',
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Eurostat（欧盟统计局）数据
        
        Args:
            indicator: 指标代码（如 "PRC_HICP_MIDX"）
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"
            limit: 限制返回记录数，默认 None（不限制）
            
        Returns:
            Dict: 包含 Eurostat 数据的字典
        """
        if not PANDAS_DATAREADER_AVAILABLE:
            print("pandas_datareader 不可用")
            return None
        
        try:
            self._rate_limit()
            
            # 参数验证
            if not indicator:
                print("指标代码不能为空")
                return None
            
            # 获取数据
            df = pdr.DataReader(
                indicator,
                'eurostat',
                start=start_date if start_date else None,
                end=end_date if end_date else None
            )
            
            if df is None or (hasattr(df, 'empty') and df.empty):
                print(f"获取 Eurostat 数据失败：{indicator}")
                return None
            
            # 获取摘要信息
            summary = self._get_dataframe_summary(df)
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(df, limit=limit)
            
            result = {
                'indicator': indicator,
                'source': 'Eurostat',
                'total_records': summary['total_records'],
                'start_date': summary['start_date'],
                'end_date': summary['end_date'],
                'data': data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取 Eurostat 数据失败 [{indicator}]: {e}")
            return None
    
    @lru_cache(maxsize=100)
    def get_data(
        self,
        name: str,
        data_source: str,
        start_date: str = '',
        end_date: str = '',
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        通用数据获取接口（支持缓存）
        
        Args:
            name: 数据系列名称
            data_source: 数据源（fred, wb, oecd, eurostat）
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 其他参数
            
        Returns:
            Dict: 包含数据的字典
        """
        if not PANDAS_DATAREADER_AVAILABLE:
            print("pandas_datareader 不可用")
            return None
        
        try:
            self._rate_limit()
            
            # 根据数据源调用不同接口
            if data_source.lower() == 'fred':
                return self.get_fred_data(name, start_date, end_date)
            elif data_source.lower() == 'wb':
                return self.get_world_bank_data(name, start_year=start_date, end_year=end_date)
            elif data_source.lower() == 'oecd':
                return self.get_oecd_data(name, start_date=start_date, end_date=end_date)
            elif data_source.lower() == 'eurostat':
                return self.get_eurostat_data(name, start_date=start_date, end_date=end_date)
            else:
                # 使用通用接口
                df = pdr.DataReader(
                    name,
                    data_source=data_source,
                    start=start_date if start_date else None,
                    end=end_date if end_date else None,
                    **kwargs
                )
                
                if df is None or (hasattr(df, 'empty') and df.empty):
                    print(f"获取数据失败：{name}")
                    return None
                
                summary = self._get_dataframe_summary(df)
                data = self._convert_dataframe_to_dict(df)
                
                result = {
                    'name': name,
                    'source': data_source,
                    'total_records': summary['total_records'],
                    'start_date': summary['start_date'],
                    'end_date': summary['end_date'],
                    'data': data,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取数据失败 [{name}]: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取数据获取器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'available': PANDAS_DATAREADER_AVAILABLE,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'cache_size': self.cache_size,
            'request_interval': self.request_interval,
            'fred_api_key_configured': bool(self.fred_api_key),
            'last_request_time': datetime.fromtimestamp(self.last_request_time).strftime('%Y-%m-%d %H:%M:%S') if self.last_request_time > 0 else 'N/A'
        }
    
    def clear_cache(self):
        """清除缓存"""
        self.get_data.cache_clear()


# 全局数据获取器实例
_global_fetcher = None


def get_fetcher(fred_api_key: Optional[str] = None) -> PandasDataFetcher:
    """
    获取全局数据获取器实例
    
    Args:
        fred_api_key: FRED API Key
        
    Returns:
        PandasDataFetcher: 数据获取器实例
    """
    global _global_fetcher
    if _global_fetcher is None:
        _global_fetcher = PandasDataFetcher(fred_api_key=fred_api_key)
    return _global_fetcher


# 便捷函数

def get_fred_data(
    series_id: Union[str, List[str]],
    start_date: str = '',
    end_date: str = '',
    limit: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    获取 FRED 经济数据（便捷函数）
    
    Args:
        series_id: 数据系列 ID
        start_date: 开始日期
        end_date: 结束日期
        limit: 限制返回记录数
        
    Returns:
        Dict: FRED 数据
    """
    return get_fetcher().get_fred_data(series_id, start_date, end_date, limit)


def get_world_bank_data(
    indicator: str,
    countries: Optional[Union[str, List[str]]] = None,
    start_year: Union[str, int] = '2010',
    end_year: Union[str, int] = '',
    limit: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    获取世界银行数据（便捷函数）
    
    Args:
        indicator: 指标代码
        countries: 国家代码
        start_year: 开始年份
        end_year: 结束年份
        limit: 限制返回记录数
        
    Returns:
        Dict: 世界银行数据
    """
    return get_fetcher().get_world_bank_data(indicator, countries, start_year, end_year, limit)


def get_exchange_rates(
    currency_pairs: Union[str, List[str]],
    start_date: str = '',
    end_date: str = '',
    limit: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    获取外汇汇率（便捷函数）
    
    Args:
        currency_pairs: 货币对
        start_date: 开始日期
        end_date: 结束日期
        limit: 限制返回记录数
        
    Returns:
        Dict: 外汇汇率数据
    """
    return get_fetcher().get_exchange_rates(currency_pairs, start_date, end_date, limit)


def get_treasury_yields(
    maturities: Optional[Union[str, List[str]]] = None,
    start_date: str = '',
    end_date: str = '',
    limit: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    获取美国国债收益率（便捷函数）
    
    Args:
        maturities: 期限
        start_date: 开始日期
        end_date: 结束日期
        limit: 限制返回记录数
        
    Returns:
        Dict: 国债收益率数据
    """
    return get_fetcher().get_treasury_yields(maturities, start_date, end_date, limit)


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("pandas_datareader 数据获取模块测试")
    print("=" * 60)
    
    # 初始化数据获取器
    fetcher = PandasDataFetcher(request_interval=2.0)
    
    # 测试 1: 获取美国 GDP 数据
    print("\n1. 测试获取美国 GDP 数据")
    gdp_data = fetcher.get_fred_data('GDP', start_date='2020-01-01', limit=10)
    if gdp_data:
        print(f"数据源：{gdp_data['source']}")
        print(f"总记录数：{gdp_data['total_records']}")
        print(f"最近 5 条数据:")
        for item in gdp_data['data'][-5:]:
            print(f"  {item}")
    else:
        print("获取失败")
    
    # 测试 2: 获取失业率数据
    print("\n2. 测试获取失业率数据 (UNRATE)")
    unemp_data = fetcher.get_fred_data('UNRATE', start_date='2023-01-01', limit=5)
    if unemp_data:
        print(f"总记录数：{unemp_data['total_records']}")
        print(f"最近 5 条数据:")
        for item in unemp_data['data'][-5:]:
            print(f"  {item}")
    else:
        print("获取失败")
    
    # 测试 3: 获取外汇汇率
    print("\n3. 测试获取外汇汇率 (USD/CNY)")
    fx_data = fetcher.get_exchange_rates('DEXUSCN', start_date='2023-01-01', limit=5)
    if fx_data:
        print(f"总记录数：{fx_data['total_records']}")
        print(f"最近 5 条数据:")
        for item in fx_data['data'][-5:]:
            print(f"  {item}")
    else:
        print("获取失败")
    
    # 测试 4: 获取国债收益率曲线
    print("\n4. 测试获取国债收益率曲线")
    treasury_data = fetcher.get_treasury_yields(start_date='2024-01-01', limit=5)
    if treasury_data:
        print(f"总记录数：{treasury_data['total_records']}")
        print(f"最近 5 条数据:")
        for item in treasury_data['data'][-5:]:
            print(f"  {item}")
    else:
        print("获取失败")
    
    # 测试 5: 获取世界银行数据
    print("\n5. 测试获取世界银行 GDP 数据 (中国)")
    wb_data = fetcher.get_world_bank_data(
        'NY.GDP.MKTP.CD',
        countries='CN',
        start_year='2018',
        limit=5
    )
    if wb_data:
        print(f"数据源：{wb_data['source']}")
        print(f"总记录数：{wb_data['total_records']}")
        print(f"最近 5 条数据:")
        for item in wb_data['data'][-5:]:
            print(f"  {item}")
    else:
        print("获取失败")
    
    # 测试 6: 获取数据获取器状态
    print("\n6. 获取数据获取器状态")
    status = fetcher.get_status()
    print(f"pandas_datareader 可用：{status['available']}")
    print(f"请求次数：{status['request_count']}")
    print(f"错误次数：{status['error_count']}")
    print(f"FRED API Key 配置：{status['fred_api_key_configured']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
