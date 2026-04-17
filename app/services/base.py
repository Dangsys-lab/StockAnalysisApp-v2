# -*- coding: utf-8 -*-
"""
Service基类
"""

from typing import Dict, Any, Optional
from app.core.online_data_source import get_online_data_manager


class BaseService:
    """
    Service层基类
    
    提供通用的数据获取和工具方法
    """
    
    def __init__(self):
        """初始化Service"""
        self._data_manager = None
    
    @property
    def data_manager(self):
        """获取数据管理器实例"""
        if self._data_manager is None:
            self._data_manager = get_online_data_manager()
        return self._data_manager
    
    def _clean_nan(self, data):
        """清理NaN值"""
        import math
        
        if isinstance(data, list):
            return [None if (isinstance(x, float) and math.isnan(x)) else x for x in data]
        elif isinstance(data, dict):
            return {k: None if (isinstance(v, float) and math.isnan(v)) else v for k, v in data.items()}
        elif isinstance(data, float) and math.isnan(data):
            return None
        else:
            return data
