import Foundation

struct LocalIndicatorResult {
    let success: Bool
    let stockCode: String
    let isPro: Bool
    let indicatorCount: Int
    let dataPoints: Int
    let data: [String: Any]
    let dataSource: String
    let isFallback: Bool
    let disclaimer: String

    func toDict() -> [String: Any] {
        return [
            "success": success,
            "stock_code": stockCode,
            "is_pro": isPro,
            "indicator_count": indicatorCount,
            "data_points": dataPoints,
            "data": data,
            "data_source": dataSource,
            "is_fallback": isFallback,
            "disclaimer": disclaimer
        ]
    }
}

class LocalIndicatorCalculator {

    static let shared = LocalIndicatorCalculator()

    private init() {}

    func calculateFreeIndicators(klineData: StockKlineData) -> LocalIndicatorResult {
        let closes = klineData.close
        let highs = klineData.high
        let lows = klineData.low
        let volumes = klineData.volume

        guard !closes.isEmpty else {
            return LocalIndicatorResult(
                success: false,
                stockCode: klineData.code,
                isPro: false,
                indicatorCount: 0,
                dataPoints: 0,
                data: [:],
                dataSource: klineData.source.displayName,
                isFallback: true,
                disclaimer: "以上为技术指标客观计算结果，仅供参考，不构成任何投资建议。"
            )
        }

        var resultData: [String: Any] = [:]
        resultData["dates"] = klineData.dates
        resultData["open"] = klineData.open
        resultData["high"] = highs
        resultData["low"] = lows
        resultData["close"] = closes
        resultData["volume"] = volumes

        let ma5 = calculateMA(data: closes, period: 5)
        let ma10 = calculateMA(data: closes, period: 10)
        let ma20 = calculateMA(data: closes, period: 20)
        resultData["ma5"] = ma5
        resultData["ma10"] = ma10
        resultData["ma20"] = ma20

        let boll = calculateBOLL(data: closes, period: 20, stdDev: 2.0)
        resultData["boll_upper"] = boll.upper
        resultData["boll_middle"] = boll.middle
        resultData["boll_lower"] = boll.lower

        let rsi = calculateRSI(data: closes, period: 14)
        resultData["rsi"] = rsi

        let indicatorCount = 6

        return LocalIndicatorResult(
            success: true,
            stockCode: klineData.code,
            isPro: false,
            indicatorCount: indicatorCount,
            dataPoints: klineData.dates.count,
            data: resultData,
            dataSource: klineData.source.displayName + "(直连)",
            isFallback: false,
            disclaimer: "以上为技术指标客观计算结果，仅供参考，不构成任何投资建议。"
        )
    }

    func calculateMA(data: [Double], period: Int) -> [Double?] {
        var result = [Double?]()
        result.reserveCapacity(data.count)

        for i in 0..<data.count {
            if i < period - 1 {
                result.append(nil)
            } else {
                let sum = data[(i - period + 1)...i].reduce(0, +)
                result.append(sum / Double(period))
            }
        }
        return result
    }

    func calculateEMA(data: [Double], period: Int) -> [Double?] {
        var result = [Double?]()
        result.reserveCapacity(data.count)

        let multiplier = 2.0 / (Double(period) + 1.0)

        for i in 0..<data.count {
            if i < period - 1 {
                result.append(nil)
            } else if i == period - 1 {
                let sum = data[0...i].reduce(0, +)
                result.append(sum / Double(period))
            } else {
                guard let prevEMA = result[i - 1] else {
                    result.append(nil)
                    continue
                }
                let ema = (data[i] - prevEMA) * multiplier + prevEMA
                result.append(ema)
            }
        }
        return result
    }

    struct BOLLResult {
        let upper: [Double?]
        let middle: [Double?]
        let lower: [Double?]
    }

    func calculateBOLL(data: [Double], period: Int = 20, stdDev: Double = 2.0) -> BOLLResult {
        let ma = calculateMA(data: data, period: period)

        var upper = [Double?]()
        var lower = [Double?]()
        upper.reserveCapacity(data.count)
        lower.reserveCapacity(data.count)

        for i in 0..<data.count {
            if i < period - 1 || ma[i] == nil {
                upper.append(nil)
                lower.append(nil)
                continue
            }

            let slice = data[(i - period + 1)...i]
            let mean = ma[i]!
            let variance = slice.reduce(0.0) { $0 + ($1 - mean) * ($1 - mean) } / Double(period)
            let sd = sqrt(variance)

            upper.append(mean + stdDev * sd)
            lower.append(mean - stdDev * sd)
        }

        return BOLLResult(upper: upper, middle: ma, lower: lower)
    }

