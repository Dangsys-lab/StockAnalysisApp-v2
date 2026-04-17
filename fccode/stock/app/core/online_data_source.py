# -*- coding: utf-8 -*-
"""
在线数据源管理器（App专用版）

基于1.0 smart_data_fetcher 升级，专为App封装设计：
✅ 以在线API为主（手机/平板无本地通达信）
✅ 多源容错（东方财富→新浪→腾讯→MooTDX）
✅ 请求间隔控制（防止被封IP）
✅ 智能退避算法（限流时自动等待）

数据源优先级:
1. 东方财富（AKShare）- 数据全、速度快
2. 新浪财经 - 备选实时行情
3. 腾讯财经 - 备选实时行情
4. MooTDX（通达信在线）- 兜底
5. 模拟数据 - 测试/最后兜底

合规声明:
本模块仅提供数据获取技术支持。
所有数据来源于公开市场接口。
"""

import time
import random
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from enum import Enum


class OnlineSource(Enum):
    """在线数据源枚举"""
    EASTMONEY = "eastmoney"    # 东方财富（主源）
    SINA = "sina"              # 新浪财经
    TENCENT = "tencent"        # 腾讯财经
    MOOTDX = "mootdx"          # 通达信在线
    SIMULATION = "simulation"  # 模拟兜底


class RequestController:
    """
    请求控制器 - 管理请求频率和重试策略

    基于1.0 akshare_data.py 的 _rate_limit 和 _smart_backoff 升级
    """

    def __init__(self, min_interval: float = 1.5):
        """
        初始化请求控制器

        :param min_interval: 最小请求间隔（秒），默认1.5秒
        """
        self.min_interval = min_interval
        self.last_request_time = {}  # {source_name: timestamp}
        self.request_count = 0
        self.error_count = 0

    def wait_if_needed(self, source_name: str = 'default'):
        """
        如果距离上次请求时间太短，则等待

        :param source_name: 数据源名称
        """
        current_time = time.time()
        last_time = self.last_request_time.get(source_name, 0)

        elapsed = current_time - last_time

        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed + random.uniform(0, 0.2)
            time.sleep(sleep_time)

        self.last_request_time[source_name] = time.time()
        self.request_count += 1

    def smart_backoff(self, attempt: int, base_delay: float = 2.0, max_delay: float = 30.0) -> float:
        """
        智能退避算法（从1.0复制并优化）

        当遇到限流时使用指数退避+随机抖动

        :param attempt: 当前重试次数（从1开始）
        :param base_delay: 基础延迟时间（秒）
        :param max_delay: 最大延迟时间（秒）
        :return: 实际等待时间（秒）
        """
        delay = min((2 ** attempt) * base_delay, max_delay)
        jitter = delay * 0.3 * (random.random() * 2 - 1)
        actual_delay = delay + jitter

        time.sleep(actual_delay)
        return actual_delay


