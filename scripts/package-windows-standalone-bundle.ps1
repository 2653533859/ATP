[CmdletBinding()]
param(
  [string]$OutputPath = '',
  [switch]$Force,
  [switch]$SkipFrontendBuild
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

$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) "atp-standalone-bundle-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

try {
  Write-Host "Staging ATP Windows Standalone Bundle in $stageRoot ..."

  # 1. Launcher scripts using here-strings
  $startBat = @'
@echo off
chcp 65001 >nul
echo [ATP] 正在启动 ATP 单机便携版...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows-standalone.ps1" -Action up -Frontend static
if %ERRORLEVEL% NEQ 0 (
  echo [ATP] 启动出现异常，请查看上方提示或 logs 目录。
)
pause
'@
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'start-atp.bat'), "$startBat`r`n", [System.Text.UTF8Encoding]::new($false))

  $stopBat = @'
@echo off
chcp 65001 >nul
echo [ATP] 正在停止 ATP 单机便携版...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows-standalone.ps1" -Action down
pause
'@
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'stop-atp.bat'), "$stopBat`r`n", [System.Text.UTF8Encoding]::new($false))

  $statusBat = @'
@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows-standalone.ps1" -Action status
pause
'@
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'status-atp.bat'), "$statusBat`r`n", [System.Text.UTF8Encoding]::new($false))

  $readme = @'
================================================================
   ATP (Automated Testing Platform) Windows 绿色单机便携版
================================================================

【快速使用说明】
1. 双击运行 start-atp.bat 即可一键启动后台服务与前端界面。
2. 启动完成后，在浏览器访问 http://127.0.0.1:8001/ 即可登录使用。
3. 需要停止服务时，双击运行 stop-atp.bat。
4. 查看运行状态时，双击运行 status-atp.bat。

【目录说明】
- backend/         : 后端核心 API 与轻量单机运行服务
- frontend/dist/   : 预构建的前端 SPA 静态资源
- scripts/         : 运维与状态管控脚本
- config/          : 默认本地轻量单机配置文件 (local-lite.env)
- .local-data/     : 本地 SQLite 数据库文件与资产存储 (运行时自动创建)
'@
  [System.IO.File]::WriteAllText((Join-Path $stageRoot 'README.txt'), "$readme`r`n", [System.Text.UTF8Encoding]::new($false))

  # 2. Stage Backend
  $targetBackend = Join-Path $stageRoot 'backend'
  New-Item -ItemType Directory -Path $targetBackend -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\app') -Destination (Join-Path $targetBackend 'app') -Recurse
  Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\alembic') -Destination (Join-Path $targetBackend 'alembic') -Recurse
  Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\alembic.ini') -Destination (Join-Path $targetBackend 'alembic.ini')
  Copy-Item -LiteralPath (Join-Path $repoRoot 'backend\requirements.txt') -Destination (Join-Path $targetBackend 'requirements.txt')

  # 3. Stage Scripts
  $targetScripts = Join-Path $stageRoot 'scripts'
  New-Item -ItemType Directory -Path $targetScripts -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts\windows-standalone.ps1') -Destination (Join-Path $targetScripts 'windows-standalone.ps1')

  # 4. Stage Config Profiles
  $targetConfig = Join-Path $stageRoot 'config\startup-profiles'
  New-Item -ItemType Directory -Path $targetConfig -Force | Out-Null
  $sourceProfile = Join-Path $repoRoot 'config\startup-profiles\local-lite.env'
  if (Test-Path -LiteralPath $sourceProfile) {
    Copy-Item -LiteralPath $sourceProfile -Destination (Join-Path $targetConfig 'local-lite.env')
  }

  # 5. Stage Frontend Dist
  $targetFrontend = Join-Path $stageRoot 'frontend'
  $sourceDist = Join-Path $repoRoot 'frontend\dist'
  if (Test-Path -LiteralPath $sourceDist) {
    New-Item -ItemType Directory -Path $targetFrontend -Force | Out-Null
    Copy-Item -LiteralPath $sourceDist -Destination (Join-Path $targetFrontend 'dist') -Recurse
  } else {
    Write-Warning "frontend\dist does not exist. Please build frontend with npm run build."
  }

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
