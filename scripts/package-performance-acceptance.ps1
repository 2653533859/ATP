[CmdletBinding()]
param(
  [string]$OutputPath = '',
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $OutputPath = Join-Path $repoRoot (Join-Path '.local-run' "atp-performance-acceptance-$timestamp.zip")
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
    throw "Output or checksum file already exists: $OutputPath. Use -Force to replace those exact files."
  }
}

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) "atp-performance-acceptance-$([guid]::NewGuid().ToString('N'))"
$manifestPath = Join-Path $stageRoot 'bundle-manifest.json'

$explicitFiles = @(
  '.env.performance-acceptance.example',
  'docker-compose.performance-acceptance.yml',
  'docs/performance-environment-acceptance.md',
  'deploy/performance-acceptance/acceptance.proto',
  'deploy/performance-acceptance/Dockerfile.target',
  'deploy/performance-acceptance/Dockerfile.tools',
  'deploy/performance-acceptance/jmeter_smoke.jmx',
  'deploy/performance-acceptance/locust_smoke.py',
  'scripts/performance-environment-smoke.py',
  'scripts/performance_acceptance_target.py'
)
$sourceDirectories = @('backend')
$excludedDirectoryNames = @(
  '.git',
  '.mypy_cache',
  '.pytest_cache',
  '.venv',
  '.venv314',
  '__pycache__',
  'tests'
)
$excludedFileNames = @(
  '.coverage',
  'celerybeat-schedule.bak',
  'celerybeat-schedule.dat',
  'celerybeat-schedule.dir',
  'jmeter.log'
)

function Get-RelativeRepoPath {
  param([Parameter(Mandatory)][string]$Path)

  $relative = $Path.Substring($repoRoot.Length).TrimStart([char[]]@('\', '/'))
  return $relative.Replace('\', '/')
}

function Copy-BundleFile {
  param([Parameter(Mandatory)][string]$RelativePath)

  $sourcePath = Join-Path $repoRoot $RelativePath
  if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "Required bundle file does not exist: $RelativePath"
  }

  $normalizedRelative = $RelativePath.Replace('\', '/')
  if ($normalizedRelative -match '(^|/)(\.env(?!\.performance-acceptance\.example$)|.*\.(key|pem|p12|pfx))$') {
    throw "Refusing to package a possible secret file: $RelativePath"
  }

  $destinationPath = Join-Path $stageRoot ($normalizedRelative.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
  $destinationDirectory = [System.IO.Path]::GetDirectoryName($destinationPath)
  New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
  Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
}

function Get-GitValue {
  param([Parameter(Mandatory)][string[]]$Arguments)

  try {
    $gitOutput = @(& git -C $repoRoot @Arguments 2>$null)
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
      $value = $gitOutput | Select-Object -First 1
      return [string]$value
    }
  } catch {
    # A source archive may be produced outside a Git checkout.
  }
  return ''
}

function Write-PortableZip {
  param(
    [Parameter(Mandatory)][string]$SourceRoot,
    [Parameter(Mandatory)][string]$DestinationPath
  )

  Add-Type -AssemblyName System.IO.Compression
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::Open(
    $DestinationPath,
    [System.IO.Compression.ZipArchiveMode]::Create
  )
  try {
    Get-ChildItem -LiteralPath $SourceRoot -File -Recurse -Force | ForEach-Object {
      $relativePath = $_.FullName.Substring($SourceRoot.Length).TrimStart([char[]]@('\', '/')).Replace('\', '/')
      $entry = $archive.CreateEntry($relativePath, [System.IO.Compression.CompressionLevel]::Optimal)
      $inputStream = [System.IO.File]::OpenRead($_.FullName)
      $outputStream = $entry.Open()
      try {
        $inputStream.CopyTo($outputStream)
      } finally {
        $outputStream.Dispose()
        $inputStream.Dispose()
      }
    }
  } finally {
    $archive.Dispose()
  }
}

try {
  New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

  foreach ($relativePath in $explicitFiles) {
    Copy-BundleFile -RelativePath $relativePath
  }

  foreach ($relativeDirectory in $sourceDirectories) {
    $sourceRoot = Join-Path $repoRoot $relativeDirectory
    if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
      throw "Required bundle directory does not exist: $relativeDirectory"
    }

    Get-ChildItem -LiteralPath $sourceRoot -File -Recurse -Force | ForEach-Object {
      $relativePath = Get-RelativeRepoPath -Path $_.FullName
      $segments = $relativePath -split '/'
      if ($segments | Where-Object { $_ -in $excludedDirectoryNames }) {
        return
      }
      if ($_.Name -in $excludedFileNames) {
        return
      }
      if ($_.Name -match '^\.env($|\.)' -and $_.Name -ne '.env.performance-acceptance.example') {
        return
      }
      if ($_.Name -match '\.(key|pem|p12|pfx)$') {
        return
      }
      Copy-BundleFile -RelativePath $relativePath
    }
  }

  $bundleFiles = @(Get-ChildItem -LiteralPath $stageRoot -File -Recurse -Force | Where-Object { $_.FullName -ne $manifestPath })
  if ($bundleFiles.Count -eq 0) {
    throw 'The performance acceptance bundle is empty.'
  }

  $fileEntries = @(
    foreach ($file in ($bundleFiles | Sort-Object FullName)) {
      $relativePath = $file.FullName.Substring($stageRoot.Length).TrimStart([char[]]@('\', '/')).Replace('\', '/')
      [ordered]@{
        path = $relativePath
        bytes = $file.Length
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
      }
    }
  )

  $manifest = [ordered]@{
    schema_version = 1
    created_at_utc = [DateTime]::UtcNow.ToString('o')
    source_commit = Get-GitValue -Arguments @('rev-parse', 'HEAD')
    worktree_dirty = -not [string]::IsNullOrWhiteSpace((Get-GitValue -Arguments @('status', '--porcelain')))
    purpose = 'ATP isolated Linux/Kubernetes performance acceptance bundle'
    files = $fileEntries
  }
  $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8

  if (Test-Path -LiteralPath $OutputPath -PathType Leaf) {
    Remove-Item -LiteralPath $OutputPath -Force
  }
  if (Test-Path -LiteralPath $sidecarPath -PathType Leaf) {
    Remove-Item -LiteralPath $sidecarPath -Force
  }
  Write-PortableZip -SourceRoot $stageRoot -DestinationPath $OutputPath

  $archiveHash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
  "$archiveHash  $([System.IO.Path]::GetFileName($OutputPath))" | Set-Content -LiteralPath $sidecarPath -Encoding ascii

  [ordered]@{
    output = $OutputPath
    sha256_file = $sidecarPath
    sha256 = $archiveHash
    file_count = $fileEntries.Count
    source_commit = $manifest.source_commit
    worktree_dirty = $manifest.worktree_dirty
  } | ConvertTo-Json -Depth 5 -Compress | Write-Output
} finally {
  if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
  }
}