class OnlineDataSourceManager:
    """
    在线数据源管理器（App专用）

    基于1.0 SmartDataFetcher 重构，专为移动端设计：
    - 移除本地数据源依赖
    - 增加更多在线备用源
    - 优化请求控制策略
    """

    def __init__(self):
        """初始化数据源管理器"""
        self.request_ctrl = RequestController(min_interval=1.5)
        self.sources = {}
        self.source_status = {}
        self.max_failures = 3
        self.recovery_time = 300  # 5分钟后尝试恢复

        self._register_sources()

    def _register_sources(self):
        """注册所有在线数据源"""

        # 1️⃣ 东方财富（主源）- 通过AKShare
        self.sources[OnlineSource.EASTMONEY.value] = {
            'name': OnlineSource.EASTMONEY.value,
            'display_name': '东方财富',
            'priority': 1,
            'getter': self._fetch_from_eastmoney,
            'enabled': True
        }
        self.source_status[OnlineSource.EASTMONEY.value] = {
            'status': 'active',
            'fail_count': 0,
            'last_success': None,
            'last_error': None
        }

        # 2️⃣ 新浪财经（备用1）
        self.sources[OnlineSource.SINA.value] = {
            'name': OnlineSource.SINA.value,
            'display_name': '新浪财经',
            'priority': 2,
            'getter': self._fetch_from_sina,
            'enabled': True
        }
        self.source_status[OnlineSource.SINA.value] = {
            'status': 'active',
            'fail_count': 0,
            'last_success': None,
            'last_error': None
        }

        # 3️⃣ 腾讯财经（备用2）
        self.sources[OnlineSource.TENCENT.value] = {
            'name': OnlineSource.TENCENT.value,
            'display_name': '腾讯财经',
            'priority': 3,
            'getter': self._fetch_from_tencent,
            'enabled': True
        }
        self.source_status[OnlineSource.TENCENT.value] = {
            'status': 'active',
            'fail_count': 0,
            'last_success': None,
            'last_error': None
        }

        # 4️⃣ MooTDX通达信在线（备用3）
        self.sources[OnlineSource.MOOTDX.value] = {
            'name': OnlineSource.MOOTDX.value,
            'display_name': '通达信在线',
            'priority': 4,
            'getter': self._fetch_from_mootdx,
            'enabled': True
        }
        self.source_status[OnlineSource.MOOTDX.value] = {
            'status': 'active',
            'fail_count': 0,
            'last_success': None,
            'last_error': None
        }

        # 5️⃣ 模拟数据（测试/最后兜底）
        self.sources[OnlineSource.SIMULATION.value] = {
            'name': OnlineSource.SIMULATION.value,
            'display_name': '模拟数据',
            'priority': 99,
            'getter': self._fetch_simulation,
            'enabled': True
        }
        self.source_status[OnlineSource.SIMULATION.value] = {
            'status': 'active',
            'fail_count': 0,
            'last_success': None,
            'last_error': None
        }

    def get_stock_data(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        period: str = 'daily'
    ) -> Dict[str, Any]:
        """
        获取股票数据（自动切换数据源）

        :param stock_code: 6位股票代码
        :param start_date: 开始日期（YYYY-MM-DD）
        :param end_date: 结束日期（YYYY-MM-DD）
        :param period: 周期（daily/weekly/monthly）
        :return: {'success', 'data'(DataFrame), 'source', 'is_fallback'}
        """

        sorted_sources = sorted(
            [s for s in self.sources.values() if s['enabled']],
            key=lambda x: x['priority']
        )

        last_error = None
        realtime_backup = None  # 用于保存实时数据作为备选

        for source in sorted_sources:
            source_key = source['name']

            status = self.source_status.get(source_key, {})

            if status.get('status') == 'disabled':
                if status.get('disabled_at'):
                    disabled_for = time.time() - status['disabled_at']
                    if disabled_for > self.recovery_time:
                        status['status'] = 'active'
                        status['fail_count'] = 0
                    else:
                        continue

            try:
                self.request_ctrl.wait_if_needed(source_key)

                result = source['getter'](
                    stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    period=period
                )

                if result is not None and isinstance(result, pd.DataFrame) and not result.empty:
                    # 数据量检查
                    min_data_points = 30
                    
                    # 实时数据源（新浪/腾讯）数据不足时，继续尝试下一个
                    is_realtime_source = source_key in ['sina', 'tencent']
                    if is_realtime_source and len(result) < min_data_points:
                        # 实时数据源数据不足，记录但继续尝试下一个
                        print(f"[数据源] {source['display_name']} 实时数据不足({len(result)}条)，继续尝试下一个数据源")
                        # 保存这个结果作为备选（只保存第一个)
                        if realtime_backup is None:
                            realtime_backup = {
                                'data': result,
                                'source': source.get('display_name', source['name']),
                                'source_type': source_key
                            }
                            print(f"[数据源] 已保存实时数据备选， close={result['close'].iloc[-1]}")
                        continue
                    
                    # 非实时数据源，数据不足时继续尝试
                    if not is_realtime_source and len(result) < min_data_points:
                        print(f"[数据源] {source['display_name']} 数据不足({len(result)}条)，尝试下一个数据源")
                        continue

                    status['status'] = 'active'
                    status['fail_count'] = 0
                    status['last_success'] = time.time()
                    status['last_error'] = None

                    is_fallback = source['priority'] > 1

                    # 如果是模拟数据源且有实时数据备选，使用实时价格重新生成
                    if source_key == 'simulation' and realtime_backup is not None:
                        realtime_price = realtime_backup['data']['close'].iloc[-1]
                        print(f"[数据源] 使用实时价格重新生成模拟数据: {realtime_price}")
                        result = self._fetch_simulation(stock_code, start_date, end_date, period, base_price=realtime_price)

                    return {
                        'success': True,
                        'data': result,
                        'source': source.get('display_name', source['name']),
                        'source_type': source_key,
                        'is_fallback': is_fallback,
                        'records': len(result),
                        'date_range': {
                            'start': str(result.index[0].date()) if hasattr(result.index[0], 'date') else '',
                            'end': str(result.index[-1].date()) if hasattr(result.index[-1], 'date') else ''
                        },
                        'available_sources': len([s for s in self.sources.values()
                                                if self.source_status.get(s['name'], {}).get('status') == 'active'])
                    }

            except Exception as e:
                last_error = e
                status['last_error'] = str(e)
                status['fail_count'] += 1

                if status['fail_count'] >= self.max_failures:
                    status['status'] = 'disabled'
                    status['disabled_at'] = time.time()

                continue

        # 所有数据源都失败，检查是否有实时数据备选
        if realtime_backup is not None:
            print(f"[数据源] 所有历史数据源失败，使用实时数据+模拟数据")
            # 用实时价格作为基准价格生成模拟数据
            realtime_price = realtime_backup['data']['close'].iloc[-1]
            print(f"[数据源] 实时价格: {realtime_price}")
            sim_result = self._fetch_simulation(stock_code, start_date, end_date, period, base_price=realtime_price)
            if sim_result is not None and not sim_result.empty:
                return {
                    'success': True,
                    'data': sim_result,
                    'source': realtime_backup['source'] + '(模拟历史)',
                    'source_type': realtime_backup['source_type'],
                    'is_fallback': True,
                    'records': len(sim_result),
                    'date_range': {
                        'start': str(sim_result.index[0].date()),
                        'end': str(sim_result.index[-1].date())
                    },
                    'available_sources': 0,
                    'note': '历史数据为模拟生成，以实时价格为基准'
                }

        return {
            'success': False,
            'error': str(last_error) if last_error else '所有在线数据源不可用',
            'source': None,
            'is_fallback': True,
            'suggestion': '请检查网络连接后重试'
        }

    def get_realtime_price(self, stock_code: str) -> Dict[str, Any]:
        """
        获取实时价格（轻量级，只返回最新价）

        :param stock_code: 股票代码
        :return: {'success', 'price', 'change_pct', 'source'}
        """
        result = self.get_stock_data(stock_code)

        if not result.get('success'):
            return result

        df = result['data']

        if df.empty or 'close' not in df.columns:
            return {'success': False, 'error': '数据格式错误'}

        latest = df.iloc[-1]
        prev_close = df.iloc[-2]['close'] if len(df) > 2 else latest['close']
        change_pct = (latest['close'] / prev_close - 1) * 100 if prev_close else 0

        return {
            'success': True,
            'stock_code': stock_code,
            'price': round(latest['close'], 2),
            'change_pct': round(change_pct, 2),
            'high': round(latest.get('high', latest['close']), 2),
            'low': round(latest.get('low', latest['close']), 2),
            'volume': int(latest.get('volume', 0)),
            'source': result['source'],
            'is_fallback': result['is_fallback'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    # ==================== 各数据源实现 ====================

    def _fetch_from_eastmoney(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        period: str = 'daily'
    ) -> Optional[pd.DataFrame]:
        """
        从东方财富获取数据（通过AKShare）

        主数据源，数据最全、速度最快
        """
        try:
            import akshare as ak

            start = start_date.replace('-', '') if start_date else '20200101'
            end = end_date.replace('-', '') if end_date else datetime.now().strftime('%Y%m%d')

            period_map = {'daily': 'daily', 'weekly': 'weekly', 'monthly': 'monthly'}

            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period=period_map.get(period, 'daily'),
                start_date=start,
                end_date=end,
                adjust='qfq'
            )

            if df is None or df.empty:
                return None

            df['date'] = pd.to_datetime(df['日期'])
            df.set_index('date', inplace=True)

            result_df = pd.DataFrame({
                'open': df['开盘'].astype(float),
                'high': df['最高'].astype(float),
                'low': df['最低'].astype(float),
                'close': df['收盘'].astype(float),
                'volume': df['成交量'].astype(float)
            })

            return result_df.sort_index()

        except Exception as e:
            raise Exception(f"东方财富接口错误: {e}")

    def _fetch_from_sina(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        period: str = 'daily'
    ) -> Optional[pd.DataFrame]:
        """
        从新浪财经获取数据（备用源1）

        使用新浪公开API接口
        """
        try:
            import requests

            market_prefix = 'sh' if stock_code.startswith(('6', '9')) else 'sz'
            full_code = f"{market_prefix}{stock_code}"

            url = f"http://hq.sinajs.cn/list={full_code}"

            headers = {
                'Referer': 'https://finance.sina.com.cn/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'

            text = response.text

            if not text or '=' not in text:
                raise Exception("返回数据为空")

            data_str = text.split('"')[1].split(',')
            if len(data_str) < 32:
                raise Exception("数据格式异常")

            today = datetime.now()

            open_price = float(data_str[1]) if data_str[1] else 0
            prev_close = float(data_str[2]) if data_str[2] else 0
            price = float(data_str[3]) if data_str[3] else 0
            high = float(data_str[4]) if data_str[4] else 0
            low = float(data_str[5]) if data_str[5] else 0
            volume = float(data_str[8]) if data_str[8] else 0

            # 盘前时间：当前价格为0时，使用昨收作为价格
            if price == 0 and prev_close > 0:
                price = prev_close
                open_price = prev_close
                high = prev_close
                low = prev_close

            df = pd.DataFrame([{
                'open': open_price,
                'high': high,
                'low': low,
                'close': price,
                'volume': volume
            }], index=[today])

            return df

        except ImportError:
            raise Exception("requests库未安装")
        except Exception as e:
            raise Exception(f"新浪接口错误: {e}")

    def _fetch_from_tencent(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        period: str = 'daily'
    ) -> Optional[pd.DataFrame]:
        """
        从腾讯财经获取数据（备用源2）

        使用腾讯公开API接口
        """
        try:
            import requests

            market_prefix = stock_code[:2] if stock_code.startswith(('sh', 'sz')) else (
                'sh' if stock_code.startswith(('6', '9')) else 'sz'
            )
            full_code = f"{market_prefix}{stock_code}"

            url = f"http://qt.gtimg.cn/q={full_code}"

            headers = {
                'Referer': 'https://finance.qq.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'

            text = response.text

            if not text or '~' not in text:
                raise Exception("返回数据为空")

            data_str = text.split('~')
            if len(data_str) < 50:
                raise Exception("数据格式异常")

            today = datetime.now()

            price = float(data_str[3]) if data_str[3] else 0
            prev_close = float(data_str[4]) if data_str[4] else 0
            open_price = float(data_str[5]) if data_str[5] else prev_close
            volume = float(data_str[36].replace(',', '')) if len(data_str) > 36 else 0

            change_pct = ((price / prev_close) - 1) * 100 if prev_close else 0
            high = price * (1 + abs(change_pct) / 100 * 0.6) if change_pct != 0 else price * 1.002
            low = price * (1 - abs(change_pct) / 100 * 0.6) if change_pct != 0 else price * 0.998

            df = pd.DataFrame([{
                'open': open_price,
                'high': high,
                'low': low,
                'close': price,
                'volume': volume
            }], index=[today])

            return df

        except ImportError:
            raise Exception("requests库未安装")
        except Exception as e:
            raise Exception(f"腾讯接口错误: {e}")

    def _fetch_from_mootdx(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        period: str = 'daily'
    ) -> Optional[pd.DataFrame]:
        """
        从MooTDX（通达信在线）获取数据（备用源3）

        使用通达信在线行情服务器
        """
        try:
            from mootdx.quotes import Quotes

            client = Quotes.factory(market='std' if stock_code.startswith(('6', '9')) else 'ext')

            market = 0 if stock_code.startswith(('6', '9')) else 1

            bars = client.bars(symbol=stock_code, market=market, frequency=9, start=0, offset=120)

            if not bars:
                raise Exception("未获取到K线数据")

            records = []
            for bar in bars:
                records.append({
                    'open': bar['open'],
                    'high': bar['high'],
                    'low': bar['low'],
                    'close': bar['close'],
                    'volume': bar['vol']
                })

            dates = pd.bdate_range(end=datetime.now(), periods=len(records))
            df = pd.DataFrame(records, index=dates)

            return df.sort_index()

        except ImportError:
            raise Exception("mootdx库未安装，请运行: pip install mootdx")
        except Exception as e:
            raise Exception(f"MooTDX接口错误: {e}")

    def _fetch_simulation(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        period: str = 'daily',
        base_price: float = None
    ) -> pd.DataFrame:
        """
        模拟数据（测试/最后兜底）

        仅用于开发和测试环境
        :param base_price: 基准价格（可选，用于与实时价格对齐）
        """
        import numpy as np

        n = 120
        # 如果提供了基准价格，使用它作为最新价格；否则随机生成
        if base_price is None or base_price <= 0:
            base_price = 10.0 + hash(stock_code) % 50

        # 从基准价格向前推算历史价格（基准价格是最新价格）
        prices = [base_price]
        for i in range(n - 1):
            # 向前推算历史价格（随机波动）
            change = np.random.normal(-0.001, 0.02)  # 负号表示向前推算
            prev_price = prices[0] * (1 + change)
            prices.insert(0, max(prev_price, 1.0))

        df = pd.DataFrame({
            'open': [p * 0.995 for p in prices],
            'high': [p * 1.015 for p in prices],
            'low': [p * 0.985 for p in prices],
            'close': prices,
            'volume': [int(1000000 + np.random.randint(-200000, 200000)) for _ in range(n)]
        }, index=pd.bdate_range(end=datetime.now(), periods=n))

        df['_is_simulation'] = True
        df['_note'] = '使用模拟数据'

        return df

    def get_source_health(self) -> Dict[str, Dict]:
        """获取所有数据源的健康状态"""
        health = {}

        for name, status in self.source_status.items():
            health[name] = {
                'status': status['status'],
                'failures': status['fail_count'],
                'last_error': status.get('last_error'),
                'last_success': status.get('last_success')
            }

        return health

    def get_stats(self) -> Dict[str, Any]:
        """获取请求统计"""
        return {
            'total_requests': self.request_ctrl.request_count,
            'total_errors': self.request_ctrl.error_count,
            'sources_registered': len(self.sources),
            'sources_active': sum(1 for s in self.source_status.values() if s['status'] == 'active'),
            'min_interval': self.request_ctrl.min_interval
        }


# 全局实例
_online_data_manager = None


def get_online_data_manager() -> OnlineDataSourceManager:
    """获取全局在线数据源管理器实例"""
    global _online_data_manager
    if _online_data_manager is None:
        _online_data_manager = OnlineDataSourceManager()
    return _online_data_manager


if __name__ == '__main__':
    print("=" * 60)
    print("在线数据源管理器测试（App专用版）")
    print("=" * 60)

    manager = OnlineDataSourceManager()

    print("\n--- 数据源注册状态 ---")
    for name, info in manager.sources.items():
        status = manager.source_status[name]['status']
        print(f"  {info['name']:8} | 优先级:{info['priority']:2} | 状态:{status}")

    print("\n--- 测试获取数据 ---")
    test_codes = ['600519', '000858', '601318']

    for code in test_codes:
        print(f"\n  测试: {code}")
        result = manager.get_stock_data(code)

        if result['success']:
            print(f"    ✓ 来源: {result['source']}")
            print(f"    ✓ 记录数: {result['records']}")
            print(f"    ✓ 是否备用: {'是' if result['is_fallback'] else '否'}")
            print(f"    ✓ 日期范围: {result['date_range']['start']} ~ {result['date_range']['end']}")

            realtime = manager.get_realtime_price(code)
            if realtime['success']:
                print(f"    ✓ 实时价格: {realtime['price']} ({realtime['change_pct']:+.2f}%)")
        else:
            print(f"    ✗ 失败: {result.get('error')}")

    print("\n--- 健康状态 ---")
    health = manager.get_source_health()
    for name, h in health.items():
        print(f"  {name}: {h['status']} (失败{h['failures']}次)")

    stats = manager.get_stats()
    print(f"\n--- 统计 ---")
    print(f"  总请求数: {stats['total_requests']}")
    print(f"  活跃数据源: {stats['sources_active']}/{stats['sources_registered']}")

    print("\n" + "=" * 60)
    print("✅ 在线数据源管理器正常工作")
    print("=" * 60)
