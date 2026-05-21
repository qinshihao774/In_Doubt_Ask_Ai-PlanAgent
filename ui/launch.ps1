#Requires -Version 5.1
<#
.SYNOPSIS
    私人规划执行助理 - Inspire UI 启动脚本
.DESCRIPTION
    启动 Inspire UI 流体玻璃态界面的 PowerShell 脚本
.NOTES
    文件名: launch.ps1
    版本: 1.0.0
#>

[CmdletBinding()]
param(
    [int]$Port = 8501,
    [switch]$Debug,
    [switch]$NoBrowser
)

# 设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 颜色定义
$Colors = @{
    Primary   = "Yellow"
    Success   = "Green"
    Error     = "Red"
    Info      = "Cyan"
    Warning   = "Magenta"
}

# 辅助函数
function Write-Header {
    Clear-Host
    Write-Host @"
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     🍜 私人规划执行助理 - Inspire UI                     ║
║                                                          ║
║     流体玻璃态设计 · 极致交互体验                         ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"@ -ForegroundColor $Colors.Primary
    Write-Host ""
}

function Write-Status {
    param(
        [string]$Message,
        [string]$Status = "Info",
        [switch]$NoNewline
    )
    $color = $Colors[$Status]
    $prefix = switch ($Status) {
        "Success" { "[✓] " }
        "Error"   { "[✗] " }
        "Warning" { "[!] " }
        "Info"    { "[→] " }
        default   { "[•] " }
    }
    
    $params = @{
        Object = $prefix + $Message
        ForegroundColor = $color
        NoNewline = $NoNewline
    }
    Write-Host @params
}

function Test-VirtualEnvironment {
    $venvPaths = @(
        "..\.venv\Scripts\Activate.ps1"
        "..\..\.venv\Scripts\Activate.ps1"
        ".venv\Scripts\Activate.ps1"
    )
    
    foreach ($path in $venvPaths) {
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}

function Start-InspireUI {
    Write-Header
    
    # 检查虚拟环境
    Write-Status -Message "检查虚拟环境..." -Status "Info"
    $venvScript = Test-VirtualEnvironment
    
    if ($venvScript) {
        Write-Status -Message "找到虚拟环境: $venvScript" -Status "Success"
        try {
            & $venvScript
            Write-Status -Message "虚拟环境已激活" -Status "Success"
        }
        catch {
            Write-Status -Message "激活虚拟环境失败，使用系统 Python" -Status "Warning"
        }
    }
    else {
        Write-Status -Message "未找到虚拟环境，使用系统 Python" -Status "Warning"
    }
    
    Write-Host ""
    
    # 检查 Streamlit
    Write-Status -Message "检查 Streamlit..." -Status "Info"
    try {
        $streamlitVersion = streamlit --version 2>&1
        Write-Status -Message "Streamlit 已安装" -Status "Success"
    }
    catch {
        Write-Status -Message "正在安装 Streamlit..." -Status "Warning"
        pip install streamlit -q
        Write-Status -Message "Streamlit 安装完成" -Status "Success"
    }
    
    Write-Host ""
    Write-Status -Message "启动 Inspire UI..." -Status "Info"
    Write-Status -Message "请稍候..." -Status "Info"
    Write-Host ""
    
    # 构造启动参数
    $arguments = @(
        "run",
        "streamlit_app.py",
        "--server.port", $Port,
        "--server.headless", "true"
    )
    
    if ($Debug) {
        $arguments += "--logger.level=debug"
    }
    
    if ($NoBrowser) {
        $arguments += "--server.headless"
    }
    
    try {
        # 启动 Streamlit
        streamlit @arguments
    }
    catch {
        Write-Header
        Write-Status -Message "启动失败！" -Status "Error"
        Write-Status -Message $_.Exception.Message -Status "Error"
        Write-Host ""
        Write-Host "按任意键退出..." -NoNewline
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}

# 主入口
if ($MyInvocation.InvocationName -ne '.') {
    Start-InspireUI
}