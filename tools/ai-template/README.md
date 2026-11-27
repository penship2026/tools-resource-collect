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
# 离线 mock：无 Key 也能产出 3 个候选，只用于链路验证
python3 tools/ai-template/cli.py generate --kind layout --request "3 列门户，移动端不溢出" --mock

# 有模型：先配置环境变量，Key 只留本机
export AI_BASE_URL="https://your-endpoint/v1"
export AI_API_KEY="..."
export AI_MODEL="..."
python3 tools/ai-template/cli.py generate --kind theme --request "暖色纸张质感，长文阅读"

# 复核：validate + compile + lint
python3 tools/ai-template/cli.py validate --spec tools/ai-template/drafts/clay/candidate-2/spec.json
python3 tools/ai-template/cli.py lint --file tools/ai-template/drafts/clay/candidate-2/clay.css
```

- 一条命令固定产 3 个候选；输出 `drafts/<key>/candidate-N/{spec.json,<key>.css,<key>.registry.json}`，根目录 `run.json` 记录来源、模型、缓存命中与 prompt 指纹。
- 默认只发 `synthetic-preview-v1` 合成样例；不读取 `jiye.mine.v1`、采集正文、作者、来源链接。
- 缓存键 `sha256(kind + system + user + model)`，命中不调用模型；非法 JSON/校验失败重试 1 次，候选同质直接报错。
- 无 `AI_BASE_URL / AI_API_KEY / AI_MODEL` 时自动降级 mock，`source=mock` 的产物不得当可上线模板。
