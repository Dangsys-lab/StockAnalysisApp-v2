# -*- coding: utf-8 -*-
"""
mootdx 数据获取核心模块

封装 mootdx 本地通达信数据接口，提供统一的股票数据获取服务
- 实时行情数据
- 历史 K 线数据
- 财务指标数据（PE、PB、ROE 等）
- 分钟线数据

符合项目规范：
- 只返回数据（dict/list/DataFrame），不返回 HTTP 响应
- 完整的异常处理
- 所有函数有文档字符串
- 使用类型注解

优势：
- ✅ 本地数据，无请求限制
- ✅ 速度极快（毫秒级）
- ✅ 数据稳定，不依赖网络
"""

import os
import time
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    from mootdx.quotes import Quotes
    MOOTDX_AVAILABLE = True
    Quotes = Quotes
except ImportError:
    MOOTDX_AVAILABLE = False
    Quotes = None


class MootdxDataFetcher:
    """
    mootdx 数据获取器
    
    提供统一的本地股票数据获取接口，封装 mootdx 常用功能
    支持缓存、错误处理和本地数据快速读取
    """
    
    def __init__(self, cache_size: int = 100, tdx_dir: str = None):
        """
        初始化数据获取器
        
        Args:
            cache_size: LRU 缓存大小，默认 100
            tdx_dir: 通达信数据目录，默认 None（自动检测）
        """
        self.cache_size = cache_size
        self.tdx_dir = tdx_dir
        self.request_count = 0
        self.error_count = 0
        self.quotes = None
        
        if not MOOTDX_AVAILABLE:
            print("警告：mootdx 库未安装，请运行：pip install mootdx")
            return
        
        try:
            # 初始化 quotes 实例（标准市场）
            self.quotes = Quotes.factory(market='std')
            print("mootdx 初始化成功")
        except Exception as e:
            print(f"mootdx 初始化失败：{e}")
            self.quotes = None
    
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
    
    def _get_market(self, code: str) -> str:
        """
        根据股票代码获取市场标识
        
        Args:
            code: 6 位股票代码
            
        Returns:
            str: 市场标识（1=上海，0=深圳）
        """
        code = code.strip()
        
        if code.startswith('6') or code.startswith('9'):
            return '1'  # 上海
        elif code.startswith('0') or code.startswith('3'):
            return '0'  # 深圳
        elif code.startswith('4') or code.startswith('8'):
            return '0'  # 北京（使用深圳市场标识）
        else:
            return '1'  # 默认上海
    
    def _convert_dataframe_to_dict(self, df: pd.DataFrame, limit: Optional[int] = None) -> List[Dict]:
        """
        将 DataFrame 转换为字典列表
        
        Args:
            df: pandas DataFrame
            limit: 限制返回的记录数（从最新开始）
            
        Returns:
            List[Dict]: 字典列表
        """
        if df is None or df.empty:
            return []
        
        try:
            # 限制记录数
            if limit:
                df = df.tail(limit)
            
            # 转换为字典列表
            records = df.to_dict('records')
            
            # 处理 datetime 类型
            for record in records:
                for key, value in record.items():
                    if isinstance(value, (pd.Timestamp, datetime)):
                        record[key] = value.strftime('%Y-%m-%d')
                    elif hasattr(value, 'item'):  # numpy 类型
                        record[key] = value.item()
            
            return records
        except Exception as e:
            print(f"DataFrame 转换失败：{e}")
            return []
    
    def get_realtime_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情数据
        
        Args:
            code: 6 位股票代码（如 "600519"）
            
        Returns:
            Dict: 包含实时行情数据的字典，失败返回 None
            {
                'code': str,          # 股票代码
                'name': str,          # 股票名称
                'current_price': float,  # 当前价格
                'open': float,        # 开盘价
                'high': float,        # 最高价
                'low': float,         # 最低价
                'prev_close': float,  # 昨收价
                'volume': int,        # 成交量（手）
                'amount': float,      # 成交额（元）
                'timestamp': str      # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        if not self.quotes:
            print("mootdx 未初始化")
            return None
        
        try:
            self.request_count += 1
            
            # 获取实时行情
            market = self._get_market(code)
            df = self.quotes.quote(market=market, symbol=code)
            
            if df is None or df.empty or len(df) == 0:
                print(f"未找到股票 {code} 的实时数据")
                return None
            
            row = df.iloc[0]
            
            result = {
                'code': code,
                'name': str(row.get('名称', '')),
                'current_price': float(row.get('价格', 0)),
                'open': float(row.get('开盘', 0)),
                'high': float(row.get('最高', 0)),
                'low': float(row.get('最低', 0)),
                'prev_close': float(row.get('昨收', 0)),
                'volume': int(row.get('成交量', 0)),
                'amount': float(row.get('成交额', 0)),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取实时数据失败 [{code}]: {e}")
            return None
    
    @lru_cache(maxsize=100)
    def get_historical_data(
        self,
        code: str,
        period: str = 'daily',
        start_date: str = '',
        end_date: str = ''
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票历史 K 线数据
        
        Args:
            code: 6 位股票代码
            period: 周期，可选 'daily'/'weekly'/'monthly'，默认 'daily'
            start_date: 开始日期，格式"YYYYMMDD"，默认空（获取全部）
            end_date: 结束日期，格式"YYYYMMDD"，默认空（获取全部）
            
        Returns:
            Dict: 包含历史数据的字典
            {
                'code': str,          # 股票代码
                'period': str,        # 周期
                'total_records': int, # 总记录数
                'data': List[Dict],   # K 线数据列表
                'latest_date': str    # 最新日期
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        if not self.quotes:
            print("mootdx 未初始化")
            return None
        
        try:
            self.request_count += 1
            
            # 使用 bars 方法获取 K 线数据（mootdx 的 bars 接口不需要 market 参数）
            df = self.quotes.bars(symbol=code)
            
            if df is None or df.empty:
                print(f"获取历史数据失败：{code}")
                return None
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(df)
            
            # 获取最新日期
            latest_date = ''
            if not df.empty and 'datetime' in df.columns:
                latest_date = df['datetime'].iloc[-1].strftime('%Y-%m-%d')
            
            result = {
                'code': code,
                'period': period,
                'total_records': len(df),
                'data': data,
                'latest_date': latest_date
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取历史数据失败 [{code}]: {e}")
            return None
    
    def get_financial_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票财务指标数据（PE、PB、ROE 等）
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含财务指标的字典
            {
                'code': str,          # 股票代码
                'pe_ratio': float,    # 市盈率（TTM）
                'pb_ratio': float,    # 市净率
                'roe': float,         # 净资产收益率
                'total_shares': float, # 总股本（万股）
                'circulating_shares': float, # 流通股本（万股）
                'eps': float,         # 每股收益
                'bvps': float,        # 每股净资产
                'timestamp': str      # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        if not self.quotes:
            print("mootdx 未初始化")
            return None
        
        try:
            self.request_count += 1
            
            # 获取财务数据（mootdx 的 finance 接口不需要 market 参数）
            df = self.quotes.finance(symbol=code)
            
            if df is None or df.empty:
                print(f"获取财务数据失败：{code}")
                return None
            
            row = df.iloc[0]
            
            # 计算 PE、PB、ROE 等指标
            # 注意：mootdx 返回的财务数据字段名可能不同
            total_shares = float(row.get('zongguben', 0))  # 总股本
            circulating_shares = float(row.get('liutongguben', 0))  # 流通股本
            net_assets = float(row.get('jingzichan', 0))  # 净资产
            net_profit = float(row.get('jinglirun', 0))  # 净利润
            
            # 计算 ROE（净资产收益率）= 净利润 / 净资产
            roe = (net_profit / net_assets * 100) if net_assets > 0 else 0
            
            # 获取实时股价用于计算 PE、PB
            realtime = self.get_realtime_data(code)
            current_price = realtime['current_price'] if realtime else 0
            
            # 计算 PE（市盈率）= 市值 / 净利润
            market_cap = current_price * total_shares
            pe_ratio = (market_cap / net_profit) if net_profit > 0 else 0
            
            # 计算 PB（市净率）= 市值 / 净资产
            pb_ratio = (market_cap / net_assets) if net_assets > 0 else 0
            
            # 每股收益 EPS = 净利润 / 总股本
            eps = net_profit / total_shares if total_shares > 0 else 0
            
            # 每股净资产 BVPS = 净资产 / 总股本
            bvps = net_assets / total_shares if total_shares > 0 else 0
            
            result = {
                'code': code,
                'pe_ratio': pe_ratio,
                'pb_ratio': pb_ratio,
                'roe': roe,
                'total_shares': total_shares,
                'circulating_shares': circulating_shares,
                'eps': eps,
                'bvps': bvps,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取财务数据失败 [{code}]: {e}")
            return None
    
    def get_basic_financials(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本财务指标（ROE、营收增长率、净利润增长率等）
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含基本财务指标的字典
            {
                'code': str,              # 股票代码
                'roe': float,             # ROE（净资产收益率）
                'revenue_growth': float,  # 营收增长率
                'profit_growth': float,   # 净利润增长率
                'gross_margin': float,    # 毛利率
                'net_margin': float,      # 净利率
                'debt_ratio': float,      # 资产负债率
                'timestamp': str          # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        if not self.quotes:
            print("mootdx 未初始化")
            return None
        
        try:
            self.request_count += 1
            
            # 获取财务数据
            market = self._get_market(code)
            df = self.quotes.finance(market=market, symbol=code)
            
            if df is None or df.empty:
                print(f"获取基本财务指标失败：{code}")
                return None
            
            row = df.iloc[0]
            
            # 从财务数据中提取关键指标
            result = {
                'code': code,
                'roe': float(row.get('roe', 0)),
                'revenue_growth': float(row.get('营业收入同比增长率', 0)),
                'profit_growth': float(row.get('净利润同比增长率', 0)),
                'gross_margin': float(row.get('毛利率', 0)),
                'net_margin': float(row.get('净利率', 0)),
                'debt_ratio': float(row.get('资产负债率', 0)),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取基本财务指标失败 [{code}]: {e}")
            return None
    
    def get_comprehensive_fundamentals(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票综合基本面数据（PE、PB、ROE、营收增长率等）
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含综合基本面数据的字典
            {
                # 估值指标
                'pe_ratio': float,            # 市盈率
                'pb_ratio': float,            # 市净率
                
                # 盈利能力
                'roe': float,                 # ROE（净资产收益率）
                'gross_margin': float,        # 毛利率
                'net_margin': float,          # 净利率
                
                # 成长能力
                'revenue_growth': float,      # 营收增长率
                'profit_growth': float,       # 净利润增长率
                
                # 财务健康
                'debt_ratio': float,          # 资产负债率
                
                # 元数据
                'timestamp': str              # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        if not self.quotes:
            print("mootdx 未初始化")
            return None
        
        try:
            self.request_count += 1
            
            # 获取财务数据
            market = self._get_market(code)
            df = self.quotes.finance(market=market, symbol=code)
            
            if df is None or df.empty:
                print(f"获取综合基本面数据失败：{code}")
                return None
            
            row = df.iloc[0]
            
            result = {
                'code': code,
                'pe_ratio': float(row.get('pe', 0)),
                'pb_ratio': float(row.get('pb', 0)),
                'roe': float(row.get('roe', 0)),
                'revenue_growth': float(row.get('营业收入同比增长率', 0)),
                'profit_growth': float(row.get('净利润同比增长率', 0)),
                'gross_margin': float(row.get('毛利率', 0)),
                'net_margin': float(row.get('净利率', 0)),
                'debt_ratio': float(row.get('资产负债率', 0)),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取综合基本面数据失败 [{code}]: {e}")
            return None
    
    def get_minute_data(
        self,
        code: str,
        period: str = '5m',
        limit: int = 100
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票分钟线数据
        
        Args:
            code: 6 位股票代码
            period: 周期，可选 '1m'/'5m'/'15m'/'30m'/'60m'，默认 '5m'
            limit: 限制返回记录数，默认 100
            
        Returns:
            Dict: 包含分钟线数据的字典
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        if not self.quotes:
            print("mootdx 未初始化")
            return None
        
        try:
            self.request_count += 1
            
            market = self._get_market(code)
            
            # 获取分钟线数据
            df = self.quotes.minute(market=market, symbol=code, period=period)
            
            if df is None or df.empty:
                print(f"获取分钟线数据失败：{code}")
                return None
            
            # 限制记录数
            if limit:
                df = df.tail(limit)
            
            data = self._convert_dataframe_to_dict(df)
            
            result = {
                'code': code,
                'period': period,
                'total_records': len(df),
                'data': data
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取分钟线数据失败 [{code}]: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取数据获取器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'available': MOOTDX_AVAILABLE and self.quotes is not None,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'cache_size': self.cache_size,
            'tdx_dir': self.tdx_dir or 'auto'
        }
    
    def clear_cache(self):
        """清除缓存"""
        self.get_historical_data.cache_clear()


# 全局数据获取器实例
_global_fetcher = None


def get_fetcher() -> MootdxDataFetcher:
    """
    获取全局数据获取器实例
    
    Returns:
        MootdxDataFetcher: 数据获取器实例
    """
    global _global_fetcher
    if _global_fetcher is None:
        _global_fetcher = MootdxDataFetcher()
    return _global_fetcher


# 便捷函数

def get_financial_data(code: str) -> Optional[Dict[str, Any]]:
    """
    获取股票财务指标（便捷函数）
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 财务指标
    """
    return get_fetcher().get_financial_data(code)


def get_comprehensive_fundamentals(code: str) -> Optional[Dict[str, Any]]:
    """
    获取股票综合基本面数据（便捷函数）
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 综合基本面数据
    """
    return get_fetcher().get_comprehensive_fundamentals(code)


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("mootdx 数据获取模块测试")
    print("=" * 60)
    
    # 初始化数据获取器
    fetcher = MootdxDataFetcher()
    
    if not fetcher.quotes:
        print("mootdx 初始化失败，请检查是否安装")
        exit(1)
    
    # 测试 1: 获取财务数据
    print("\n1. 测试获取财务数据（PE、PB、ROE）")
    financial_data = fetcher.get_financial_data("600519")
    if financial_data:
        print(f"股票：{financial_data['code']}")
        print(f"市盈率 (PE): {financial_data['pe_ratio']}")
        print(f"市净率 (PB): {financial_data['pb_ratio']}")
        print(f"净资产收益率 (ROE): {financial_data['roe']}")
        print(f"总股本：{financial_data['total_shares']} 万股")
    else:
        print("获取失败")
    
    # 测试 2: 获取综合基本面数据
    print("\n2. 测试获取综合基本面数据")
    fundamentals = fetcher.get_comprehensive_fundamentals("600519")
    if fundamentals:
        print(f"股票：{fundamentals['code']}")
        print(f"PE: {fundamentals['pe_ratio']}")
        print(f"PB: {fundamentals['pb_ratio']}")
        print(f"ROE: {fundamentals['roe']}%")
        print(f"营收增长率：{fundamentals['revenue_growth']}%")
        print(f"净利润增长率：{fundamentals['profit_growth']}%")
        print(f"毛利率：{fundamentals['gross_margin']}%")
        print(f"净利率：{fundamentals['net_margin']}%")
        print(f"资产负债率：{fundamentals['debt_ratio']}%")
    else:
        print("获取失败")
    
    # 测试 3: 获取历史数据
    print("\n3. 测试获取历史数据（最近 5 条）")
    historical_data = fetcher.get_historical_data("600519", period="daily")
    if historical_data:
        print(f"总记录数：{historical_data['total_records']}")
        print(f"最新日期：{historical_data['latest_date']}")
        print("最近 5 条数据:")
        for item in historical_data['data'][-5:]:
            date = item.get('datetime', 'N/A')
            open_price = item.get('open', 'N/A')
            close = item.get('close', 'N/A')
            print(f"  {date}: 开盘={open_price}, 收盘={close}")
    else:
        print("获取失败")
    
    # 测试 4: 获取状态
    print("\n4. 获取数据获取器状态")
    status = fetcher.get_status()
    print(f"mootdx 可用：{status['available']}")
    print(f"请求次数：{status['request_count']}")
    print(f"错误次数：{status['error_count']}")
    print(f"数据目录：{status['tdx_dir']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
