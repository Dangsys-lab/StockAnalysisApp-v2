# -*- coding: utf-8 -*-
"""
智能数据获取器 - 多数据源自动切换

根据数据源可用性和数据类型，自动选择最优数据源
优先使用本地数据源（mootdx），失败时自动切换到在线数据源（AKShare）

符合项目规范：
- 只返回数据（dict/list），不返回 HTTP 响应
- 完整的异常处理
- 所有函数有文档字符串
- 使用类型注解

架构设计：
1. 估值数据（PE、PB、ROE）→ 优先 mootdx（本地）
2. 资金流向（北向资金、主力流入）→ 必须 AKShare（在线）
3. 成长数据（营收增长率、净利润增长率）→ 优先 mootdx，失败切 AKShare
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

# 导入各个数据源
try:
    from mootdx_data import MootdxDataFetcher
    MOOTDX_AVAILABLE = True
except ImportError:
    MOOTDX_AVAILABLE = False
    MootdxDataFetcher = None

try:
    from pytdx_data import PytdxDataFetcher
    PYTDX_AVAILABLE = True
except ImportError:
    PYTDX_AVAILABLE = False
    PytdxDataFetcher = None

try:
    from akshare_data import AKShareDataFetcher
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    AKShareDataFetcher = None


class DataSourceType(Enum):
    """数据源类型枚举"""
    LOCAL = "local"  # 本地数据源
    ONLINE = "online"  # 在线数据源


class DataSourcePriority(Enum):
    """数据源优先级"""
    MOOTDX = 1  # 最高优先级（本地）
    PYTDX = 2   # 中等优先级（本地/在线）
    AKSHARE = 3  # 最低优先级（在线）


class SmartDataFetcher:
    """
    智能数据获取器
    
    自动管理多个数据源，根据数据类型和可用性选择最优数据源
    支持故障自动切换、性能监控、缓存优化
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        初始化智能数据获取器
        
        Args:
            cache_enabled: 是否启用缓存，默认 True
        """
        self.cache_enabled = cache_enabled
        self.cache = {}
        self.cache_timestamp = {}
        
        # 缓存有效期配置（秒）
        self.cache_ttl = {
            'valuation': 300,        # 估值数据 5 分钟
            'financials': 3600,      # 财务数据 1 小时
            'capital_flow': 60,      # 资金流向 1 分钟
            'comprehensive': 300,    # 综合数据 5 分钟
        }
        
        # 初始化数据源
        self.data_sources = {}
        self.data_source_status = {}
        
        self._init_data_sources()
        
        # 性能统计
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'local_success': 0,
            'online_success': 0,
            'failures': 0
        }
    
    def _init_data_sources(self):
        """初始化所有数据源"""
        # 1. 初始化 mootdx（本地数据源 - 最高优先级）
        if MOOTDX_AVAILABLE and MootdxDataFetcher:
            try:
                self.data_sources['mootdx'] = MootdxDataFetcher()
                self.data_source_status['mootdx'] = {
                    'available': True,
                    'type': DataSourceType.LOCAL,
                    'priority': DataSourcePriority.MOOTDX
                }
                print("✓ mootdx 数据源初始化成功")
            except Exception as e:
                print(f"✗ mootdx 数据源初始化失败：{e}")
                self.data_source_status['mootdx'] = {'available': False}
        else:
            print("⚠ mootdx 库未安装，跳过")
            self.data_source_status['mootdx'] = {'available': False}
        
        # 2. 初始化 pytdx（本地/在线数据源 - 中等优先级）
        if PYTDX_AVAILABLE and PytdxDataFetcher:
            try:
                # 优先使用在线模式（本地模式需要配置数据目录）
                self.data_sources['pytdx'] = PytdxDataFetcher(mode='online')
                self.data_source_status['pytdx'] = {
                    'available': True,
                    'type': DataSourceType.ONLINE,
                    'priority': DataSourcePriority.PYTDX
                }
                print("✓ pytdx 数据源初始化成功（在线模式）")
            except Exception as e:
                print(f"✗ pytdx 数据源初始化失败：{e}")
                self.data_source_status['pytdx'] = {'available': False}
        else:
            print("⚠ pytdx 库未安装，跳过")
            self.data_source_status['pytdx'] = {'available': False}
        
        # 3. 初始化 AKShare（在线数据源 - 备用）
        if AKSHARE_AVAILABLE and AKShareDataFetcher:
            try:
                # AKShare 限流严格，设置较大的请求间隔
                self.data_sources['akshare'] = AKShareDataFetcher(request_interval=3.0)
                self.data_source_status['akshare'] = {
                    'available': True,
                    'type': DataSourceType.ONLINE,
                    'priority': DataSourcePriority.AKSHARE
                }
                print("✓ AKShare 数据源初始化成功")
            except Exception as e:
                print(f"✗ AKShare 数据源初始化失败：{e}")
                self.data_source_status['akshare'] = {'available': False}
        else:
            print("⚠ AKShare 库未安装，跳过")
            self.data_source_status['akshare'] = {'available': False}
    
    def _get_from_cache(self, key: str, data_type: str) -> Optional[Dict]:
        """
        从缓存获取数据
        
        Args:
            key: 缓存键（如股票代码）
            data_type: 数据类型
            
        Returns:
            Optional[Dict]: 缓存的数据，过期或不存在返回 None
        """
        if not self.cache_enabled:
            return None
        
        if key not in self.cache:
            return None
        
        # 检查缓存是否过期
        if key in self.cache_timestamp:
            timestamp = self.cache_timestamp[key]
            ttl = self.cache_ttl.get(data_type, 300)
            
            if (datetime.now().timestamp() - timestamp) > ttl:
                # 缓存过期
                del self.cache[key]
                del self.cache_timestamp[key]
                return None
        
        self.stats['cache_hits'] += 1
        return self.cache[key]
    
    def _save_to_cache(self, key: str, data: Dict, data_type: str):
        """
        保存数据到缓存
        
        Args:
            key: 缓存键
            data: 数据
            data_type: 数据类型
        """
        if not self.cache_enabled:
            return
        
        self.cache[key] = data
        self.cache_timestamp[key] = datetime.now().timestamp()
    
    def _try_data_sources(
        self,
        method_name: str,
        code: str,
        data_type: str,
        cache_key: str = None
    ) -> Optional[Dict]:
        """
        尝试多个数据源获取数据（按优先级）
        
        Args:
            method_name: 方法名称
            code: 股票代码
            data_type: 数据类型（用于缓存）
            cache_key: 缓存键，默认使用 code
            
        Returns:
            Optional[Dict]: 获取到的数据
        """
        if not cache_key:
            cache_key = code
        
        # 1. 先尝试从缓存获取
        cached = self._get_from_cache(cache_key, data_type)
        if cached:
            return cached
        
        self.stats['total_requests'] += 1
        
        # 2. 按优先级尝试数据源
        sorted_sources = sorted(
            [
                (name, status) 
                for name, status in self.data_source_status.items() 
                if status.get('available', False)
            ],
            key=lambda x: x[1]['priority'].value
        )
        
        last_error = None
        
        for source_name, source_status in sorted_sources:
            try:
                source = self.data_sources[source_name]
                
                if not hasattr(source, method_name):
                    print(f"⚠ {source_name} 不支持方法 {method_name}")
                    continue
                
                # 调用方法获取数据
                method = getattr(source, method_name)
                result = method(code)
                
                if result:
                    # 成功获取
                    if source_status['type'] == DataSourceType.LOCAL:
                        self.stats['local_success'] += 1
                    else:
                        self.stats['online_success'] += 1
                    
                    # 保存到缓存
                    self._save_to_cache(cache_key, result, data_type)
                    
                    return result
                
            except Exception as e:
                last_error = e
                print(f"⚠ {source_name}.{method_name}() 失败：{e}")
                continue
        
        # 所有数据源都失败
        self.stats['failures'] += 1
        print(f"✗ 所有数据源获取失败：{method_name}({code})")
        
        if last_error:
            print(f"  最后错误：{last_error}")
        
        return None
    
    def get_comprehensive_fundamentals(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取综合基本面数据（智能切换）
        
        策略：
        1. 估值数据（PE、PB）→ 优先 mootdx
        2. 财务数据（ROE、增长率）→ 优先 mootdx
        3. 资金流向 → 必须 AKShare
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 综合基本面数据
        """
        result = {
            'code': code,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_sources_used': []
        }
        
        # 1. 获取估值和财务数据（优先本地）
        valuation_data = self._try_data_sources(
            method_name='get_comprehensive_fundamentals',
            code=code,
            data_type='comprehensive',
            cache_key=f"valuation:{code}"
        )
        
        if valuation_data:
            result.update(valuation_data)
            result['data_sources_used'].append('valuation')
        
        # 2. 获取资金流向数据（必须 AKShare）
        if AKSHARE_AVAILABLE and AKShareDataFetcher:
            try:
                ak_fetcher = self.data_sources.get('akshare')
                if ak_fetcher:
                    # 获取资金流向
                    capital_flow = ak_fetcher.get_capital_flow(code)
                    
                    if capital_flow:
                        result.update({
                            'north_flow': capital_flow.get('north_flow', 0),
                            'main_force_net': capital_flow.get('main_force_net', 0),
                            'large_order_net': capital_flow.get('large_order_net', 0),
                            'flow_ratio': capital_flow.get('flow_ratio', 0),
                        })
                        result['data_sources_used'].append('capital_flow_akshare')
                    
                    # 获取北向资金持股
                    north_hold = ak_fetcher.get_north_capital_flow(code)
                    
                    if north_hold:
                        result.update({
                            'north_hold_ratio': north_hold.get('north_hold_ratio', 0),
                            'north_hold_value': north_hold.get('north_hold_value', 0),
                        })
                        result['data_sources_used'].append('north_hold_akshare')
                    
            except Exception as e:
                print(f"获取资金流向数据失败：{e}")
        
        # 如果没有使用任何数据源，返回 None
        if not result['data_sources_used']:
            return None
        
        return result
    
    def get_valuation_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取估值数据（PE、PB、ROE 等）
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 估值数据
        """
        return self._try_data_sources(
            method_name='get_comprehensive_fundamentals',
            code=code,
            data_type='valuation'
        )
    
    def get_capital_flow(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取资金流向数据
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 资金流向数据
        """
        if not AKSHARE_AVAILABLE or 'akshare' not in self.data_sources:
            print("⚠ 无可用数据源获取资金流向数据")
            return None
        
        try:
            ak_fetcher = self.data_sources['akshare']
            return ak_fetcher.get_capital_flow(code)
        except Exception as e:
            print(f"获取资金流向失败：{e}")
            return None
    
    def get_realtime_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情数据
        
        Args:
            code: 6 位股票代码
            
        Returns:
            Dict: 实时行情数据
        """
        return self._try_data_sources(
            method_name='get_realtime_data',
            code=code,
            data_type='realtime'
        )
    
    def get_historical_data(
        self,
        code: str,
        period: str = 'daily'
    ) -> Optional[Dict[str, Any]]:
        """
        获取历史 K 线数据
        
        Args:
            code: 6 位股票代码
            period: 周期，'daily'/'weekly'/'monthly'
            
        Returns:
            Dict: 历史 K 线数据
        """
        return self._try_data_sources(
            method_name='get_historical_data',
            code=code,
            data_type='historical',
            cache_key=f"historical:{code}:{period}"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取数据获取器状态
        
        Returns:
            Dict: 状态信息
        """
        return {
            'data_sources': {
                name: {
                    'available': status.get('available', False),
                    'type': status.get('type', DataSourceType.ONLINE).value,
                    'priority': status.get('priority', DataSourcePriority.AKSHARE).name
                }
                for name, status in self.data_source_status.items()
            },
            'stats': self.stats,
            'cache_enabled': self.cache_enabled,
            'cache_size': len(self.cache)
        }
    
    def clear_cache(self):
        """清除所有缓存"""
        self.cache.clear()
        self.cache_timestamp.clear()
        print("✓ 缓存已清除")


