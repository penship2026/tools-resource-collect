# AI 设计管理处（本机工具）

- 本目录只在开发者本机使用，不参与 Pages 发布。
- `drafts/` 存放未审批的版式/主题草稿；`.gitignore` 阻止入库。
- 审批通过后才原子发布到 `assets/layouts/`、`assets/themes/` 与注册表。
- 展示清单由 `site.yml` 的 `display.visible_layouts` / `display.visible_themes` 控制，本机管理页只写这两个字段。
- 不提交 API Key、候选截图、模型缓存；无 AI 时站点仍完整可用。

## A1 编译器

```text
python3 tools/ai-template/cli.py validate --spec tests/fixtures/specs/layout-news-dense.json
python3 tools/ai-template/cli.py compile --spec tests/fixtures/specs/layout-news-dense.json --out /tmp/ai-layout
python3 tools/ai-template/cli.py compile --spec tests/fixtures/specs/theme-mist.json --out /tmp/ai-theme
python3 tools/ai-template/cli.py lint --file /tmp/ai-theme/mist.css
```

- `compile` 默认不写时间戳，保证同一 Spec 两次编译字节一致；需要留痕加 `--timestamp`。
- 版式输出 = 选定 archetype 基座（改写成新 key）+ Spec 覆盖；主题输出只含 `:root` + 29 token。
- 每次编译同时产出 `<key>.registry.json`，`sidebar` 固定 false，等待 A4 审批后并入注册表。

## A2 生成管线

```text
# 离线 mock：无 Key 也能跑通链路，默认 1 个候选
python3 tools/ai-template/cli.py generate --kind layout --request "3 列门户，移动端不溢出" --mock

# 一次要多个候选：--count 1–5
python3 tools/ai-template/cli.py generate --kind theme --request "暖色纸张质感" --mock --count 3

# 有模型：复制 .env.example 为 .env 并填写，Key 只留本机
cp tools/ai-template/.env.example tools/ai-template/.env
# 或直接 export（二选一；.env 不覆盖已 export 的值）
export AI_BASE_URL="https://your-endpoint/v1"
export AI_API_KEY="..."
export AI_MODEL="..."
python3 tools/ai-template/cli.py generate --kind theme --request "暖色纸张质感，长文阅读"

# 免费通道：OpenRouter（注册后创建 Key，:free 模型免预充值，约 50 次/日）
# .env 写入：
# AI_BASE_URL=https://openrouter.ai/api/v1
# AI_API_KEY=sk-or-v1-...
# AI_MODEL=baidu/ernie-5.5-flash-preview:free
# 备选：nvidia/nemotron-3-ultra-550b-a55b:free / google/gemma-4-31b-it:free

# 免费通道：本机 Ollama（无需 Key，CPU 推理慢）
# AI_BASE_URL=http://127.0.0.1:11434/v1
# AI_API_KEY=ollama-local
# AI_MODEL=deepseek-r1:7b

# 复核：validate + compile + lint
python3 tools/ai-template/cli.py validate --spec tools/ai-template/drafts/clay/candidate-2/spec.json
python3 tools/ai-template/cli.py lint --file tools/ai-template/drafts/clay/candidate-2/clay.css
```

- `--count 1–5` 决定候选数量，默认 1；输出 `drafts/<key>/candidate-N/{spec.json,<key>.css,<key>.registry.json}`，根目录 `run.json` 记录来源、模型、缓存命中与 prompt 指纹。
- 默认只发 `synthetic-preview-v1` 合成样例；不读取 `jiye.mine.v1`、采集正文、作者、来源链接。
- 缓存键 `sha256(kind + system + user + model)`，命中不调用模型；非法 JSON/校验失败重试 1 次，候选同质直接报错。
- 无 `AI_BASE_URL / AI_API_KEY / AI_MODEL` 时自动降级 mock，`source=mock` 的产物不得当可上线模板。

## A3 预览与闸门

```text
# 完整：5 套展示主题 × 1280/768/390 截图 + G1–G6
python3 tools/ai-template/cli.py preview --spec tools/ai-template/drafts/<key>/candidate-N/spec.json

# 冒烟：只跑 default 主题
python3 tools/ai-template/cli.py preview --spec ... --quick

# 无 Chrome：只跑静态 G1/G2/G4 token/G5/G6 token，视觉标记 skipped
python3 tools/ai-template/cli.py preview --spec ... --no-shot
```

