import Foundation
import StoreKit

@MainActor
class IAPManager: ObservableObject {

    static let shared = IAPManager()

    @Published var isProUser: Bool = false
    @Published var products: [Product] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?

    private let productID = "com.stockanalysis.pro.lifetime"

    private init() {
        loadPurchaseStatus()
        setupTransactionObserver()
    }

    func loadProducts() async {
        isLoading = true
        errorMessage = nil

        do {
            let storeProducts = try await Product.products(for: [productID])
            self.products = storeProducts
        } catch {
            errorMessage = "加载产品失败: \(error.localizedDescription)"
        }

        isLoading = false
    }

    func purchasePro() async throws -> Bool {
        guard let product = products.first else {
            throw IAPError.productNotFound
        }

        isLoading = true
        defer { isLoading = false }

        let result = try await product.purchase()

        switch result {
        case .success(let verification):
            let transaction = try checkVerified(verification)
            isProUser = true
            savePurchaseStatus()
            await transaction.finish()
            return true

        case .userCancelled:
            throw IAPError.purchaseCancelled

        case .pending:
            throw IAPError.purchasePending

        @unknown default:
            throw IAPError.unknown
        }
    }

    func restorePurchase() async throws {
        isLoading = true
        defer { isLoading = false }

        var restored = false

        for await result in Transaction.currentEntitlements {
            do {
                let transaction = try checkVerified(result)

                if transaction.productID == productID {
                    isProUser = true
                    savePurchaseStatus()
                    restored = true
                }
            } catch {
            }
        }

        if !restored {
            throw IAPError.noPurchasesToRestore
        }
    }

    func checkPurchaseStatus() async {
        guard let result = await Transaction.currentEntitlement(for: productID) else {
            isProUser = false
            return
        }

        do {
            let transaction = try checkVerified(result)
            isProUser = transaction.revocationDate == nil
            savePurchaseStatus()
        } catch {
            isProUser = false
        }
    }

    private func checkVerified<T>(_ result: VerificationResult<T>) throws -> T {
        switch result {
        case .unverified:
            throw IAPError.verificationFailed
        case .verified(let safe):
            return safe
        }
    }

    private func setupTransactionObserver() {
        Task {
            for await result in Transaction.updates {
                do {
                    let transaction = try checkVerified(result)

                    if transaction.productID == productID {
                        isProUser = true
                        savePurchaseStatus()
                    }

                    await transaction.finish()
                } catch {
                }
            }
        }
    }

    private func savePurchaseStatus() {
        UserDefaults.standard.set(isProUser, forKey: "isProUser")
        UserDefaults.standard.set(Date(), forKey: "purchaseDate")
        UserDefaults.standard.synchronize()
    }

    private func loadPurchaseStatus() {
        isProUser = UserDefaults.standard.bool(forKey: "isProUser")
    }
}

enum IAPError: LocalizedError {
    case productNotFound
    case purchaseCancelled
    case purchasePending
    case verificationFailed
    case noPurchasesToRestore
    case unknown

    var errorDescription: String? {
        switch self {
        case .productNotFound:
            return "产品未找到"
        case .purchaseCancelled:
            return "购买已取消"
        case .purchasePending:
            return "购买待处理"
        case .verificationFailed:
            return "购买验证失败"
        case .noPurchasesToRestore:
            return "没有可恢复的购买"
        case .unknown:
            return "未知错误"
        }
    }
}

extension IAPManager {

    func getPriceString() -> String {
        guard let product = products.first else {
            return "¥12.00"
        }
        return product.displayPrice
    }

    func getProductDescription() -> String {
        guard let product = products.first else {
            return "专业版 - 终身使用"
        }
        return product.description
    }
}