# 全局实例
_global_smart_fetcher = None


def get_smart_fetcher(cache_enabled: bool = True) -> SmartDataFetcher:
    """
    获取全局智能数据获取器实例
    
    Args:
        cache_enabled: 是否启用缓存
        
    Returns:
        SmartDataFetcher: 智能数据获取器
    """
    global _global_smart_fetcher
    if _global_smart_fetcher is None:
        _global_smart_fetcher = SmartDataFetcher(cache_enabled=cache_enabled)
    return _global_smart_fetcher


# 便捷函数

def get_comprehensive_fundamentals(code: str) -> Optional[Dict[str, Any]]:
    """获取综合基本面数据（便捷函数）"""
    return get_smart_fetcher().get_comprehensive_fundamentals(code)


def get_valuation_data(code: str) -> Optional[Dict[str, Any]]:
    """获取估值数据（便捷函数）"""
    return get_smart_fetcher().get_valuation_data(code)


def get_capital_flow(code: str) -> Optional[Dict[str, Any]]:
    """获取资金流向数据（便捷函数）"""
    return get_smart_fetcher().get_capital_flow(code)


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("智能数据获取器测试")
    print("=" * 60)
    
    # 创建智能获取器
    fetcher = SmartDataFetcher(cache_enabled=True)
    
    # 测试 1: 获取综合基本面数据
    print("\n1. 测试获取综合基本面数据（600519 贵州茅台）")
    result = fetcher.get_comprehensive_fundamentals("600519")
    
    if result:
        print(f"股票代码：{result['code']}")
        print(f"PE: {result.get('pe_ratio', 'N/A')}")
        print(f"PB: {result.get('pb_ratio', 'N/A')}")
        print(f"ROE: {result.get('roe', 'N/A')}%")
        print(f"营收增长率：{result.get('revenue_growth', 'N/A')}%")
        print(f"北向资金：{result.get('north_flow', 'N/A')} 万元")
        print(f"主力净流入：{result.get('main_force_net', 'N/A')} 万元")
        print(f"使用的数据源：{', '.join(result.get('data_sources_used', []))}")
    else:
        print("获取失败")
    
    # 测试 2: 获取实时数据
    print("\n2. 测试获取实时数据")
    realtime = fetcher.get_realtime_data("600519")
    if realtime:
        print(f"当前价格：{realtime.get('current_price', 'N/A')}")
        print(f"涨跌幅：{realtime.get('change_pct', 'N/A')}%")
    else:
        print("获取失败")
    
    # 测试 3: 获取状态
    print("\n3. 获取数据获取器状态")
    status = fetcher.get_status()
    
    print("数据源状态:")
    for name, info in status['data_sources'].items():
        available = "✓" if info['available'] else "✗"
        print(f"  {available} {name}: {info['type']} (优先级：{info['priority']})")
    
    print(f"\n统计信息:")
    print(f"  总请求：{status['stats']['total_requests']}")
    print(f"  缓存命中：{status['stats']['cache_hits']}")
    print(f"  本地成功：{status['stats']['local_success']}")
    print(f"  在线成功：{status['stats']['online_success']}")
    print(f"  失败次数：{status['stats']['failures']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
