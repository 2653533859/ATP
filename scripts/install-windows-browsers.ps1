[CmdletBinding()]
param(
  [ValidateSet('chromium', 'firefox', 'webkit', 'all')]
  [string]$Browser = 'chromium',
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$driver = Join-Path $repoRoot 'backend\_internal\playwright\driver'
$node = Join-Path $driver 'node.exe'
$cli = Join-Path $driver 'package\cli.js'
if (-not (Test-Path -LiteralPath $node -PathType Leaf) -or -not (Test-Path -LiteralPath $cli -PathType Leaf)) {
  throw 'Bundled Playwright driver is missing. Install the complete Windows desktop package first.'
}
foreach ($profile in @(
  (Join-Path $repoRoot 'config\startup-profiles\local-lite.env'),
  (Join-Path $env:LOCALAPPDATA 'ATP\Desktop\config\startup-profiles\local-lite.env')
)) {
  if (-not (Test-Path -LiteralPath $profile -PathType Leaf)) { continue }
  $configured = Get-Content -LiteralPath $profile -Encoding UTF8 |
    Where-Object { $_ -match '^\s*PLAYWRIGHT_BROWSERS_PATH=' } | Select-Object -Last 1
  if ($configured) {
    $env:PLAYWRIGHT_BROWSERS_PATH = ($configured -split '=', 2)[1].Trim().Trim('"', "'")
    break
  }
}
if ([string]::IsNullOrWhiteSpace($env:PLAYWRIGHT_BROWSERS_PATH)) {
  $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $env:LOCALAPPDATA 'ms-playwright'
}
$arguments = @($cli, 'install')
if ($DryRun) { $arguments += '--dry-run' }
if ($Browser -ne 'all') { $arguments += $Browser }
& $node @arguments
if ($LASTEXITCODE -ne 0) { throw "Playwright browser installation failed: $LASTEXITCODE" }
