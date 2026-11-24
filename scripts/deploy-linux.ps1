<#
.SYNOPSIS
  ATP Linux 服务端自动化发布脚本（发布至 192.168.3.196:2222）。

.DESCRIPTION
  完成以下自动化闭环：
  1. 连通性检查与分支检测（在 HookMode 下非 main 或无法连接时安全跳过，不阻塞 push）；
  2. 幂等检测：比对本地 commit 与远端实际运行镜像 tag，相同则跳过；
  3. 前端生产构建（npm run build / vue-tsc + vite build）；
  4. 归档打包源码（backend + deploy）与前端构建产物（dist）；
  5. 远端数据库自动备份（pg_dump -F c 到 release 目录）；
  6. 上传归档并在远端基于当前基础镜像构建 overlay 镜像（backend、worker、frontend）；
  7. 导入镜像至 K3s containerd；
  8. 执行 Helm upgrade 与 cloud-web 容器重启；
  9. 服务健康探针检测（/health、/runtime、Web 8080 端口）；
  10. 自动清理本地临时构建包。

.PARAMETER ServerHost
  目标 Linux 主机地址（默认 192.168.3.196）。

.PARAMETER ServerPort
  目标 SSH 端口（默认 2222）。

.PARAMETER ServerUser
  目标 SSH 用户（默认 root）。

.PARAMETER HookMode
  若指定，表示作为 Git 钩子（如 pre-push）运行：
  - 若设置了 ATP_SKIP_DEPLOY=1 则静默跳过；
  - 若目标分支不是 main 则静默跳过；
  - 若网络不可达（2s 超时）则告警跳过，避免阻断 push。

.PARAMETER Force
  忽略幂等检查，强制重新构建与部署。

.PARAMETER SkipBuild
  跳过本地前端 npm run build 步骤（直接使用现有 frontend/dist）。
