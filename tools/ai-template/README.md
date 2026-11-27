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
