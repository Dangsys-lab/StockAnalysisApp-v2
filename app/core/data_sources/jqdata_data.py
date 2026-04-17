# -*- coding: utf-8 -*-
"""
JQData 数据获取核心模块

封装聚宽 JQData 接口，提供统一的金融数据获取服务
- 沪深 A 股行情数据
- 上市公司财务数据
- 指数数据
- 基金数据
- 期货数据

符合项目规范：
- 只返回数据（dict/list/DataFrame），不返回 HTTP 响应
- 完整的异常处理
- 所有函数有文档字符串
- 使用类型注解

试用政策：
- 有效期：3 个月
- 每日流量：100 万条
- 数据范围：前 15 个月 ~ 前 3 个月（不含最近 3 个月）
- 基础数据全部免费
"""

import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Any
import pandas as pd

try:
    import jqdatasdk as jq
    JQDATA_AVAILABLE = True
except ImportError:
    JQDATA_AVAILABLE = False
    jq = None


class JQDataFetcher:
    """
    JQData 数据获取器
    
    提供统一的金融数据获取接口，封装 JQData 常用功能
    支持认证管理、流量控制、缓存优化
    """
    
    def __init__(self, cache_size: int = 100):
        """
        初始化数据获取器
        
        Args:
            cache_size: LRU 缓存大小，默认 100
        """
        self.cache_size = cache_size
        self.request_count = 0
        self.error_count = 0
        self.is_authenticated = False
        self.account_info = None
        
        if not JQDATA_AVAILABLE:
            print("警告：jqdatasdk 库未安装，请运行：pip install jqdatasdk")
            return
        
        print("JQData 初始化成功，请先调用 auth() 方法登录")
    
    def auth(self, username: str, password: str) -> bool:
        """
        登录聚宽账号
        
        Args:
            username: 聚宽用户名（手机号/邮箱）
            password: 聚宽密码
            
        Returns:
            bool: 是否认证成功
        """
        if not JQDATA_AVAILABLE:
            print("jqdatasdk 库未安装")
            return False
        
        try:
            # 登录认证
            result = jq.auth(username, password)
            
            if result:
                self.is_authenticated = True
                print("✓ JQData 登录成功")
                
                # 获取账号信息
                self.account_info = self.get_account_info()
                
                return True
            else:
                print("✗ JQData 登录失败，请检查用户名和密码")
                return False
                
        except Exception as e:
            print(f"✗ JQData 登录失败：{e}")
            return False
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        获取账号信息
        
        Returns:
            Dict: 账号信息
            {
                'user_id': str,         # 用户 ID
                'account_type': str,    # 账号类型（试用/正式）
                'daily_quota': int,     # 每日流量额度
                'used_quota': int,      # 已用流量
                'remaining_quota': int, # 剩余流量
                'expiry_date': str,     # 到期日期
                'connection_count': int # 连接数
            }
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        try:
            info = jq.get_account_info()
            
            result = {
                'user_id': info.get('user_id', ''),
                'account_type': info.get('account_type', 'unknown'),
                'daily_quota': info.get('daily_quota', 0),
                'used_quota': info.get('used_quota', 0),
                'remaining_quota': info.get('remaining_quota', 0),
                'expiry_date': info.get('expiry_date', ''),
                'connection_count': info.get('connection_count', 0)
            }
            
            return result
            
        except Exception as e:
            print(f"获取账号信息失败：{e}")
            return None
    
    def _format_stock_code(self, code: str) -> str:
        """
        格式化股票代码为 JQData 格式
        
        Args:
            code: 6 位股票代码（如 "600519"）
            
        Returns:
            str: JQData 格式（如 "600519.XSHG"）
        """
        code = code.strip()
        
        if code.startswith('6') or code.startswith('9'):
            return f"{code}.XSHG"  # 上海证券交易所
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.XSHE"  # 深圳证券交易所
        elif code.startswith('4') or code.startswith('8'):
            return f"{code}.BJSE"  # 北京证券交易所
        else:
            return f"{code}.XSHG"
    
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
    
    def get_stock_list(self) -> Optional[List[Dict[str, str]]]:
        """
        获取 A 股股票列表
        
        Returns:
            List[Dict]: 股票列表
            [
                {'code': '600519.XSHG', 'name': '贵州茅台', 'market': 'XSHG'},
                ...
            ]
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        try:
            self.request_count += 1
            
            # 获取所有股票
            df = jq.get_all_securities(['stock'])
            
            if df is None or df.empty:
                print("获取股票列表失败")
                return None
            
            result = []
            for index, row in df.iterrows():
                result.append({
                    'code': index[0] if isinstance(index, tuple) else str(index),
                    'name': row.get('display_name', ''),
                    'market': row.get('exchange', ''),
                    'start_date': str(row.get('start_date', ''))[:10],
                    'end_date': str(row.get('end_date', ''))[:10]
                })
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取股票列表失败：{e}")
            return None
    
    def get_fundamentals(self, code: str, date: str = None) -> Optional[Dict[str, Any]]:
        """
        获取股票基本面数据（估值、财务等）
        
        Args:
            code: 6 位股票代码
            date: 查询日期，格式 'YYYY-MM-DD'，默认 None（最新可用）
            
        Returns:
            Dict: 基本面数据
            {
                # 估值指标
                'pe_ratio': float,          # 市盈率
                'pb_ratio': float,          # 市净率
                'ps_ratio': float,          # 市销率
                'pcf_ratio': float,         # 市现率
                'market_cap': float,        # 总市值
                'circulating_cap': float,   # 流通市值
                
                # 财务指标
                'roe': float,               # ROE
                'revenue': float,           # 营业收入
                'net_profit': float,        # 净利润
                'gross_margin': float,      # 毛利率
                
                # 元数据
                'date': str,                # 数据日期
                'timestamp': str            # 时间戳
            }
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self.request_count += 1
            
            # 格式化股票代码
            jq_code = self._format_stock_code(code)
            
            # 查询估值数据
            from jqdatasdk import query, valuation
            q = query(valuation).filter(valuation.code == jq_code)
            
            if date:
                df = jq.get_fundamentals(q, date=date)
            else:
                df = jq.get_fundamentals(q)
            
            if df is None or df.empty:
                print(f"获取基本面数据失败：{code}")
                return None
            
            row = df.iloc[0]
            
            result = {
                'code': code,
                'pe_ratio': float(row.get('pe_ratio', 0)),
                'pb_ratio': float(row.get('pb_ratio', 0)),
                'ps_ratio': float(row.get('ps_ratio', 0)),
                'pcf_ratio': float(row.get('pcf_ratio', 0)),
                'market_cap': float(row.get('market_cap', 0)),
                'circulating_cap': float(row.get('circulating_cap', 0)),
                'date': str(row.get('day', ''))[:10],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取基本面数据失败 [{code}]: {e}")
            return None
    
    def get_financial_data(self, code: str, stat_date: str = None) -> Optional[Dict[str, Any]]:
        """
        获取股票财务数据（利润表、资产负债表等）
        
        Args:
            code: 6 位股票代码
            stat_date: 财报统计日期，格式 'YYYYqQ' 或 'YYYY'，如 '2023q4' 或 '2023'
            
        Returns:
            Dict: 财务数据
            {
                'code': str,
                'roe': float,               # 净资产收益率
                'revenue_growth': float,    # 营收增长率
                'profit_growth': float,     # 净利润增长率
                'gross_margin': float,      # 毛利率
                'net_margin': float,        # 净利率
                'debt_ratio': float,        # 资产负债率
                'revenue': float,           # 营业收入
                'net_profit': float,        # 净利润
                'stat_date': str,           # 统计日期
                'timestamp': str
            }
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self.request_count += 1
            
            jq_code = self._format_stock_code(code)
            
            # 查询利润表数据
            from jqdatasdk import query, income
            q = query(income).filter(income.code == jq_code)
            
            if stat_date:
                df = jq.get_fundamentals(q, statDate=stat_date)
            else:
                # 获取最新财报
                df = jq.get_fundamentals(q)
            
            if df is None or df.empty:
                print(f"获取财务数据失败：{code}")
                return None
            
            row = df.iloc[0]
            
            # 计算财务指标
            total_revenue = float(row.get('total_operating_revenue', 0))
            net_profit = float(row.get('net_profit', 0))
            
            # 营收增长率（需要对比去年同期）
            revenue_growth = float(row.get('operating_revenue_year_on_year', 0))
            
            # 净利润增长率
            profit_growth = float(row.get('net_profit_year_on_year', 0))
            
            # ROE（净资产收益率）
            roe = float(row.get('roe', 0))
            
            # 毛利率
            gross_margin = float(row.get('gross_profit_margin', 0))
            
            # 净利率
            net_margin = float(row.get('net_profit_margin', 0))
            
            result = {
                'code': code,
                'roe': roe,
                'revenue_growth': revenue_growth,
                'profit_growth': profit_growth,
                'gross_margin': gross_margin,
                'net_margin': net_margin,
                'revenue': total_revenue,
                'net_profit': net_profit,
                'stat_date': str(row.get('stat_date', '')),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取财务数据失败 [{code}]: {e}")
            return None
    
    def get_balance_sheet(self, code: str, stat_date: str = None) -> Optional[Dict[str, Any]]:
        """
        获取资产负债表数据
        
        Args:
            code: 6 位股票代码
            stat_date: 财报统计日期
            
        Returns:
            Dict: 资产负债表数据
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self.request_count += 1
            
            jq_code = self._format_stock_code(code)
            
            from jqdatasdk import query, balance
            q = query(balance).filter(balance.code == jq_code)
            
            if stat_date:
                df = jq.get_fundamentals(q, statDate=stat_date)
            else:
                df = jq.get_fundamentals(q)
            
            if df is None or df.empty:
                return None
            
            row = df.iloc[0]
            
            result = {
                'code': code,
                'total_assets': float(row.get('total_assets', 0)),
                'total_liabilities': float(row.get('total_liability', 0)),
                'total_equity': float(row.get('total_equity', 0)),
                'debt_ratio': float(row.get('total_liability', 0)) / float(row.get('total_assets', 1)),
                'stat_date': str(row.get('stat_date', '')),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取资产负债表失败 [{code}]: {e}")
            return None
    
    def get_cash_flow(self, code: str, stat_date: str = None) -> Optional[Dict[str, Any]]:
        """
        获取现金流量表数据
        
        Args:
            code: 6 位股票代码
            stat_date: 财报统计日期
            
        Returns:
            Dict: 现金流量表数据
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self.request_count += 1
            
            jq_code = self._format_stock_code(code)
            
            from jqdatasdk import query, cash_flow
            q = query(cash_flow).filter(cash_flow.code == jq_code)
            
            if stat_date:
                df = jq.get_fundamentals(q, statDate=stat_date)
            else:
                df = jq.get_fundamentals(q)
            
            if df is None or df.empty:
                return None
            
            row = df.iloc[0]
            
            result = {
                'code': code,
                'operating_cash_flow': float(row.get('operating_activities_net_cash_flow', 0)),
                'investing_cash_flow': float(row.get('investing_activities_net_cash_flow', 0)),
                'financing_cash_flow': float(row.get('financing_activities_net_cash_flow', 0)),
                'free_cash_flow': float(row.get('free_cash_flow', 0)),
                'stat_date': str(row.get('stat_date', '')),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取现金流量表失败 [{code}]: {e}")
            return None
    
    def get_comprehensive_fundamentals(self, code: str, date: str = None) -> Optional[Dict[str, Any]]:
        """
        获取综合基本面数据（整合估值、财务、资产负债表）
        
        Args:
            code: 6 位股票代码
            date: 查询日期
            
        Returns:
            Dict: 综合基本面数据
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        # 1. 获取估值数据
        valuation = self.get_fundamentals(code, date)
        
        # 2. 获取财务数据
        financials = self.get_financial_data(code)
        
        # 3. 获取资产负债表
        balance = self.get_balance_sheet(code)
        
        # 4. 合并数据
        result = {
            'code': code,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': 'JQData'
        }
        
        if valuation:
            result.update(valuation)
        
        if financials:
            result.update({
                'roe': financials.get('roe', 0),
                'revenue_growth': financials.get('revenue_growth', 0),
                'profit_growth': financials.get('profit_growth', 0),
                'gross_margin': financials.get('gross_margin', 0),
                'net_margin': financials.get('net_margin', 0),
            })
        
        if balance:
            result.update({
                'debt_ratio': balance.get('debt_ratio', 0),
                'total_assets': balance.get('total_assets', 0),
                'total_liabilities': balance.get('total_liabilities', 0),
            })
        
        return result
    
    def get_price(self, code: str, start_date: str, end_date: str = None, 
                  frequency: str = 'daily', fields: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取股票价格数据
        
        Args:
            code: 6 位股票代码
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，默认 None（今天）
            frequency: 频率，'daily'/'weekly'/'monthly'/'minute'
            fields: 字段列表，['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            Dict: 价格数据
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        if not self._validate_stock_code(code):
            print(f"无效的股票代码：{code}")
            return None
        
        try:
            self.request_count += 1
            
            jq_code = self._format_stock_code(code)
            
            # 获取价格数据
            df = jq.get_price(
                jq_code,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                fields=fields,
                skip_paused=False
            )
            
            if df is None or df.empty:
                print(f"获取价格数据失败：{code}")
                return None
            
            # 转换为字典列表
            data = self._convert_dataframe_to_dict(df)
            
            result = {
                'code': code,
                'start_date': start_date,
                'end_date': end_date or datetime.now().strftime('%Y-%m-%d'),
                'frequency': frequency,
                'total_records': len(df),
                'data': data
            }
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取价格数据失败 [{code}]: {e}")
            return None
    
    def get_index_members(self, index_code: str) -> Optional[List[Dict[str, str]]]:
        """
        获取指数成分股
        
        Args:
            index_code: 指数代码（如 '000300.XSHG' 沪深 300）
            
        Returns:
            List[Dict]: 成分股列表
        """
        if not self.is_authenticated:
            print("请先登录")
            return None
        
        try:
            self.request_count += 1
            
            jq_code = self._format_stock_code(index_code)
            
            # 获取成分股
            df = jq.get_index_stocks(jq_code)
            
            if df is None:
                return None
            
            result = []
            for code in df:
                result.append({
                    'code': code.split('.')[0],
                    'jq_code': code,
                    'index': index_code
                })
            
            return result
            
        except Exception as e:
            self.error_count += 1
            print(f"获取指数成分股失败 [{index_code}]: {e}")
            return None
    
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
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取数据获取器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'available': JQDATA_AVAILABLE and self.is_authenticated,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'account_info': self.account_info
        }
    
    def logout(self):
        """登出"""
        if self.is_authenticated:
            try:
                jq.logout()
                self.is_authenticated = False
                print("✓ JQData 已登出")
            except Exception as e:
                print(f"登出失败：{e}")


# 全局实例
_global_jq_fetcher = None


def get_jq_fetcher() -> JQDataFetcher:
    """
    获取全局 JQData 获取器实例
    
    Returns:
        JQDataFetcher: JQData 获取器
    """
    global _global_jq_fetcher
    if _global_jq_fetcher is None:
        _global_jq_fetcher = JQDataFetcher()
    return _global_jq_fetcher


# 便捷函数

def auth(username: str, password: str) -> bool:
    """登录 JQData（便捷函数）"""
    return get_jq_fetcher().auth(username, password)


def get_comprehensive_fundamentals(code: str, date: str = None) -> Optional[Dict[str, Any]]:
    """获取综合基本面数据（便捷函数）"""
    return get_jq_fetcher().get_comprehensive_fundamentals(code, date)


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("JQData 数据获取模块测试")
    print("=" * 60)
    
    # 创建获取器
    fetcher = JQDataFetcher()
    
    if not JQDATA_AVAILABLE:
        print("jqdatasdk 库未安装，请先安装：pip install jqdatasdk")
        exit(1)
    
    # 提示登录
    print("\n请先登录 JQData")
    print("提示：首次使用需要注册聚宽账号（https://www.joinquant.com）")
    print("试用账号：3 个月有效期，100 万条/天流量\n")
    
    # 测试登录（需要用户输入）
    # username = input("请输入聚宽用户名：")
    # password = input("请输入聚宽密码：")
    
    # 如果不想手动输入，可以在这里硬编码（不推荐）
    username = "your_username"
    password = "your_password"
    
    if not fetcher.auth(username, password):
        print("登录失败，请检查用户名和密码")
        exit(1)
    
    # 获取账号信息
    print("\n获取账号信息:")
    account_info = fetcher.get_account_info()
    if account_info:
        print(f"用户 ID: {account_info['user_id']}")
        print(f"账号类型：{account_info['account_type']}")
        print(f"每日流量：{account_info['daily_quota']} 条")
        print(f"已用流量：{account_info['used_quota']} 条")
        print(f"剩余流量：{account_info['remaining_quota']} 条")
        print(f"到期日期：{account_info['expiry_date']}")
    
    # 测试 1: 获取股票列表
    print("\n" + "=" * 60)
    print("1. 测试获取股票列表（前 5 只）")
    stock_list = fetcher.get_stock_list()
    if stock_list:
        for stock in stock_list[:5]:
            print(f"  {stock['code']}: {stock['name']}")
        print(f"  ... 共 {len(stock_list)} 只股票")
    else:
        print("获取失败")
    
    # 测试 2: 获取综合基本面数据
    print("\n" + "=" * 60)
    print("2. 测试获取综合基本面数据（600519 贵州茅台）")
    result = fetcher.get_comprehensive_fundamentals("600519")
    
    if result:
        print(f"股票代码：{result['code']}")
        print(f"市盈率 (PE): {result.get('pe_ratio', 'N/A')}")
        print(f"市净率 (PB): {result.get('pb_ratio', 'N/A')}")
        print(f"ROE: {result.get('roe', 'N/A')}%")
        print(f"毛利率：{result.get('gross_margin', 'N/A')}%")
        print(f"净利率：{result.get('net_margin', 'N/A')}%")
        print(f"资产负债率：{result.get('debt_ratio', 'N/A')}%")
        print(f"数据日期：{result.get('date', 'N/A')}")
        print(f"数据来源：{result.get('data_source', 'N/A')}")
    else:
        print("获取失败")
    
    # 测试 3: 获取状态
    print("\n" + "=" * 60)
    print("3. 获取数据获取器状态")
    status = fetcher.get_status()
    print(f"JQData 可用：{status['available']}")
    print(f"请求次数：{status['request_count']}")
    print(f"错误次数：{status['error_count']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
