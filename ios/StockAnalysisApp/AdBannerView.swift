import SwiftUI

struct AdBannerView: View {

    @ObservedObject var proStatus = ProStatusManager.shared

    var body: some View {
        if proStatus.showAds {
            adContent
        }
    }

    private var adContent: some View {
        VStack(spacing: 0) {
            Divider()

            HStack(spacing: 12) {
                Image(systemName: "megaphone.fill")
                    .font(.title2)
                    .foregroundColor(.orange)

                VStack(alignment: .leading, spacing: 4) {
                    Text("升级专业版")
                        .font(.headline)
                        .foregroundColor(.primary)

                    Text("移除广告 · 解锁全部功能")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                Button(action: {
                    NotificationCenter.default.post(
                        name: Notification.Name("ShowPurchaseView"),
                        object: nil
                    )
                }) {
                    Text("升级")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.orange)
                        .cornerRadius(8)
                }
            }
            .padding()
            .background(Color(.systemGray6))

            Divider()
        }
    }
}

#Preview {
    VStack {
        Text("内容区域")
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        AdBannerView()
    }
}
