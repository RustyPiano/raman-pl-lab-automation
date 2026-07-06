#!/bin/bash
# Stop hook: enforce the project-status maintenance convention (see CLAUDE.md).
# If the session produced git commits newer than docs/PROJECT_STATUS.md, block
# the turn from ending once and ask Claude to refresh the status doc.
set -u

input=$(cat)

# Never re-block while Claude is already continuing because of this hook.
if echo "$input" | jq -e '.stop_hook_active == true' >/dev/null 2>&1; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" 2>/dev/null || exit 0

doc="docs/PROJECT_STATUS.md"
[ -f "$doc" ] || exit 0
git rev-parse HEAD >/dev/null 2>&1 || exit 0

# In sync if the latest commit itself touched the status doc.
if git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null | grep -qx "$doc"; then
  exit 0
fi

head_ts=$(git log -1 --format=%ct 2>/dev/null) || exit 0
# stat: macOS (-f %m) first, GNU (-c %Y) fallback.
doc_ts=$(stat -f %m "$doc" 2>/dev/null || stat -c %Y "$doc" 2>/dev/null) || exit 0

if [ "${head_ts:-0}" -gt "${doc_ts:-0}" ]; then
  cat <<'JSON'
{"decision":"block","reason":"仓库里有比 docs/PROJECT_STATUS.md 更新的 git 提交。请先按 CLAUDE.md 的「状态文档维护约定」更新它（当前阶段/最近完成/下一步/已知问题，「最后更新」改为今天），再结束回合。只需保存文件，不必单独提交。"}
JSON
fi
exit 0
