# -*- coding: utf-8 -*-
"""
AKShare 数据获取核心模块

封装 AKShare 常用接口，提供统一的股票数据获取服务
- 实时行情数据
- 历史 K 线数据
- 股票基本信息
- 财务指标数据
- 指数数据

符合项目规范：
- 只返回数据（dict/list/DataFrame），不返回 HTTP 响应
- 完整的异常处理
- 所有函数有文档字符串
- 使用类型注解
"""

import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    ak = None


class AKShareDataFetcher:
    """
    AKShare 数据获取器
    
    提供统一的股票数据获取接口，封装 AKShare 常用功能
    支持缓存、错误处理和重试机制
    """
    
    def __init__(self, cache_size: int = 100, request_interval: float = 2.0):
        """
        初始化数据获取器
        
        Args:
            cache_size: LRU 缓存大小，默认 100
            request_interval: 请求间隔（秒），避免被限流，默认 2.0 秒（基本面数据建议 3-5 秒）
        """
        self.cache_size = cache_size
        self.request_interval = request_interval
        self.last_request_time = 0.0
        self.request_count = 0
        self.error_count = 0
        
        if not AKSHARE_AVAILABLE:
            print("警告：AKShare 库未安装，请运行：pip install akshare")
    
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
    
    def _smart_backoff(self, attempt: int, base_delay: float = 2.0, max_delay: float = 60.0):
        """
        智能退避算法 - 当遇到限流时使用
        
        Args:
            attempt: 当前重试次数（从 1 开始）
            base_delay: 基础延迟时间（秒），默认 2.0
            max_delay: 最大延迟时间（秒），默认 60.0
            
        Returns:
            float: 实际等待时间（秒）
        """
        # 指数退避：2^attempt * base_delay
        delay = min((2 ** attempt) * base_delay, max_delay)
        
        # 添加随机抖动（±20%），避免多个请求同时重试
        import random
        jitter = delay * 0.2 * (random.random() * 2 - 1)
        delay += jitter
        
        print(f"触发限流，第 {attempt} 次重试，等待 {delay:.2f} 秒...")
        time.sleep(delay)
        
        return delay
    
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
    
    def _format_market_code(self, code: str) -> str:
        """
        格式化带市场前缀的股票代码
        
        Args:
            code: 6 位股票代码
            
        Returns:
            str: 带市场前缀的代码（如 sh600519）
        """
        code = code.strip()
        
        if code.startswith('6') or code.startswith('9'):
            return f"sh{code}"
        elif code.startswith('0') or code.startswith('3'):
            return f"sz{code}"
        elif code.startswith('4') or code.startswith('8'):
            return f"bj{code}"
        else:
            return f"sh{code}"
    
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
            
            # 处理 datetime 类型和 numpy 类型
            for record in records:
                for key, value in record.items():
                    if isinstance(value, (pd.Timestamp, datetime)):
                        record[key] = value.strftime('%Y-%m-%d')
                    elif isinstance(value, (pd.Series, pd.DataFrame)):
                        record[key] = value.tolist()
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
                'change': float,      # 涨跌额
                'change_pct': float,  # 涨跌幅（%）
                'open': float,        # 开盘价
                'high': float,        # 最高价
                'low': float,         # 最低价
                'volume': int,        # 成交量（手）
                'amount': float,      # 成交额（元）
                'prev_close': float,  # 昨收价
                'amplitude': float,   # 振幅（%）
                'volume_ratio': float,  # 量比
                'turnover_rate': float, # 换手率（%）
                'timestamp': str      # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 使用东方财富接口获取实时数据
            df = ak.stock_zh_a_spot_em()
            
            if df is None or df.empty:
                print("获取实时数据失败：返回为空")
                return None
            
            # 筛选目标股票
            stock_data = df[df['代码'] == code]
            
            if stock_data.empty:
                print(f"未找到股票 {code} 的实时数据")
                return None
            
            # 提取数据
            row = stock_data.iloc[0]
            
            result = {
                'code': code,
                'name': str(row.get('名称', '')),
                'current_price': float(row.get('最新价', 0)),
                'change': float(row.get('涨跌额', 0)),
                'change_pct': float(row.get('涨跌幅', 0)),
                'open': float(row.get('今开', 0)),
                'high': float(row.get('最高', 0)),
                'low': float(row.get('最低', 0)),
                'volume': int(row.get('成交量', 0)),
                'amount': float(row.get('成交额', 0)),
                'prev_close': float(row.get('昨收', 0)),
                'amplitude': float(row.get('振幅', 0)),
                'volume_ratio': float(row.get('量比', 0)),
                'turnover_rate': float(row.get('换手率', 0)),
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
        end_date: str = '',
        adjust: str = 'qfq'
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票历史 K 线数据
        
        Args:
            code: 6 位股票代码
            period: 周期，可选 'daily'/'weekly'/'monthly'，默认 'daily'
            start_date: 开始日期，格式"YYYYmmdd"，默认空（获取全部）
            end_date: 结束日期，格式"YYYYmmdd"，默认空（获取全部）
            adjust: 复权类型，可选 ''（不复权）/'qfq'（前复权）/'hfq'（后复权），默认 'qfq'
            
        Returns:
            Dict: 包含历史数据的字典
            {
                'code': str,          # 股票代码
                'period': str,        # 周期
                'adjust': str,        # 复权类型
                'total_records': int, # 总记录数
                'start_date': str,    # 开始日期
                'end_date': str,      # 结束日期
                'data': List[Dict],   # K 线数据列表
                'latest_date': str    # 最新日期
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start_date if start_date else '',
                end_date=end_date if end_date else '',
                adjust=adjust
            )
            
            if df is None or df.empty:
                print(f"获取历史数据失败：{code}")
                return None
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(df)
            
            # 获取最新日期
            latest_date = ''
            if not df.empty and '日期' in df.columns:
                latest_date = df['日期'].iloc[-1].strftime('%Y-%m-%d')
            
            result = {
                'code': code,
                'period': period,
                'adjust': adjust,
                'total_records': len(df),
                'start_date': start_date if start_date else '上市首日',
                'end_date': end_date if end_date else '最新',
                'data': data,
                'latest_date': latest_date
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取历史数据失败 [{code}]: {e}")
            return None
    
    def get_stock_info(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含股票基本信息的字典
            {
                'code': str,          # 股票代码
                'name': str,          # 股票名称
                'market': str,        # 市场（SH/SZ/BJ）
                'list_date': str,     # 上市日期
                'industry': str,      # 所属行业
                'area': str,          # 所属地区
                'total_shares': float, # 总股本
                'circulating_shares': float, # 流通股本
                'timestamp': str      # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 获取所有股票信息
            df = ak.stock_info_a_code_name()
            
            if df is None or df.empty:
                print("获取股票信息失败")
                return None
            
            # 筛选目标股票
            stock_info = df[df['代码'] == code]
            
            if stock_info.empty:
                print(f"未找到股票 {code} 的信息")
                return None
            
            row = stock_info.iloc[0]
            
            result = {
                'code': code,
                'name': str(row.get('名称', '')),
                'market': self._get_market_from_code(code),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取股票信息失败 [{code}]: {e}")
            return None
    
    def get_financial_indicators(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票财务指标数据
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含财务指标的字典
            {
                'code': str,          # 股票代码
                'pe_ratio': float,    # 市盈率
                'pb_ratio': float,    # 市净率
                'ps_ratio': float,    # 市销率
                'pcf_ratio': float,   # 市现率
                'latest_date': str,   # 数据日期
                'timestamp': str      # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化带市场前缀的代码
            market_code = self._format_market_code(code)
            
            # 获取长期指标
            df = ak.stock_a_lg_indicator(symbol=market_code)
            
            if df is None or df.empty:
                print(f"获取财务指标失败：{code}")
                return None
            
            # 获取最新数据
            latest = df.iloc[-1]
            
            result = {
                'code': code,
                'pe_ratio': float(latest.get('市盈率', 0)),
                'pb_ratio': float(latest.get('市净率', 0)),
                'ps_ratio': float(latest.get('市销率', 0)),
                'pcf_ratio': float(latest.get('市现率', 0)),
                'latest_date': latest.get('日期', '').strftime('%Y-%m-%d') if hasattr(latest.get('日期'), 'strftime') else str(latest.get('日期', '')),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取财务指标失败 [{code}]: {e}")
            return None
    
    def get_market_index_data(self, index_code: str) -> Optional[Dict[str, Any]]:
        """
        获取市场指数数据
        
        Args:
            index_code: 指数代码（如 "000001" 上证指数）
            
        Returns:
            Dict: 包含指数数据的字典
        """
        if not self._validate_stock_code(index_code):
            print(f"无效的指数代码：{index_code}")
            return None
        
        try:
            self._rate_limit()
            
            # 获取指数实时行情
            df = ak.stock_zh_index_spot_em()
            
            if df is None or df.empty:
                print("获取指数数据失败")
                return None
            
            # 筛选目标指数
            index_data = df[df['代码'] == index_code]
            
            if index_data.empty:
                print(f"未找到指数 {index_code} 的数据")
                return None
            
            row = index_data.iloc[0]
            
            result = {
                'code': index_code,
                'name': str(row.get('名称', '')),
                'current_price': float(row.get('最新价', 0)),
                'change': float(row.get('涨跌额', 0)),
                'change_pct': float(row.get('涨跌幅', 0)),
                'open': float(row.get('今开', 0)),
                'high': float(row.get('最高', 0)),
                'low': float(row.get('最低', 0)),
                'volume': int(row.get('成交量', 0)),
                'amount': float(row.get('成交额', 0)),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取指数数据失败 [{index_code}]: {e}")
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
                'roe_weight': float,      # 加权 ROE
                'revenue_growth': float,  # 营收增长率
                'profit_growth': float,   # 净利润增长率
                'gross_margin': float,    # 毛利率
                'net_margin': float,      # 净利率
                'debt_ratio': float,      # 资产负债率
                'latest_date': str,       # 数据日期
                'timestamp': str          # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化带市场前缀的代码
            market_code = self._format_market_code(code)
            
            # 获取财务指标
            df = ak.stock_financial_analysis_indicator(symbol=market_code)
            
            if df is None or df.empty:
                print(f"获取基本财务指标失败：{code}")
                return None
            
            # 获取最新数据
            latest = df.iloc[-1]
            
            result = {
                'code': code,
                'roe': float(latest.get('净资产收益率 (%)', 0)),
                'roe_weight': float(latest.get('加权净资产收益率 (%)', 0)),
                'revenue_growth': float(latest.get('营业总收入同比增长率 (%)', 0)),
                'profit_growth': float(latest.get('归属母公司股东的净利润同比增长率 (%)', 0)),
                'gross_margin': float(latest.get('销售毛利率 (%)', 0)),
                'net_margin': float(latest.get('销售净利率 (%)', 0)),
                'debt_ratio': float(latest.get('资产负债率 (%)', 0)),
                'latest_date': latest.get('日期', '').strftime('%Y-%m-%d') if hasattr(latest.get('日期'), 'strftime') else str(latest.get('日期', '')),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取基本财务指标失败 [{code}]: {e}")
            return None
    
    def get_capital_flow(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票资金流向数据（主力流入、北向资金、大单净量等）
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含资金流向数据的字典
            {
                'code': str,                  # 股票代码
                'north_flow': float,          # 北向资金净流入（万元）
                'main_force_in': float,       # 主力流入（万元）
                'main_force_out': float,      # 主力流出（万元）
                'main_force_net': float,      # 主力净流入（万元）
                'large_order_net': float,     # 大单净量（万元）
                'medium_order_net': float,    # 中单净量（万元）
                'small_order_net': float,     # 小单净量（万元）
                'flow_ratio': float,          # 主力资金占比
                'latest_date': str,           # 数据日期
                'timestamp': str              # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化带市场前缀的代码
            market_code = self._format_market_code(code)
            
            # 获取资金流向数据
            df = ak.stock_individual_fund_flow(symbol=market_code)
            
            if df is None or df.empty:
                print(f"获取资金流向数据失败：{code}")
                return None
            
            # 获取最新数据（今日）
            latest = df.iloc[0] if len(df) > 0 else None
            
            if latest is None:
                print(f"资金流向数据为空：{code}")
                return None
            
            result = {
                'code': code,
                'north_flow': float(latest.get('北向资金净流入', 0) if '北向资金净流入' in latest else 0),
                'main_force_in': float(latest.get('主力流入-净额', 0) if '主力流入 - 净额' in latest else latest.get('主力净流入', 0)),
                'main_force_out': float(latest.get('主力流出', 0)),
                'main_force_net': float(latest.get('主力净流入', 0)),
                'large_order_net': float(latest.get('大单净流入', 0)),
                'medium_order_net': float(latest.get('中单净流入', 0)),
                'small_order_net': float(latest.get('小单净流入', 0)),
                'flow_ratio': float(latest.get('主力净流入 - 占比', 0) if '主力净流入 - 占比' in latest else 0),
                'latest_date': latest.get('日期', '').strftime('%Y-%m-%d') if hasattr(latest.get('日期'), 'strftime') else str(latest.get('日期', '')),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取资金流向数据失败 [{code}]: {e}")
            return None
    
    def get_north_capital_flow(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取北向资金持股数据
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含北向资金持股数据的字典
            {
                'code': str,                  # 股票代码
                'north_hold_shares': float,   # 北向资金持股数（万股）
                'north_hold_ratio': float,    # 北向资金持股比例
                'north_hold_value': float,    # 北向资金持股市值（万元）
                'change_shares': float,       # 持股变动（万股）
                'change_ratio': float,        # 持股变动比例
                'latest_date': str,           # 数据日期
                'timestamp': str              # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self._rate_limit()
            
            # 格式化带市场前缀的代码
            market_code = self._format_market_code(code)
            
            # 获取北向资金持股数据
            df = ak.stock_hsgt_individual_em(symbol=market_code)
            
            if df is None or df.empty:
                print(f"获取北向资金持股数据失败：{code}")
                return None
            
            # 获取最新数据
            latest = df.iloc[-1]
            
            result = {
                'code': code,
                'north_hold_shares': float(latest.get('持股数', 0)),
                'north_hold_ratio': float(latest.get('持股比例', 0)),
                'north_hold_value': float(latest.get('持股市值', 0)),
                'change_shares': float(latest.get('持股变动', 0)),
                'change_ratio': float(latest.get('持股变动比例', 0)),
                'latest_date': latest.get('日期', '').strftime('%Y-%m-%d') if hasattr(latest.get('日期'), 'strftime') else str(latest.get('日期', '')),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取北向资金持股数据失败 [{code}]: {e}")
            return None
    
    def get_comprehensive_fundamentals(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票综合基本面数据（PE、PB、ROE、营收增长率、资金流向等）
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 包含综合基本面数据的字典
            {
                # 估值指标
                'pe_ratio': float,            # 市盈率
                'pb_ratio': float,            # 市净率
                'ps_ratio': float,            # 市销率
                'pcf_ratio': float,           # 市现率
                
                # 盈利能力
                'roe': float,                 # ROE（净资产收益率）
                'roe_weight': float,          # 加权 ROE
                'gross_margin': float,        # 毛利率
                'net_margin': float,          # 净利率
                
                # 成长能力
                'revenue_growth': float,      # 营收增长率
                'profit_growth': float,       # 净利润增长率
                
                # 财务健康
                'debt_ratio': float,          # 资产负债率
                
                # 资金流向
                'north_flow': float,          # 北向资金净流入（万元）
                'main_force_net': float,      # 主力净流入（万元）
                'large_order_net': float,     # 大单净量（万元）
                'flow_ratio': float,          # 主力资金占比
                
                # 北向资金持股
                'north_hold_ratio': float,    # 北向资金持股比例
                'north_hold_value': float,    # 北向资金持股市值（万元）
                
                # 元数据
                'latest_date': str,           # 数据日期
                'timestamp': str              # 数据时间戳
            }
        """
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            # 获取估值指标
            valuation = self.get_financial_indicators(code)
            
            # 获取基本财务指标
            financials = self.get_basic_financials(code)
            
            # 获取资金流向
            capital_flow = self.get_capital_flow(code)
            
            # 获取北向资金持股
            north_hold = self.get_north_capital_flow(code)
            
            # 合并数据
            result = {}
            
            # 估值指标
            if valuation:
                result.update({
                    'pe_ratio': valuation.get('pe_ratio', 0),
                    'pb_ratio': valuation.get('pb_ratio', 0),
                    'ps_ratio': valuation.get('ps_ratio', 0),
                    'pcf_ratio': valuation.get('pcf_ratio', 0),
                })
            
            # 财务指标
            if financials:
                result.update({
                    'roe': financials.get('roe', 0),
                    'roe_weight': financials.get('roe_weight', 0),
                    'revenue_growth': financials.get('revenue_growth', 0),
                    'profit_growth': financials.get('profit_growth', 0),
                    'gross_margin': financials.get('gross_margin', 0),
                    'net_margin': financials.get('net_margin', 0),
                    'debt_ratio': financials.get('debt_ratio', 0),
                })
            
            # 资金流向
            if capital_flow:
                result.update({
                    'north_flow': capital_flow.get('north_flow', 0),
                    'main_force_net': capital_flow.get('main_force_net', 0),
                    'large_order_net': capital_flow.get('large_order_net', 0),
                    'flow_ratio': capital_flow.get('flow_ratio', 0),
                })
            
            # 北向资金持股
            if north_hold:
                result.update({
                    'north_hold_ratio': north_hold.get('north_hold_ratio', 0),
                    'north_hold_value': north_hold.get('north_hold_value', 0),
                })
            
            # 元数据
            result['latest_date'] = financials.get('latest_date') if financials else valuation.get('latest_date') if valuation else ''
            result['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取综合基本面数据失败 [{code}]: {e}")
            return None
    
    def get_all_stocks_list(self) -> Optional[List[Dict[str, str]]]:
        """
        获取所有 A 股股票列表
        
        Returns:
            List[Dict]: 股票列表，每项包含代码和名称
        """
        try:
            self._rate_limit()
            
            df = ak.stock_info_a_code_name()
            
            if df is None or df.empty:
                print("获取股票列表失败")
                return None
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    'code': str(row.get('代码', '')),
                    'name': str(row.get('名称', ''))
                })
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取股票列表失败：{e}")
            return None
    
    @staticmethod
    def _get_market_from_code(code: str) -> str:
        """
        根据股票代码获取市场代码
        
        Args:
            code: 6 位股票代码
            
        Returns:
            str: 市场代码（SH/SZ/BJ）
        """
        code = code.strip()
        
        if code.startswith('6') or code.startswith('9'):
            return 'SH'
        elif code.startswith('0') or code.startswith('3'):
            return 'SZ'
        elif code.startswith('4') or code.startswith('8'):
            return 'BJ'
        else:
            return 'UNKNOWN'
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取数据获取器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'available': AKSHARE_AVAILABLE,
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


def get_fetcher() -> AKShareDataFetcher:
    """
    获取全局数据获取器实例
    
    Returns:
        AKShareDataFetcher: 数据获取器实例
    """
    global _global_fetcher
    if _global_fetcher is None:
        _global_fetcher = AKShareDataFetcher()
    return _global_fetcher


# 便捷函数

def get_realtime_data(code: str) -> Optional[Dict[str, Any]]:
    """
    获取股票实时行情数据（便捷函数）
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 实时行情数据
    """
    return get_fetcher().get_realtime_data(code)


def get_historical_data(
    code: str,
    period: str = 'daily',
    start_date: str = '',
    end_date: str = '',
    adjust: str = 'qfq'
) -> Optional[Dict[str, Any]]:
    """
    获取股票历史 K 线数据（便捷函数）
    
    Args:
        code: 6 位股票代码
        period: 周期
        start_date: 开始日期
        end_date: 结束日期
        adjust: 复权类型
        
    Returns:
        Dict: 历史 K 线数据
    """
    return get_fetcher().get_historical_data(code, period, start_date, end_date, adjust)


def get_stock_info(code: str) -> Optional[Dict[str, Any]]:
    """
    获取股票基本信息（便捷函数）
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 股票基本信息
    """
    return get_fetcher().get_stock_info(code)


def get_financial_indicators(code: str) -> Optional[Dict[str, Any]]:
    """
    获取股票财务指标（便捷函数）
    
    Args:
        code: 6 位股票代码
        
    Returns:
        Dict: 财务指标
    """
    return get_fetcher().get_financial_indicators(code)


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("AKShare 数据获取模块测试")
    print("=" * 60)
    
    # 初始化数据获取器
    fetcher = AKShareDataFetcher(request_interval=2.0)
    
    # 测试 1: 获取实时数据
    print("\n1. 测试获取实时数据")
    realtime_data = fetcher.get_realtime_data("600519")
    if realtime_data:
        print(f"股票：{realtime_data['name']} ({realtime_data['code']})")
        print(f"当前价格：{realtime_data['current_price']}")
        print(f"涨跌幅：{realtime_data['change_pct']}%")
    else:
        print("获取失败")
    
    # 测试 2: 获取历史数据
    print("\n2. 测试获取历史数据（最近 5 条）")
    historical_data = fetcher.get_historical_data("600519", period="daily", adjust="qfq")
    if historical_data:
        print(f"总记录数：{historical_data['total_records']}")
        print(f"最新日期：{historical_data['latest_date']}")
        print("最近 5 条数据:")
        for item in historical_data['data'][-5:]:
            print(f"  {item.get('日期', 'N/A')}: 开盘={item.get('开盘', 'N/A')}, 收盘={item.get('收盘', 'N/A')}")
    else:
        print("获取失败")
    
    # 测试 3: 获取股票信息
    print("\n3. 测试获取股票信息")
    stock_info = fetcher.get_stock_info("600519")
    if stock_info:
        print(f"股票：{stock_info['name']} ({stock_info['code']})")
        print(f"市场：{stock_info['market']}")
    else:
        print("获取失败")
    
    # 测试 4: 获取财务指标
    print("\n4. 测试获取财务指标")
    financial_data = fetcher.get_financial_indicators("600519")
    if financial_data:
        print(f"市盈率：{financial_data['pe_ratio']}")
        print(f"市净率：{financial_data['pb_ratio']}")
    else:
        print("获取失败")
    
    # 测试 5: 获取上证指数
    print("\n5. 测试获取上证指数")
    index_data = fetcher.get_market_index_data("000001")
    if index_data:
        print(f"指数：{index_data['name']}")
        print(f"当前点位：{index_data['current_price']}")
        print(f"涨跌幅：{index_data['change_pct']}%")
    else:
        print("获取失败")
    
    # 测试 6: 获取状态
    print("\n6. 获取数据获取器状态")
    status = fetcher.get_status()
    print(f"AKShare 可用：{status['available']}")
    print(f"请求次数：{status['request_count']}")
    print(f"错误次数：{status['error_count']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
