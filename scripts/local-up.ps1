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
# 探测目标（host:port）一律从 .env 读取，不写死 127.0.0.1。.env 目前指向 WSL 网卡
# IP，而该 IP 在 WSL 重启后会变；写死会造成「探测全绿但 alembic 连不上」这种最难
# 排查的失败。同理，.env 若被切到 q19 验收栈（25432/26379/29000），探测也会跟随。
#
# 基础设施容器可能被其他项目共用，因此 -Action down 只停应用进程；要停基础设施
# 请手动执行 wsl -u root -e docker stop postgresql redis MinIO
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

$EnvFile = Join-Path $RepoRoot '.env'

# 基础设施服务表：容器名 + .env 中的 host/port 键 + 容器内的就绪探针。
# Container 只作为查找依据，实际启动用 docker ps -a 里的真实名字（Docker 容器名
# 大小写敏感，而 PowerShell 字符串比较不敏感，写死大小写会 docker start 报 no
# such container）。ReadyCommand 为 $null 表示端口可连接即视为就绪。
$InfraServices = @(
  @{ Label = 'PostgreSQL'; Container = 'postgresql'; HostKey = 'POSTGRES_HOST'; PortKey = 'POSTGRES_PORT'; DefaultPort = 5432; ReadyCommand = @('pg_isready', '-q') },
  @{ Label = 'Redis'; Container = 'redis'; HostKey = 'REDIS_HOST'; PortKey = 'REDIS_PORT'; DefaultPort = 6379; ReadyCommand = $null },
  @{ Label = 'MinIO'; Container = 'MinIO'; HostKey = 'MINIO_HOST'; PortKey = 'MINIO_PORT'; DefaultPort = 9000; ReadyCommand = $null }
)

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

function Get-EnvValues {
  # 与 windows-local.ps1 的 Get-DotEnvValues 保持同样的解析规则（含去引号），
  # 那个函数依赖 windows-local.ps1 的脚本作用域变量，无法跨脚本调用。
  param([string]$Path)
  $values = @{}
  foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
      $value = $Matches[2]
      if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
      $values[$Matches[1]] = $value
    }
  }
  return $values
}

function Invoke-WslDocker {
  param([string[]]$DockerArgs, [switch]$IncludeStderr)
  # WSL 在 NAT 模式下会向 stderr 写 localhost 代理警告。在
  # $ErrorActionPreference='Stop' 下，外部命令写 stderr 会被当成终止错误，
  # 即使加了 2>$null 也一样，因此这里局部降级后再判断退出码。
  # 需要解析 stdout 的调用必须丢弃 stderr，否则代理警告会混进结果；
  # 只看退出码的调用用 -IncludeStderr 保留原因，便于报错时给出根因。
  $previous = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    if ($IncludeStderr) {
      $output = & wsl.exe -u root -e docker @DockerArgs 2>&1
    } else {
      $output = & wsl.exe -u root -e docker @DockerArgs 2>$null
    }
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previous
  }
  return [pscustomobject]@{ ExitCode = $code; Output = $output }
}

function Resolve-InfraTargets {
  # .env 缺失必须在这里失败。否则后端 Settings 会静默回落到 localhost /
  # atp_password_change_me，而本机 5432 上确实有东西在听，alembic 就会连到一个
  # 非预期的库，用户看到的是「alembic upgrade head failed」而不是真正的原因。
  if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing env file: $EnvFile. Run Copy-Item .env.example .env and fill private values."
  }

  $values = Get-EnvValues -Path $EnvFile
  $targets = @()
  foreach ($service in $InfraServices) {
    $hostName = if ($values.ContainsKey($service.HostKey)) { [string]$values[$service.HostKey] } else { '' }
    if ([string]::IsNullOrWhiteSpace($hostName)) {
      throw "$($service.HostKey) is not set in $EnvFile."
    }
    $portText = if ($values.ContainsKey($service.PortKey)) { [string]$values[$service.PortKey] } else { [string]$service.DefaultPort }
    $port = 0
    if (-not [int]::TryParse($portText, [ref]$port)) {
      throw "$($service.PortKey) in $EnvFile is not a valid port: $portText"
    }
    $targets += [pscustomobject]@{
      Label        = $service.Label
      Container    = $service.Container
      HostName     = $hostName
      Port         = $port
      ReadyCommand = $service.ReadyCommand
    }
  }
  return $targets
}

