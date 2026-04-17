# -*- coding: utf-8 -*-
"""
综合分析报告API接口（增强版）

v2.1 更新内容:
✅ 请求频率限制（报告计算消耗资源，需严格控制）
✅ 响应缓存（避免重复计算）
✅ 输入验证增强

合规声明:
本接口仅提供技术指标的客观数据汇总和状态描述。
所有输出严格遵循合规要求，不含任何投资建议或操作指引。
"""

from flask import request, jsonify
from datetime import datetime
import pandas as pd

from . import api_bp
from app.core.report_generator import ReportGenerator
from app.core.indicators.calculator import IndicatorCalculatorV2
from app.core.adaptive import MarketEnvironmentDetector, AdaptiveThresholdManager
from app.core.api_middleware import rate_limit, cache_response


@api_bp.route('/api/report/<stock_code>', methods=['GET'])
@rate_limit('report')
@cache_response('medium')
def get_stock_report(stock_code):
    """
    获取指定股票的综合技术分析报告（带缓存，15分钟刷新）

    新增特性:
    - 限流：每分钟最多10次请求（计算密集型，严格限制）
    - 缓存：相同参数15分钟内返回缓存（避免重复计算）

    :param stock_code: 6位股票代码
    :return: 报告JSON（纯客观技术状态描述）
    """
    try:
        is_pro = request.args.get('is_pro', 'false').lower() == 'true'

        # 验证股票代码格式
        if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
            return jsonify({
                'success': False,
                'message': '请提供有效的6位数字股票代码',
                'stock_code': stock_code or ''
            }), 400

        data_reader = get_data_reader()

        df = data_reader.get_daily_data(
            stock_code,
            start_date=(datetime.now() - pd.Timedelta(days=365)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        if df.empty:
            return jsonify({
                'success': False,
                'message': f'未找到股票 {stock_code} 的数据',
                'stock_code': stock_code,
                '_cached': False,
                'disclaimer': '数据获取失败。'
            }), 404

        if not is_pro:
            return jsonify({
                'success': True,
                'stock_code': stock_code,
                'is_pro': False,
                'message': '综合分析报告为专业版功能',
                'upgrade_prompt': '升级到专业版以获取完整的技术面总结报告',
                '_cached': False,
                'disclaimer': '以上信息仅供参考，不构成任何投资建议。'
            })

        calc = IndicatorCalculatorV2()

        data_dict = {
            'open': df['open'].tolist(),
            'high': df['high'].tolist(),
            'low': df['low'].tolist(),
            'close': df['close'].tolist(),
            'volume': df['volume'].tolist()
        }

        indicators_result = calc.calculate_all(data_dict)

        detector = MarketEnvironmentDetector()
        index_df = data_reader.get_daily_data(
            'sh000001',
            start_date=(datetime.now() - pd.Timedelta(days=120)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        market_env = None
        if not index_df.empty:
            env_data = {
                'close': index_df['close'].tolist(),
                'high': index_df['high'].tolist(),
                'low': index_df['low'].tolist(),
                'volume': index_df['volume'].tolist()
            }
            market_env = detector.detect(env_data, 60)

        manager = AdaptiveThresholdManager()
        thresholds = manager.get_thresholds(
            market_env['status'] if market_env else 'oscillation'
        )

        generator = ReportGenerator()
        report = generator.generate_report(
            indicators_result['data'],
            thresholds=thresholds.get('all_thresholds', {}),
            market_env=market_env
        )

        report['stock_code'] = stock_code
        report['stock_name'] = get_stock_name(stock_code)
        report['data_points'] = len(df)
        report['date_range'] = {
            'start': str(df.index[0].date()) if not df.empty else '',
            'end': str(df.index[-1].date()) if not df.empty else ''
        }
        report['_cached'] = False

        return jsonify(report)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '生成报告时发生错误',
            '_cached': False,
            'disclaimer': '服务暂时不可用，请稍后重试。'
        }), 500


@api_bp.route('/api/report/summary/<stock_code>', methods=['GET'])
@rate_limit('report')
@cache_response('short')
def get_report_summary(stock_code):
    """
    获取简版报告摘要（用于列表页快速预览）

    短期缓存5分钟，保证相对实时性

    :param stock_code: 6位股票代码
    :return: 摘要JSON
    """
    try:
        full_report = _get_cached_report(stock_code)

        if not full_report or not full_report.get('success'):
            return jsonify({
                'success': True,
                'stock_code': stock_code,
                'score': 50,
                'status': '数据加载中',
                'signal_counts': {'bullish': 0, 'bearish': 0},
                'quick_summary': '暂无数据，请刷新后查看完整报告',
                '_cached': False
            })

        summary = full_report.get('summary', {})

        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'score': full_report.get('score', 50),
            'status': summary.get('status', '未知'),
            'signal_counts': summary.get('signal_counts', {'bullish': 0, 'bearish': 0}),
            'quick_summary': summary.get('pattern_description', ''),
            'market_context': summary.get('market_context', ''),
            'generated_at': full_report.get('generated_at', ''),
            '_cached': False
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            '_cached': False
        }), 500


