# ATP 本地一键启动入口。
#
# 应用进程（Backend / Celery Worker / Beat / Frontend）的启停仍由
# scripts/windows-local.ps1 负责，本脚本只补齐它不覆盖的两步：
#   1. 确认 .env 指向的 PostgreSQL / Redis / MinIO 已在 WSL Docker 中运行；
#   2. 启动应用前把数据库升级到 alembic head。
#
# 第 2 步是必要的：schema 由 Alembic 管理，后端启动时只「警告」数据库不在 head，
# 不会自动升级，落后的 schema 会在运行期报错而不是启动期。
#
# 基础设施容器使用 .env 的标准端口（5432/6379/9000），与 q19 验收栈
# （25432/26379/29000）互不冲突。这些容器可能被其他项目共用，因此
# -Action down 只停应用进程；要停基础设施请手动执行
# wsl -u root -e docker stop postgresql redis MinIO
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/local-up.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/local-up.ps1 -Action status
#   powershell -ExecutionPolicy Bypass -File scripts/local-up.ps1 -Action down
#   powershell -ExecutionPolicy Bypass -File scripts/local-up.ps1 -SkipMigrate

param(
  [ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')]
  [string]$Action = 'up',
  [switch]$SkipInfra,
  [switch]$SkipMigrate,
  [ValidateRange(10, 300)]
  [int]$InfraTimeoutSeconds = 90,
  [ValidateRange(20, 500)]
  [int]$Tail = 120
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LocalRunner = Join-Path $PSScriptRoot 'windows-local.ps1'
$BackendDir = Join-Path $RepoRoot 'backend'
$BackendPython = Join-Path $BackendDir '.venv\Scripts\python.exe'

# .env 指向的基础设施容器名。MinIO 大小写敏感，与 docker ps 输出一致。
$InfraContainers = @('postgresql', 'redis', 'MinIO')
$InfraPorts = @(5432, 6379, 9000)

function Write-Step {
  param([string]$Message)
  Write-Host "[step] $Message" -ForegroundColor Cyan
}

function Write-Ok {
  param([string]$Message)
  Write-Host "[ok]   $Message" -ForegroundColor Green
}

function Write-Warn {
  param([string]$Message)
  Write-Host "[warn] $Message" -ForegroundColor Yellow
}

function Test-TcpPort {
  param([string]$TargetHost, [int]$Port, [int]$TimeoutMs = 2000)
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs)) { return $false }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Invoke-WslDocker {
  param([string[]]$DockerArgs)
  # WSL 在 NAT 模式下会向 stderr 写 localhost 代理警告。在
  # $ErrorActionPreference='Stop' 下，外部命令写 stderr 会被当成终止错误，
  # 即使加了 2>$null 也一样，因此这里局部降级后再判断退出码。
  $previous = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $output = & wsl.exe -u root -e docker @DockerArgs 2>$null
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previous
  }
  return [pscustomobject]@{ ExitCode = $code; Output = $output }
}

function Start-Infrastructure {
  Write-Step 'Checking infrastructure containers in WSL Docker'

  if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw 'wsl.exe not found. Start PostgreSQL/Redis/MinIO manually, or rerun with -SkipInfra.'
  }

  $running = Invoke-WslDocker -DockerArgs @('ps', '--format', '{{.Names}}')
  if ($running.ExitCode -ne 0) {
    throw 'Cannot reach Docker inside WSL. Confirm the WSL distribution and Docker are running.'
  }

  $runningNames = @($running.Output | Where-Object { $_ })
  $toStart = @($InfraContainers | Where-Object { $runningNames -notcontains $_ })

  if ($toStart.Count -eq 0) {
    Write-Ok 'All infrastructure containers are already running'
  } else {
    Write-Step ('Starting: ' + ($toStart -join ', '))
    $started = Invoke-WslDocker -DockerArgs (@('start') + $toStart)
    if ($started.ExitCode -ne 0) {
      throw ('Failed to start: ' + ($toStart -join ', ') + ". Check 'wsl -u root -e docker ps -a'.")
    }
  }

  # 容器 running 不等于服务可连接，必须等端口真正就绪。宿主重启后出现过
  # 容器已启动但 PostgreSQL 仍拒绝连接的情况。
  $deadline = (Get-Date).AddSeconds($InfraTimeoutSeconds)
  foreach ($port in $InfraPorts) {
    $ready = $false
    while ((Get-Date) -lt $deadline) {
      if (Test-TcpPort -TargetHost '127.0.0.1' -Port $port) {
        $ready = $true
        break
      }
      Start-Sleep -Seconds 2
    }
    if (-not $ready) {
      throw "Port $port did not become reachable within $InfraTimeoutSeconds seconds."
    }
    Write-Ok "Infrastructure port $port reachable"
  }
}

function Update-Database {
  Write-Step 'Upgrading database to alembic head'

  if (-not (Test-Path -LiteralPath $BackendPython)) {
    throw "Backend virtual environment not found: $BackendPython. Run 'make setup' first."
  }

  Push-Location $BackendDir
  try {
    # alembic 把 INFO 日志写到 stderr；同样需要局部降级，否则正常的迁移日志
    # 会在 $ErrorActionPreference='Stop' 下被当成终止错误。
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $BackendPython -m alembic upgrade head 2>&1 | ForEach-Object { Write-Host $_ }
      $code = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $previous
    }
    if ($code -ne 0) {
      throw 'alembic upgrade head failed. Resolve the migration error before starting the app.'
    }
  } finally {
    Pop-Location
  }
  Write-Ok 'Database is at alembic head'
}

if (-not (Test-Path -LiteralPath $LocalRunner)) {
  throw "Missing application runner: $LocalRunner"
}

if ($Action -eq 'up' -or $Action -eq 'restart') {
  if ($SkipInfra) {
    Write-Warn 'Skipping infrastructure check (-SkipInfra)'
  } else {
    Start-Infrastructure
  }

  if ($SkipMigrate) {
    Write-Warn 'Skipping migration (-SkipMigrate); the backend only warns when schema is behind'
  } else {
    Update-Database
  }
}

Write-Step "Delegating to windows-local.ps1 -Action $Action"
& $LocalRunner -Action $Action -Tail $Tail

if ($Action -eq 'up' -or $Action -eq 'restart') {
  Write-Host ''
  Write-Ok 'Local stack is up'
  Write-Host '  Frontend : http://127.0.0.1:5173/login'
  Write-Host '  Backend  : http://127.0.0.1:8000/health'
  Write-Host '  API docs : http://127.0.0.1:8000/docs'
  Write-Host ''
  Write-Host '  Status   : powershell -ExecutionPolicy Bypass -File scripts/local-up.ps1 -Action status'
  Write-Host '  Logs     : powershell -ExecutionPolicy Bypass -File scripts/local-up.ps1 -Action logs'
  Write-Host '  Stop app : powershell -ExecutionPolicy Bypass -File scripts/local-up.ps1 -Action down'
  Write-Host ''
  Write-Warn 'Sign in with the account stored in the database, not FIRST_ADMIN_PASSWORD from .env:'
  Write-Warn 'FIRST_ADMIN_* only seeds the very first boot, so a later password change makes .env stale.'
}
