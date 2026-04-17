import SwiftUI

struct ContentView: View {

    @StateObject private var proStatus = ProStatusManager.shared
    @State private var showPurchaseView = false
    @State private var selectedTab = 0

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                headerView

                TabView(selection: $selectedTab) {
                    homeView
                        .tabItem {
                            Image(systemName: "house.fill")
                            Text("首页")
                        }
                        .tag(0)

                    marketView
                        .tabItem {
                            Image(systemName: "thermometer")
                            Text("市场")
                        }
                        .tag(1)

                    portfolioView
                        .tabItem {
                            Image(systemName: "star.fill")
                            Text("自选")
                        }
                        .tag(2)

                    settingsView
                        .tabItem {
                            Image(systemName: "gearshape.fill")
                            Text("设置")
                        }
                        .tag(3)
                }
                .accentColor(.blue)

                AdBannerView()
            }
            .task {
                await proStatus.checkStatus()
            }
            .sheet(isPresented: $showPurchaseView) {
                PurchaseView()
            }
            .onReceive(NotificationCenter.default.publisher(for: Notification.Name("ShowPurchaseView"))) { _ in
                showPurchaseView = true
            }
            .onAppear {
                let args = ProcessInfo.processInfo.arguments
                if args.contains("--tab-market") {
                    selectedTab = 1
                } else if args.contains("--tab-portfolio") {
                    selectedTab = 2
                } else if args.contains("--tab-settings") {
                    selectedTab = 3
                }
            }
            .onOpenURL { url in
                switch url.host {
                case "market":
                    selectedTab = 1
                case "portfolio":
                    selectedTab = 2
                case "settings":
                    selectedTab = 3
                default:
                    selectedTab = 0
                }
            }
        }
    }

    private var headerView: some View {
        HStack {
            Text("股票分析工具")
                .font(.title2)
                .fontWeight(.bold)

            Spacer()

            DataRouteIndicator(proStatus: proStatus)

            if proStatus.isProUser {
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("专业版")
                        .fontWeight(.medium)
                }
                .font(.subheadline)
                .foregroundColor(.white)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Color.green)
                .cornerRadius(20)
            } else {
                Button(action: {
                    showPurchaseView = true
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "crown.fill")
                            .foregroundColor(.yellow)
                        Text("升级专业版")
                            .fontWeight(.medium)
                    }
                    .font(.subheadline)
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [Color.orange, Color.yellow]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(20)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
    }

    private var homeView: some View {
        ScrollView {
            VStack(spacing: 24) {
                if proStatus.isProUser {
                    proWelcomeCard
                } else {
                    freeVersionCard
                }

                featureGrid

                if !proStatus.isProUser {
                    UpgradePromptView()
                }
            }
            .padding()
        }
    }

    private var marketView: some View {
        ScrollView {
            VStack(spacing: 24) {
                marketThermometer

                if !proStatus.isProUser {
                    UpgradeBannerSmall()
                }
            }
            .padding()
        }
    }

    private var portfolioView: some View {
        ScrollView {
            VStack(spacing: 24) {
                portfolioList

                if !proStatus.isProUser {
                    UpgradeBannerSmall()
                }
            }
            .padding()
        }
    }

    private var settingsView: some View {
        ScrollView {
            VStack(spacing: 24) {
                accountSection
                settingsSection
                aboutSection
            }
            .padding()
        }
    }

    private var proWelcomeCard: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "crown.fill")
                    .font(.largeTitle)
                    .foregroundColor(.yellow)

                Spacer()

                Text("已激活专业版")
                    .font(.headline)
                    .foregroundColor(.green)
            }

            Divider()

            HStack(spacing: 6) {
                Circle()
                    .fill(Color.blue)
                    .frame(width: 8, height: 8)
                Text("云服务模式")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("·")
                    .foregroundColor(.secondary)
                Text("FC云函数 · 全部17+指标")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            VStack(alignment: .leading, spacing: 12) {
                FeatureRow(icon: "checkmark.circle", title: "17个技术指标", description: "全部解锁使用")
                FeatureRow(icon: "checkmark.circle", title: "综合分析报告", description: "多维度技术面总结")
                FeatureRow(icon: "checkmark.circle", title: "无广告体验", description: "纯净的使用环境")
                FeatureRow(icon: "checkmark.circle", title: "深色模式", description: "护眼夜间模式")
                FeatureRow(icon: "infinity", title: "终身使用", description: "一次购买，永久有效")
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(16)
    }

    private var freeVersionCard: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "person.crop.circle")
                    .font(.largeTitle)
                    .foregroundColor(.blue)

                Spacer()

                Text("免费版")
                    .font(.headline)
                    .foregroundColor(.secondary)
            }

            Divider()

            HStack(spacing: 6) {
                Circle()
                    .fill(Color.green)
                    .frame(width: 8, height: 8)
                Text("直连模式")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text("·")
                    .foregroundColor(.secondary)
                Text("手机直连公开API")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            VStack(alignment: .leading, spacing: 12) {
                FeatureRow(icon: "checkmark.circle", title: "基础指标查询", description: "MA5/MA10/MA20/BOLL/RSI")
                FeatureRow(icon: "antenna.radiowaves.left_and_right", title: "直连数据源", description: "新浪/腾讯/东方财富")
                FeatureRow(icon: "checkmark.circle", title: "深色模式", description: "已开放使用")
                FeatureRow(icon: "checkmark.circle", title: "参考股票", description: "已开放使用")
                FeatureRow(icon: "lock.fill", title: "综合分析报告", description: "部分可见，完整需升级", locked: true)
                FeatureRow(icon: "xmark.circle", title: "包含广告", description: "升级后可移除", locked: true)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(16)
    }

    private var featureGrid: some View {
        LazyVGrid(columns: [
            GridItem(.flexible()),
            GridItem(.flexible())
        ], spacing: 16) {
            FeatureButton(
                icon: "chart.bar",
                title: "市场温度计",
                color: .blue,
                isLocked: false
            )

            FeatureButton(
                icon: "magnifyingglass",
                title: "参考股票",
                color: .green,
                isLocked: false
            )

            FeatureButton(
                icon: "doc.text",
                title: "指标分析",
                color: .orange,
                isLocked: false
            )

            FeatureButton(
                icon: "star.fill",
                title: "自选股",
                color: .red,
                isLocked: false
            )

            FeatureButton(
                icon: "moon.fill",
                title: "深色模式",
                color: .indigo,
                isLocked: false
            )

            FeatureButton(
                icon: "gearshape",
                title: "设置",
                color: .gray,
                isLocked: false
            )
        }
    }

    private var marketThermometer: some View {
        VStack(spacing: 16) {
            Text("市场温度计")
                .font(.title2)
                .fontWeight(.bold)

            Text("实时感知市场环境")
                .font(.subheadline)
                .foregroundColor(.secondary)

            ZStack {
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color(.systemGray6))

                VStack(spacing: 12) {
                    Image(systemName: "thermometer.sun")
                        .font(.system(size: 48))
                        .foregroundColor(.orange)

                    Text("65分")
                        .font(.system(size: 36, weight: .bold))

                    Text("震荡市")
                        .font(.headline)
                        .foregroundColor(.secondary)
                }
                .padding()
            }
        }
    }

    private var portfolioList: some View {
        VStack(spacing: 16) {
            Text("自选股")
                .font(.title2)
                .fontWeight(.bold)

            Text("管理您关注的股票")
                .font(.subheadline)
                .foregroundColor(.secondary)

            VStack(spacing: 12) {
                StockRow(code: "600519", name: "贵州茅台", price: "1688.00")
                StockRow(code: "000858", name: "五粮液", price: "158.50")
                StockRow(code: "601318", name: "中国平安", price: "48.20")
            }
        }
    }

    private var accountSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("账户")
                .font(.headline)

            if proStatus.isProUser {
                HStack {
                    Image(systemName: "checkmark.shield.fill")
                        .foregroundColor(.green)

                    VStack(alignment: .leading, spacing: 4) {
                        Text("专业版已激活")
                            .font(.subheadline)
                            .fontWeight(.medium)

                        if let date = proStatus.purchaseDate {
                            Text("购买日期: \(date, style: .date)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }

                    Spacer()
                }
                .padding()
                .background(Color.green.opacity(0.1))
                .cornerRadius(12)
            } else {
                Button(action: {
                    showPurchaseView = true
                }) {
                    HStack {
                        Image(systemName: "crown.fill")
                            .foregroundColor(.yellow)

                        VStack(alignment: .leading, spacing: 4) {
                            Text("升级专业版")
                                .font(.subheadline)
                                .fontWeight(.medium)

                            Text("¥12.00 · 终身使用")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        Spacer()

                        Image(systemName: "chevron.right")
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                }
            }
        }
    }

    private var settingsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("功能设置")
                .font(.headline)

            VStack(spacing: 12) {
                SettingRow(icon: "bell", title: "通知设置", subtitle: "管理推送通知")
                SettingRow(icon: "moon", title: "深色模式", subtitle: "已开放使用")
                SettingRow(icon: "arrow.clockwise", title: "数据刷新", subtitle: "设置刷新频率")
            }
        }
    }

    private var aboutSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("关于")
                .font(.headline)

            VStack(spacing: 12) {
                SettingRow(icon: "info.circle", title: "版本", subtitle: "v2.0")
                SettingRow(icon: "doc.text", title: "隐私政策", subtitle: "查看隐私政策")
                SettingRow(icon: "envelope", title: "联系我们", subtitle: "nimeipo@126.com")
            }
        }
    }
}

