import Foundation
import Network
import CoreTelephony

enum NetworkType: String, CaseIterable {
    case wifi = "WiFi"
    case cellular5G = "5G"
    case cellular4G = "4G"
    case cellular3G = "3G"
    case cellular2G = "2G"
    case unknown = "未知"
    case noConnection = "无网络"

    var icon: String {
        switch self {
        case .wifi: return "wifi"
        case .cellular5G: return "antenna.radiowaves.left.and.right"
        case .cellular4G: return "antenna.radiowaves.left.and.right"
        case .cellular3G: return "antenna.radiowaves.left.and.right"
        case .cellular2G: return "antenna.radiowaves.left.and.right"
        case .unknown: return "questionmark.circle"
        case .noConnection: return "xmark.circle"
        }
    }

    var displayName: String {
        return self.rawValue
    }
}

class NetworkMonitor: ObservableObject {
    static let shared = NetworkMonitor()

    @Published var currentNetworkType: NetworkType = .unknown
    @Published var isConnected: Bool = false
    @Published var connectionInterface: String = ""

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "NetworkMonitor")
    private let telephonyInfo = CTTelephonyNetworkInfo()

    init() {
        startMonitoring()
    }

    func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.updateNetworkStatus(path: path)
            }
        }
        monitor.start(queue: queue)
    }

    func stopMonitoring() {
        monitor.cancel()
    }

    private func updateNetworkStatus(path: NWPath) {
        isConnected = (path.status == .satisfied)

        if !isConnected {
            currentNetworkType = .noConnection
            connectionInterface = ""
            return
        }

        if path.usesInterfaceType(.wifi) {
            currentNetworkType = .wifi
            connectionInterface = "WiFi"
        } else if path.usesInterfaceType(.cellular) {
            connectionInterface = "蜂窝网络"
            currentNetworkType = getCellularType()
        } else {
            currentNetworkType = .unknown
            connectionInterface = "其他"
        }
    }

    private func getCellularType() -> NetworkType {
        if #available(iOS 14.1, *) {
            if let serviceId = telephonyInfo.dataServiceIdentifier,
               let radioTech = telephonyInfo.serviceCurrentRadioAccessTechnology?[serviceId] {
                return radioAccessTechnologyToNetworkType(radioTech)
            }
        }

        if let radioTech = telephonyInfo.currentRadioAccessTechnology {
            return radioAccessTechnologyToNetworkType(radioTech)
        }

        return .unknown
    }

    private func radioAccessTechnologyToNetworkType(_ radioTech: String) -> NetworkType {
        switch radioTech {
        case CTRadioAccessTechnologyNR:
            return .cellular5G
        case CTRadioAccessTechnologyLTE:
            return .cellular4G
        case CTRadioAccessTechnologyHSDPA,
             CTRadioAccessTechnologyHSUPA,
             CTRadioAccessTechnologyWCDMA,
             CTRadioAccessTechnologyeHRPD:
            return .cellular3G
        default:
            return .cellular2G
        }
    }

    deinit {
        stopMonitoring()
    }
}
