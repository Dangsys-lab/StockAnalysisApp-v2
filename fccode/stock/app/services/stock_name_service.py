# -*- coding: utf-8 -*-
"""
股票名称服务 - 提供股票代码到名称的映射

职责:
1. 获取股票名称
2. 缓存股票名称
3. 支持多种数据源
"""

from typing import Dict, Optional


class StockNameService:
    """股票名称服务"""
    
    _cache: Dict[str, str] = {}
    
    def get_name(self, stock_code: str) -> Optional[str]:
        """
        获取股票名称
        
        :param stock_code: 股票代码
        :return: 股票名称
        """
        if stock_code in self._cache:
            return self._cache[stock_code]
        
        name = self._fetch_name(stock_code)
        if name:
            self._cache[stock_code] = name
        return name
    
    def _fetch_name(self, stock_code: str) -> Optional[str]:
        """从数据源获取股票名称"""
        try:
            import requests
            
            if stock_code.startswith(('6', '9')):
                full_code = f"sh{stock_code}"
            else:
                full_code = f"sz{stock_code}"
            
            url = f"http://hq.sinajs.cn/list={full_code}"
            headers = {
                'Referer': 'http://finance.sina.com.cn',
                'User-Agent': 'Mozilla/5.0'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            response.encoding = 'gbk'
            
            if response.status_code == 200:
                text = response.text
                if 'hq_str_' in text:
                    data_str = text.split('"')[1]
                    if data_str:
                        name = data_str.split(',')[0]
                        return name
            
            return None
        except Exception as e:
            print(f"[StockNameService] 获取名称失败: {e}")
            return None
