import SwiftUI

@main
struct StockAnalysisAppApp: App {
    @StateObject private var networkMonitor = NetworkMonitor()
    @StateObject private var proStatus = ProStatusManager.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(networkMonitor)
                .withProStatus()
        }
    }
}
