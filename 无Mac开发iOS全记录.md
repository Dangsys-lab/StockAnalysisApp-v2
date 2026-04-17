# 无 Mac 开发 iOS App 全记录

> 从零到上架，全程没有碰过一台 Mac 电脑

**项目**: 股票技术分析工具 v2.0  
**时间**: 2026年4月12日 - 4月14日  
**硬件**: Windows 电脑，16GB 内存，无独立显卡  
**AI 工具**: Trae IDE + GLM-5.1（智谱免费内置）  
**结果**: ✅ IPA 成功上传到 App Store Connect

---

## 一、起因

我有一个 3.0 版本的 iOS 股票分析 App，代码完整，但一直没上架。3.0 功能太多，审核风险大。于是决定先做一个精简的 2.0 免费版，快速上架验证流程。

问题是——我没有 Mac。

iOS 开发的传统路径是：Mac 电脑 → Xcode 编译 → 模拟器测试 → 真机调试 → 上架。每一步都离不开 macOS。但我不想为了一个验证性的 App 去买 Mac 或者租云服务器。

**核心思路**：用 GitHub Actions 的 macOS runner 代替本地 Mac，用 XcodeGen 代替 Xcode 图形界面，用 CI/CD 自动化代替手动操作。

---

## 二、技术方案

### 2.1 工具链

| 环节 | 传统方式 | 我的方案 |
|------|---------|---------|
| 代码编辑 | Xcode (macOS) | Trae IDE (Windows) |
| 项目配置 | Xcode 图形界面 | XcodeGen (project.yml) |
| 编译构建 | Xcode 本地编译 | GitHub Actions (macOS runner) |
| 模拟器测试 | Xcode Simulator | GitHub Actions + xcrun simctl |
| 截图 | 模拟器/真机截图 | GitHub Actions 自动截图 |
| 代码签名 | Xcode 自动签名 | 手动证书 + Provisioning Profile |
| IPA 导出 | Xcode Organizer | xcodebuild -exportArchive |
| 上传 App Store | Transporter / Xcode | xcrun altool (API Key) |
| 后端服务 | 自建服务器 | 阿里云函数计算 FC |

### 2.2 架构设计

```
免费用户:
  手机 App → 直连新浪/腾讯/东方财富 API → 本地计算 6 项指标

内购用户 (¥12 终身):
  手机 App → 阿里云 FC 云函数 → 返回 17+ 项指标
```

### 2.3 文件结构

```
D:\wyj\ios\2.0bendi\
├── .github/workflows/
│   └── build-ios.yml          # GitHub Actions 全流程
├── ios/
│   ├── project.yml             # XcodeGen 项目配置
│   └── StockAnalysisApp/
│       ├── Info.plist
│       ├── ExportOptions.plist
│       ├── ContentView.swift
│       ├── IndicatorAPIService.swift
│       ├── IAPManager.swift
│       ├── LocalIndicatorCalculator.swift
│       ├── ProStatusManager.swift
│       ├── DirectDataSourceService.swift
│       ├── NetworkMonitor.swift
│       ├── UpgradePromptView.swift
│       ├── PurchaseView.swift
│       └── AdBannerView.swift
└── fccode/                     # 阿里云 FC 后端代码
```

---

## 三、踩坑全记录

### 3.1 第一关：Xcode 版本不匹配

**现象**: GitHub Actions 默认的 Xcode 版本与项目格式不兼容

**错误信息**:
```
project format 77 (Xcode 16) incompatible with Xcode 15.4
```

**解决**: 在 workflow 中手动选择 Xcode 16.4
```yaml
- name: Select Xcode 16.4
  run: sudo xcode-select -s /Applications/Xcode_16.4.app
```

**教训**: GitHub Actions 的 macOS runner 预装多个 Xcode 版本，必须显式选择

---

### 3.2 第二关：StoreKit 1 和 StoreKit 2 类型混用

**现象**: IAPManager 中 `products` 声明为 `[SKProduct]`（StoreKit 1），但代码使用 StoreKit 2 的 `Product` API

**错误信息**:
```
Cannot convert value of type 'Product' to expected element type 'SKProduct'
```

**解决**: 统一使用 StoreKit 2
```swift
// 之前
var products: [SKProduct] = []

// 之后
var products: [Product] = []
```

**教训**: StoreKit 1 和 2 不能混用，iOS 16+ 推荐全用 StoreKit 2

