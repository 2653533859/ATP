[CmdletBinding()]
param([switch]$SkipBackendBuild)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendExe = Join-Path $repoRoot '.local-run\pyinstaller\dist\atp-backend\atp-backend.exe'
$vsDevCmd = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat'
if (-not (Test-Path -LiteralPath $vsDevCmd -PathType Leaf)) { throw "Visual Studio Build Tools missing: $vsDevCmd" }
if (-not $SkipBackendBuild) {
  & (Join-Path $PSScriptRoot 'build-windows-backend.ps1')
  if ($LASTEXITCODE -ne 0) { throw 'Frozen backend build failed.' }
}
if (-not (Test-Path -LiteralPath $backendExe -PathType Leaf)) { throw 'Frozen backend is missing.' }

$previousLocalMode = [Environment]::GetEnvironmentVariable('VITE_ATP_LOCAL_MODE', 'Process')
$previousBackendOrigin = [Environment]::GetEnvironmentVariable('VITE_BACKEND_ORIGIN', 'Process')
try {
  $env:VITE_ATP_LOCAL_MODE = 'true'
  $env:VITE_BACKEND_ORIGIN = ''
  Push-Location (Join-Path $repoRoot 'frontend')
  try {
    $buildCommand = "call `"$vsDevCmd`" -arch=amd64 -host_arch=amd64 >nul && npx --yes `"@tauri-apps/cli@^2`" build --bundles msi"
    & cmd.exe /d /s /c $buildCommand
    if ($LASTEXITCODE -ne 0) { throw "Tauri MSI build failed: $LASTEXITCODE" }
  } finally { Pop-Location }
} finally {
  [Environment]::SetEnvironmentVariable('VITE_ATP_LOCAL_MODE', $previousLocalMode, 'Process')
  [Environment]::SetEnvironmentVariable('VITE_BACKEND_ORIGIN', $previousBackendOrigin, 'Process')
}
