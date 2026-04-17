@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   App Store Connect API Key Base64 编码工具
echo ========================================
echo.

set /p P8_PATH="请输入 P8 文件完整路径: "

if not exist "%P8_PATH%" (
    echo [错误] 文件不存在: %P8_PATH%
    pause
    exit /b 1
)

echo.
echo [处理中] 正在读取文件...
echo.

powershell -Command "$content = Get-Content '%P8_PATH%' -Raw; $bytes = [System.Text.Encoding]::UTF8.GetBytes($content); $base64 = [Convert]::ToBase64String($bytes); Write-Output ''; Write-Output '========== Base64 编码结果 =========='; Write-Output $base64; Write-Output '===================================='; Write-Output ''; Write-Output '请复制上面的 Base64 字符串到 GitHub Secrets'; $base64 | clip; Write-Output '[提示] 已自动复制到剪贴板！'"

echo.
echo 完成！
pause
