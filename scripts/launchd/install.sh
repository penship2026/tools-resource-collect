#!/bin/bash
# 安装 / 卸载本机 launchd 定时采集(兜底调度)。
#
# 用法:
#   scripts/launchd/install.sh                          # 生成 plist(默认 08:10),不装载
#   scripts/launchd/install.sh --load                   # 生成并装载
#   scripts/launchd/install.sh --hour 8 --minute 30 --load
#   scripts/launchd/install.sh --uninstall              # 卸载并删除 plist
#
# 注意:与 GitHub Actions(每天 07:00)错开时间,不要同时跑;两者都写 assets/data,
# 同时执行会互相覆盖,约定「先提交者为准」。

set -euo pipefail

LABEL="com.jiye.collect"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$ROOT/scripts/launchd/com.jiye.collect.plist.in"
HOUR=8
MINUTE=10
DO_LOAD=0
DO_UNINSTALL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hour) HOUR="$2"; shift 2 ;;
    --minute) MINUTE="$2"; shift 2 ;;
    --load) DO_LOAD=1; shift ;;
    --uninstall) DO_UNINSTALL=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

if [[ "$DO_UNINSTALL" == "1" ]]; then
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
  rm -f "$DEST"
  echo "已卸载 $LABEL,并删除 $DEST"
  exit 0
fi

if [[ ! -x "$ROOT/scripts/launchd/collect.sh" ]]; then
  chmod +x "$ROOT/scripts/launchd/collect.sh"
fi

# 路径里可能含空格与中文,替换时转义 sed 的特殊字符
ROOT_ESC="${ROOT//\\/\\\\}"
ROOT_ESC="${ROOT_ESC//&/\\&}"
ROOT_ESC="${ROOT_ESC//|/\\|}"

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__LABEL__|$LABEL|g" \
    -e "s|__ROOT__|$ROOT_ESC|g" \
    -e "s|__HOUR__|$HOUR|g" \
    -e "s|__MINUTE__|$MINUTE|g" \
    "$TEMPLATE" > "$DEST"

plutil -lint "$DEST" >/dev/null
echo "已生成: $DEST (每天 ${HOUR}:$(printf '%02d' "$MINUTE"))"

if [[ "$DO_LOAD" == "1" ]]; then
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$UID" "$DEST"
  echo "已装载。立即试跑一次: launchctl kickstart -k gui/$UID/$LABEL"
  echo "查看状态: launchctl print gui/$UID/$LABEL | head -20"
else
  echo "未装载。确认无误后执行:"
  echo "  launchctl bootstrap gui/$UID \"$DEST\""
fi

echo "日志: $ROOT/logs/launchd.out.log 与 launchd.err.log(采集脚本自身输出也写这里)"
echo "卸载: $ROOT/scripts/launchd/install.sh --uninstall"
