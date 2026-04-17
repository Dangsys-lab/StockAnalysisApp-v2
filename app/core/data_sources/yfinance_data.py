# -*- coding: utf-8 -*-
"""
yfinance 数据获取核心模块

封装 yfinance API 常用接口，提供统一的股票数据获取服务
- 支持美股/港股实时行情、历史数据
- 股票基本信息、财务数据
- 分析师评级、新闻等

符合项目规范：
- 只返回数据（dict/list/DataFrame），不返回 HTTP 响应
- 完整的异常处理
- 所有函数有文档字符串
- 使用类型注解
"""

import time
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Any

try:
    import yfinance as yf
    import pandas as pd
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None
    pd = None


class YFinanceDataFetcher:
    """
    yfinance 数据获取器
    
    提供统一的股票数据获取接口，封装 yfinance 常用功能
    支持缓存、错误处理和重试机制
    """
    
    def __init__(self, cache_size: int = 100, request_interval: float = 1.0):
        """
        初始化数据获取器
        
        Args:
            cache_size: LRU 缓存大小，默认 100
            request_interval: 请求间隔（秒），避免被限流，默认 1.0 秒
        """
        self.cache_size = cache_size
        self.request_interval = request_interval
        self.last_request_time = 0.0
        self.request_count = 0
        self.error_count = 0
        
        if not YFINANCE_AVAILABLE:
            print("警告：yfinance 库未安装，请运行：pip install yfinance")
    
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
    
    def _validate_stock_code(self, code: str, market: str = 'US') -> bool:
        """
        验证股票代码格式
        
        Args:
            code: 股票代码
            market: 市场类型，'US'（美股）或 'HK'（港股）
            
        Returns:
            bool: 是否有效
        """
        if not code or not isinstance(code, str):
            return False
        
        code = code.strip().upper()
        
        if market == 'US':
            # 美股代码通常为 1-5 个字母
            return 1 <= len(code) <= 5 and code.replace('.', '').replace('-', '').isalnum()
        elif market == 'HK':
            # 港股代码为 4 位数字.HK
            if '.HK' in code:
                stock_part = code.replace('.HK', '')
                return stock_part.isdigit() and len(stock_part) == 4
            else:
                return code.isdigit() and len(code) == 4
        else:
            return False
    
    def _format_hk_code(self, code: str) -> str:
        """
        格式化港股代码
        
        Args:
            code: 股票代码
            
        Returns:
            str: 带.HK 后缀的代码
        """
        code = code.strip().upper()
        if '.HK' not in code and code.isdigit() and len(code) == 4:
            return f"{code}.HK"
        return code
    
    def _convert_dataframe_to_dict(self, df: Any, limit: Optional[int] = None) -> List[Dict]:
        """
        将 DataFrame 转换为字典列表
        
        Args:
            df: pandas DataFrame
            limit: 限制返回的记录数（从最新开始）
            
        Returns:
            List[Dict]: 字典列表
        """
        if df is None or (hasattr(df, 'empty') and df.empty):
            return []
        
        try:
            # 限制记录数
            if limit:
                df = df.tail(limit)
            
            # 转换为字典列表
            records = df.to_dict('records')
            
            # 处理 datetime 类型和 numpy 类型
            for record in records:
                for key, value in record.items():
                    if hasattr(value, 'strftime'):  # datetime 类型
                        record[key] = value.strftime('%Y-%m-%d')
                    elif hasattr(value, 'item'):  # numpy 类型
                        record[key] = value.item()
            
            return records
        except Exception as e:
            print(f"DataFrame 转换失败：{e}")
            return []
    
    def get_realtime_data(self, code: str, market: str = 'US') -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情数据（使用最新历史数据模拟）
        
        Args:
            code: 股票代码（如 "AAPL" 或 "0700"）
            market: 市场类型，'US'（美股）或 'HK'（港股），默认 'US'
            
        Returns:
            Dict: 包含实时行情数据的字典，失败返回 None
            {
                'code': str,          # 股票代码
                'name': str,          # 股票名称
                'current_price': float,  # 当前价格
                'change': float,      # 涨跌额
                'change_pct': float,  # 涨跌幅（%）
                'open': float,        # 开盘价
                'high': float,        # 最高价
                'low': float,         # 最低价
                'volume': int,        # 成交量
                'market_cap': float,  # 市值
                'pe_ratio': float,    # 市盈率
                'timestamp': str      # 数据时间戳
            }
        """
        if not self._validate_stock_code(code, market):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化代码（港股需要.HK 后缀）
            if market == 'HK':
                ticker_code = self._format_hk_code(code)
            else:
                ticker_code = code.upper()
            
            # 创建 Ticker 对象
            ticker = yf.Ticker(ticker_code)
            
            # 获取最新历史数据（模拟实时数据）
            hist = ticker.history(period='1d', interval='1m')
            
            if hist is None or hist.empty:
                # 尝试获取 5 天数据
                hist = ticker.history(period='5d', interval='1d')
                if hist is None or hist.empty:
                    print(f"获取股票 {ticker_code} 数据失败：返回为空")
                    return None
            
            # 获取最新数据
            latest = hist.iloc[-1]
            prev_close = hist.iloc[-2]['Close'] if len(hist) > 1 else latest['Close']
            
            # 获取股票信息
            info = ticker.info
            
            # 计算涨跌
            current_price = float(latest['Close'])
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0
            
            result = {
                'code': code.upper(),
                'name': info.get('longName', info.get('shortName', '')),
                'current_price': current_price,
                'change': round(change, 2),
                'change_pct': round(change_pct, 2),
                'open': float(latest.get('Open', current_price)),
                'high': float(latest.get('High', current_price)),
                'low': float(latest.get('Low', current_price)),
                'volume': int(latest.get('Volume', 0)),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
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
        market: str = 'US',
        period: str = '1y',
        start_date: str = '',
        end_date: str = '',
        interval: str = '1d'
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票历史 K 线数据
        
        Args:
            code: 股票代码
            market: 市场类型，'US'（美股）或 'HK'（港股），默认 'US'
            period: 周期，如 '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'
            start_date: 开始日期，格式"YYYY-MM-DD"，默认空（使用 period）
            end_date: 结束日期，格式"YYYY-MM-DD"，默认空（到今天）
            interval: 时间间隔，如 '1m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'
            
        Returns:
            Dict: 包含历史数据的字典
            {
                'code': str,          # 股票代码
                'period': str,        # 周期
                'interval': str,      # 时间间隔
                'total_records': int, # 总记录数
                'start_date': str,    # 开始日期
                'end_date': str,      # 结束日期
                'data': List[Dict],   # K 线数据列表
                'latest_date': str    # 最新日期
            }
        """
        if not self._validate_stock_code(code, market):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化代码
            if market == 'HK':
                ticker_code = self._format_hk_code(code)
            else:
                ticker_code = code.upper()
            
            # 创建 Ticker 对象
            ticker = yf.Ticker(ticker_code)
            
            # 获取历史数据
            if start_date and end_date:
                hist = ticker.history(start=start_date, end=end_date, interval=interval)
            else:
                hist = ticker.history(period=period, interval=interval)
            
            if hist is None or hist.empty:
                print(f"获取历史数据失败：{ticker_code}")
                return None
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(hist)
            
            # 添加日期字段
            for i, record in enumerate(data):
                record['Date'] = hist.index[i].strftime('%Y-%m-%d')
            
            # 获取最新日期
            latest_date = hist.index[-1].strftime('%Y-%m-%d') if len(hist) > 0 else ''
            
            result = {
                'code': code.upper(),
                'period': period,
                'interval': interval,
                'total_records': len(hist),
                'start_date': start_date if start_date else period,
                'end_date': end_date if end_date else '最新',
                'data': data,
                'latest_date': latest_date
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取历史数据失败 [{code}]: {e}")
            return None
    
    def get_stock_info(self, code: str, market: str = 'US') -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息
        
        Args:
            code: 股票代码
            market: 市场类型，'US'（美股）或 'HK'（港股），默认 'US'
            
        Returns:
            Dict: 包含股票基本信息的字典
            {
                'code': str,          # 股票代码
                'name': str,          # 股票名称
                'market': str,        # 市场（US/HK）
                'sector': str,        # 所属行业
                'industry': str,      # 所在行业
                'market_cap': float,  # 市值
                'currency': str,      # 货币
                'timestamp': str      # 数据时间戳
            }
        """
        if not self._validate_stock_code(code, market):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化代码
            if market == 'HK':
                ticker_code = self._format_hk_code(code)
            else:
                ticker_code = code.upper()
            
            # 创建 Ticker 对象
            ticker = yf.Ticker(ticker_code)
            
            # 获取信息
            info = ticker.info
            
            if not info:
                print(f"未找到股票 {ticker_code} 的信息")
                return None
            
            result = {
                'code': code.upper(),
                'name': info.get('longName', info.get('shortName', '')),
                'market': market,
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'currency': info.get('currency', 'USD' if market == 'US' else 'HKD'),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取股票信息失败 [{code}]: {e}")
            return None
    
    def get_financial_data(self, code: str, market: str = 'US') -> Optional[Dict[str, Any]]:
        """
        获取股票财务指标数据
        
        Args:
            code: 股票代码
            market: 市场类型，'US'（美股）或 'HK'（港股），默认 'US'
            
        Returns:
            Dict: 包含财务指标的字典
            {
                'code': str,              # 股票代码
                'pe_ratio': float,        # 市盈率
                'forward_pe': float,      # 远期市盈率
                'pb_ratio': float,        # 市净率
                'ps_ratio': float,        # 市销率
                'dividend_yield': float,  # 股息率
                'eps': float,             # 每股收益
                'beta': float,            # Beta 系数
                '52_week_high': float,    # 52 周最高价
                '52_week_low': float,     # 52 周最低价
                'timestamp': str          # 数据时间戳
            }
        """
        if not self._validate_stock_code(code, market):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化代码
            if market == 'HK':
                ticker_code = self._format_hk_code(code)
            else:
                ticker_code = code.upper()
            
            # 创建 Ticker 对象
            ticker = yf.Ticker(ticker_code)
            
            # 获取信息
            info = ticker.info
            
            if not info:
                print(f"获取财务指标失败：{ticker_code}")
                return None
            
            result = {
                'code': code.upper(),
                'pe_ratio': info.get('trailingPE', 0),
                'forward_pe': info.get('forwardPE', 0),
                'pb_ratio': info.get('priceToBook', 0),
                'ps_ratio': info.get('priceToSalesTrailing12Months', 0),
                'dividend_yield': info.get('dividendYield', 0),
                'eps': info.get('trailingEps', 0),
                'beta': info.get('beta', 0),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取财务指标失败 [{code}]: {e}")
            return None
    
    def get_analyst_ratings(self, code: str, market: str = 'US') -> Optional[Dict[str, Any]]:
        """
        获取分析师评级
        
        Args:
            code: 股票代码
            market: 市场类型，'US'（美股）或 'HK'（港股），默认 'US'
            
        Returns:
            Dict: 包含分析师评级的字典
            {
                'code': str,              # 股票代码
                'recommendations': List,  # 推荐评级列表
                'upgrades_downgrades': List,  # 评级升级/降级
                'timestamp': str          # 数据时间戳
            }
        """
        if not self._validate_stock_code(code, market):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化代码
            if market == 'HK':
                ticker_code = self._format_hk_code(code)
            else:
                ticker_code = code.upper()
            
            # 创建 Ticker 对象
            ticker = yf.Ticker(ticker_code)
            
            # 获取推荐评级
            recommendations = ticker.recommendations
            upgrades_downgrades = ticker.upgrades_downgrades
            
            # 转换为字典
            rec_data = self._convert_dataframe_to_dict(recommendations) if recommendations is not None else []
            up_down_data = self._convert_dataframe_to_dict(upgrades_downgrades) if upgrades_downgrades is not None else []
            
            result = {
                'code': code.upper(),
                'recommendations': rec_data,
                'upgrades_downgrades': up_down_data,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取分析师评级失败 [{code}]: {e}")
            return None
    
    def get_news(self, code: str, market: str = 'US') -> Optional[List[Dict[str, Any]]]:
        """
        获取股票相关新闻
        
        Args:
            code: 股票代码
            market: 市场类型，'US'（美股）或 'HK'（港股），默认 'US'
            
        Returns:
            List[Dict]: 新闻列表
        """
        if not self._validate_stock_code(code, market):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化代码
            if market == 'HK':
                ticker_code = self._format_hk_code(code)
            else:
                ticker_code = code.upper()
            
            # 创建 Ticker 对象
            ticker = yf.Ticker(ticker_code)
            
            # 获取新闻
            news = ticker.news
            
            if not news:
                return []
            
            # 格式化新闻数据
            result = []
            for item in news:
                news_item = {
                    'title': item.get('title', ''),
                    'publisher': item.get('publisher', ''),
                    'link': item.get('link', ''),
                    'publish_time': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M:%S') if item.get('providerPublishTime') else '',
                    'summary': item.get('summary', '')
                }
                result.append(news_item)
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取新闻失败 [{code}]: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取数据获取器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'available': YFINANCE_AVAILABLE,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'cache_size': self.cache_size,
            'request_interval': self.request_interval,
            'last_request_time': datetime.fromtimestamp(self.last_request_time).strftime('%Y-%m-%d %H:%M:%S') if self.last_request_time > 0 else 'N/A'
        }
    
    def clear_cache(self):
        """清除缓存"""
        self.get_historical_data.cache_clear()


# 全局数据获取器实例
_global_fetcher = None


def get_fetcher() -> YFinanceDataFetcher:
    """
    获取全局数据获取器实例
    
    Returns:
        YFinanceDataFetcher: 数据获取器实例
    """
    global _global_fetcher
    if _global_fetcher is None:
        _global_fetcher = YFinanceDataFetcher()
    return _global_fetcher


# 便捷函数

def get_realtime_data(code: str, market: str = 'US') -> Optional[Dict[str, Any]]:
    """
    获取股票实时行情数据（便捷函数）
    
    Args:
        code: 股票代码
        market: 市场类型，默认 'US'
        
    Returns:
        Dict: 实时行情数据
    """
    return get_fetcher().get_realtime_data(code, market)


def get_historical_data(
    code: str,
    market: str = 'US',
    period: str = '1y',
    start_date: str = '',
    end_date: str = '',
    interval: str = '1d'
) -> Optional[Dict[str, Any]]:
    """
    获取股票历史 K 线数据（便捷函数）
    
    Args:
        code: 股票代码
        market: 市场类型，默认 'US'
        period: 周期
        start_date: 开始日期
        end_date: 结束日期
        interval: 时间间隔
        
    Returns:
        Dict: 历史 K 线数据
    """
    return get_fetcher().get_historical_data(code, market, period, start_date, end_date, interval)


def get_stock_info(code: str, market: str = 'US') -> Optional[Dict[str, Any]]:
    """
    获取股票基本信息（便捷函数）
    
    Args:
        code: 股票代码
        market: 市场类型，默认 'US'
        
    Returns:
        Dict: 股票基本信息
    """
    return get_fetcher().get_stock_info(code, market)


def get_financial_data(code: str, market: str = 'US') -> Optional[Dict[str, Any]]:
    """
    获取股票财务指标（便捷函数）
    
    Args:
        code: 股票代码
        market: 市场类型，默认 'US'
        
    Returns:
        Dict: 财务指标
    """
    return get_fetcher().get_financial_data(code, market)


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("yfinance 数据获取模块测试")
    print("=" * 60)
    
    # 初始化数据获取器
    fetcher = YFinanceDataFetcher(request_interval=2.0)
    
    # 测试 1: 获取美股实时数据
    print("\n1. 测试获取美股实时数据 (AAPL)")
    realtime_data = fetcher.get_realtime_data("AAPL", market='US')
    if realtime_data:
        print(f"股票：{realtime_data['name']} ({realtime_data['code']})")
        print(f"当前价格：{realtime_data['current_price']}")
        print(f"涨跌幅：{realtime_data['change_pct']}%")
    else:
        print("获取失败")
    
    # 测试 2: 获取港股实时数据
    print("\n2. 测试获取港股实时数据 (0700)")
    realtime_data = fetcher.get_realtime_data("0700", market='HK')
    if realtime_data:
        print(f"股票：{realtime_data['name']} ({realtime_data['code']})")
        print(f"当前价格：{realtime_data['current_price']}")
        print(f"涨跌幅：{realtime_data['change_pct']}%")
    else:
        print("获取失败")
    
    # 测试 3: 获取历史数据
    print("\n3. 测试获取历史数据 (最近 5 条)")
    historical_data = fetcher.get_historical_data("AAPL", market='US', period='1mo')
    if historical_data:
        print(f"总记录数：{historical_data['total_records']}")
        print(f"最新日期：{historical_data['latest_date']}")
        print("最近 5 条数据:")
        for item in historical_data['data'][-5:]:
            print(f"  {item.get('Date', 'N/A')}: 收盘={item.get('Close', 'N/A')}")
    else:
        print("获取失败")
    
    # 测试 4: 获取股票信息
    print("\n4. 测试获取股票信息")
    stock_info = fetcher.get_stock_info("AAPL", market='US')
    if stock_info:
        print(f"股票：{stock_info['name']} ({stock_info['code']})")
        print(f"行业：{stock_info['industry']}")
    else:
        print("获取失败")
    
    # 测试 5: 获取财务指标
    print("\n5. 测试获取财务指标")
    financial_data = fetcher.get_financial_data("AAPL", market='US')
    if financial_data:
        print(f"市盈率：{financial_data['pe_ratio']}")
        print(f"市净率：{financial_data['pb_ratio']}")
    else:
        print("获取失败")
    
    # 测试 6: 获取状态
    print("\n6. 获取数据获取器状态")
    status = fetcher.get_status()
    print(f"yfinance 可用：{status['available']}")
    print(f"请求次数：{status['request_count']}")
    print(f"错误次数：{status['error_count']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
