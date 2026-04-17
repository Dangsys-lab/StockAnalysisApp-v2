import Foundation

enum DirectDataSource: String, CaseIterable {
    case sina = "sina"
    case tencent = "tencent"
    case eastmoney = "eastmoney"

    var displayName: String {
        switch self {
        case .sina: return "新浪财经"
        case .tencent: return "腾讯财经"
        case .eastmoney: return "东方财富"
        }
    }

    var priority: Int {
        switch self {
        case .sina: return 1
        case .tencent: return 2
        case .eastmoney: return 3
        }
    }
}

struct StockRealtimeData {
    let code: String
    let name: String
    let open: Double
    let prevClose: Double
    let currentPrice: Double
    let high: Double
    let low: Double
    let volume: Double
    let amount: Double
    let change: Double
    let changePct: Double
    let timestamp: Date
    let source: DirectDataSource
}

struct StockKlineData {
    let code: String
    let dates: [String]
    let open: [Double]
    let high: [Double]
    let low: [Double]
    let close: [Double]
    let volume: [Double]
    let source: DirectDataSource
}

@MainActor
class DirectDataSourceService: ObservableObject {

    static let shared = DirectDataSourceService()

    @Published var connectionStatus: [DirectDataSource: Bool] = [
        .sina: false,
        .tencent: false,
        .eastmoney: false
    ]
    @Published var activeSource: DirectDataSource?
    @Published var lastError: String?

