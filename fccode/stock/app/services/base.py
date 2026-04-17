# -*- coding: utf-8 -*-
"""
Service基类 - 所有Service层的基类

职责:
1. 提供通用的服务方法
2. 统一异常处理
3. 日志记录
"""

from typing import Dict, Any, Optional


class BaseService:
    """Service基类"""
    
    def __init__(self):
        self._data_reader = None
        self._stock_name_service = None
    
    @property
    def data_reader(self):
        """获取数据读取器"""
        if self._data_reader is None:
            from app.services.data_service import DataReader
            self._data_reader = DataReader()
        return self._data_reader
    
    @property
    def stock_name_service(self):
        """获取股票名称服务"""
        if self._stock_name_service is None:
            from app.services.stock_name_service import StockNameService
            self._stock_name_service = StockNameService()
        return self._stock_name_service
    
    def _handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """
        统一错误处理
        
        :param error: 异常对象
        :param context: 错误上下文
        :return: 错误响应字典
        """
        error_msg = str(error)
        print(f"[{self.__class__.__name__}] {context}: {error_msg}")
        
        return {
            'success': False,
            'error': error_msg,
            'message': f'{context}失败'
        }