def get_stock_name(stock_code: str) -> str:
    """获取股票名称"""
    try:
        from app.services.stock_name_service import StockNameService
        service = StockNameService()
        name = service.get_name(stock_code)
        return name or ''
    except Exception:
        try:
            from pytdx.reader import TdxReader
            reader = TdxReader()

            if stock_code.startswith(('6', '9')):
                market = 'sh'
            else:
                market = 'sz'

            file_path = f"C:\\new_tdx\\vipdoc\\{market}\\T0002\\hq_cache\\shm.tnf"
            stocks = reader.to_df(file_path)

            match = stocks[stocks['code'] == stock_code]
            if not match.empty:
                return match.iloc[0]['name']

            return ''
        except Exception:
            return ''


def _get_cached_report(stock_code: str):
    """获取缓存的报告（简化版）"""
    try:
        from app.core.report_generator import ReportGenerator
        from app.core.indicators.calculator import IndicatorCalculatorV2
        from app.core.adaptive import AdaptiveThresholdManager

        data_reader = get_data_reader()
        df = data_reader.get_daily_data(
            stock_code,
            start_date=(datetime.now() - pd.Timedelta(days=180)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d')
        )

        if df.empty:
            return None

        calc = IndicatorCalculatorV2()
        data_dict = {
            'open': df['open'].tolist(),
            'high': df['high'].tolist(),
            'low': df['low'].tolist(),
            'close': df['close'].tolist(),
            'volume': df['volume'].tolist()
        }

        indicators_result = calc.calculate_all(data_dict)

        manager = AdaptiveThresholdManager()
        thresholds = manager.get_thresholds('oscillation')

        generator = ReportGenerator()
        report = generator.generate_report(
            indicators_result['data'],
            thresholds=thresholds.get('all_thresholds', {})
        )

        return report

    except Exception as e:
        print(f"缓存报告获取失败: {e}")
        return None


def get_data_reader():
    """获取数据读取器实例"""
    try:
        from app.services.data_service import DataService
        return DataService().get_data_reader()
    except ImportError:
        class SimpleDataReader:
            def get_daily_data(self, code, start_date=None, end_date=None):
                import os
                try:
                    from pytdx.reader import TdxDailyBarReader
                    reader = TdxDailyBarReader()

                    market = 'sh' if code.startswith(('6', '9')) else 'sz'
                    prefix = market
                    base_path = r"C:\new_tdx\vipdoc"
                    file_path = os.path.join(base_path, market, 'lday', f"{prefix}{code}.day")

                    if not os.path.exists(file_path):
                        return pd.DataFrame()

                    df = reader.get_df(file_path)
                    df = df.sort_index()

                    if start_date:
                        df = df[df.index >= pd.Timestamp(start_date)]
                    if end_date:
                        df = df[df.index <= pd.Timestamp(end_date)]

                    return df
                except Exception as e:
                    print(f"数据读取失败: {e}")
                    return pd.DataFrame()

        return SimpleDataReader()


if __name__ == '__main__':
    print("分析报告API模块（增强版）已加载")
    print("可用端点:")
    print("  GET /api/report/<code>       - 获取完整报告（严格限流+中期缓存）")
    print("  GET /api/report/summary/<code> - 获取摘要（限流+短期缓存）")
