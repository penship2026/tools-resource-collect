# 内置模板 Spec（抽取）

这里存放从现有内置页面模板抽取的 Design Spec，只作为**克隆起点**，不等于替换现有 CSS。

- `layout/standard.json`、`layout/news.json`、`layout/magazine.json` 对应现有三套版式。
- `theme/default.json`、`theme/dark.json`、`theme/tech.json`、`theme/campus.json`、`theme/classical.json`、`theme/anime.json` 对应现有六套主题，29 个 token 与 CSS 一一对应。
- 管理页出现「克隆新版本」按钮后，从对应 Spec 复制一个新 key 草稿，再手改 / 预览 / 批准；旧版 CSS 与注册表不动。
- 抽取值按现有版式的结构、密度、封面比和响应式断点，以及主题的 token 值填写；编译器会生成新 key 的 CSS，视觉上以现有页面为基准，不保证逐像素相同。
- `tech` / `anime` 的 `--brand / --bg` 对比度分别为 2.50 / 2.86，低于 AI 模板 G4 的 3.0；克隆后预览会标红，需要先调深品牌色再批准。这是内置主题的历史状态，不是新 Spec 引入的问题。
- `anime` 的 `--hero-wash` 原值超过 schema 单值 160 字符，抽取时压缩成等价的 8 位十六进制 alpha 写法。
