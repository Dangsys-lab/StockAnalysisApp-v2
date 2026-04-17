# -*- coding: utf-8 -*-
"""
在线数据源管理器 - 3.0版本

功能:
- 多源容错（东方财富→新浪→腾讯→MooTDX→模拟）
- 请求间隔控制（防止被封IP）
- 智能退避算法

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
from typing import Dict, Any, Optional, List
from enum import Enum


class OnlineSource(Enum):
    """在线数据源枚举"""
    EASTMONEY = "eastmoney"
    SINA = "sina"
    TENCENT = "tencent"
    MOOTDX = "mootdx"
    SIMULATION = "simulation"


class RequestController:
    """
    请求控制器 - 管理请求频率和重试策略
    """

    def __init__(self, min_interval: float = 1.5):
        """
        初始化请求控制器

        :param min_interval: 最小请求间隔（秒），默认1.5秒
        """
        self.min_interval = min_interval
        self.last_request_time = {}
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
        智能退避算法

        :param attempt: 当前重试次数
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
    在线数据源管理器
    """

    def __init__(self):
        """初始化数据源管理器"""
        self.request_ctrl = RequestController(min_interval=1.5)
        self.sources = {}
        self.source_status = {}
        self.max_failures = 3
        self.recovery_time = 300

        self._register_sources()

    def _register_sources(self):
        """注册所有在线数据源"""
        sources_config = [
            (OnlineSource.EASTMONEY, '东方财富', 1, self._fetch_from_eastmoney),
            (OnlineSource.SINA, '新浪财经', 2, self._fetch_from_sina),
            (OnlineSource.TENCENT, '腾讯财经', 3, self._fetch_from_tencent),
            (OnlineSource.MOOTDX, '通达信在线', 4, self._fetch_from_mootdx),
            (OnlineSource.SIMULATION, '模拟数据', 99, self._fetch_simulation),
        ]

        for source_enum, display_name, priority, getter in sources_config:
            name = source_enum.value
            self.sources[name] = {
                'name': name,
                'display_name': display_name,
                'priority': priority,
                'getter': getter,
                'enabled': True
            }
            self.source_status[name] = {
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
        realtime_backup = None

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
                    min_data_points = 30
                    is_realtime_source = source_key in ['sina', 'tencent']
                    
                    if is_realtime_source and len(result) < min_data_points:
                        if realtime_backup is None:
                            realtime_backup = {
                                'data': result,
                                'source': source.get('display_name', source['name']),
                                'source_type': source_key
                            }
                        continue
                    
                    if not is_realtime_source and len(result) < min_data_points:
                        continue

                    status['status'] = 'active'
                    status['fail_count'] = 0
                    status['last_success'] = time.time()
                    status['last_error'] = None

                    is_fallback = source['priority'] > 1

                    if source_key == 'simulation' and realtime_backup is not None:
                        realtime_price = realtime_backup['data']['close'].iloc[-1]
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

        if realtime_backup is not None:
            realtime_price = realtime_backup['data']['close'].iloc[-1]
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
                    'note': '历史数据为模拟生成'
                }

        return {
            'success': False,
            'error': str(last_error) if last_error else '所有在线数据源不可用',
            'source': None,
            'is_fallback': True,
            'suggestion': '请检查网络连接后重试'
        }

    def _fetch_from_eastmoney(self, stock_code: str, start_date: str = None, end_date: str = None, period: str = 'daily') -> Optional[pd.DataFrame]:
        """从东方财富获取数据"""
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

    def _fetch_from_sina(self, stock_code: str, start_date: str = None, end_date: str = None, period: str = 'daily') -> Optional[pd.DataFrame]:
        """从新浪财经获取数据"""
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

    def _fetch_from_tencent(self, stock_code: str, start_date: str = None, end_date: str = None, period: str = 'daily') -> Optional[pd.DataFrame]:
        """从腾讯财经获取数据"""
        try:
            import requests

            market_prefix = 'sh' if stock_code.startswith(('6', '9')) else 'sz'
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

    def _fetch_from_mootdx(self, stock_code: str, start_date: str = None, end_date: str = None, period: str = 'daily') -> Optional[pd.DataFrame]:
        """从MooTDX获取数据"""
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
            raise Exception("mootdx库未安装")
        except Exception as e:
            raise Exception(f"MooTDX接口错误: {e}")

    def _fetch_simulation(self, stock_code: str, start_date: str = None, end_date: str = None, period: str = 'daily', base_price: float = None) -> pd.DataFrame:
        """模拟数据"""
        import numpy as np

        n = 120
        if base_price is None or base_price <= 0:
            base_price = 10.0 + hash(stock_code) % 50

        prices = [base_price]
        for i in range(n - 1):
            change = np.random.normal(-0.001, 0.02)
            prev_price = prices[0] * (1 + change)
            prices.insert(0, max(prev_price, 1.0))

        df = pd.DataFrame({
            'open': [p * 0.995 for p in prices],
            'high': [p * 1.015 for p in prices],
            'low': [p * 0.985 for p in prices],
            'close': prices,
            'volume': [int(1000000 + np.random.randint(-200000, 200000)) for _ in range(n)]
        }, index=pd.bdate_range(end=datetime.now(), periods=n))

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


_online_data_manager = None


def get_online_data_manager() -> OnlineDataSourceManager:
    """获取全局在线数据源管理器实例"""
    global _online_data_manager
    if _online_data_manager is None:
        _online_data_manager = OnlineDataSourceManager()
    return _online_data_manager
