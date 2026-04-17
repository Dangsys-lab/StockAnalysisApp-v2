# -*- coding: utf-8 -*-
"""
Apple IAP收据验证器

功能:
- 验证Apple内购收据
- 判断用户是否为专业版用户
"""

import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime


class ReceiptVerifier:
    """
    Apple收据验证器
    """
    
    SANDBOX_URL = "https://sandbox.itunes.apple.com/verifyReceipt"
    PRODUCTION_URL = "https://buy.itunes.apple.com/verifyReceipt"
    
    VALID_PRODUCT_IDS = [
        'com.stockanalysis.pro.lifetime',
    ]
    
    def __init__(self, shared_secret: str = None):
        """
        初始化验证器
        
        :param shared_secret: Apple共享密钥
        """
        self.shared_secret = shared_secret
    
    def verify_receipt(self, receipt_data: str, environment: str = 'production') -> Dict[str, Any]:
        """
        验证收据
        
        :param receipt_data: Base64编码的收据数据
        :param environment: 环境 (production/sandbox)
        :return: 验证结果
        """
        url = self.PRODUCTION_URL if environment == 'production' else self.SANDBOX_URL
        
        payload = {
            'receipt-data': receipt_data,
            'exclude-old-transactions': True
        }
        
        if self.shared_secret:
            payload['password'] = self.shared_secret
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            status = result.get('status', -1)
            
            if status == 0:
                return {
                    'success': True,
                    'receipt': result.get('receipt', {}),
                    'latest_receipt_info': result.get('latest_receipt_info', [])
                }
            elif status == 21007:
                return self.verify_receipt(receipt_data, 'sandbox')
            else:
                error_messages = {
                    21000: 'App Store无法读取提供的JSON对象',
                    21002: '收据数据不符合格式',
                    21003: '收据无法被验证',
                    21004: '提供的共享密钥与账户不匹配',
                    21005: '收据服务器当前不可用',
                    21006: '收据有效但订阅已过期',
                    21008: '收据来自生产环境但发送到沙盒环境验证'
                }
                return {
                    'success': False,
                    'error': error_messages.get(status, f'验证失败，状态码: {status}'),
                    'status': status
                }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': '请求超时，请稍后重试'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'网络请求失败: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'验证过程出错: {str(e)}'
            }
    
    def check_premium_status(self, receipt_data: str) -> Dict[str, Any]:
        """
        检查用户是否为专业版用户
        
        :param receipt_data: Base64编码的收据数据
        :return: {'is_pro': bool, 'message': str, 'purchase_date': str, 'features': dict}
        """
        result = self.verify_receipt(receipt_data)
        
        if not result.get('success'):
            return {
                'is_pro': False,
                'message': result.get('error', '收据验证失败'),
                'features': {
                    'all_indicators': False,
                    'portfolio_limit': 5,
                    'custom_params': False,
                    'monitor_conditions': False
                }
            }
        
        receipt = result.get('receipt', {})
        latest_receipt_info = result.get('latest_receipt_info', [])
        
        all_purchases = latest_receipt_info if latest_receipt_info else []
        if 'in_app' in receipt:
            all_purchases.extend(receipt['in_app'])
        
        for purchase in all_purchases:
            product_id = purchase.get('product_id', '')
            if product_id in self.VALID_PRODUCT_IDS:
                purchase_date_ms = purchase.get('purchase_date_ms', 0)
                purchase_date = datetime.fromtimestamp(int(purchase_date_ms) / 1000).strftime('%Y-%m-%d %H:%M:%S') if purchase_date_ms else None
                
                return {
                    'is_pro': True,
                    'is_lifetime_pro': True,
                    'message': '终身专业版用户',
                    'purchase_date': purchase_date,
                    'product_id': product_id,
                    'features': {
                        'all_indicators': True,
                        'portfolio_limit': 10,
                        'custom_params': False,
                        'monitor_conditions': False
                    }
                }
        
        original_purchase_date = receipt.get('original_purchase_date')
        
        return {
            'is_pro': False,
            'message': '未找到专业版购买记录',
            'original_purchase_date': original_purchase_date,
            'features': {
                'all_indicators': False,
                'portfolio_limit': 5,
                'custom_params': False,
                'monitor_conditions': False
            }
        }


_verifier_instance = None


def get_receipt_verifier(shared_secret: str = None) -> ReceiptVerifier:
    """
    获取收据验证器实例
    
    :param shared_secret: Apple共享密钥
    :return: ReceiptVerifier实例
    """
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = ReceiptVerifier(shared_secret)
    return _verifier_instance
