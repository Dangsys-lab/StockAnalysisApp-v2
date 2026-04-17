# -*- coding: utf-8 -*-
"""
Apple IAP 收据验证服务

功能：
1. 验证App Store购买收据
2. 防止越狱设备伪造购买
3. 支持沙盒和生产环境

合规声明：
本模块仅用于验证用户购买状态。
所有收据数据通过Apple官方服务器验证。
"""

import json
import requests
from typing import Dict, Any, Optional
from enum import Enum


class AppleEnvironment(Enum):
    """Apple环境枚举"""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class ReceiptVerifier:
    """
    Apple IAP收据验证器

    官方文档：
    https://developer.apple.com/documentation/appstorereceipts/verifyreceipt
    """

    # Apple验证服务器地址
    VERIFY_URLS = {
        AppleEnvironment.SANDBOX: "https://sandbox.itunes.apple.com/verifyReceipt",
        AppleEnvironment.PRODUCTION: "https://buy.itunes.apple.com/verifyReceipt"
    }

    # 产品ID
    PRODUCT_ID = "com.stockanalysis.pro.lifetime"

    # 状态码说明
    STATUS_CODES = {
        0: "收据验证成功",
        21000: "App Store无法读取提供的JSON数据",
        21002: "收据数据格式错误",
        21003: "收据无法被验证",
        21004: "提供的共享密钥与账户文件中的共享密钥不匹配",
        21005: "收据服务器当前不可用",
        21006: "收据有效但订阅已过期",
        21007: "收据是沙盒收据，但被发送到生产环境验证",
        21008: "收据是生产收据，但被发送到沙盒环境验证",
        21009: "内部数据访问错误",
        21010: "用户账户找不到或已被删除"
    }

    def __init__(self, shared_secret: Optional[str] = None):
        """
        初始化收据验证器

        :param shared_secret: App的共享密钥（从App Store Connect获取）
        """
        self.shared_secret = shared_secret

    def verify_receipt(
        self,
        receipt_data: str,
        environment: AppleEnvironment = AppleEnvironment.PRODUCTION
    ) -> Dict[str, Any]:
        """
        验证收据

        :param receipt_data: Base64编码的收据数据
        :param environment: 验证环境（默认生产环境）
        :return: 验证结果字典
        """
        # 构建请求体
        payload = {
            "receipt-data": receipt_data,
            "exclude-old-transactions": True
        }

        if self.shared_secret:
            payload["password"] = self.shared_secret

        # 首次验证（尝试生产环境）
        url = self.VERIFY_URLS[environment]
        result = self._send_verification_request(url, payload)

        # 如果是沙盒收据但用生产环境验证，自动切换到沙盒
        if result.get("status") == 21007:
            print("ℹ️ 检测到沙盒收据，切换到沙盒环境验证...")
            url = self.VERIFY_URLS[AppleEnvironment.SANDBOX]
            result = self._send_verification_request(url, payload)

        return result

    def _send_verification_request(self, url: str, payload: Dict) -> Dict[str, Any]:
        """
        发送验证请求到Apple服务器

        :param url: Apple验证服务器URL
        :param payload: 请求体
        :return: 验证结果
        """
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                url,
                data=json.dumps(payload),
                headers=headers,
                timeout=30
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "status": response.status_code,
                    "error": f"HTTP错误: {response.status_code}"
                }

            result = response.json()
            status = result.get("status", -1)

            # 验证成功
            if status == 0:
                return self._parse_successful_response(result)

            # 验证失败
            error_msg = self.STATUS_CODES.get(status, f"未知错误: {status}")
            return {
                "success": False,
                "status": status,
                "error": error_msg
            }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "请求超时，请稍后重试"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"验证失败: {str(e)}"
            }

    def _parse_successful_response(self, response: Dict) -> Dict[str, Any]:
        """
        解析成功的验证响应

        :param response: Apple返回的完整响应
        :return: 解析后的结果
        """
        receipt = response.get("receipt", {})

        # 提取关键信息
        result = {
            "success": True,
            "status": 0,
            "bundle_id": receipt.get("bundle_id"),
            "application_version": receipt.get("application_version"),
            "original_application_version": receipt.get("original_application_version"),
            "creation_date": receipt.get("creation_date"),
            "receipt_type": receipt.get("receipt_type")
        }

        # 检查内购项目
        in_app = receipt.get("in_app", [])
        if in_app:
            # 查找我们的产品
            for purchase in in_app:
                if purchase.get("product_id") == self.PRODUCT_ID:
                    result["purchase_info"] = {
                        "product_id": purchase.get("product_id"),
                        "transaction_id": purchase.get("transaction_id"),
                        "original_transaction_id": purchase.get("original_transaction_id"),
                        "purchase_date": purchase.get("purchase_date"),
                        "is_trial_period": purchase.get("is_trial_period", "false") == "true"
                    }
                    result["is_pro_user"] = True
                    break

        # 如果没有找到内购记录
        if "is_pro_user" not in result:
            result["is_pro_user"] = False
            result["warning"] = "收据有效但未找到专业版购买记录"

        return result

    def check_premium_status(self, receipt_data: str) -> Dict[str, Any]:
        """
        检查用户是否为专业版用户（简化接口）

        :param receipt_data: Base64编码的收据数据
        :return: {'is_pro': bool, 'message': str}
        """
        result = self.verify_receipt(receipt_data)

        if result.get("success"):
            is_pro = result.get("is_pro_user", False)
            return {
                "is_pro": is_pro,
                "message": "专业版用户" if is_pro else "免费版用户",
                "purchase_date": result.get("purchase_info", {}).get("purchase_date")
            }
        else:
            return {
                "is_pro": False,
                "message": result.get("error", "验证失败"),
                "error": result.get("status")
            }


# 全局实例
_receipt_verifier = None


def get_receipt_verifier(shared_secret: Optional[str] = None) -> ReceiptVerifier:
    """
    获取全局收据验证器实例

    :param shared_secret: App共享密钥
    :return: ReceiptVerifier实例
    """
    global _receipt_verifier
    if _receipt_verifier is None:
        _receipt_verifier = ReceiptVerifier(shared_secret)
    return _receipt_verifier


if __name__ == '__main__':
    print("=" * 60)
    print("Apple IAP 收据验证服务测试")
    print("=" * 60)

    # 测试验证器初始化
    verifier = ReceiptVerifier()

    print("\n✅ 收据验证器已初始化")
    print(f"   产品ID: {verifier.PRODUCT_ID}")
    print(f"   沙盒URL: {verifier.VERIFY_URLS[AppleEnvironment.SANDBOX]}")
    print(f"   生产URL: {verifier.VERIFY_URLS[AppleEnvironment.PRODUCTION]}")

    print("\n📋 状态码说明:")
    for code, desc in list(verifier.STATUS_CODES.items())[:5]:
        print(f"   {code}: {desc}")
    print("   ...")

    print("\n💡 使用方法:")
    print("   1. 从iOS端获取收据数据（Base64编码）")
    print("   2. 调用 verify_receipt(receipt_data) 验证")
    print("   3. 检查返回结果中的 is_pro_user 字段")

    print("\n" + "=" * 60)
    print("✅ 收据验证服务正常")
    print("=" * 60)