---

### 3.3 第三关：Swift 没有 GB18030 编码

**现象**: 通达信数据文件使用 GB18030 编码，Swift 标准库不支持

**错误信息**:
```
Type 'String.Encoding' has no member 'gb18030'
```

**解决**: 使用 CoreFoundation 的 CFString API
```swift
private func decodeGB18030(_ data: Data) -> String? {
    let cfEncoding = CFStringEncoding(CFStringEncodings.GB_18030_2000.rawValue)
    return data.withUnsafeBytes { rawBufferPointer in
        if let baseAddress = rawBufferPointer.baseAddress {
            let bytes = baseAddress.assumingMemoryBound(to: UInt8.self)
            let length = CFIndex(data.count)
            if let cfString = CFStringCreateWithBytes(
                kCFAllocatorDefault, bytes, length, cfEncoding, false
            ) {
                return cfString as String
            }
        }
        return nil
    }
}
```

**教训**: Swift 标准库编码支持有限，复杂编码要靠 CoreFoundation

---

### 3.4 第四关：东方财富 API 返回 Int 不是 Double

**现象**: 东方财富 API 的价格字段返回 Int 类型（单位：分），代码按 Double 解析

**错误信息**:
```
Could not cast value of type '__NSCFNumber' (0x...) to 'NSNumber' (0x...)
```

**解决**:
```swift
// 之前
let price = dataDict["f43"] as? Double ?? 0

// 之后
let price = Double(dataDict["f43"] as? Int ?? 0) / 100.0
```

**教训**: 不同 API 的数据类型不一定和文档一致，要实测验证

---

### 3.5 第五关：CI 环境无法上传到 App Store

**现象**: ExportOptions.plist 的 `destination` 设为 `upload`，但 CI 没有 Apple 账号登录

**错误信息**:
```
Failed to Use Accounts
```

**解决**: 改为 `export`（只导出 IPA，不直接上传）
```xml
<key>destination</key>
<string>export</string>
```

然后用 `xcrun altool --upload-app` 通过 API Key 上传

**教训**: CI 环境不适合交互式登录，API Key 是唯一可靠方案

---

### 3.6 第六关：模拟器截图 Tab 不切换

**现象**: 4 张截图全部是首页，URL Scheme 导航不生效

**原因**: `xcrun simctl openurl` 在 App 已在前台时不会触发 `onOpenURL`

**解决**: 改用启动参数 + 每次重启 App
```swift
// ContentView.swift
.onAppear {
    let args = ProcessInfo.processInfo.arguments
    if args.contains("--tab-market") { selectedTab = 1 }
    else if args.contains("--tab-portfolio") { selectedTab = 2 }
    else if args.contains("--tab-settings") { selectedTab = 3 }
}
```

```bash
# workflow
xcrun simctl terminate "$SIMULATOR_ID" com.dangsys.stockanalyzer
xcrun simctl launch "$SIMULATOR_ID" com.dangsys.stockanalyzer --tab-market
```

**教训**: 模拟器自动化截图不能依赖 URL Scheme，启动参数更可靠

---

### 3.7 第七关：iOS 模拟器运行时缺失

**现象**: Xcode 16.4 的 macOS 15 runner 没有预装 iOS 模拟器运行时

**错误信息**:
```
no simulator found for destination
```

**解决**: 自动检测并安装运行时，创建模拟器设备
```yaml
- name: Install iOS Simulator Runtime
  run: |
    if ! xcrun simctl list runtimes | grep -q "iOS"; then
      xcodebuild -downloadPlatform iOS
    fi

- name: Create Simulator
  run: |
    RUNTIME=$(xcrun simctl list runtimes | grep "iOS" | head -1 | \
      sed 's/.*- \(com\.apple\.CoreSimulator\.SimRuntime\.[^ ]*\).*/\1/')
    DEVICETYPE=$(xcrun simctl list devicetypes | grep "iPhone 16" | head -1 | \
      sed 's/.*- \(com\.apple\.CoreSimulator\.SimDeviceType\.[^ ]*\).*/\1/')
    xcrun simctl create "iPhone 16" "$DEVICETYPE" "$RUNTIME"
```

**教训**: GitHub Actions 的 macOS runner 环境不是开箱即用的，需要自己准备

---

### 3.8 第八关：Bundle ID 不匹配

**现象**: IPA 上传到 App Store Connect 失败

