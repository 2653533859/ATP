[CmdletBinding()]
param(
  [string]$OutputPath = '',
  [switch]$Force,
  [switch]$SkipFrontendBuild,
  [switch]$FrozenBackend,
  [switch]$SkipFrozenBackendBuild
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $OutputPath = Join-Path $repoRoot (Join-Path '.local-run' "atp-windows-standalone-$timestamp.zip")
} elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
  $OutputPath = Join-Path $repoRoot $OutputPath
}

$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = [System.IO.Path]::GetDirectoryName($OutputPath)
if ([string]::IsNullOrWhiteSpace($outputDirectory)) {
  throw "Unable to resolve output directory for '$OutputPath'."
}

if ([System.IO.Path]::GetExtension($OutputPath).ToLowerInvariant() -ne '.zip') {
  throw 'OutputPath must point to a .zip file.'
}
$sidecarPath = "$OutputPath.sha256"
if ((Test-Path -LiteralPath $OutputPath -PathType Leaf) -or (Test-Path -LiteralPath $sidecarPath -PathType Leaf)) {
  if (-not $Force) {
    throw "Output or checksum file already exists: $OutputPath. Use -Force to overwrite."
  }
  Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $sidecarPath -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

if (-not $SkipFrontendBuild) {
  $previousLocalMode = [Environment]::GetEnvironmentVariable('VITE_ATP_LOCAL_MODE', 'Process')
  $previousBackendOrigin = [Environment]::GetEnvironmentVariable('VITE_BACKEND_ORIGIN', 'Process')
  try {
    $env:VITE_ATP_LOCAL_MODE = 'true'
    $env:VITE_BACKEND_ORIGIN = ''
    Push-Location (Join-Path $repoRoot 'frontend')
    try {
      & npm.cmd run build
      if ($LASTEXITCODE -ne 0) { throw 'Local frontend build failed.' }
    } finally {
      Pop-Location
    }
  } finally {
    [Environment]::SetEnvironmentVariable('VITE_ATP_LOCAL_MODE', $previousLocalMode, 'Process')
    [Environment]::SetEnvironmentVariable('VITE_BACKEND_ORIGIN', $previousBackendOrigin, 'Process')
  }
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'frontend\dist\index.html') -PathType Leaf)) {
  throw 'Local frontend dist is missing.'
}
if ($FrozenBackend -and -not $SkipFrozenBackendBuild) {
  & (Join-Path $repoRoot 'scripts\build-windows-backend.ps1')
  if ($LASTEXITCODE -ne 0) { throw 'Bundled backend build failed.' }
}

$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) "atp-standalone-bundle-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

try {
  Write-Host "Staging ATP Windows Standalone Bundle in $stageRoot ..."

  # 1. Launcher scripts using here-strings
  $startBat = @'
@echo off
echo [ATP] Starting the local ATP app...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows-standalone.ps1" -Action up -Frontend static
if %ERRORLEVEL% NEQ 0 (
  echo [ATP] Startup failed. Check the error above and the local logs.
) else (
  start "" "http://127.0.0.1:8001/"
)
pause
'@
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'start-atp.bat'), "$startBat`r`n", [System.Text.Encoding]::ASCII)

  $stopBat = @'
