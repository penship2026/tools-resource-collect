#!/usr/bin/env bash
# 集页 · 本地三服务一键启动（macOS）
#
# 用法：
#   double-click docs/start-all.command
#   ./docs/start-all.command              # 启动并打开浏览器，按 Ctrl+C 停止全部
#   ./docs/start-all.command --no-open    # 启动但不打开浏览器
#   ./docs/start-all.command --check      # 只做启动自检，就绪后立即停止
#
# 端口可用环境变量覆盖：WEB_PORT / DESIGN_PORT / COLLECT_PORT
# 日志默认写入：${TMPDIR:-/tmp}/jiye-studio/

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WEB_PORT="${WEB_PORT:-8000}"
DESIGN_PORT="${DESIGN_PORT:-8787}"
COLLECT_PORT="${COLLECT_PORT:-8765}"
TMP_BASE="${TMPDIR:-/tmp}"
TMP_BASE="${TMP_BASE%/}"
LOG_DIR="${JIYE_LOG_DIR:-$TMP_BASE/jiye-studio}"
LOG_DIR="${LOG_DIR%/}"

OPEN_BROWSER=1
CHECK_ONLY=0

usage() {
  cat <<'EOF'
集页本地三服务一键启动

  ./docs/start-all.command              启动并打开浏览器
  ./docs/start-all.command --no-open    启动但不打开浏览器
  ./docs/start-all.command --check      启动自检，通过后自动停止

端口：
  WEB_PORT=8000      网站静态服务
  DESIGN_PORT=8787   模板设计服务
  COLLECT_PORT=8765  采集服务（API + 采集页）

按 Ctrl+C 停止全部服务。日志在 ${TMPDIR:-/tmp}/jiye-studio/。
EOF
}

for arg in "$@"; do
  case "$arg" in
    --no-open) OPEN_BROWSER=0 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "未知参数：$arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$ROOT/index.html" || ! -d "$ROOT/collector" || ! -d "$ROOT/tools/ai-template" ]]; then
  echo "启动失败：$ROOT 不像集页项目根目录。" >&2
  echo "请把本脚本放在项目的 docs/ 目录下再运行。" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "启动失败：找不到 python3。请先安装 Python 3。" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "启动失败：找不到 curl。" >&2
  exit 1
fi

mkdir -p "$LOG_DIR" || {
  echo "启动失败：无法创建日志目录 $LOG_DIR" >&2
  exit 1
}

COLLECT_LOG="$LOG_DIR/collect.log"
DESIGN_LOG="$LOG_DIR/design.log"
WEB_LOG="$LOG_DIR/web.log"
COLLECT_PID=""
DESIGN_PID=""
WEB_PID=""

cleanup() {
  trap - EXIT INT TERM HUP
  echo ""
  echo "正在停止服务..."
  for pid in "$COLLECT_PID" "$DESIGN_PID" "$WEB_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  # 某些环境会忽略 SIGTERM：最多等 2 秒，仍未退出则强制终止
  local i alive
  for ((i = 1; i <= 10; i++)); do
    alive=0
    for pid in "$COLLECT_PID" "$DESIGN_PID" "$WEB_PID"; do
      if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        alive=1
      fi
    done
    [[ "$alive" -eq 0 ]] && break
    sleep 0.2
  done
  for pid in "$COLLECT_PID" "$DESIGN_PID" "$WEB_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$COLLECT_PID" "$DESIGN_PID" "$WEB_PID"; do
    if [[ -n "$pid" ]]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
  echo "已停止。"
}

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

check_port() {
  local name="$1" port="$2"
  if port_in_use "$port"; then
    echo "启动失败：$name 端口 $port 已被占用。" >&2
    echo "占用进程：" >&2
    lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | sed -n '1,5p' >&2
    echo "可换端口，例如：WEB_PORT=8010 DESIGN_PORT=8797 COLLECT_PORT=8775 ./docs/start-all.command" >&2
    exit 1
  fi
}