function Start-Infrastructure {
  param([object[]]$Targets)

  Write-Step 'Checking infrastructure containers in WSL Docker'

  if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw 'wsl.exe not found. Start PostgreSQL/Redis/MinIO manually, or rerun with -SkipInfra.'
  }

  $listed = Invoke-WslDocker -DockerArgs @('ps', '-a', '--format', '{{.Names}}|{{.State}}')
  if ($listed.ExitCode -ne 0) {
    throw 'Cannot reach Docker inside WSL. Confirm the WSL distribution and Docker are running.'
  }

  $containers = @{}
  foreach ($line in @($listed.Output | Where-Object { $_ })) {
    $parts = ([string]$line).Split('|')
    if ($parts.Count -ge 2) { $containers[$parts[0]] = $parts[1] }
  }

  $resolved = @{}
  $toStart = @()
  foreach ($target in $Targets) {
    # 取回真实键名再启动：PowerShell 的哈希表查找与 -eq 都不区分大小写，而
    # docker start 区分，直接用表里写死的大小写会报 no such container。
    $actual = @($containers.Keys | Where-Object { $_ -eq $target.Container }) | Select-Object -First 1
    if (-not $actual) {
      Write-Warn "Container '$($target.Container)' not found in WSL Docker; expecting $($target.HostName):$($target.Port) to be served elsewhere"
      continue
    }
    $resolved[$target.Label] = $actual
    if ($containers[$actual] -ne 'running') { $toStart += $actual }
  }

  if ($toStart.Count -eq 0) {
    Write-Ok 'All known infrastructure containers are already running'
  } else {
    Write-Step ('Starting: ' + ($toStart -join ', '))
    $started = Invoke-WslDocker -DockerArgs (@('start') + $toStart) -IncludeStderr
    if ($started.ExitCode -ne 0) {
      throw ('Failed to start ' + ($toStart -join ', ') + ': ' + ((@($started.Output) -join '; ')))
    }
  }

  foreach ($target in $Targets) {
    $endpoint = "$($target.HostName):$($target.Port)"

    # 容器 running 不等于服务可连接。每个端点单独计时：共用一个 deadline 时，
    # 前一个端点耗尽预算会让后面的 while 一次都不执行，把本来可连接的端口
    # 报成不可达。
    $deadline = (Get-Date).AddSeconds($InfraTimeoutSeconds)
    $reachable = $false
    while (-not $reachable) {
      if (Test-TcpPort -TargetHost $target.HostName -Port $target.Port) { $reachable = $true; break }
      if ((Get-Date) -ge $deadline) { break }
      Start-Sleep -Seconds 2
    }
    if (-not $reachable) {
      throw "$($target.Label) endpoint $endpoint unreachable after $InfraTimeoutSeconds seconds. Check the host/port in $EnvFile; the WSL interface IP changes across WSL restarts."
    }

    if ($target.ReadyCommand -and $resolved.ContainsKey($target.Label)) {
      # TCP 可连接仍不等于就绪：PostgreSQL 在恢复期间就已接受连接，但会回
      # FATAL: the database system is starting up，紧接着 alembic 就失败——
      # 正是这个等待本该拦掉的情况。所以再补一次服务级握手。
      $deadline = (Get-Date).AddSeconds($InfraTimeoutSeconds)
      $accepting = $false
      while (-not $accepting) {
        $probe = Invoke-WslDocker -DockerArgs (@('exec', $resolved[$target.Label]) + $target.ReadyCommand)
        if ($probe.ExitCode -eq 0) { $accepting = $true; break }
        if ((Get-Date) -ge $deadline) { break }
        Start-Sleep -Seconds 2
      }
      if (-not $accepting) {
        throw "$($target.Label) at $endpoint accepts TCP but is still not ready after $InfraTimeoutSeconds seconds."
      }
    }

    Write-Ok "$($target.Label) ready at $endpoint"
  }
}

function Update-Database {
  Write-Step 'Upgrading database to alembic head'

  # -SkipInfra 会跳过 Resolve-InfraTargets，因此这里独立再确认一次：缺 .env 时
  # alembic 会连到 Settings 的默认库，报错信息会指向迁移而非真正的配置缺失。
  if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing env file: $EnvFile. Run Copy-Item .env.example .env and fill private values."
  }

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
    Start-Infrastructure -Targets (Resolve-InfraTargets)
  }

  if ($SkipMigrate) {
    Write-Warn 'Skipping migration (-SkipMigrate); the backend only warns when schema is behind'
  } else {
    Update-Database
  }
}

Write-Step "Delegating to windows-local.ps1 -Action $Action"
# 先清零再读：$LASTEXITCODE 只由外部命令和被调脚本的 exit 写入，不清零可能读到
# 之前调用残留的值。windows-local.ps1 的 doctor 分支是 exit (Show-Doctor)，丢掉
# 这个码会让环境损坏的 doctor 也向调用方报成功。沿用 scripts/startup.ps1 的写法。
$global:LASTEXITCODE = 0
& $LocalRunner -Action $Action -Tail $Tail
$delegateExit = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }

if ($delegateExit -eq 0 -and ($Action -eq 'up' -or $Action -eq 'restart')) {
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

exit $delegateExit
