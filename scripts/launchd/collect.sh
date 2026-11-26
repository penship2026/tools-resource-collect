#!/bin/bash
# 本机兜底采集:由 launchd 每天调用(见 scripts/launchd/install.sh)。
#
# 默认只采集、不提交;设置 AUTO_PUSH=1 才会 git 提交并推送。
# 与 GitHub Actions 共用同一份 topics.yml;若本机存在 topics.local.yml 会一并采集。

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

export TZ="${TZ:-Asia/Shanghai}"
# launchd 的 PATH 很精简,补上 Homebrew 的常见位置,避免找不到 python3
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

PAGES="${PAGES:-10}"   # 每个主题搜索页数,默认 10 页(每页 20 条)
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始采集 (pages=$PAGES)"

TOPIC_ARGS=(--topics topics.yml)
if [[ -f topics.local.yml ]]; then
  TOPIC_ARGS+=(--topics topics.local.yml)
fi

python3 collector/generate.py "${TOPIC_ARGS[@]}" --pages "$PAGES"
RC=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 采集结束 rc=$RC"

# 自检:索引/数据文件一致性有问题时不推送(避免把半坏数据推上去)
if python3 collector/generate.py --verify; then
  VERIFY_RC=0
else
  VERIFY_RC=1
  echo "自检未通过,本次不提交"
  RC=1
fi

if [[ "${AUTO_PUSH:-0}" == "1" && "$VERIFY_RC" == "0" ]]; then
  if git pull --rebase --autostash; then
    if ! git diff --quiet -- assets/data; then
      git add assets/data
      git commit -m "data: launchd 定时采集 $(date '+%Y-%m-%d %H:%M')" >/dev/null
      git push || echo "git push 失败:检查网络与凭据"
    else
      echo "数据无变化,不提交"
    fi
  else
    echo "git pull 失败,跳过提交(请先处理工作区冲突)"
  fi
fi

exit $RC
