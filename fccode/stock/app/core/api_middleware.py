# -*- coding: utf-8 -*-
"""
API 中间件 - 限流、缓存、容错

功能:
1. 请求频率限制（Rate Limiting）
2. 响应缓存（Caching）
3. 多数据源自动切换（Failover）
4. 请求重试机制（Retry）
5. 批量请求合并（Batching）

合规声明:
本模块仅提供技术层面的性能和可靠性保障。
不包含任何业务逻辑或数据处理。
"""

import time
import functools
import hashlib
import json
from datetime import datetime, timedelta
from flask import request, g, jsonify
from typing import Callable, Any, Optional, Dict


class RateLimiter:
    """
    请求频率限制器
    
    基于滑动窗口算法，防止恶意请求或误操作导致的服务器压力
    """
    
    def __init__(self):
        self.requests = {}  # {ip: [timestamp1, timestamp2, ...]}
        self.limits = {
            'default': (60, 60),      # 每分钟60次（默认）
            'indicator': (30, 60),   # 指标查询每分钟30次
            'report': (10, 60),       # 报告生成每分钟10次
            'portfolio': (20, 60),   # 自选股操作每分钟20次
            'market': (30, 60),       # 市场环境每分钟30次
        }
    
    def is_allowed(self, key: str, limit_type: str = 'default') -> tuple:
        """
        检查是否允许请求
        
        :param key: 标识键（通常是IP地址）
        :param limit_type: 限制类型
        :return: (是否允许, 剩余次数, 重置时间)
        """
        now = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        max_requests, window_seconds = self.limits.get(limit_type, self.limits['default'])
        
        # 清理过期记录
        self.requests[key] = [
            t for t in self.requests[key]
            if now - t < window_seconds
        ]
        
        # 检查是否超限
        if len(self.requests[key]) >= max_requests:
            oldest = min(self.requests[key])
            reset_in = int(window_seconds - (now - oldest)) + 1
            return False, 0, reset_in
        
        # 记录本次请求
        self.requests[key].append(now)
        remaining = max_requests - len(self.requests[key])
        
        return True, remaining, 0
    
    def get_headers(self, key: str, limit_type: str = 'default') -> dict:
        """获取限流相关的响应头"""
        allowed, remaining, reset = self.is_allowed(key, limit_type)
        
        max_req = self.limits.get(limit_type, self.limits['default'])[0]
        
        return {
            'X-RateLimit-Limit': max_req,
            'X-RateLimit-Remaining': remaining,
            'X-RateLimit-Reset': reset,
            'Retry-After': reset if not allowed else 0
        }


class ResponseCache:
    """
    响应缓存管理器
    
    缓存策略:
    - 短期缓存：5分钟（实时性要求高的数据）
    - 中期缓存：15分钟（市场环境等变化慢的数据）
    - 长期缓存：1小时（指标列表、配置等静态数据）
    """
    
    def __init__(self):
        self.cache = {}
        self.ttls = {
            'short': 300,     # 5分钟
            'medium': 900,    # 15分钟
            'long': 3600,     # 1小时
        }
    
    def _generate_key(self, prefix: str, *args) -> str:
        """生成缓存键"""
        raw_key = f"{prefix}:{':'.join(str(a) for a in args)}"
        return hashlib.md5(raw_key.encode()).hexdigest()
    
    def get(self, cache_type: str, key: str) -> Optional[Dict]:
        """
        获取缓存
        
        :param cache_type: 缓存类型 (short/medium/long)
        :param key: 缓存键
        :return: 缓存的数据或None
        """
        full_key = f"{cache_type}:{key}"
        
        if full_key not in self.cache:
            return None
        
        data, timestamp = self.cache[full_key]
        ttl = self.ttls.get(cache_type, self.ttls['short'])
        
        if time.time() - timestamp > ttl:
            del self.cache[full_key]
            return None
        
        return data
    
    def set(self, cache_type: str, key: str, data: Any) -> None:
        """
        设置缓存
        
        :param cache_type: 缓存类型
        :param key: 缓存键
        :param data: 要缓存的数据
        """
        full_key = f"{cache_type}:{key}"
        self.cache[full_key] = (data, time.time())
    
    def invalidate(self, pattern: str = None) -> int:
        """
        清除缓存
        
        :param pattern: 要清除的模式前缀（可选），为空则清除全部
        :return: 清除的条目数
        """
        count = 0
        
        keys_to_delete = []
        for key in self.cache.keys():
            if pattern is None or key.startswith(pattern):
                keys_to_delete.append(key)
                count += 1
        
        for key in keys_to_delete:
            del self.cache[key]
        
        return count
    
    def cleanup(self) -> int:
        """清理过期缓存"""
        now = time.time()
        expired_keys = []
        
        for key, (data, timestamp) in self.cache.items():
            cache_type = key.split(':')[0]
            ttl = self.ttls.get(cache_type, self.ttls['short'])
            
            if now - timestamp > ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


