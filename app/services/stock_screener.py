# -*- coding: utf-8 -*-
"""
智能选股服务 - 核心逻辑

功能:
- 从沪深300成分股中筛选技术面出现反弹信号的股票
- 多指标评分机制
- 结果缓存
"""

import json
import os
import time
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.stock_filter import StockFilter


CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'cache')
HS300_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'hs300_stocks.json')


class StockScreener:
    """
    智能选股服务
    
    从沪深300成分股中筛选技术面出现反弹信号的股票
    """

    def __init__(self):
        self.stock_filter = StockFilter()
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR, exist_ok=True)

    def load_hs300(self) -> List[Dict]:
        """
        加载沪深300成分股列表

        :return: 成分股列表 [{code, name}]
        """
        if not os.path.exists(HS300_FILE):
            return []
        with open(HS300_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('stocks', [])

    def screen(self, top_n: int = 4) -> Dict[str, Any]:
        """
        执行选股流程

        :param top_n: 返回前N只股票
        :return: 选股结果
        """
        start_time = time.time()

        hs300 = self.load_hs300()
        if not hs300:
            return {'success': False, 'error': '沪深300成分股列表为空'}

        hs300_codes = set(s['code'] for s in hs300)
        hs300_names = {s['code']: s['name'] for s in hs300}

        market_df = self._fetch_market_data()
        if market_df is None or market_df.empty:
            return {'success': False, 'error': '获取市场行情失败'}

        market_df['代码'] = market_df['代码'].astype(str).str.zfill(6)
        market_df = market_df[market_df['代码'].isin(hs300_codes)]

        filtered_df = self.stock_filter.filter_all(market_df)
        filter_log = self.stock_filter.get_log()

        if filtered_df.empty:
            return {'success': False, 'error': '过滤后无候选股票', 'filter_log': filter_log}

        if '涨跌幅' in filtered_df.columns:
            filtered_df = filtered_df.copy()
            filtered_df['abs_change'] = pd.to_numeric(filtered_df['涨跌幅'], errors='coerce').abs()
            filtered_df = filtered_df.nlargest(20, 'abs_change')

        candidates = filtered_df['代码'].tolist()
        scored_stocks = self._score_stocks(candidates, hs300_names)

        if not scored_stocks:
            return {'success': False, 'error': '评分后无合格股票', 'filter_log': filter_log}

        scored_stocks.sort(key=lambda x: x['total_score'], reverse=True)
        top_stocks = scored_stocks[:top_n]

        result = {
            'success': True,
            'stocks': top_stocks,
            'filter_log': filter_log,
            'candidate_count': len(candidates),
            'scored_count': len(scored_stocks),
            'screened_at': datetime.now().isoformat(),
            'duration_seconds': round(time.time() - start_time, 2)
        }

        self._save_cache(result)

        return result

    def _fetch_market_data(self) -> Optional[pd.DataFrame]:
        """
        获取全市场当日行情

        :return: 行情DataFrame或None
        """
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                df['成交额'] = pd.to_numeric(df.get('成交额', 0), errors='coerce').fillna(0) / 10000
                return df
        except Exception as e:
            print(f"[选股] 东方财富获取行情失败: {e}")

        try:
            return self._fetch_market_from_sina()
        except Exception as e:
            print(f"[选股] 新浪获取行情失败: {e}")

        return None

    def _fetch_market_from_sina(self) -> Optional[pd.DataFrame]:
        """
        通过新浪API获取沪深300成分股行情（备用方案）

        :return: 行情DataFrame或None
        """
        import requests as req

        hs300 = self.load_hs300()
        if not hs300:
            return None

        all_data = []
        batch_size = 30

        for i in range(0, len(hs300), batch_size):
            batch = hs300[i:i + batch_size]
            codes = []
            for s in batch:
                code = s['code']
                prefix = 'sh' if code.startswith('6') else 'sz'
                codes.append(f"{prefix}{code}")

            url = f"http://hq.sinajs.cn/list={','.join(codes)}"
            headers = {'Referer': 'http://finance.sina.com.cn'}

            try:
                resp = req.get(url, headers=headers, timeout=10)
                resp.encoding = 'gbk'
                lines = resp.text.strip().split('\n')

                for j, line in enumerate(lines):
                    if '=' not in line:
                        continue
                    parts = line.split('"')
                    if len(parts) < 2:
                        continue
                    fields = parts[1].split(',')
                    if len(fields) < 32:
                        continue

                    name = fields[0]
                    open_price = float(fields[1]) if fields[1] else 0
                    yesterday_close = float(fields[2]) if fields[2] else 0
                    current_price = float(fields[3]) if fields[3] else 0
                    high = float(fields[4]) if fields[4] else 0
                    low = float(fields[5]) if fields[5] else 0
                    volume = float(fields[8]) if fields[8] else 0
                    amount = float(fields[9]) if fields[9] else 0

                    change_pct = 0
                    if yesterday_close > 0:
                        change_pct = (current_price - yesterday_close) / yesterday_close * 100

                    code = batch[j]['code'] if j < len(batch) else ''

                    all_data.append({
                        '代码': code,
                        '名称': name,
                        '涨跌幅': round(change_pct, 2),
                        '成交额': amount / 10000,
                        '开盘': open_price,
                        '最高': high,
                        '最低': low,
                        '收盘': current_price,
                        '成交量': volume
                    })

            except Exception as e:
                print(f"[选股] 新浪批次 {i} 获取失败: {e}")
                continue

            if i + batch_size < len(hs300):
                time.sleep(0.3)

        if all_data:
            return pd.DataFrame(all_data)
        return None

    def _score_stocks(self, codes: List[str], name_map: Dict[str, str]) -> List[Dict]:
        """
        对候选股票进行技术指标评分

        :param codes: 候选股票代码列表
        :param name_map: 代码→名称映射
        :return: 评分结果列表
        """
        scored = []
        total = len(codes)

        for i, code in enumerate(codes):
            if i > 0 and i % 5 == 0:
                time.sleep(0.2)

            try:
                hist = self._fetch_history(code)
                if hist is None or len(hist) < 30:
                    continue

                scores = self._calculate_scores(hist)
                if scores is None:
                    continue

                total_score = (
                    scores['rsi_score'] * 0.30 +
                    scores['boll_score'] * 0.25 +
                    scores['volume_score'] * 0.20 +
                    scores['macd_score'] * 0.15 +
                    scores['ma_score'] * 0.10
                )

                scored.append({
                    'code': code,
                    'name': name_map.get(code, code),
                    'total_score': round(total_score, 2),
                    'detail_scores': {k: round(v, 2) for k, v in scores.items()},
                    'latest_close': round(float(hist['close'].iloc[-1]), 2),
                    'change_pct': round(float(hist['close'].iloc[-1] / hist['close'].iloc[-2] - 1) * 100, 2) if len(hist) >= 2 else 0
                })

            except Exception as e:
                print(f"[选股] 评分 {code} 失败: {e}")
                continue

        return scored

    def _fetch_history(self, code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """
        获取股票历史数据

        :param code: 股票代码
        :param days: 天数
        :return: 历史数据DataFrame或None
        """
        try:
            from app.core.online_data_source import OnlineDataSourceManager
            ds = OnlineDataSourceManager()
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime('%Y-%m-%d')
            end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
            result = ds.get_stock_data(code, start_date, end_date)

            if result.get('success') and result.get('data') is not None:
                df = result['data']
                if len(df) >= 30:
                    required = ['open', 'high', 'low', 'close', 'volume']
                    for col in required:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    df = df.dropna(subset=[c for c in required if c in df.columns])
                    if len(df) >= 30:
                        return df[required]

        except Exception:
            pass

        return None

    def _calculate_scores(self, hist: pd.DataFrame) -> Optional[Dict[str, float]]:
        """
        计算技术指标评分

        :param hist: 历史数据DataFrame
        :return: 各项评分字典
        """
        try:
            close = hist['close'].values
            volume = hist['volume'].values

            if len(close) < 30:
                return None

            rsi = self._calc_rsi(close, 14)
            rsi_score = max(0, (50 - rsi) / 50) * 100 if rsi is not None else 0

            boll_pos = self._calc_boll_position(close, 20)
            boll_score = max(0, (1 - boll_pos)) * 100 if boll_pos is not None else 0

            vol_ratio = self._calc_volume_ratio(volume, 5)
            volume_score = min(100, max(0, (vol_ratio - 1) * 50)) if vol_ratio is not None else 0

            macd_cross = self._calc_macd_cross(close)
            macd_score = 100 if macd_cross else 0

            ma_score = 100 if close[-1] > np.mean(close[-5:]) else 0

            return {
                'rsi_score': rsi_score,
                'boll_score': boll_score,
                'volume_score': volume_score,
                'macd_score': macd_score,
                'ma_score': ma_score
            }

        except Exception:
            return None

    def _calc_rsi(self, close: np.ndarray, period: int = 14) -> Optional[float]:
        """
        计算RSI

        :param close: 收盘价数组
        :param period: RSI周期
        :return: RSI值或None
        """
        if len(close) < period + 1:
            return None
        deltas = np.diff(close[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_boll_position(self, close: np.ndarray, period: int = 20) -> Optional[float]:
        """
        计算布林带位置百分比

        :param close: 收盘价数组
        :param period: 布林带周期
        :return: 位置百分比(0-1)或None
        """
        if len(close) < period:
            return None
        recent = close[-period:]
        ma = np.mean(recent)
        std = np.std(recent)
        if std == 0:
            return 0.5
        upper = ma + 2 * std
        lower = ma - 2 * std
        width = upper - lower
        if width == 0:
            return 0.5
        return (close[-1] - lower) / width

    def _calc_volume_ratio(self, volume: np.ndarray, period: int = 5) -> Optional[float]:
        """
        计算量比

        :param volume: 成交量数组
        :param period: 均量周期
        :return: 量比或None
        """
        if len(volume) < period + 1:
            return None
        avg_vol = np.mean(volume[-(period + 1):-1])
        if avg_vol == 0:
            return None
        return volume[-1] / avg_vol

    def _calc_macd_cross(self, close: np.ndarray) -> bool:
        """
        判断MACD是否金叉或柱状线转正

        :param close: 收盘价数组
        :return: 是否出现信号
        """
        if len(close) < 35:
            return False
        ema12 = self._calc_ema(close, 12)
        ema26 = self._calc_ema(close, 26)
        if ema12 is None or ema26 is None:
            return False
        dif = ema12 - ema26
        if len(dif) < 10:
            return False
        dea = self._calc_ema_series(dif, 9)
        if dea is None or len(dea) < 2:
            return False
        macd_hist = (dif[-len(dea):] - dea) * 2
        if len(macd_hist) < 2:
            return False
        if macd_hist[-1] > 0 and macd_hist[-2] <= 0:
            return True
        if macd_hist[-1] > macd_hist[-2] and macd_hist[-2] > macd_hist[-3] if len(macd_hist) >= 3 else False:
            return True
        return False

    def _calc_ema(self, data: np.ndarray, period: int) -> Optional[np.ndarray]:
        """
        计算EMA

        :param data: 数据数组
        :param period: EMA周期
        :return: EMA数组或None
        """
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = data[i] * multiplier + ema[i - 1] * (1 - multiplier)
        return ema

    def _calc_ema_series(self, data: np.ndarray, period: int) -> Optional[np.ndarray]:
        """
        计算EMA（用于MACD的DEA线）

        :param data: DIF数组
        :param period: DEA周期
        :return: DEA数组或None
        """
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        dea = np.zeros(len(data))
        dea[0] = data[0]
        for i in range(1, len(data)):
            dea[i] = data[i] * multiplier + dea[i - 1] * (1 - multiplier)
        return dea

    def _save_cache(self, result: Dict):
        """
        保存选股结果到缓存

        :param result: 选股结果
        """
        cache_file = os.path.join(CACHE_DIR, 'selected_stocks.json')
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def load_cache(self) -> Optional[Dict]:
        """
        从缓存加载选股结果

        :return: 缓存的选股结果或None
        """
        cache_file = os.path.join(CACHE_DIR, 'selected_stocks.json')
        if not os.path.exists(cache_file):
            return None
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            screened_at = data.get('screened_at', '')
            if screened_at:
                screened_time = datetime.fromisoformat(screened_at)
                if (datetime.now() - screened_time).days > 1:
                    return None
            return data
        except Exception:
            return None