**错误信息**:
```
No suitable application records were found.
Verify your bundle identifier 'com.wyj.StockAnalysisApp' is correct
```

**原因**: 项目代码用 `com.wyj.StockAnalysisApp`，但 App Store Connect 注册的是 `com.dangsys.stockanalyzer`

**解决**: 统一 Bundle ID，修改 4 个文件：
- `project.yml` → `PRODUCT_BUNDLE_IDENTIFIER`
- `Info.plist` → `CFBundleURLName`
- `ExportOptions.plist` → `provisioningProfiles`
- `build-ios.yml` → `simctl launch/terminate` + `PROVISIONING_PROFILE_SPECIFIER`

同时创建新的 Provisioning Profile 并更新 GitHub Secrets

**教训**: Bundle ID 是 iOS 开发的"身份证号"，从第一天就要确定好，改一次牵一发动全身

---

### 3.9 第九关：API Key 权限不足

**现象**: 第一个 App Store Connect API Key 角色是 Developer，无法上传构建版本

**解决**: 创建 Admin 角色的新 API Key，更新 GitHub Secrets
```
APP_STORE_CONNECT_KEY_ID = <YOUR_KEY_ID> (Admin)
APP_STORE_CONNECT_ISSUER_ID = <YOUR_ISSUER_ID>
APP_STORE_CONNECT_API_KEY_BASE64 = <.p8 文件 base64>
```

**教训**: App Store Connect API Key 的角色至少要 Admin 才能上传构建版本

---

## 四、最终 CI/CD 流程

```yaml
# 完整的 GitHub Actions 工作流
push 代码
  → checkout
  → 选择 Xcode 16.4
  → 安装 iOS 模拟器运行时
  → 创建 iPhone 16 模拟器
  → 安装 XcodeGen
  → 生成 Xcode 项目
  → 编译模拟器版本
  → 启动模拟器 → 截取 4 个 Tab 截图
  → 上传截图为 Artifact
  → 导入 Apple Distribution 证书
  → 安装 Provisioning Profile
  → Archive 签名打包
  → 导出 IPA
  → 通过 API Key 上传到 App Store Connect
  → 上传 IPA 为 Artifact（备用）
  → 清理证书
```

**总耗时**: 约 8-12 分钟

---

## 五、关键配置清单

### 5.1 GitHub Secrets（6 个）

| Secret | 用途 | 获取方式 |
|--------|------|---------|
| `P12_BASE64` | Apple Distribution 证书 | OpenSSL 生成 → base64 编码 |
| `P12_PASSWORD` | 证书密码 | 自己设定 |
| `PROVISION_BASE64` | Provisioning Profile | Apple Developer 下载 → base64 编码 |
| `APP_STORE_CONNECT_KEY_ID` | API Key ID | App Store Connect 创建 |
| `APP_STORE_CONNECT_ISSUER_ID` | API Issuer ID | App Store Connect 页面 |
| `APP_STORE_CONNECT_API_KEY_BASE64` | API .p8 文件 | App Store Connect 下载 → base64 编码 |

### 5.2 Apple Developer Portal 配置

1. **App ID**: `com.dangsys.stockanalyzer`
2. **Apple Distribution 证书**: Team ID `<YOUR_TEAM_ID>`
3. **Provisioning Profile**: `StockAnalyzer_Dist`（App Store 类型）
4. **App Store Connect API Key**: `<YOUR_KEY_ID>`（Admin 角色）

### 5.3 阿里云 FC 后端

- **URL**: `https://stock-qamkwqdxbb.cn-hangzhou.fcapp.run`
- **免费版接口**: `/api/free/indicators`
- **专业版接口**: `/api/pro/indicators`
- **隐私政策**: `/privacy`
- **技术支持**: `/support`

---

## 六、费用清单

| 项目 | 费用 |
|------|------|
| Apple Developer 年费 | ¥688/年 |
| GitHub Actions | 免费（公开仓库无限分钟） |
| 阿里云 FC | 免费额度内 |
| 阿里云 DashScope | 免费额度已用完（未使用） |
| Trae IDE + GLM-5.1 | 免费 |
| XcodeGen | 开源免费 |
| **总计** | **¥688/年**（仅 Apple 开发者费） |

---

## 七、时间线