wait_ready() {
  local name="$1" url="$2" pid="$3" log="$4"
  local i
  for ((i = 1; i <= 60; i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "启动失败：$name 进程已退出。" >&2
      echo "--- $log（最后 20 行）---" >&2
      tail -n 20 "$log" >&2 || true
      return 1
    fi
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      echo "  ✓ $name 已就绪  $url"
      return 0
    fi
    sleep 0.5
  done
  echo "启动失败：$name 在 30 秒内未就绪。" >&2
  echo "--- $log（最后 20 行）---" >&2
  tail -n 20 "$log" >&2 || true
  return 1
}

open_url() {
  if [[ "$OPEN_BROWSER" -eq 1 ]] && command -v open >/dev/null 2>&1; then
    open "$1" >/dev/null 2>&1 || true
  fi
}

check_port "网站服务" "$WEB_PORT"
check_port "设计服务" "$DESIGN_PORT"
check_port "采集服务" "$COLLECT_PORT"

: >"$COLLECT_LOG"
: >"$DESIGN_LOG"
: >"$WEB_LOG"

cd "$ROOT" || exit 1

trap cleanup EXIT INT TERM HUP

echo "集页 · 本地三服务启动中"
echo "项目：$ROOT"
echo "日志：$LOG_DIR"
echo ""

# 1) 采集服务：只提供 /api/*、采集页与设置页，静态展示交给独立网站服务
python3 collector/server.py --api-only --port "$COLLECT_PORT" >>"$COLLECT_LOG" 2>&1 &
COLLECT_PID=$!

# 2) 设计服务：模板 IDE、旧评审页、设计管理处
python3 tools/ai-template/cli.py serve --port "$DESIGN_PORT" >>"$DESIGN_LOG" 2>&1 &
DESIGN_PID=$!

# 3) 网站服务：本地静态预览，只绑定 127.0.0.1；no-store，采集后刷新即见新数据
python3 scripts/site_server.py --port "$WEB_PORT" >>"$WEB_LOG" 2>&1 &
WEB_PID=$!

wait_ready "采集服务" "http://127.0.0.1:${COLLECT_PORT}/api/health" "$COLLECT_PID" "$COLLECT_LOG" || exit 1
wait_ready "设计服务" "http://127.0.0.1:${DESIGN_PORT}/" "$DESIGN_PID" "$DESIGN_LOG" || exit 1
wait_ready "网站服务" "http://127.0.0.1:${WEB_PORT}/index.html" "$WEB_PID" "$WEB_LOG" || exit 1

echo ""
echo "服务地址："
echo "  网站服务  http://127.0.0.1:${WEB_PORT}/"
echo "  采集服务  http://127.0.0.1:${COLLECT_PORT}/collect.html"
echo "  采集设置  http://127.0.0.1:${COLLECT_PORT}/settings.html"
echo "  设计服务  http://127.0.0.1:${DESIGN_PORT}/"
echo "  设计评审  http://127.0.0.1:${DESIGN_PORT}/review"
echo "  设计管理  http://127.0.0.1:${DESIGN_PORT}/manage.html"
echo ""

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo "自检通过，正在停止服务。"
  exit 0
fi

open_url "http://127.0.0.1:${WEB_PORT}/"
open_url "http://127.0.0.1:${COLLECT_PORT}/collect.html"
open_url "http://127.0.0.1:${DESIGN_PORT}/"

echo "浏览器已打开。按 Ctrl+C 停止全部服务；关闭此终端也会停止。"
echo "后台日志：$LOG_DIR"

while :; do
  for pair in "采集服务:$COLLECT_PID" "设计服务:$DESIGN_PID" "网站服务:$WEB_PID"; do
    name="${pair%%:*}"
    pid="${pair##*:}"
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "服务异常退出：$name（PID $pid），请查看日志 $LOG_DIR。" >&2
      exit 1
    fi
  done
  sleep 2
done
