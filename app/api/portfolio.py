# -*- coding: utf-8 -*-
"""
自选股管理API接口（增强版）

v2.1 更新内容:
✅ 请求频率限制（防止频繁操作）
✅ 查询接口缓存（减少数据库压力）
✅ 输入验证增强（更严格的参数检查）

合规声明:
本接口仅提供用户自选股票的数据存储和查询功能。
不包含任何投资建议或推荐内容。
"""

from flask import request, jsonify
from datetime import datetime
import json

from . import api_bp
from app.core.portfolio_db import PortfolioDatabase
from app.core.api_middleware import rate_limit, cache_response


def get_db():
    """获取数据库实例"""
    return PortfolioDatabase()


@api_bp.route('/api/portfolio', methods=['GET'])
@rate_limit('portfolio')
@cache_response('short')
def get_portfolio_list():
    """
    获取自选股票列表（带缓存，5分钟刷新）

    新增特性:
    - 限流：每分钟最多20次请求
    - 缓存：相同参数5分钟内返回缓存
    - 自动补充股票名称

    Query参数:
        - group: 分组名称（可选）
        - sort: 排序字段 (add_date/stock_code/stock_name)
        - order: 排序方向 (ASC/DESC)

    :return: 自选股票列表JSON
    """
    try:
        group_name = request.args.get('group')
        sort_by = request.args.get('sort', 'add_date')
        order = request.args.get('order', 'DESC')

        db = get_db()
        stocks = db.get_all_stocks(
            group_name=group_name,
            sort_by=sort_by,
            order=order
        )

        from app.services.stock_name_service import StockNameService
        name_service = StockNameService()
        
        from app.api.market import _fetch_stock_from_sina
        
        for stock in stocks:
            stock_name = stock.get('stock_name', '')
            if not stock_name or stock_name == stock.get('stock_code', ''):
                fetched_name = name_service.get_name(stock.get('stock_code', ''))
                if fetched_name:
                    stock['stock_name'] = fetched_name
            
            try:
                price, change = _fetch_stock_from_sina(stock.get('stock_code', ''))
                if price is not None:
                    stock['current_price'] = round(price, 2)
                    stock['change_pct'] = round(change, 2)
                else:
                    stock['current_price'] = None
                    stock['change_pct'] = None
            except Exception:
                stock['current_price'] = None
                stock['change_pct'] = None

        groups = db.get_groups()
        total_count = db.get_count()

        return jsonify({
            'success': True,
            'stocks': stocks,
            'total_count': total_count,
            'groups': groups,
            'current_group': group_name or '全部',
            '_cached': False,
            'disclaimer': '自选股仅为个人收藏功能，不构成任何投资建议。'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取自选列表时发生错误'
        }), 500


@api_bp.route('/api/portfolio/<stock_code>', methods=['GET'])
@rate_limit('portfolio')
@cache_response('short')
def get_portfolio_stock(stock_code):
    """
    获取单只自选股票详情（带缓存）

    :param stock_code: 6位股票代码
    :return: 股票详情JSON
    """
    try:
        db = get_db()
        stock = db.get_stock(stock_code)

        if not stock:
            return jsonify({
                'success': False,
                'message': f'未找到股票 {stock_code} 的自选记录',
                'in_portfolio': False
            }), 404

        return jsonify({
            'success': True,
            'stock': stock,
            'in_portfolio': True,
            '_cached': False
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '查询失败'
        }), 500


@api_bp.route('/api/portfolio', methods=['POST'])
@rate_limit('portfolio')
def add_to_portfolio():
    """
    添加股票到自选列表（仅限流，不缓存）

    写入操作不能缓存，保证数据一致性

    请求体(JSON):
        {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "group_name": "默认",
            "note": "",
            "add_price": 1800.00
        }

    :return: 操作结果JSON
    """
    try:
        data = request.json or {}

        stock_code = data.get('stock_code', '').strip()

        # 增强的输入验证
        if not stock_code:
            return jsonify({
                'success': False,
                'message': '请提供股票代码'
            }), 400

        if len(stock_code) != 6 or not stock_code.isdigit():
            return jsonify({
                'success': False,
                'message': '请提供有效的6位数字股票代码'
            }), 400

        db = get_db()

        if db.check_exists(stock_code):
            return jsonify({
                'success': False,
                'message': f'股票 {stock_code} 已在自选列表中',
                'already_exists': True
            }), 409

        # 如果没有传股票名称，自动获取
        stock_name = data.get('stock_name', '')
        if not stock_name:
            try:
                from app.services.stock_name_service import StockNameService
                name_service = StockNameService()
                stock_name = name_service.get_name(stock_code) or stock_code
            except Exception as e:
                print(f"[警告] 获取股票名称失败: {e}")
                stock_name = stock_code

        result = db.add_stock(
            stock_code=stock_code,
            stock_name=stock_name,
            group_name=data.get('group_name', '默认'),
            note=data.get('note', ''),
            add_price=float(data.get('add_price', 0))
        )

        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '添加失败'
        }), 500


@api_bp.route('/api/portfolio/<stock_code>', methods=['PUT'])
@rate_limit('portfolio')
def update_portfolio_stock(stock_code):
    """
    更新自选股票信息（仅限流，不缓存）

    写入操作不能缓存

    :param stock_code: 6位股票代码
    :return: 操作结果JSON
    """
    try:
        data = request.json or {}

        db = get_db()

        if not db.check_exists(stock_code):
            return jsonify({
                'success': False,
                'message': f'股票 {stock_code} 不在自选列表中'
            }), 404

        result = db.update_stock(stock_code, **data)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '更新失败'
        }), 500