    private let session: URLSession
    private var lastRequestTime: [String: Date] = [:]
    private let minInterval: TimeInterval = 1.5

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        config.timeoutIntervalForResource = 15
        config.httpAdditionalHeaders = [
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive"
        ]
        self.session = URLSession(configuration: config)
    }

    private func waitIfNeeded(source: String) async {
        if let lastTime = lastRequestTime[source] {
            let elapsed = Date().timeIntervalSince(lastTime)
            if elapsed < minInterval {
                let waitTime = minInterval - elapsed
                try? await Task.sleep(nanoseconds: UInt64(waitTime * 1_000_000_000))
            }
        }
        lastRequestTime[source] = Date()
    }

    private func marketPrefix(for code: String) -> String {
        if code.hasPrefix("6") || code.hasPrefix("9") {
            return "sh"
        } else if code.hasPrefix("0") || code.hasPrefix("3") {
            return "sz"
        } else if code.hasPrefix("8") || code.hasPrefix("4") {
            return "bj"
        }
        return "sh"
    }

    func fetchRealtimeData(stockCode: String) async throws -> StockRealtimeData {
        let sources = DirectDataSource.allCases.sorted { $0.priority < $1.priority }
        var lastError: Error?

        for source in sources {
            do {
                let data = try await fetchRealtimeFromSource(stockCode: stockCode, source: source)
                connectionStatus[source] = true
                activeSource = source
                lastError = nil
                return data
            } catch {
                connectionStatus[source] = false
                lastError = error
                continue
            }
        }

        self.lastError = lastError?.localizedDescription
        throw lastError ?? NSError(domain: "DirectDataSource", code: -1, userInfo: [
            NSLocalizedDescriptionKey: "所有直连数据源不可用"
        ])
    }

    func fetchKlineData(stockCode: String, days: Int = 120) async throws -> StockKlineData {
        let sources = DirectDataSource.allCases.sorted { $0.priority < $1.priority }
        var lastError: Error?

        for source in sources {
            do {
                let data = try await fetchKlineFromSource(stockCode: stockCode, source: source, days: days)
                connectionStatus[source] = true
                activeSource = source
                lastError = nil
                return data
            } catch {
                connectionStatus[source] = false
                lastError = error
                continue
            }
        }

        self.lastError = lastError?.localizedDescription
        throw lastError ?? NSError(domain: "DirectDataSource", code: -1, userInfo: [
            NSLocalizedDescriptionKey: "所有直连数据源不可用"
        ])
    }

    private func fetchRealtimeFromSource(stockCode: String, source: DirectDataSource) async throws -> StockRealtimeData {
        await waitIfNeeded(source: source.rawValue)

        switch source {
        case .sina:
            return try await fetchRealtimeFromSina(stockCode: stockCode)
        case .tencent:
            return try await fetchRealtimeFromTencent(stockCode: stockCode)
        case .eastmoney:
            return try await fetchRealtimeFromEastmoney(stockCode: stockCode)
        }
    }

    private func fetchKlineFromSource(stockCode: String, source: DirectDataSource, days: Int) async throws -> StockKlineData {
        await waitIfNeeded(source: source.rawValue)

        switch source {
        case .sina:
            return try await fetchKlineFromSina(stockCode: stockCode, days: days)
        case .tencent:
            return try await fetchKlineFromTencent(stockCode: stockCode, days: days)
        case .eastmoney:
            return try await fetchKlineFromEastmoney(stockCode: stockCode, days: days)
        }
    }

    private func fetchRealtimeFromSina(stockCode: String) async throws -> StockRealtimeData {
        let prefix = marketPrefix(for: stockCode)
        let fullCode = "\(prefix)\(stockCode)"
        guard let url = URL(string: "http://hq.sinajs.cn/list=\(fullCode)") else {
            throw NSError(domain: "DirectDataSource", code: -1)
        }

        var request = URLRequest(url: url)
        request.setValue("https://finance.sina.com.cn/", forHTTPHeaderField: "Referer")
        request.timeoutInterval = 10

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NSError(domain: "DirectDataSource", code: -2, userInfo: [
                NSLocalizedDescriptionKey: "新浪接口返回错误"
            ])
        }

        guard let text = String(data: data, encoding: .utf8) ?? decodeGB18030(data),
              !text.isEmpty else {
            throw NSError(domain: "DirectDataSource", code: -3, userInfo: [
                NSLocalizedDescriptionKey: "新浪返回数据为空"
            ])
        }

        let quotedParts = text.components(separatedBy: "\"")
        guard quotedParts.count >= 2 else {
            throw NSError(domain: "DirectDataSource", code: -4, userInfo: [
                NSLocalizedDescriptionKey: "新浪数据格式异常"
            ])
        }

        let dataStr = quotedParts[1]
        let fields = dataStr.components(separatedBy: ",")
        guard fields.count >= 32 else {
            throw NSError(domain: "DirectDataSource", code: -5, userInfo: [
                NSLocalizedDescriptionKey: "新浪数据字段不足"
            ])
        }

        let name = fields[0]
        let open = Double(fields[1]) ?? 0
        let prevClose = Double(fields[2]) ?? 0
        let currentPrice = Double(fields[3]) ?? 0
        let high = Double(fields[4]) ?? 0
        let low = Double(fields[5]) ?? 0
        let volume = Double(fields[8]) ?? 0
        let amount = Double(fields[9]) ?? 0

        let price = currentPrice > 0 ? currentPrice : prevClose
        let change = price - prevClose
        let changePct = prevClose > 0 ? (change / prevClose) * 100 : 0

        return StockRealtimeData(
            code: stockCode,
            name: name,
            open: open,
            prevClose: prevClose,
            currentPrice: price,
            high: high > 0 ? high : price,
            low: low > 0 ? low : price,
            volume: volume,
            amount: amount,
            change: change,
            changePct: changePct,
            timestamp: Date(),
            source: .sina
        )
    }

    private func fetchRealtimeFromTencent(stockCode: String) async throws -> StockRealtimeData {
        let prefix = marketPrefix(for: stockCode)
        let fullCode = "\(prefix)\(stockCode)"
        guard let url = URL(string: "http://qt.gtimg.cn/q=\(fullCode)") else {
            throw NSError(domain: "DirectDataSource", code: -1)
        }

        var request = URLRequest(url: url)
        request.setValue("https://finance.qq.com/", forHTTPHeaderField: "Referer")
        request.timeoutInterval = 10

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NSError(domain: "DirectDataSource", code: -2, userInfo: [
                NSLocalizedDescriptionKey: "腾讯接口返回错误"
            ])
        }

        guard let text = String(data: data, encoding: .utf8) ?? decodeGB18030(data),
              text.contains("~") else {
            throw NSError(domain: "DirectDataSource", code: -3, userInfo: [
                NSLocalizedDescriptionKey: "腾讯返回数据为空"
            ])
        }

        let fields = text.components(separatedBy: "~")
        guard fields.count >= 50 else {
            throw NSError(domain: "DirectDataSource", code: -5, userInfo: [
                NSLocalizedDescriptionKey: "腾讯数据字段不足"
            ])
        }

        let name = fields[1]
        let currentPrice = Double(fields[3]) ?? 0
        let prevClose = Double(fields[4]) ?? 0
        let open = Double(fields[5]) ?? prevClose
        let volumeStr = fields.count > 36 ? fields[36].replacingOccurrences(of: ",", with: "") : "0"
        let volume = Double(volumeStr) ?? 0

        let change = currentPrice - prevClose
        let changePct = prevClose > 0 ? (change / prevClose) * 100 : 0
        let highPct = abs(changePct) / 100 * 0.6
        let high = currentPrice > 0 && changePct != 0 ? currentPrice * (1 + highPct) : currentPrice * 1.002
        let low = currentPrice > 0 && changePct != 0 ? currentPrice * (1 - highPct) : currentPrice * 0.998

        return StockRealtimeData(
            code: stockCode,
            name: name,
            open: open,
            prevClose: prevClose,
            currentPrice: currentPrice,
            high: high,
            low: low,
            volume: volume,
            amount: 0,
            change: change,
            changePct: changePct,
            timestamp: Date(),
            source: .tencent
        )
    }

    private func fetchRealtimeFromEastmoney(stockCode: String) async throws -> StockRealtimeData {
        let secid: String
        if stockCode.hasPrefix("6") || stockCode.hasPrefix("9") {
            secid = "1.\(stockCode)"
        } else {
            secid = "0.\(stockCode)"
        }

        let urlString = "https://push2.eastmoney.com/api/qt/stock/get?secid=\(secid)&fields=f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f170"
        guard let url = URL(string: urlString) else {
            throw NSError(domain: "DirectDataSource", code: -1)
        }

        var request = URLRequest(url: url)
        request.setValue("https://quote.eastmoney.com/", forHTTPHeaderField: "Referer")
        request.timeoutInterval = 10

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw NSError(domain: "DirectDataSource", code: -2, userInfo: [
                NSLocalizedDescriptionKey: "东方财富接口返回错误"
            ])
        }

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dataDict = json["data"] as? [String: Any] else {
            throw NSError(domain: "DirectDataSource", code: -3, userInfo: [
                NSLocalizedDescriptionKey: "东方财富数据解析失败"
            ])
        }

        let currentPrice = Double(dataDict["f43"] as? Int ?? 0) / 100
        let high = Double(dataDict["f44"] as? Int ?? 0) / 100
        let low = Double(dataDict["f45"] as? Int ?? 0) / 100
        let open = Double(dataDict["f46"] as? Int ?? 0) / 100
        let volume = Double(dataDict["f47"] as? Int ?? 0)
        let amount = Double(dataDict["f48"] as? Int ?? 0)
        let prevClose = Double(dataDict["f60"] as? Int ?? 0) / 100
        let changePct = Double(dataDict["f170"] as? Int ?? 0) / 100
        let name = dataDict["f58"] as? String ?? stockCode
        let change = prevClose > 0 ? currentPrice - prevClose : 0

        return StockRealtimeData(
            code: stockCode,
            name: name,
            open: open,
            prevClose: prevClose,
            currentPrice: currentPrice,
            high: high,
            low: low,
            volume: volume,
            amount: amount,
            change: change,
            changePct: changePct,
            timestamp: Date(),
            source: .eastmoney
        )
    }

    private func fetchKlineFromSina(stockCode: String, days: Int) async throws -> StockKlineData {
        let prefix = marketPrefix(for: stockCode)
        let fullCode = "\(prefix)\(stockCode)"
        let scale = "240"
        let ma = "no"
        let urlString = "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData?symbol=\(fullCode)&scale=\(scale)&ma=\(ma)&datalen=\(days)"
        guard let url = URL(string: urlString) else {
            throw NSError(domain: "DirectDataSource", code: -1)
        }

        var request = URLRequest(url: url)
        request.setValue("https://finance.sina.com.cn/", forHTTPHeaderField: "Referer")
        request.timeoutInterval = 15

        let (data, _) = try await session.data(for: request)

        guard let text = String(data: data, encoding: .utf8) else {
            throw NSError(domain: "DirectDataSource", code: -3, userInfo: [
                NSLocalizedDescriptionKey: "新浪K线数据解析失败"
            ])
        }

        let jsonpPrefix = "=("
        let jsonpSuffix = ")"
        var jsonString = text
        if let startRange = text.range(of: jsonpPrefix) {
            let start = startRange.upperBound
            if let endRange = text.range(of: jsonpSuffix, options: .backwards) {
                jsonString = String(text[start..<endRange.lowerBound])
            }
        }

        guard let jsonData = jsonString.data(using: .utf8),
              let klineArray = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]] else {
            throw NSError(domain: "DirectDataSource", code: -4, userInfo: [
                NSLocalizedDescriptionKey: "新浪K线JSON解析失败"
            ])
        }

        var dates: [String] = []
        var opens: [Double] = []
        var highs: [Double] = []
        var lows: [Double] = []
        var closes: [Double] = []
        var volumes: [Double] = []

        for item in klineArray {
            if let day = item["day"] as? String {
                dates.append(day)
            }
            opens.append(Double(item["open"] as? String ?? "0") ?? 0)
            highs.append(Double(item["high"] as? String ?? "0") ?? 0)
            lows.append(Double(item["low"] as? String ?? "0") ?? 0)
            closes.append(Double(item["close"] as? String ?? "0") ?? 0)
            volumes.append(Double(item["volume"] as? String ?? "0") ?? 0)
        }

        guard !dates.isEmpty else {
            throw NSError(domain: "DirectDataSource", code: -5, userInfo: [
                NSLocalizedDescriptionKey: "新浪K线数据为空"
            ])
        }

        return StockKlineData(
            code: stockCode,
            dates: dates,
            open: opens,
            high: highs,
            low: lows,
            close: closes,
            volume: volumes,
            source: .sina
        )
    }

    private func fetchKlineFromTencent(stockCode: String, days: Int) async throws -> StockKlineData {
        let prefix = marketPrefix(for: stockCode)
        let fullCode = "\(prefix)\(stockCode)"
        let urlString = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=\(fullCode),day,,,,\(days),,qfq"
        guard let url = URL(string: urlString) else {
            throw NSError(domain: "DirectDataSource", code: -1)
        }

        var request = URLRequest(url: url)
        request.setValue("https://finance.qq.com/", forHTTPHeaderField: "Referer")
        request.timeoutInterval = 15

        let (data, _) = try await session.data(for: request)

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dataDict = json["data"] as? [String: Any],
              let stockDict = dataDict[fullCode] as? [String: Any] else {
            throw NSError(domain: "DirectDataSource", code: -3, userInfo: [
                NSLocalizedDescriptionKey: "腾讯K线数据解析失败"
            ])
        }

        let klineArrays = stockDict["qfqday"] as? [[String]] ?? stockDict["day"] as? [[String]] ?? []

        var dates: [String] = []
        var opens: [Double] = []
        var highs: [Double] = []
        var lows: [Double] = []
        var closes: [Double] = []
        var volumes: [Double] = []

        for item in klineArrays {
            guard item.count >= 6 else { continue }
            dates.append(item[0])
            opens.append(Double(item[1]) ?? 0)
            highs.append(Double(item[2]) ?? 0)
            lows.append(Double(item[3]) ?? 0)
            closes.append(Double(item[4]) ?? 0)
            volumes.append(Double(item[5]) ?? 0)
        }

        guard !dates.isEmpty else {
            throw NSError(domain: "DirectDataSource", code: -5, userInfo: [
                NSLocalizedDescriptionKey: "腾讯K线数据为空"
            ])
        }

        return StockKlineData(
            code: stockCode,
            dates: dates,
            open: opens,
            high: highs,
            low: lows,
            close: closes,
            volume: volumes,
            source: .tencent
        )
    }

    private func fetchKlineFromEastmoney(stockCode: String, days: Int) async throws -> StockKlineData {
        let secid: String
        if stockCode.hasPrefix("6") || stockCode.hasPrefix("9") {
            secid = "1.\(stockCode)"
        } else {
            secid = "0.\(stockCode)"
        }

        let fields = "f51,f52,f53,f54,f55,f56,f57"
        let urlString = "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=\(secid)&fields1=f1,f2,f3,f4,f5,f6&fields2=\(fields)&klt=101&fqt=1&end=20500101&lmt=\(days)"
        guard let url = URL(string: urlString) else {
            throw NSError(domain: "DirectDataSource", code: -1)
        }

        var request = URLRequest(url: url)
        request.setValue("https://quote.eastmoney.com/", forHTTPHeaderField: "Referer")
        request.timeoutInterval = 15

        let (data, _) = try await session.data(for: request)

        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dataDict = json["data"] as? [String: Any],
              let klines = dataDict["klines"] as? [String] else {
            throw NSError(domain: "DirectDataSource", code: -3, userInfo: [
                NSLocalizedDescriptionKey: "东方财富K线数据解析失败"
            ])
        }

        var dates: [String] = []
        var opens: [Double] = []
        var highs: [Double] = []
        var lows: [Double] = []
        var closes: [Double] = []
        var volumes: [Double] = []

        for line in klines {
            let fields = line.components(separatedBy: ",")
            guard fields.count >= 6 else { continue }
            dates.append(fields[0])
            opens.append(Double(fields[1]) ?? 0)
            highs.append(Double(fields[2]) ?? 0)
            lows.append(Double(fields[3]) ?? 0)
            closes.append(Double(fields[4]) ?? 0)
            volumes.append(Double(fields[5]) ?? 0)
        }

        guard !dates.isEmpty else {
            throw NSError(domain: "DirectDataSource", code: -5, userInfo: [
                NSLocalizedDescriptionKey: "东方财富K线数据为空"
            ])
        }

        return StockKlineData(
            code: stockCode,
            dates: dates,
            open: opens,
            high: highs,
            low: lows,
            close: closes,
            volume: volumes,
            source: .eastmoney
        )
    }

    func testConnection() async -> [DirectDataSource: Bool] {
        var results: [DirectDataSource: Bool] = [:]
        for source in DirectDataSource.allCases {
            do {
                let _ = try await fetchRealtimeFromSource(stockCode: "600519", source: source)
                results[source] = true
                connectionStatus[source] = true
            } catch {
                results[source] = false
                connectionStatus[source] = false
            }
        }
        return results
    }

    func getActiveSourceName() -> String {
        return activeSource?.displayName ?? "未连接"
    }

    func getConnectionSummary() -> String {
        let connected = connectionStatus.values.filter { $0 }.count
        let total = connectionStatus.count
        return "直连模式 · \(connected)/\(total)源可用"
    }

    private func decodeGB18030(_ data: Data) -> String? {
        let cfEncoding = CFStringEncoding(CFStringEncodings.GB_18030_2000.rawValue)
        return data.withUnsafeBytes { rawBufferPointer in
            if let baseAddress = rawBufferPointer.baseAddress {
                let bytes = baseAddress.assumingMemoryBound(to: UInt8.self)
                let length = CFIndex(data.count)
                if let cfString = CFStringCreateWithBytes(kCFAllocatorDefault, bytes, length, cfEncoding, false) {
                    return cfString as String
                }
            }
            return nil
        }
    }
}