@echo off
echo [ATP] Stopping the local ATP app...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows-standalone.ps1" -Action down
pause
'@
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'stop-atp.bat'), "$stopBat`r`n", [System.Text.Encoding]::ASCII)

  $statusBat = @'
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows-standalone.ps1" -Action status
pause
'@
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'status-atp.bat'), "$statusBat`r`n", [System.Text.Encoding]::ASCII)

  $readme = if ($FrozenBackend) { @'
================================================================
   ATP Windows 自带 Python 后端便携包
================================================================

1. 解压整个 ZIP；请勿只运行压缩包内的 exe。
2. 双击 start-atp.bat，首次启动会在非 C 盘建立 ATP_resources 并生成私有管理员凭据。
3. 在浏览器访问 http://127.0.0.1:8001/；用 stop-atp.bat 停止服务。

backend/atp-backend.exe 与 backend/_internal/ 必须保持在同一目录。
本包不需要另装 Python，但目前仍不是带桌面窗口的 MSI 安装程序。
本机配置、数据库和云端 API Key 均不包含在包内。
'@ } else { @'
================================================================
   ATP (Automated Testing Platform) Windows 源码便携包
================================================================

【快速使用说明】
1. 先安装 Python 3.12，在解压目录运行 python -m venv backend\.venv。
2. 运行 backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt。
3. 双击 start-atp.bat 启动；首次启动会在非 C 盘创建私有数据目录和随机管理员凭据。
4. 在浏览器访问 http://127.0.0.1:8001/；用 stop-atp.bat 停止服务。

此包不是免安装 Windows 安装程序，也不包含 Python 运行时或个人账号数据。

【目录说明】
- backend/         : 后端核心 API 与轻量单机运行服务
- frontend/dist/   : 预构建的前端 SPA 静态资源
- scripts/         : 运维与状态管控脚本
- config/          : 首次启动时生成本机私有配置，不随包分发
- .local-data/     : 本地 SQLite 数据库文件与资产存储 (运行时自动创建)
'@ }
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'README.txt'), "$readme`r`n", [System.Text.UTF8Encoding]::new($false))

  # 2. Stage Backend
  $targetBackend = Join-Path $stageRoot 'backend'
  New-Item -ItemType Directory -Path $targetBackend -Force | Out-Null
  if ($FrozenBackend) {
    $frozenSource = Join-Path $repoRoot '.local-run\pyinstaller\dist\atp-backend'
    if (-not (Test-Path -LiteralPath (Join-Path $frozenSource 'atp-backend.exe') -PathType Leaf)) {
      throw 'PyInstaller output is missing.'
    }
    Get-ChildItem -LiteralPath $frozenSource -Force | ForEach-Object {
      Copy-Item -LiteralPath $_.FullName -Destination $targetBackend -Recurse
    }
  } else {
    Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\app') -Destination (Join-Path $targetBackend 'app') -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\alembic') -Destination (Join-Path $targetBackend 'alembic') -Recurse
    Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\alembic.ini') -Destination (Join-Path $targetBackend 'alembic.ini')
    Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\requirements.txt') -Destination (Join-Path $targetBackend 'requirements.txt')
  }

  # 3. Stage Scripts
  $targetScripts = Join-Path $stageRoot 'scripts'
  New-Item -ItemType Directory -Path $targetScripts -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts\windows-standalone.ps1') -Destination (Join-Path $targetScripts 'windows-standalone.ps1')

  # 4. Stage Config Profiles
  $targetConfig = Join-Path $stageRoot 'config\startup-profiles'
  New-Item -ItemType Directory -Path $targetConfig -Force | Out-Null
  # Never include the developer machine's signing key, admin password or cloud API key.

  # 5. Stage Frontend Dist
  $targetFrontend = Join-Path $stageRoot 'frontend'
  $sourceDist = Join-Path $repoRoot 'frontend\dist'
  New-Item -ItemType Directory -Path $targetFrontend -Force | Out-Null
  Copy-Item -LiteralPath $sourceDist -Destination (Join-Path $targetFrontend 'dist') -Recurse

  # Clean Python cache in staging
  Get-ChildItem -LiteralPath $stageRoot -Directory -Recurse -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

  # 6. Generate SHA-256 Manifest
  Write-Host "Generating manifest..."
  $files = Get-ChildItem -LiteralPath $stageRoot -File -Recurse
  $manifestItems = @()
  $sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    foreach ($file in $files) {
      $rel = $file.FullName.Substring($stageRoot.Length).TrimStart('\', '/') -replace '\\', '/'
      $stream = [System.IO.File]::OpenRead($file.FullName)
      try {
        $hashBytes = $sha256.ComputeHash($stream)
        $hashHex = [BitConverter]::ToString($hashBytes).Replace('-', '').ToLowerInvariant()
      } finally {
        $stream.Dispose()
      }
      $manifestItems += @{
        path = $rel
        size = $file.Length
        sha256 = $hashHex
      }
    }
  } finally {
    $sha256.Dispose()
  }

  $manifestObj = @{
    name = "atp-windows-standalone"
    created_at = (Get-Date -Format 'o')
    file_count = $manifestItems.Count
    files = $manifestItems
  }
  $manifestJson = $manifestObj | ConvertTo-Json -Depth 5
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'manifest.json'), $manifestJson, [System.Text.UTF8Encoding]::new($false))

  # 7. Create ZIP archive
  Write-Host "Creating archive $OutputPath ..."
  if (Test-Path -LiteralPath $OutputPath) { Remove-Item -LiteralPath $OutputPath -Force }
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::CreateFromDirectory($stageRoot, $OutputPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

  # 8. Sidecar SHA256 for ZIP
  $zipStream = [System.IO.File]::OpenRead($OutputPath)
  $zipSha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    $zipHash = [BitConverter]::ToString($zipSha256.ComputeHash($zipStream)).Replace('-', '').ToLowerInvariant()
  } finally {
    $zipStream.Dispose()
    $zipSha256.Dispose()
  }
  [System.IO.File]::WriteAllText($sidecarPath, "$zipHash  $([System.IO.Path]::GetFileName($OutputPath))`r`n", [System.Text.UTF8Encoding]::new($false))

  $zipItem = Get-Item -LiteralPath $OutputPath
  Write-Host "=========================================================="
  Write-Host "Bundle created successfully!"
  Write-Host "Archive  : $OutputPath ($([math]::Round($zipItem.Length / 1MB, 2)) MB)"
  Write-Host "Checksum : $zipHash"
  Write-Host "Sidecar  : $sidecarPath"
  Write-Host "=========================================================="
} finally {
  if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