@api_bp.route('/api/portfolio/<stock_code>', methods=['DELETE'])
@rate_limit('portfolio')
def remove_from_portfolio(stock_code):
    """
    从自选列表移除股票（仅限流，不缓存）

    写入操作不能缓存

    :param stock_code: 6位股票代码
    :return: 操作结果JSON
    """
    try:
        db = get_db()

        if not db.check_exists(stock_code):
            return jsonify({
                'success': False,
                'message': f'股票 {stock_code} 不在自选列表中'
            }), 404

        result = db.remove_stock(stock_code)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '移除失败'
        }), 500


@api_bp.route('/api/portfolio/groups', methods=['GET'])
@rate_limit('portfolio')
@cache_response('medium')
def get_portfolio_groups():
    """
    获取所有分组及数量（中期缓存，15分钟刷新）

    分组信息变化较少，适合中期缓存

    :return: 分组列表JSON
    """
    try:
        db = get_db()
        groups = db.get_groups()
        total = db.get_count()

        return jsonify({
            'success': True,
            'groups': groups,
            'total_stocks': total,
            '_cached': False,
            'disclaimer': '分组为用户自定义分类，无特殊含义。'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/api/portfolio/check/<stock_code>', methods=['GET'])
@rate_limit('portfolio')
@cache_response('short')
def check_in_portfolio(stock_code):
    """
    检查股票是否在自选中（带缓存）

    :param stock_code: 6位股票代码
    :return: 检查结果JSON
    """
    try:
        db = get_db()
        exists = db.check_exists(stock_code)

        result = {
            'success': True,
            'stock_code': stock_code,
            'in_portfolio': exists,
            '_cached': False
        }

        if exists:
            stock = db.get_stock(stock_code)
            if stock:
                result['stock_info'] = {
                    'group_name': stock['group_name'],
                    'add_date': stock['add_date'],
                    'note': stock['note']
                }

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/api/portfolio/import', methods=['POST'])
@rate_limit('portfolio')
def import_portfolio():
    """
    批量导入自选股票（仅限流，不缓存）

    批量写入操作，需要严格限制频率

    请求体(Json):
        [
            {"stock_code": "600519", "stock_name": "贵州茅台", ...},
            {"stock_code": "000858", "stock_name": "五粮液", ...}
        ]

    :return: 导入结果JSON
    """
    try:
        data = request.json or []

        if not isinstance(data, list):
            return jsonify({
                'success': False,
                'message': '请提供股票列表数组'
            }), 400

        if len(data) > 100:
            return jsonify({
                'success': False,
                'message': '单次最多导入100只股票'
            }), 400

        # 验证每条记录的格式
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                return jsonify({
                    'success': False,
                    'message': f'第{i+1}条记录格式错误，应为对象'
                }), 400

            code = item.get('stock_code', '')
            if not code or len(code) != 6 or not code.isdigit():
                return jsonify({
                    'success': False,
                    'message': f'第{i+1}条记录的股票代码无效: {code}'
                }), 400

        db = get_db()
        result = db.import_stocks(data)

        return jsonify(result), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '导入失败'
        }), 500


@api_bp.route('/api/portfolio/export', methods=['GET'])
@rate_limit('portfolio')
@cache_response('short')
def export_portfolio():
    """
    导出自选股票列表（带缓存）

    Query参数:
        - group: 导出指定分组（可选）
        - format: 输出格式 (json/csv)，默认json

    :return: 导出数据JSON
    """
    try:
        group_name = request.args.get('group')
        export_format = request.args.get('format', 'json').lower()

        db = get_db()
        stocks = db.export_stocks(group_name=group_name)

        if export_format == 'csv':
            import csv
            import io

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'stock_code', 'stock_name', 'group_name',
                'note', 'add_price', 'add_date'
            ])
            writer.writeheader()

            for stock in stocks:
                writer.writerow({
                    'stock_code': stock['stock_code'],
                    'stock_name': stock['stock_name'],
                    'group_name': stock['group_name'],
                    'note': stock['note'] or '',
                    'add_price': stock['add_price'] or '',
                    'add_date': stock['add_date'] or ''
                })

            from flask import Response
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': 'attachment; filename=portfolio.csv'
                }
            )

        return jsonify({
            'success': True,
            'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'count': len(stocks),
            'stocks': stocks,
            '_cached': False,
            'disclaimer': '导出数据仅供个人使用，请勿传播。'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '导出失败'
        }), 500


if __name__ == '__main__':
    print("自选股API模块（增强版）已加载")
    print("可用端点:")
    print("  GET    /api/portfolio              - 获取自选列表（限流+缓存）")
    print("  POST   /api/portfolio              - 添加自选股（限流）")
    print("  GET    /api/portfolio/<code>       - 获取详情（限流+缓存）")
    print("  PUT    /api/portfolio/<code>       - 更新信息（限流）")
    print("  DELETE /api/portfolio/<code>       - 删除自选股（限流）")
    print("  GET    /api/portfolio/groups       - 获取分组（限流+中期缓存）")
    print("  GET    /api/portfolio/check/<code> - 检查是否在自选（限流+缓存）")
    print("  POST   /api/portfolio/import       - 批量导入（限流）")
    print("  GET    /api/portfolio/export       - 导出列表（限流+缓存）")