#>
[CmdletBinding()]
param(
  [string]$ServerHost = '192.168.3.196',
  [int]$ServerPort = 2222,
  [string]$ServerUser = 'root',
  [string]$AdbScanMode = '',
  [string]$AdbServerSocket = '',
  [switch]$HookMode,
  [switch]$Force,
  [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $RepoRoot 'frontend'
$BackendDir = Join-Path $RepoRoot 'backend'

function Log-Info([string]$msg)  { Write-Host "[deploy-linux] $msg" -ForegroundColor Cyan }
function Log-Ok([string]$msg)    { Write-Host "[deploy-linux] $msg" -ForegroundColor Green }
function Log-Warn([string]$msg)  { Write-Host "[deploy-linux] WARN: $msg" -ForegroundColor Yellow }
function Log-Error([string]$msg) { Write-Host "[deploy-linux] ERROR: $msg" -ForegroundColor Red }

$sshTarget = "${ServerUser}@${ServerHost}"
$sshOpts = @('-p', $ServerPort, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=2', '-o', 'StrictHostKeyChecking=accept-new')
$scpOpts = @('-P', $ServerPort, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=accept-new')

# 1. 钩子模式下的快速旁路检查
if ($HookMode) {
  if ($env:ATP_SKIP_DEPLOY -in @('1', 'true', 'TRUE', 'yes', 'YES') -or $env:SKIP_DEPLOY -in @('1', 'true', 'TRUE', 'yes', 'YES')) {
    Log-Info "检测到环境变量 ATP_SKIP_DEPLOY，跳过 Linux 服务端自动部署。"
    exit 0
  }

  $rawRef = if ($env:PRE_COMMIT_REMOTE_BRANCH) {
    $env:PRE_COMMIT_REMOTE_BRANCH
  } elseif ($env:PRE_COMMIT_LOCAL_BRANCH) {
    $env:PRE_COMMIT_LOCAL_BRANCH
  } else {
    try {
      (& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null).Trim()
    } catch {
      'unknown'
    }
  }
  $targetBranch = $rawRef -replace '^refs/heads/', '' -replace '^origin/', ''

  if ($targetBranch -ne 'main') {
    Log-Info "当前推送分支为 '$targetBranch'（非 'main'），跳过 Linux 服务端部署。"
    exit 0
  }

  # 快速 SSH 连通性探测（2秒超时），无法连接时不阻断 git push
  $oldEap = $ErrorActionPreference
  $ErrorActionPreference = 'SilentlyContinue'
  & ssh @sshOpts $sshTarget "exit 0" 2>$null
  $sshStatus = $LASTEXITCODE
  $ErrorActionPreference = $oldEap
  if ($sshStatus -ne 0) {
    Log-Warn "无法通过 SSH 连通 Linux 服务端 $ServerHost`:$ServerPort（可能未连接局域网），跳过自动部署。"
    exit 0
  }
}

# 2. 获取当前 Commit SHA
$currentCommit = (& git -C $RepoRoot rev-parse --short HEAD).Trim()
if ([string]::IsNullOrWhiteSpace($currentCommit)) {
  Log-Error "无法解析当前本地 Git 提交哈希。"
  exit 1
}

$dateStr = Get-Date -Format 'yyyyMMdd'
$releaseDir = "/opt/atp-release-$currentCommit-$dateStr"

Log-Info "准备部署 commit '$currentCommit' 至 $ServerHost`:$ServerPort ..."

# 3. 幂等比对：检查远端当前运行的后端镜像 Tag
if (-not $Force) {
  try {
    $remoteImage = (& ssh @sshOpts $sshTarget "kubectl get deployment atp-single-node-atp-backend -n atp-single-node -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null").Trim()
    if ($remoteImage -match ':([^:]+)$') {
      $remoteTag = $Matches[1]
      if ($remoteTag -eq $currentCommit) {
        Log-Ok "服务端当前运行版本正是 '$currentCommit'，线上已是最新状态，跳过重复构建与割接。"
        exit 0
      }
    }
  } catch {
    Log-Warn "查询远端版本失败，将继续执行标准发布流程。"
  }
}

$sourceTar = Join-Path $RepoRoot "source-$currentCommit.tar"
$frontendTar = Join-Path $RepoRoot "frontend-dist-$currentCommit.tar.gz"

try {
  # 4. 前端构建
  if (-not $SkipBuild) {
    Log-Info "执行前端生产构建..."
    $npmCmd = if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { 'npm.cmd' } else { 'npm' }
    Push-Location $FrontendDir
    try {
      & $npmCmd run build
      if ($LASTEXITCODE -ne 0) {
        throw "前端构建失败 (exit code $LASTEXITCODE)"
      }
    } finally {
      Pop-Location
    }
  } else {
    Log-Info "跳过前端构建，复用现有 frontend/dist..."
  }

  $frontendDist = Join-Path $FrontendDir 'dist'
  if (-not (Test-Path -LiteralPath $frontendDist)) {
    throw "未找到前端构建产物目录: $frontendDist"
  }

  $sourceFileName = "source-$currentCommit.tar"
  $frontendFileName = "frontend-dist-$currentCommit.tar.gz"

  # 5. 打包归档（源码严格使用 git archive 导出指定提交，杜绝混入工作区未提交脏文件或本地 .env）
  Log-Info "打包已提交源码 ($currentCommit) 与前端产物..."
  Push-Location $RepoRoot
  try {
    & git -C $RepoRoot archive --format=tar -o $sourceFileName $currentCommit backend deploy
    if ($LASTEXITCODE -ne 0) { throw "git archive 打包源码失败" }

    Push-Location $FrontendDir
    try {
      & tar -czf "../$frontendFileName" dist
      if ($LASTEXITCODE -ne 0) { throw "打包前端产物失败" }
    } finally {
      Pop-Location
    }
  } finally {
    Pop-Location
  }

  # 6. 远端目录创建与数据库安全备份
  Log-Info "远端创建发布目录并备份线上数据库..."
  $preflightCmd = "set -e; mkdir -p $releaseDir; docker exec atp-q19-acceptance-20260824-postgres-1 pg_dump -U atp_runtime -d atp_acceptance -F c -b > $releaseDir/pre-release-atp.dump; ls -lh $releaseDir/pre-release-atp.dump"
  & ssh @sshOpts $sshTarget $preflightCmd
  if ($LASTEXITCODE -ne 0) {
    throw "远端前置安全备份执行失败"
  }

  # 7. 上传产物归档
  Log-Info "上传产物归档至服务端..."
  Push-Location $RepoRoot
  try {
    & scp @scpOpts $sourceFileName $frontendFileName "${sshTarget}:${releaseDir}/"
  } finally {
    Pop-Location
  }
  if ($LASTEXITCODE -ne 0) {
    throw "上传产物到远端失败"
  }

  # 8. 远端解包、构建镜像、导入 K3s 并割接 Helm
  # 等待 K3s 各核心 Deployment 滚动完成后再启动 cloud-web，避开并发网络规则竞争。
  Log-Info "远端解包、构建镜像并割接 K3s / Cloud-Web..."
  $helmConfigLines = ""
  if (-not [string]::IsNullOrWhiteSpace($AdbScanMode) -or -not [string]::IsNullOrWhiteSpace($AdbServerSocket)) {
    $helmConfigLines = "config:`n"
    if (-not [string]::IsNullOrWhiteSpace($AdbScanMode)) {
      $helmConfigLines += "  ADB_SCAN_MODE: $($AdbScanMode.Trim())`n"
    }
    if (-not [string]::IsNullOrWhiteSpace($AdbServerSocket)) {
      $helmConfigLines += "  ADB_SERVER_SOCKET: $($AdbServerSocket.Trim())`n"
    }
  }
  $remoteCommands = @(
    "set -eo pipefail",
    "cd $releaseDir",
    "tar -xf source-$currentCommit.tar",
    "tar -xzf frontend-dist-$currentCommit.tar.gz",
    "printf 'ARG BASE_IMAGE=registry.local/atp/backend:42b8558f
FROM `${BASE_IMAGE}
RUN cp /app/requirements.txt /tmp/base-requirements.txt 2>/dev/null || touch /tmp/base-requirements.txt
COPY backend/ /app/
RUN if ! cmp -s /tmp/base-requirements.txt /app/requirements.txt; then pip install --no-cache-dir -r /app/requirements.txt; fi && rm -f /tmp/base-requirements.txt && chmod 0755 /app/docker-start.sh && find /app -type d -name __pycache__ -exec rm -rf {} +
LABEL org.opencontainers.image.revision=$currentCommit
' > Dockerfile.overlay",
    "printf 'FROM registry.local/atp/frontend:42b8558f
RUN rm -rf /usr/share/nginx/html/*
COPY dist/ /usr/share/nginx/html/
LABEL org.opencontainers.image.revision=$currentCommit
' > Dockerfile.frontend",
    "printf 'image:
  backend:
    tag: $currentCommit
    pullPolicy: Never
  worker:
    tag: $currentCommit
    pullPolicy: Never
worker:
  imageTag: $currentCommit
performanceWorker:
  imageTag: $currentCommit
$helmConfigLines' > site-image-overrides.yaml",
    "mkdir -p cloud-web",
    "printf 'services:
  atp-web:
    image: registry.local/atp/frontend:$currentCommit
    container_name: atp-cloud-web
    restart: unless-stopped
    ports:
      - `${ATP_WEB_BIND_IP:-127.0.0.1}:`${ATP_WEB_PORT:-8080}:80
    extra_hosts:
      - host.docker.internal:host-gateway
    healthcheck:
      test: [CMD, wget, -q, -O, /dev/null, http://127.0.0.1/]
      interval: 30s
      timeout: 5s
      retries: 3
' > cloud-web/compose.yaml",
    "printf 'ATP_WEB_BIND_IP=192.168.3.196
ATP_WEB_PORT=8080
' > cloud-web/.env",
    "docker build -f Dockerfile.overlay --build-arg BASE_IMAGE=registry.local/atp/backend:42b8558f -t registry.local/atp/backend:$currentCommit .",
    "docker build -f Dockerfile.overlay --build-arg BASE_IMAGE=registry.local/atp/worker:42b8558f -t registry.local/atp/worker:$currentCommit .",
    "docker build -f Dockerfile.frontend -t registry.local/atp/frontend:$currentCommit .",
    "docker save registry.local/atp/backend:$currentCommit | k3s ctr images import -",
    "docker save registry.local/atp/worker:$currentCommit | k3s ctr images import -",
    "helm upgrade atp-single-node deploy/helm/atp -n atp-single-node --reuse-values -f site-image-overrides.yaml | tee helm-upgrade.log",
    "kubectl -n atp-single-node rollout status deployment/atp-single-node-atp-backend --timeout=120s",
    "kubectl -n atp-single-node rollout status deployment/atp-single-node-atp-worker --timeout=120s",
    "kubectl -n atp-single-node rollout status deployment/atp-single-node-atp-beat --timeout=120s",
    "(cd cloud-web && docker compose up -d)",
    "iptables -C DOCKER-USER -p tcp --dport 80 -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER 1 -p tcp --dport 80 -j ACCEPT"
  ) -join " && "

  & ssh @sshOpts $sshTarget $remoteCommands
  if ($LASTEXITCODE -ne 0) {
    throw "远端构建与割接执行失败"
  }

  # 9. 探针验证
  Log-Info "执行线上服务健康探针..."
  $probeCmd = "curl -sS -f --retry 5 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/health > /dev/null && curl -sS -f --retry 5 --retry-delay 1 --retry-connrefused http://127.0.0.1:8000/api/v1/runtime > /dev/null && curl -sS -f --retry 5 --retry-delay 1 --retry-connrefused -I http://192.168.3.196:8080/ > /dev/null && curl -sS -f --retry 5 --retry-delay 1 --retry-connrefused http://192.168.3.196:8080/api/v1/runtime > /dev/null && echo 'PROBE_ALL_OK'"
  $probeRaw = & ssh @sshOpts $sshTarget $probeCmd
  $probeExit = $LASTEXITCODE
  $probeOutput = (($probeRaw | ForEach-Object { "$_" }) -join "`n").Trim()
  if ($probeExit -ne 0 -or $probeOutput -notmatch 'PROBE_ALL_OK') {
    throw "线上健康探针未通过 (exit=$probeExit)"
  }

  Log-Ok "服务端已成功发布并验证通过！版本: $currentCommit"
  Log-Ok "Web 入口: http://${ServerHost}:8080/ | 后端: http://${ServerHost}:8000/api/v1"
} finally {
  # 10. 清理本地临时归档
  if (Test-Path -LiteralPath $sourceTar) {
    Remove-Item -LiteralPath $sourceTar -Force -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $frontendTar) {
    Remove-Item -LiteralPath $frontendTar -Force -ErrorAction SilentlyContinue
  }
}