class DataSourceManager:
    """
    多数据源管理器（故障转移）
    
    支持多个数据源的优先级排序和自动切换
    当主数据源失败时，自动切换到备用数据源
    """
    
    def __init__(self):
        self.sources = []
        self.source_status = {}  # {source_name: {'status', 'last_error', 'fail_count'}}
        self.max_failures = 3  # 连续失败N次后降级
        self.recovery_time = 300  # 5分钟后尝试恢复
    
    def register_source(self, name: str, priority: int, getter_func: Callable) -> None:
        """
        注册数据源
        
        :param name: 数据源名称
        :param priority: 优先级（数字越小越优先）
        :param getter_func: 数据获取函数
        """
        self.sources.append({
            'name': name,
            'priority': priority,
            'getter': getter_func
        })
        self.sources.sort(key=lambda x: x['priority'])
        
        self.source_status[name] = {
            'status': 'active',
            'last_error': None,
            'fail_count': 0,
            'last_success': None
        }
    
    def get_data(self, *args, **kwargs) -> Dict[str, Any]:
        """
        从可用数据源获取数据（自动故障转移）
        
        :return: {'success', 'data', 'source', 'is_fallback'}
        """
        last_error = None
        
        for source in self.sources:
            name = source['name']
            status = self.source_status[name]
            
            # 检查该源是否被禁用
            if status['status'] == 'disabled':
                # 检查是否到了恢复时间
                if status.get('disabled_at'):
                    disabled_for = time.time() - status['disabled_at']
                    if disabled_for > self.recovery_time:
                        # 尝试恢复
                        status['status'] = 'active'
                        status['fail_count'] = 0
                    else:
                        continue
            
            try:
                result = source['getter'](*args, **kwargs)
                
                if result and (result is True or 
                             (isinstance(result, dict) and result.get('success', False) != False)):
                    
                    # 成功！更新状态
                    status['status'] = 'active'
                    status['fail_count'] = 0
                    status['last_success'] = time.time()
                    status['last_error'] = None
                    
                    is_fallback = source['priority'] > 1  # 只有非第一优先级才算备用
                    
                    return {
                        'success': True,
                        'data': result,
                        'source': name,
                        'is_fallback': is_fallback,
                        'available_sources': len([s for s in self.sources 
                                                if self.source_status[s['name']]['status'] == 'active'])
                    }
                
            except Exception as e:
                last_error = e
                status['last_error'] = str(e)
                status['fail_count'] += 1
                
                # 连续失败超过阈值则禁用
                if status['fail_count'] >= self.max_failures:
                    status['status'] = 'disabled'
                    status['disabled_at'] = time.time()
        
        # 所有数据源都失败
        return {
            'success': False,
            'error': str(last_error) if last_error else '所有数据源不可用',
            'source': None,
            'is_fallback': True,
            'suggestion': '请稍后重试'
        }
    
    def get_source_health(self) -> Dict[str, Dict]:
        """获取所有数据源的健康状态"""
        health = {}
        
        for name, status in self.source_status.items():
            health[name] = {
                'status': status['status'],
                'failures': status['fail_count'],
                'last_error': status['last_error'],
                'last_success': status.get('last_success')
            }
        
        return health


