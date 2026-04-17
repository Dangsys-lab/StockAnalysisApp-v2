import Foundation

enum DataRouteMode {
    case direct
    case cloudFunction

    var displayName: String {
        switch self {
        case .direct: return "直连模式"
        case .cloudFunction: return "云服务模式"
        }
    }

    var description: String {
        switch self {
        case .direct: return "手机直连公开API，本地计算指标"
        case .cloudFunction: return "通过云函数获取完整分析"
        }
    }
}

class IndicatorAPIService {
    static let shared = IndicatorAPIService()

    private let fcBaseURL: String
    private let session: URLSession
    private let directService = DirectDataSourceService.shared
    private let localCalculator = LocalIndicatorCalculator.shared

    @Published var currentMode: DataRouteMode = .direct
    @Published var isConnecting: Bool = false
    @Published var connectionError: String?

    private init() {
        #if DEBUG
        self.fcBaseURL = "http://localhost:9100"
        #else
        self.fcBaseURL = "https://stock-qamkwqdxbb.cn-hangzhou.fcapp.run"
        #endif

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)
    }

    func getIndicators(
        stockCode: String,
        isPro: Bool,
        completion: @escaping (Result<[String: Any], Error>) -> Void
    ) {
        if isPro {
            getIndicatorsFromFC(stockCode: stockCode, isPro: true, completion: completion)
        } else {
            getIndicatorsDirect(stockCode: stockCode, completion: completion)
        }
    }

    func getIndicatorsAsync(
        stockCode: String,
        isPro: Bool
    ) async throws -> [String: Any] {
        if isPro {
            currentMode = .cloudFunction
            return try await getIndicatorsFromFCAsync(stockCode: stockCode, isPro: true)
        } else {
            currentMode = .direct
            return try await getIndicatorsDirectAsync(stockCode: stockCode)
        }
    }

    private func getIndicatorsDirect(
        stockCode: String,
        completion: @escaping (Result<[String: Any], Error>) -> Void
    ) {
        currentMode = .direct
        isConnecting = true
        connectionError = nil

        Task { @MainActor in
            do {
                let result = try await getIndicatorsDirectAsync(stockCode: stockCode)
                isConnecting = false
                completion(.success(result))
            } catch {
                isConnecting = false
                connectionError = error.localizedDescription

                let fallbackResult: [String: Any] = [
                    "success": false,
                    "message": "直连数据源不可用: \(error.localizedDescription)",
                    "stock_code": stockCode,
                    "mode": "direct",
                    "suggestion": "请检查网络后重试，或升级专业版使用云服务"
                ]
                completion(.success(fallbackResult))
            }
        }
    }

    private func getIndicatorsDirectAsync(stockCode: String) async throws -> [String: Any] {
        let klineData = try await directService.fetchKlineData(stockCode: stockCode, days: 120)
        let result = localCalculator.calculateFreeIndicators(klineData: klineData)
        var dict = result.toDict()
        dict["mode"] = "direct"
        dict["mode_display"] = DataRouteMode.direct.displayName
        return dict
    }

    private func getIndicatorsFromFC(
        stockCode: String,
        isPro: Bool,
        completion: @escaping (Result<[String: Any], Error>) -> Void
    ) {
        currentMode = .cloudFunction
        isConnecting = true
        connectionError = nil

        var components = URLComponents(string: "\(fcBaseURL)/api/indicators/\(stockCode)")!
        let queryItems = [
            URLQueryItem(name: "is_pro", value: isPro ? "true" : "false")
        ]

        components.queryItems = queryItems

        guard let url = components.url else {
            completion(.failure(NSError(domain: "InvalidURL", code: -1)))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 30

        let task = session.dataTask(with: request) { [weak self] data, response, error in
            Task { @MainActor in
                self?.isConnecting = false

                if let error = error {
                    self?.connectionError = error.localizedDescription
                    completion(.failure(error))
                    return
                }

                guard let data = data else {
                    self?.connectionError = "无响应数据"
                    completion(.failure(NSError(domain: "NoData", code: -1)))
                    return
                }

                do {
                    if var json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        json["mode"] = "cloud_function"
                        json["mode_display"] = DataRouteMode.cloudFunction.displayName
                        completion(.success(json))
                    } else {
                        completion(.failure(NSError(domain: "InvalidJSON", code: -1)))
                    }
                } catch {
                    completion(.failure(error))
                }
            }
        }

        task.resume()
    }

    private func getIndicatorsFromFCAsync(stockCode: String, isPro: Bool) async throws -> [String: Any] {
        var components = URLComponents(string: "\(fcBaseURL)/api/indicators/\(stockCode)")!
        let queryItems = [
            URLQueryItem(name: "is_pro", value: isPro ? "true" : "false")
        ]

        components.queryItems = queryItems

        guard let url = components.url else {
            throw NSError(domain: "InvalidURL", code: -1)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 30

        let (data, _) = try await session.data(for: request)

        guard var json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NSError(domain: "InvalidJSON", code: -1)
        }

        json["mode"] = "cloud_function"
        json["mode_display"] = DataRouteMode.cloudFunction.displayName
        return json
    }

    func getCurrentModeDisplay() -> String {
        return currentMode.displayName
    }

    func getConnectionInfo() -> [String: Any] {
        return [
            "mode": currentMode == .direct ? "direct" : "cloud_function",
            "mode_display": currentMode.displayName,
            "is_connecting": isConnecting,
            "error": connectionError ?? ""
        ]
    }

    func testDirectConnection() async -> [DirectDataSource: Bool] {
        return await directService.testConnection()
    }
}
