# 1. 检查 SSH 端口转发隧道
$listening = netstat -ano | Select-String -Pattern '127\.0\.0\.1:26379\s+.*LISTENING'
if (-not $listening) {
  Write-Host '>>> 正在拉起连接远端服务端的 SSH 隧道 (25432, 26379, 29000)...' -ForegroundColor Yellow
  $tunnelArgs = @('-N','-T','-p','2222','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','-L','127.0.0.1:25432:127.0.0.1:25432','-L','127.0.0.1:26379:127.0.0.1:26379','-L','127.0.0.1:29000:127.0.0.1:29000','root@192.168.3.196')
  Start-Process -FilePath 'ssh.exe' -ArgumentList $tunnelArgs -WindowStyle Hidden
  Start-Sleep -Seconds 2
} else {
  Write-Host '>>> 远端连接隧道已就绪。' -ForegroundColor Green
}

# 2. 注入环境配置并启动录制 Worker
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

. .\scripts\windows-process-env.ps1
$vals = @{}
$envPath = Join-Path $RepoRoot '.local-run\android-worker-196.env'
if (-not (Test-Path $envPath)) {
  Write-Host "错误: 缺少配置文件 $envPath" -ForegroundColor Red
  exit 1
}

foreach ($line in (Get-Content -Path $envPath -Encoding UTF8)) {
  if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
    $vals[$Matches[1]] = $Matches[2]
  }
}
$null = Push-AtpProcessEnvironment -Values $vals
$workerHost = ($env:COMPUTERNAME -replace '[^a-zA-Z0-9._-]', '-').Trim('-')
if ([string]::IsNullOrWhiteSpace($workerHost)) { $workerHost = 'win' }
$env:WEB_RECORDER_WORKER_ID = 'web-win-' + $workerHost
$env:WEB_RECORDER_MODE = 'worker'

Write-Host ''
Write-Host '===================================================' -ForegroundColor Green
Write-Host ('>>> 本地录制服务已上线 (Worker ID: ' + $env:WEB_RECORDER_WORKER_ID + ')') -ForegroundColor Green
Write-Host '>>> 打开 http://192.168.3.196:8080/ 点击开始录制' -ForegroundColor Cyan
Write-Host '>>> 本电脑屏幕上将直接弹出真实 Chromium 浏览器窗口！' -ForegroundColor Cyan
Write-Host '===================================================' -ForegroundColor Green
Write-Host '提示：录制期间请保持本控制台窗口打开；录制结束关闭本窗口即可。' -ForegroundColor Gray
Write-Host ''

Push-Location (Join-Path $RepoRoot 'backend')
& .\.venv\Scripts\python.exe -m app.web_recording_worker
Pop-Location
