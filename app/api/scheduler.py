# -*- coding: utf-8 -*-
"""
定时任务API - 选股任务触发

功能:
- 手动触发选股任务
- 查看选股缓存状态
- 供阿里云FC定时触发器调用
"""

from flask import jsonify, request
from . import api_bp

from app.services.stock_screener import StockScreener


@api_bp.route('/api/scheduler/screen-stocks', methods=['POST'])
def trigger_screen_stocks():
    """
    触发选股任务

    供FC定时触发器每天下午4点调用
    也可手动触发用于测试

    :return: 选股结果JSON
    """
    try:
        screener = StockScreener()
        result = screener.screen(top_n=4)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f"选股完成，筛选出 {len(result['stocks'])} 只股票",
                'stocks': result['stocks'],
                'filter_log': result.get('filter_log', []),
                'candidate_count': result.get('candidate_count', 0),
                'scored_count': result.get('scored_count', 0),
                'duration_seconds': result.get('duration_seconds', 0),
                'screened_at': result.get('screened_at', '')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '选股失败'),
                'filter_log': result.get('filter_log', [])
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'选股任务执行异常: {str(e)}'
        })


@api_bp.route('/api/scheduler/cache-status', methods=['GET'])
def get_cache_status():
    """
    查看选股缓存状态

    :return: 缓存状态JSON
    """
    try:
        screener = StockScreener()
        cache = screener.load_cache()

        if cache is None:
            return jsonify({
                'success': True,
                'cached': False,
                'message': '无缓存数据'
            })

        return jsonify({
            'success': True,
            'cached': True,
            'screened_at': cache.get('screened_at', ''),
            'stock_count': len(cache.get('stocks', [])),
            'stocks': cache.get('stocks', []),
            'candidate_count': cache.get('candidate_count', 0),
            'scored_count': cache.get('scored_count', 0),
            'duration_seconds': cache.get('duration_seconds', 0)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
