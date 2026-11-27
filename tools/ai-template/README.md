# AI 设计管理处（本机工具）

- 本目录只在开发者本机使用，不参与 Pages 发布。
- `drafts/` 存放未审批的版式/主题草稿；`.gitignore` 阻止入库。
- 审批通过后才原子发布到 `assets/layouts/`、`assets/themes/` 与注册表。
- 展示清单由 `site.yml` 的 `display.visible_layouts` / `display.visible_themes` 控制，本机管理页只写这两个字段。
- 不提交 API Key、候选截图、模型缓存；无 AI 时站点仍完整可用。