    func calculateRSI(data: [Double], period: Int = 14) -> [Double?] {
        var result = [Double?]()
        result.reserveCapacity(data.count)

        if data.count < 2 {
            return data.map { _ in nil }
        }

        var gains = [Double]()
        var losses = [Double]()

        for i in 1..<data.count {
            let change = data[i] - data[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        }

        for i in 0..<data.count {
            if i < period {
                result.append(nil)
                continue
            }

            let gainIndex = i - 1
            if gainIndex < period - 1 {
                result.append(nil)
                continue
            }

            let startIdx = gainIndex - period + 1
            let endIdx = gainIndex

            if startIdx == 0 {
                let avgGain = gains[startIdx...endIdx].reduce(0, +) / Double(period)
                let avgLoss = losses[startIdx...endIdx].reduce(0, +) / Double(period)

                if avgLoss == 0 {
                    result.append(100.0)
                } else {
                    let rs = avgGain / avgLoss
                    result.append(100.0 - (100.0 / (1.0 + rs)))
                }
            } else {
                guard let prevRSI = result[i - 1] else {
                    result.append(nil)
                    continue
                }

                let prevAvgGain = gains[(startIdx - 1)...(endIdx - 1)].reduce(0, +) / Double(period)
                let prevAvgLoss = losses[(startIdx - 1)...(endIdx - 1)].reduce(0, +) / Double(period)

                let currentGain = gains[endIdx]
                let currentLoss = losses[endIdx]

                let avgGain = (prevAvgGain * Double(period - 1) + currentGain) / Double(period)
                let avgLoss = (prevAvgLoss * Double(period - 1) + currentLoss) / Double(period)

                if avgLoss == 0 {
                    result.append(100.0)
                } else {
                    let rs = avgGain / avgLoss
                    result.append(100.0 - (100.0 / (1.0 + rs)))
                }
            }
        }

        return result
    }

    func calculateKDJ(highs: [Double], lows: [Double], closes: [Double], n: Int = 9, m1: Int = 3, m2: Int = 3) -> [String: [Double?]] {
        var kValues = [Double?]()
        var dValues = [Double?]()
        var jValues = [Double?]()

        var prevK = 50.0
        var prevD = 50.0

        for i in 0..<closes.count {
            if i < n - 1 {
                kValues.append(nil)
                dValues.append(nil)
                jValues.append(nil)
                continue
            }

            let highSlice = highs[(i - n + 1)...i]
            let lowSlice = lows[(i - n + 1)...i]
            let highest = highSlice.max() ?? 0
            let lowest = lowSlice.min() ?? 0

            let rsv = highest != lowest ? (closes[i] - lowest) / (highest - lowest) * 100.0 : 50.0

            let k = (2.0 / Double(m1)) * prevK + (1.0 / Double(m1)) * rsv
            let d = (2.0 / Double(m2)) * prevD + (1.0 / Double(m2)) * k
            let j = 3.0 * k - 2.0 * d

            kValues.append(k)
            dValues.append(d)
            jValues.append(j)

            prevK = k
            prevD = d
        }

        return ["k": kValues, "d": dValues, "j": jValues]
    }

    func calculateWR(highs: [Double], lows: [Double], closes: [Double], period: Int = 14) -> [Double?] {
        var result = [Double?]()
        result.reserveCapacity(closes.count)

        for i in 0..<closes.count {
            if i < period - 1 {
                result.append(nil)
                continue
            }

            let highSlice = highs[(i - period + 1)...i]
            let lowSlice = lows[(i - period + 1)...i]
            let highest = highSlice.max() ?? 0
            let lowest = lowSlice.min() ?? 0

            if highest == lowest {
                result.append(-50.0)
            } else {
                let wr = (highest - closes[i]) / (highest - lowest) * (-100.0)
                result.append(wr)
            }
        }

        return result
    }

    func getFreeIndicatorList() -> [String: [String]] {
        return [
            "trend": ["MA5", "MA10", "MA20", "BOLL"],
            "oscillator": ["RSI"]
        ]
    }

    func getFreeIndicatorCount() -> Int {
        return 6
    }
}
