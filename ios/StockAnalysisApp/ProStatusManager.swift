import Foundation
import SwiftUI
import Combine

@MainActor
class ProStatusManager: ObservableObject {

    static let shared = ProStatusManager()

    @Published var isProUser: Bool = false
    @Published var showAds: Bool = true
    @Published var showUpgradePrompt: Bool = true
    @Published var purchaseDate: Date?
    @Published var isReviewMode: Bool = false
    @Published var dataRouteMode: DataRouteMode = .direct
    @Published var directConnectionStatus: [DirectDataSource: Bool] = [:]
    @Published var fcConnectionStatus: Bool = false
    @Published var networkType: NetworkType = .unknown
    @Published var isConnected: Bool = false

    private let iapManager = IAPManager.shared
    private var cancellables = Set<AnyCancellable>()

    private init() {
        checkReviewMode()
        setupBindings()
        setupNetworkBindings()
        loadStatus()
    }

    private func checkReviewMode() {
        if isRunningInAppStoreReview() {
            isReviewMode = true
            isProUser = true
            showAds = false
            showUpgradePrompt = false
        }
    }

    private func isRunningInAppStoreReview() -> Bool {
        if let reviewMode = UserDefaults.standard.string(forKey: "ForceReviewMode"), reviewMode == "YES" {
            return true
        }

        #if DEBUG
        if ProcessInfo.processInfo.environment["SIMULATOR_DEVICE_NAME"] != nil {
            return false
        }
        #endif

        if let sandboxEnv = ProcessInfo.processInfo.environment["STOREKIT_SANDBOX"], sandboxEnv == "1" {
            return true
        }

        if Bundle.main.appStoreReceiptURL?.lastPathComponent == "sandboxReceipt" {
            return true
        }

        return false
    }

    static func forceReviewMode() {
        UserDefaults.standard.set("YES", forKey: "ForceReviewMode")
        UserDefaults.standard.synchronize()
    }

    static func disableReviewMode() {
        UserDefaults.standard.removeObject(forKey: "ForceReviewMode")
        UserDefaults.standard.synchronize()
    }

    private func setupBindings() {
        if isReviewMode { return }

        iapManager.$isProUser
            .receive(on: DispatchQueue.main)
            .sink { [weak self] isPro in
                self?.updateStatus(isPro: isPro)
            }
            .store(in: &cancellables)
    }

    private func setupNetworkBindings() {
        NetworkMonitor.shared.$currentNetworkType
            .receive(on: DispatchQueue.main)
            .assign(to: &$networkType)

        NetworkMonitor.shared.$isConnected
            .receive(on: DispatchQueue.main)
            .assign(to: &$isConnected)
    }

    func updateStatus(isPro: Bool) {
        if isReviewMode { return }

        isProUser = isPro
        showAds = !isPro
        showUpgradePrompt = !isPro
        dataRouteMode = isPro ? .cloudFunction : .direct

        if isPro {
            purchaseDate = UserDefaults.standard.object(forKey: "purchaseDate") as? Date ?? Date()
        }

        saveStatus()
    }

    func checkStatus() async {
        if isReviewMode { return }
        await iapManager.checkPurchaseStatus()
    }

    func getVersionDescription() -> String {
        return isProUser ? "专业版" : "免费版"
    }

    func getFeaturePermissionDescription() -> String {
        if isProUser {
            return "已解锁全部高级功能"
        } else {
            return "部分功能需要升级专业版"
        }
    }

    func getDataRouteDescription() -> String {
        if isProUser {
            return "云服务模式 · FC云函数 · 全部17+指标"
        } else {
            return "直连模式 · 手机直连API · 基础6项指标"
        }
    }

    func testDirectConnections() async {
        let results = await DirectDataSourceService.shared.testConnection()
        directConnectionStatus = results
    }

    private func saveStatus() {
        if isReviewMode { return }

        UserDefaults.standard.set(isProUser, forKey: "isProUser")
        UserDefaults.standard.set(showAds, forKey: "showAds")
        UserDefaults.standard.set(showUpgradePrompt, forKey: "showUpgradePrompt")
        if let date = purchaseDate {
            UserDefaults.standard.set(date, forKey: "purchaseDate")
        }
        UserDefaults.standard.synchronize()
    }

    private func loadStatus() {
        if isReviewMode { return }

        isProUser = UserDefaults.standard.bool(forKey: "isProUser")
        showAds = !isProUser
        showUpgradePrompt = !isProUser
        dataRouteMode = isProUser ? .cloudFunction : .direct
        purchaseDate = UserDefaults.standard.object(forKey: "purchaseDate") as? Date
    }
}

struct ProStatusKey: EnvironmentKey {
    static let defaultValue = ProStatusManager.shared
}

extension EnvironmentValues {
    var proStatus: ProStatusManager {
        get { self[ProStatusKey.self] }
        set { self[ProStatusKey.self] = newValue }
    }
}

extension View {
    func withProStatus() -> some View {
        self.environmentObject(ProStatusManager.shared)
    }
}
