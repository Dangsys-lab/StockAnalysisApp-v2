# -*- coding: utf-8 -*-
"""
内购验证API接口

功能:
1. 接收iOS端发送的收据数据
2. 验证收据真实性
3. 返回用户购买状态

合规声明:
本接口仅用于验证用户购买状态。
所有收据数据通过Apple官方服务器验证。
"""

from flask import request, jsonify
import os

from app.api import api_bp


@api_bp.route('/api/iap/verify', methods=['POST'])
def verify_iap_receipt():
    """
    验证Apple IAP收据

    请求体(JSON):
    {
        "receipt_data": "Base64编码的收据数据",
        "environment": "production"
    }

    返回:
    {
        "success": true,
        "is_pro": true,
        "message": "专业版用户",
        "purchase_date": "2026-04-07..."
    }
    """
    try:
        data = request.json or {}

        receipt_data = data.get('receipt_data', '').strip()
        if not receipt_data:
            return jsonify({
                'success': False,
                'error': '缺少收据数据',
                'message': '请提供receipt_data参数'
            }), 400

        environment = data.get('environment', 'production')

        shared_secret = os.environ.get('APPLE_SHARED_SECRET')

        from app.core.receipt_verifier import get_receipt_verifier
        verifier = get_receipt_verifier(shared_secret)
        result = verifier.check_premium_status(receipt_data)

        return jsonify({
            'success': True,
            'is_pro': result.get('is_pro', False),
            'message': result.get('message', ''),
            'purchase_date': result.get('purchase_date'),
            'disclaimer': '购买状态基于Apple官方验证结果'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '收据验证失败'
        }), 500


@api_bp.route('/api/iap/restore', methods=['POST'])
def restore_iap_purchase():
    """
    恢复购买

    请求体(JSON):
    {
        "receipt_data": "Base64编码的收据数据"
    }

    返回:
    {
        "success": true,
        "is_pro": true,
        "message": "已恢复购买"
    }
    """
    try:
        data = request.json or {}

        receipt_data = data.get('receipt_data', '').strip()
        if not receipt_data:
            return jsonify({
                'success': False,
                'error': '缺少收据数据'
            }), 400

        shared_secret = os.environ.get('APPLE_SHARED_SECRET')

        from app.core.receipt_verifier import get_receipt_verifier
        verifier = get_receipt_verifier(shared_secret)
        result = verifier.check_premium_status(receipt_data)

        if result.get('is_pro'):
            return jsonify({
                'success': True,
                'is_pro': True,
                'message': '已恢复购买',
                'purchase_date': result.get('purchase_date')
            })
        else:
            return jsonify({
                'success': False,
                'is_pro': False,
                'message': '未找到购买记录'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '恢复购买失败'
        }), 500


@api_bp.route('/api/iap/status', methods=['GET'])
def get_iap_status():
    """
    获取内购服务状态

    返回:
    {
        "success": true,
        "service": "Apple IAP Verification",
        "status": "active"
    }
    """
    return jsonify({
        'success': True,
        'service': 'Apple IAP Verification',
        'status': 'active',
        'product_id': 'com.stockanalysis.pro.lifetime',
        'price': '¥12.00',
        'type': 'lifetime',
        'features': {
            'all_indicators': True,
            'custom_params': True,
            'report_generation': True,
            'no_ads': True
        },
        'disclaimer': '内购服务正常运行'
    })
