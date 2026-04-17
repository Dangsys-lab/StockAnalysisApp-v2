"""读取股票名称的程序"""

import pandas as pd
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict

# 路径配置
NAME_CSV_PATH = Path("D:/tdxday/all_stocks.csv")


@lru_cache(maxsize=1)
def load_stock_names() -> pd.DataFrame:
    """加载股票名称映射，使用LRU缓存避免重复读取
    
    同时从主数据库文件和本地补充文件加载，合并去重
    
    Returns:
        DataFrame包含: 代码, 名称, 交易所
    """
    import re
    
    # 本地补充文件（优先使用，因为格式更可靠）
    local_name_csv = Path(__file__).parent / "name.csv"
    local_df = None
    if local_name_csv.exists():
        try:
            local_df = pd.read_csv(local_name_csv, encoding='utf-8-sig', dtype={'代码': str})
            # 过滤掉代码不是6位数字的行
            local_df = local_df[local_df['代码'].str.match(r'^\d{6}$', na=False)]
        except Exception as e:
            print(f"读取本地name.csv失败: {e}")
            local_df = None
    
    # 主数据库文件
    main_df = None
    if NAME_CSV_PATH.exists():
        # 尝试多种编码
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030']
        for encoding in encodings:
            try:
                main_df = pd.read_csv(NAME_CSV_PATH, encoding=encoding, dtype={'代码': str})
                # 过滤掉代码不是6位数字的行（格式错误的数据）
                main_df = main_df[main_df['代码'].str.match(r'^\d{6}$', na=False)]
                break
            except UnicodeDecodeError:
                continue
        if main_df is None:
            print(f"警告: 无法解码文件: {NAME_CSV_PATH}")
    else:
        print(f"警告: 股票名称文件不存在: {NAME_CSV_PATH}")
    
    # 合并数据
    if local_df is not None and main_df is not None:
        # 合并数据并去重
        combined_df = pd.concat([main_df, local_df], ignore_index=True)
        # 根据代码去重，保留最后出现的记录（本地文件优先）
        combined_df = combined_df.drop_duplicates(subset=['代码'], keep='last')
        return combined_df
    elif local_df is not None:
        return local_df
    elif main_df is not None:
        return main_df
    else:
        # 如果都失败了，返回空DataFrame
        return pd.DataFrame(columns=['代码', '名称', '交易所'])


def get_all_stock_names() -> list:
    """获取所有股票名称列表
    
    Returns:
        包含股票信息字典的列表，每个字典包含代码、名称、交易所
    """
    df = load_stock_names()
    stock_list = []
    for _, row in df.iterrows():
        stock_list.append({
            "code": str(row['代码']),
            "name": str(row['名称']),
            "market": str(row['交易所'])
        })
    return stock_list


def search_stock_by_name(name: str) -> list:
    """根据股票名称搜索股票
    
    Args:
        name: 股票名称或名称的一部分
        
    Returns:
        包含匹配股票信息字典的列表
    """
    df = load_stock_names()
    # 模糊匹配股票名称
    match = df[df['名称'].str.contains(name, na=False, case=False)]
    result = []
    for _, row in match.iterrows():
        result.append({
            "code": str(row['代码']),
            "name": str(row['名称']),
            "market": str(row['交易所'])
        })
    return result


if __name__ == "__main__":
    # 测试获取所有股票名称
    print("获取所有股票名称:")
    stocks = get_all_stock_names()
    print(f"共找到 {len(stocks)} 只股票")
    if stocks:
        print("前5只股票:")
        for stock in stocks[:5]:
            print(f"代码: {stock['code']}, 名称: {stock['name']}, 市场: {stock['market']}")
    
    # 测试搜索股票
    print("\n搜索股票 '石化':")
    results = search_stock_by_name("石化")
    for stock in results:
        print(f"代码: {stock['code']}, 名称: {stock['name']}, 市场: {stock['market']}")
