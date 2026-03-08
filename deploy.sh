#!/usr/bin/env bash
#
# ATP 自动化测试平台 — 一键部署脚本
#
# 用法: ./deploy.sh [up|down|restart|logs|status]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

# ── 颜色 ──────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── 前置检查 ──────────────────────────────
check_deps() {
    for cmd in docker; do
        if ! command -v "$cmd" &>/dev/null; then
            error "$cmd 未安装，请先安装后重试"
            exit 1
        fi
    done

    if ! docker compose version &>/dev/null; then
        error "docker compose 不可用，请确认 Docker Compose V2 已安装"
        exit 1
    fi
}

# ── 初始化 .env ───────────────────────────
init_env() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_EXAMPLE" ]; then
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            warn ".env 文件不存在，已从 .env.example 复制"
            warn "请编辑 .env 修改密码等敏感配置后重新运行"
            exit 0
        else
            error ".env.example 文件不存在"
            exit 1
        fi
    fi
}

# ── 命令 ──────────────────────────────────
cmd_up() {
    info "启动 ATP 平台..."
    docker compose up -d --build
    info "等待服务就绪..."
    sleep 5
    cmd_status
    echo ""
    info "部署完成！"
    info "  前端:        http://localhost:80"
    info "  后端 API:    http://localhost:80/api/v1"
    info "  MinIO 控制台: http://localhost:9001"
    info "  Flower 监控:  http://localhost:5555"
    info "  默认管理员:   admin / Admin@123456"
}

cmd_down() {
    info "停止 ATP 平台..."
    docker compose down
    info "已停止"
}

cmd_restart() {
    info "重启 ATP 平台..."
    docker compose restart
    info "已重启"
}

cmd_logs() {
    docker compose logs -f --tail=100 "${@:2}"
}

cmd_status() {
    docker compose ps
}

# ── 主入口 ────────────────────────────────
main() {
    check_deps
    init_env

    local action="${1:-up}"
    case "$action" in
        up)      cmd_up ;;
        down)    cmd_down ;;
        restart) cmd_restart ;;
        logs)    cmd_logs "$@" ;;
        status)  cmd_status ;;
        *)
            echo "用法: $0 [up|down|restart|logs|status]"
            echo ""
            echo "  up       构建并启动所有服务（默认）"
            echo "  down     停止并移除所有容器"
            echo "  restart  重启所有服务"
            echo "  logs     查看日志（可指定服务名）"
            echo "  status   查看服务状态"
            exit 1
            ;;
    esac
}

main "$@"