struct FeatureButton: View {
    let icon: String
    let title: String
    let color: Color
    var isLocked: Bool = false

    var body: some View {
        VStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 16)
                    .fill(color.opacity(0.1))

                Image(systemName: icon)
                    .font(.system(size: 32))
                    .foregroundColor(color)

                if isLocked {
                    ZStack {
                        Circle()
                            .fill(Color.black.opacity(0.6))

                        Image(systemName: "lock.fill")
                            .foregroundColor(.white)
                    }
                    .frame(width: 28, height: 28)
                }
            }
            .frame(height: 80)

            Text(title)
                .font(.subheadline)
                .multilineTextAlignment(.center)
                .lineLimit(2)
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String
    var locked: Bool = false

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(locked ? .gray : .blue)
                .frame(width: 30)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                    .foregroundColor(locked ? .gray : .primary)

                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()
        }
    }
}

struct StockRow: View {
    let code: String
    let name: String
    let price: String

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.headline)

                Text(code)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            Text("¥\(price)")
                .font(.headline)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct SettingRow: View {
    let icon: String
    let title: String
    let subtitle: String
    var locked: Bool = false

    var body: some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(locked ? .gray : .blue)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline)
                    .foregroundColor(locked ? .gray : .primary)

                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            if locked {
                Image(systemName: "lock.fill")
                    .foregroundColor(.gray)
                    .font(.caption)
            } else {
                Image(systemName: "chevron.right")
                    .foregroundColor(.secondary)
                    .font(.caption)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct DataRouteIndicator: View {
    @ObservedObject var proStatus: ProStatusManager

    private var networkColor: Color {
        switch proStatus.networkType {
        case .wifi: return .blue
        case .cellular5G: return .green
        case .cellular4G: return .orange
        case .cellular3G: return .yellow
        case .noConnection: return .red
        default: return .gray
        }
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: proStatus.networkType.icon)
                .foregroundColor(networkColor)
                .font(.caption2)

            Text(proStatus.networkType.displayName)
                .font(.caption2)
                .foregroundColor(.secondary)

            Divider()
                .frame(height: 12)

            Circle()
                .fill(proStatus.isProUser ? Color.blue : Color.green)
                .frame(width: 6, height: 6)

            Text(proStatus.isProUser ? "云服务" : "直连")
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(Color(.systemGray5))
        )
    }
}

#Preview {
    ContentView()
}
