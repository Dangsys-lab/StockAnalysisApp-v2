import SwiftUI

struct UpgradePromptView: View {

    @ObservedObject var proStatus = ProStatusManager.shared
    @State private var showPurchase = false

    var body: some View {
        if proStatus.showUpgradePrompt {
            upgradeContent
                .sheet(isPresented: $showPurchase) {
                    PurchaseView()
                }
        }
    }

    private var upgradeContent: some View {
        VStack(spacing: 16) {
            HStack {
                Image(systemName: "crown.fill")
                    .foregroundColor(.yellow)
                    .font(.title2)

                Text("升级专业版")
                    .font(.headline)
                    .foregroundColor(.primary)

                Spacer()
            }

            VStack(alignment: .leading, spacing: 12) {
                FeatureItem(icon: "checkmark.circle", text: "17个技术指标全解锁", color: .green)
                FeatureItem(icon: "checkmark.circle", text: "完整综合分析报告", color: .green)
                FeatureItem(icon: "checkmark.circle", text: "无广告纯净体验", color: .green)
                FeatureItem(icon: "infinity", text: "终身使用 · 一次购买", color: .blue)
            }

            VStack(spacing: 12) {
                HStack {
                    Text("¥12.00")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(.primary)

                    Text("终身使用")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    Spacer()
                }

                Button(action: {
                    showPurchase = true
                }) {
                    HStack {
                        Image(systemName: "crown.fill")
                        Text("立即升级")
                            .fontWeight(.semibold)
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [Color.yellow, Color.orange]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .cornerRadius(12)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(16)
    }
}

struct FeatureItem: View {
    let icon: String
    let text: String
    let color: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(color)
                .frame(width: 20)

            Text(text)
                .font(.subheadline)
                .foregroundColor(.primary)

            Spacer()
        }
    }
}

struct UpgradeBannerSmall: View {

    @ObservedObject var proStatus = ProStatusManager.shared
    @State private var showPurchase = false

    var body: some View {
        if proStatus.showUpgradePrompt {
            Button(action: {
                showPurchase = true
            }) {
                HStack(spacing: 12) {
                    Image(systemName: "crown.fill")
                        .foregroundColor(.yellow)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("升级专业版")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)

                        Text("解锁全部功能 · ¥12.00")
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
            .buttonStyle(PlainButtonStyle())
            .sheet(isPresented: $showPurchase) {
                PurchaseView()
            }
        }
    }
}

struct LockedFeatureOverlay: View {

    @ObservedObject var proStatus = ProStatusManager.shared
    @State private var showPurchase = false

    let featureName: String

    var body: some View {
        if !proStatus.isProUser {
            ZStack {
                Color.black.opacity(0.5)

                VStack(spacing: 16) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 48))
                        .foregroundColor(.white)

                    Text(featureName)
                        .font(.headline)
                        .foregroundColor(.white)

                    Text("升级专业版解锁此功能")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.8))

                    Button(action: {
                        showPurchase = true
                    }) {
                        HStack {
                            Image(systemName: "crown.fill")
                            Text("立即升级")
                        }
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 20)
                        .padding(.vertical, 10)
                        .background(Color.orange)
                        .cornerRadius(8)
                    }
                }
            }
            .sheet(isPresented: $showPurchase) {
                PurchaseView()
            }
        }
    }
}

#Preview {
    VStack(spacing: 20) {
        UpgradePromptView()

        Divider()

        UpgradeBannerSmall()
    }
    .padding()
}