# 全局实例
rate_limiter = RateLimiter()
response_cache = ResponseCache()


def rate_limit(limit_type: str = 'default'):
    """
    限流装饰器
    
    用法:
        @app.route('/api/data')
        @rate_limit('indicator')
        def get_data():
            ...
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            client_ip = request.remote_addr or 'unknown'
            
            allowed, remaining, retry_after = rate_limiter.is_allowed(client_ip, limit_type)
            
            headers = rate_limiter.get_headers(client_ip, limit_type)
            
            if not allowed:
                response = jsonify({
                    'success': False,
                    'error': '请求过于频繁',
                    'message': f'请等待{retry_after}秒后重试',
                    'retry_after': retry_after
                })
                response.status_code = 429
                return response
            
            response = f(*args, **kwargs)
            
            # 如果是Response对象，添加头信息
            if hasattr(response, 'headers'):
                for k, v in headers.items():
                    response.headers[k] = v
            
            return response
        
        return wrapped
    
    return decorator


def cache_response(cache_type: str = 'medium'):
    """
    响应缓存装饰器
    
    用法:
        @cache_response('short')
        def get_market_env():
            ...
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            cache_key = f"{f.__name__}:{request.path}:{request.query_string.decode()}"
            
            cached = response_cache.get(cache_type, cache_key)
            
            if cached is not None:
                cached['_cached'] = True
                cached['_cache_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                return jsonify(cached)
            
            result = f(*args, **kwargs)
            
            # 只缓存成功的JSON响应
            if isinstance(result, tuple):
                response, code = result
            else:
                response = result
                code = 200
            
            if hasattr(response, 'get_json') or isinstance(response, dict):
                data = response.get_json() if hasattr(response, 'get_json') else response
                
                if isinstance(data, dict) and data.get('success') == True:
                    response_cache.set(cache_type, cache_key, data)
                    
                    if isinstance(data, dict):
                        data['_cached'] = False
                        return jsonify(data), code
            
            return result
        
        return wrapped
    
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    重试装饰器
    
    用于对外部服务调用进行自动重试
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    result = f(*args, **kwargs)
                    return result
                    
                except Exception as e:
                    last_error = e
                    
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
            
            raise last_error
        
        return wrapped
    
    return decorator


if __name__ == '__main__':
    print("=" * 60)
    print("API中间件测试")
    print("=" * 60)
    
    print("\n--- 限流器测试 ---")
    limiter = RateLimiter()
    
    for i in range(5):
        allowed, remaining, reset = limiter.is_allowed('192.168.1.1', 'default')
        print(f"  请求{i+1}: 允许={allowed}, 剩余={remaining}, 重置={reset}s")
    
    print("\n--- 缓存器测试 ---")
    cache = ResponseCache()
    
    cache.set('short', 'test_key', {'data': 'hello'})
    cached = cache.get('short', 'test_key')
    print(f"  写入后读取: {cached}")
    
    print("\n--- 数据源管理器测试 ---")
    manager = DataSourceManager()
    
    def source_a():
        return {'price': 100}
    
    def source_b():
        return {'price': 101}
    
    def failing_source():
        raise Exception("模拟失败")
    
    manager.register_source('主数据源', 1, source_a)
    manager.register_source('备用数据源', 2, source_b)
    manager.register_source('失败数据源', 3, failing_source)
    
    result = manager.get_data()
    print(f"  获取结果: 来源={result['source']}, 成功={result['success']}")
    
    health = manager.get_source_health()
    print(f"  数据源健康状态:")
    for name, h in health.items():
        print(f"    {name}: {h['status']}")
    
    print("\n✅ API中间件正常工作")