| 时间 | 事件 |
|------|------|
| 4月12日 23:00 | 开始部署 2.0 项目文件 |
| 4月12日 23:30 | 第一次 GitHub Actions 构建，Xcode 版本不匹配 |
| 4月13日 00:15 | 修复 Xcode 版本，StoreKit 类型错误 |
| 4月13日 00:45 | 修复 GB18030 编码、东方财富 API 类型 |
| 4月13日 01:30 | 修复 Provisioning Profile、ExportOptions |
| 4月13日 02:00 | IPA 首次导出成功！ |
| 4月13日 09:00 | 配置 Apple Developer 证书 |
| 4月13日 10:00 | GitHub Secrets 配置完成 |
| 4月13日 11:00 | 发现 FC URL 是占位符，更新为真实 URL |
| 4月13日 12:00 | 添加隐私政策和技术支持页面 |
| 4月13日 12:30 | 添加自动截图功能（URL Scheme 方式） |
| 4月13日 13:30 | 截图 Tab 不切换，改用启动参数方式 |
| 4月13日 14:00 | 截图成功！4 张不同 Tab 的截图 |
| 4月13日 16:00 | 添加 IPA 自动上传到 App Store Connect |
| 4月13日 17:00 | 发现 Transporter 只有 Mac 版 |
| 4月13日 17:30 | 配置 App Store Connect API Key |
| 4月13日 18:00 | API Key 上传失败（Developer 角色权限不够） |
| 4月14日 01:00 | 创建 Admin 角色 API Key，上传仍然失败 |
| 4月14日 02:00 | 发现 Bundle ID 不匹配！ |
| 4月14日 04:30 | 修改 Bundle ID + 新 Provisioning Profile |
| 4月14日 04:50 | **全部成功！IPA 上传到 App Store Connect** ✅ |

**总耗时**: 约 30 小时（含等待和调试）

---

## 八、经验总结

### 8.1 做对了的事

1. **用 XcodeGen 代替手动 .xcodeproj**：项目配置代码化，Git 友好，CI 友好
2. **GitHub Actions 全自动化**：编译、截图、签名、上传一条龙
3. **API Key 上传代替 Transporter**：不需要 Mac，不需要手动操作
4. **先做 2.0 精简版**：功能少，审核风险低，快速验证流程
5. **FC 云函数做后端**：免费额度够用，不需要服务器

### 8.2 踩过的坑

1. **Bundle ID 要第一天就定好**：改一次要改 4-5 个文件 + 重新申请证书
2. **API Key 角色要选 Admin**：Developer 角色没有上传构建版本的权限
3. **模拟器运行时不是预装的**：GitHub Actions 的 macOS runner 需要自己安装
4. **URL Scheme 截图不靠谱**：App 在前台时 openurl 不触发 onOpenURL
5. **altool 上传的错误信息很重要**：不要用 `|| echo` 吞掉错误

### 8.3 给后来者的建议

1. **先在 App Store Connect 创建 App**，确定 Bundle ID，再开始写代码
2. **Apple Developer 证书和 Profile 要提前准备好**，CI 配置时直接用
3. **GitHub Secrets 用 Node.js + tweetsodium 加密**，PowerShell 坑太多
4. **模拟器截图用启动参数**，不要用 URL Scheme
5. **上传步骤加 `|| echo` 防阻塞**，但日志里要能看到真实错误
6. **每次只改一个东西**，改完验证再改下一个
7. **VPN 要随时准备好**，GitHub 在国内网络不稳定

---

## 九、这证明了什么

1. **无 Mac 开发 iOS App 是可行的**：从代码编写到上架，全程不需要 Mac
2. **AI 辅助开发是真实的**：GLM-5.1 连续 30 小时自主调试，不被用户带偏
3. **CI/CD 是 iOS 开发的未来**：自动化比手动操作更可靠、更可复现
4. **免费方案可以走通**：除了 Apple Developer 年费，其他工具全部免费

---

## 十、致谢

- **GLM-5.1**：30 小时自主工作，13 轮编译调试，从未放弃
- **Trae IDE**：免费内置 AI，Windows 上开发 iOS 的最佳选择
- **GitHub Actions**：免费 macOS runner，公开仓库无限分钟
- **XcodeGen**：让 iOS 项目配置代码化成为可能
- **阿里云 FC**：免费额度内的云函数，后端零成本

---

> *"没有 Mac 也能上架 iOS App，这不是魔法，这是工程。"*
>
> — 2026年4月14日 凌晨
