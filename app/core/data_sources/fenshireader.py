"""读取分时图数据的程序"""

import pandas as pd
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict
from datetime import datetime
import requests

# 路径配置
INTRADAY_DATA_BASE_PATH = Path("C:/new_tdx/vipdoc/fs/导出数据")


class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self):
        self.current_source = "local"
        # 强制使用本地数据源，实时API只提供当天数据无法满足技术指标计算需求
        self._force_local = True
        self.sources = {}
        self.connection_status = {}
        self.api_info = {}
        self._init_sources()
    
    def _init_sources(self):
        """初始化数据源"""
        self.connection_status["local"] = "connected"
        self.api_info["local"] = {"type": "本地数据", "path": str(INTRADAY_DATA_BASE_PATH)}
    
    def get_current_source(self) -> str:
        """获取当前数据源"""
        return self.current_source

# 全局数据源管理器实例
data_source_manager = DataSourceManager()


def get_realtime_data_from_sina(market: str, code: str) -> Optional[pd.DataFrame]:
    """从新浪财经获取实时数据"""
    try:
        symbol = f"{market}{code}"
        url = f"http://hq.sinajs.cn/list={symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.text
            # 解析新浪数据格式
            if f'var hq_str_{symbol}="' in data:
                stock_data = data.split(f'var hq_str_{symbol}="')[1].split('";')[0]
                parts = stock_data.split(',')
                if len(parts) >= 33:
                    # 新浪返回的字段: 名称,今日开盘价,昨日收盘价,当前价,今日最高价,今日最低价
                    today = datetime.now().strftime('%Y-%m-%d')
                    df_data = {
                        'date': [today],
                        'open': [float(parts[1])],
                        'high': [float(parts[4])],
                        'low': [float(parts[5])],
                        'close': [float(parts[3])],
                        'volume': [int(float(parts[8]))],
                        'amount': [float(parts[9])]
                    }
                    df = pd.DataFrame(df_data)
                    df['date'] = pd.to_datetime(df['date'])
                    return df
    except Exception as e:
        print(f"新浪API获取数据失败: {e}")
    return None


def get_realtime_data_from_tencent(market: str, code: str) -> Optional[pd.DataFrame]:
    """从腾讯财经获取实时数据"""
    try:
        symbol = f"{market}{code}"
        url = f"http://qt.gtimg.cn/q={symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.text
            # 解析腾讯数据格式
            if f'v_{symbol}="' in data:
                stock_data = data.split(f'v_{symbol}="')[1].split('";')[0]
                parts = stock_data.split('~')
                if len(parts) >= 45:
                    today = datetime.now().strftime('%Y-%m-%d')
                    df_data = {
                        'date': [today],
                        'open': [float(parts[5])],
                        'high': [float(parts[33])],
                        'low': [float(parts[34])],
                        'close': [float(parts[3])],
                        'volume': [int(float(parts[6]))],
                        'amount': [float(parts[37])]
                    }
                    df = pd.DataFrame(df_data)
                    df['date'] = pd.to_datetime(df['date'])
                    return df
    except Exception as e:
        print(f"腾讯API获取数据失败: {e}")
    return None


@lru_cache(maxsize=128)
def read_intraday_data(market: str, code: str) -> pd.DataFrame:
    """读取分时数据，使用LRU缓存避免重复读取
    
    根据当前数据源设置决定从本地或实时API获取数据
    
    Args:
        market: 市场代码 (sh/sz/bj)
        code: 股票代码
        
    Returns:
        DataFrame包含: open, high, low, close, amount, volume, code, market
    """
    current_source = data_source_manager.get_current_source()
    
    # 本地数据源：从本地文件读取
    if current_source == "local":
        file_path = INTRADAY_DATA_BASE_PATH / f"{market}_{market}{code}.csv"
        if file_path.exists():
            df = pd.read_csv(file_path)
            return df
        raise FileNotFoundError(f"本地分时数据文件不存在: {file_path}")
    
    # 实时API数据源：获取实时数据作为分时数据
    # 由于实时API通常只提供当前快照，这里返回单条数据
    df = None
    if current_source == "sina":
        df = get_realtime_data_from_sina(market, code)
    elif current_source == "tencent":
        df = get_realtime_data_from_tencent(market, code)
    
    if df is not None:
        # 添加时间列作为分时数据格式
        df['time'] = datetime.now().strftime('%H:%M')
        return df
    
    # 回退到本地数据
    file_path = INTRADAY_DATA_BASE_PATH / f"{market}_{market}{code}.csv"
    if file_path.exists():
        df = pd.read_csv(file_path)
        return df
    raise FileNotFoundError(f"分时数据文件不存在: {file_path}")


def get_intraday_data(market: str, code: str) -> dict:
    """获取分时数据并返回结构化结果
    
    Args:
        market: 市场代码 (sh/sz/bj)
        code: 股票代码
        
    Returns:
        包含分时数据的字典
    """
    try:
        df = read_intraday_data(market, code)
        data = df.to_dict('records')
        
        return {
            'code': code,
            'market': market,
            'data': data,
            'total_records': len(data)
        }
    except FileNotFoundError as e:
        return {'error': f'分时数据文件不存在: {str(e)}'}
    except Exception as e:
        return {'error': str(e)}


def get_market_from_code(code: str) -> str:
    """根据股票代码获取市场代码
    
    Args:
        code: 股票代码
        
    Returns:
        市场代码 (sh/sz/bj)
    """
    code = str(code).zfill(6)
    if code.startswith('6'):
        return 'sh'
    elif code.startswith('0') or code.startswith('3'):
        return 'sz'
    elif code.startswith('4') or code.startswith('8'):
        return 'bj'
    return 'sh'


def clear_cache():
    """清除所有缓存"""
    read_intraday_data.cache_clear()


if __name__ == "__main__":
    # 测试读取分时数据
    test_codes = ["000852", "600000"]
    for code in test_codes:
        market = get_market_from_code(code)
        print(f"\n读取股票 {code} 的分时数据:")
        result = get_intraday_data(market, code)
        if 'error' in result:
            print(f"错误: {result['error']}")
        else:
            print(f"成功获取 {result['total_records']} 条分时数据")
            if result['data']:
                print("前5条数据:")
                for item in result['data'][:5]:
                    print(item)
    
    # 测试清除缓存
    print("\n清除缓存")
    clear_cache()
    print("缓存已清除")