- 输出写在候选目录：`preview/index.html`、`metrics.json`；截图在临时 Chrome profile，不提交大图。
- 失败返回非 0，`metrics.json` 的 `gates` 逐项带 `G1_SCHEMA` / `G2_FORBIDDEN` / `G3_RENDER` / `G4_CONTRAST` / `G6_DHASH` 等错误码。
- 版式：5 套展示主题 × 三档；主题：同一 fixture 套 5 套展示主题 × 三档；每候选 15 张。
- G6 版式对比基座 archetype，结构与截图 dHash 双指标；主题对比当前 5 套展示主题的主色/背景/字体/圆角。

## A4 评审工作台与设计管理处

```text
# 只监听 127.0.0.1，不发布到 Pages
python3 tools/ai-template/cli.py serve --port 8787

# 浏览器：http://127.0.0.1:8787/          候选对比 / 批准 / 驳回 / 迭代
# 浏览器：http://127.0.0.1:8787/manage.html 展示清单上下架 / 排序 / 预览

# 等价命令行
python3 tools/ai-template/cli.py approve --spec tools/ai-template/drafts/<key>/candidate-1/spec.json --reviewer liyan
python3 tools/ai-template/cli.py reject --spec ... --reviewer liyan --reason 同质化
python3 tools/ai-template/cli.py revise --spec ... --comments "标题区太重"
python3 tools/ai-template/cli.py display --kind theme --key anime --on
```

- 批准要求 `reviewer` + `metrics.json` 的 `ok=true` 与 `visual=checked`；缺一返回 `APPROVE_*` 错误码。
- 批准按 CSS → docs → review → 注册表 → `published.json` 顺序原子写，失败回滚；草稿保留；批准只写工作区，**不自动 git commit**。
- 发布产物：`assets/layouts|themes/<key>.css`、`docs/templates/<key>.{json,md}`、`tools/ai-template/reviews/<date>-<key>.json`，并在 `assets/templates.js` / `assets/theme.js` 的 `AI_*` 标记前插入注册表条目。
- 驳回记录到 `reviews/<date>-<key>-reject.json`，原因固定四类；迭代最多 2 轮，第 3 轮返回 `REVISE_LIMIT` 转人工。
- 管理处只写 `site.yml` 的 `display.visible_layouts` / `display.visible_themes` / `display.max_layouts` / `display.max_themes` 与 `assets/site.js`，不动 `editorial`；默认版式/主题各最多 5 套，可在管理页把上限调到 1–20；`standard` / `default` 锁定；超过上限上架返回 `DISPLAY_FULL`，下架锁定项返回 `DISPLAY_LOCKED`。
- 设计库可多于 5 套；未展示的设计仍留在管理页，可预览或换入。运行时只读 `site.js` 过滤，不调用模型，不需要 `tools/`。

## A4.5 模板编辑维护

```text
# 评审页顶部：选类型/写需求/候选数 1–5 → 生成
# 卡片内：展开 Spec 手改 → 保存为 candidate-1-eN；按意见重生成 → candidate-1-rN
# 批准：可勾选“批准后立即上架”
# 管理处：已发布 AI 模板“克隆新版本”；旧模板“下线归档”
```

- `POST /api/generate`：`{kind, request, constraints, count, mock}`，mock 只用于链路验证。
- `POST /api/spec/save`：`{path, spec}`，校验后写 `candidate-N-eN`，不覆盖旧候选。
- `POST /api/revise`：`{path, comments, reviewer, max_rounds}`，写 `candidate-N-rN`，服务器上限 3 轮。
- `POST /api/approve`：加 `push:true` 时批准后写展示清单与 `site.js`；展示位满返回 `push_message`，不回滚发布。
- `POST /api/clone`：`{kind, key, new_key, new_name}`；已发布 AI 模板从 `docs/templates` 取 Spec，内置版式/主题从 `builtin-specs/layout|theme` 取抽取 Spec。
- `POST /api/archive`：`{kind, key}`，先移出展示清单，再写 `published.json.archived`；CSS/注册表不动，锁定项拒绝。
