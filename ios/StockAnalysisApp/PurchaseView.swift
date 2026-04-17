import SwiftUI

struct PurchaseView: View {

    @StateObject private var iapManager = IAPManager.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {

                    Image(systemName: "crown.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.yellow)
                        .padding(.top, 20)

                    Text("升级专业版")
                        .font(.title)
                        .fontWeight(.bold)

                    Text("解锁全部高级功能")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    VStack(alignment: .leading, spacing: 16) {
                        FeatureRow(icon: "chart.line.uptrend.xyaxis", title: "完整技术指标", description: "17个技术指标，全面分析")
                        FeatureRow(icon: "doc.text.fill", title: "完整分析报告", description: "多维度技术面总结")
                        FeatureRow(icon: "eye.slash.fill", title: "无广告体验", description: "纯净的使用环境")
                        FeatureRow(icon: "infinity", title: "终身使用", description: "一次购买，永久有效")
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)

                    VStack(spacing: 12) {
                        Text(iapManager.getPriceString())
                            .font(.system(size: 36, weight: .bold))
                            .foregroundColor(.primary)

                        Text("终身使用 · 无订阅")
                            .font(.subheadline)
                            .foregroundColor(.secondary)

                        Text("相比竞品订阅制年省¥200+")
                            .font(.caption)
                            .foregroundColor(.green)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(Color.green.opacity(0.1))
                            .cornerRadius(8)
                    }
                    .padding(.vertical, 8)

                    if iapManager.isLoading {
                        ProgressView("处理中...")
                            .frame(maxWidth: .infinity)
                            .padding()
                    } else {
                        Button(action: {
                            Task {
                                await purchasePro()
                            }
                        }) {
                            Text("立即购买")
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
                        .disabled(iapManager.isLoading)
                    }

                    Button(action: {
                        Task {
                            await restorePurchase()
                        }
                    }) {
                        Text("恢复购买")
                            .font(.subheadline)
                            .foregroundColor(.blue)
                    }
                    .padding(.top, 8)

                    if let error = iapManager.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red)
                            .padding()
                            .background(Color.red.opacity(0.1))
                            .cornerRadius(8)
                    }

                    Text("购买后可在设置中恢复。如有问题请联系客服。")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.top, 8)
                }
                .padding()
            }
            .navigationTitle("专业版")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("关闭") {
                        dismiss()
                    }
                }
            }
            .task {
                await iapManager.loadProducts()
            }
        }
    }

    private func purchasePro() async {
        do {
            let success = try await iapManager.purchasePro()
            if success {
                dismiss()
            }
        } catch {
            iapManager.errorMessage = error.localizedDescription
        }
    }

    private func restorePurchase() async {
        do {
            try await iapManager.restorePurchase()
            dismiss()
        } catch {
            iapManager.errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    PurchaseView()
}
