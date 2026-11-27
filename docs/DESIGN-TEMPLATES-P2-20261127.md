# 二期详细设计 · AI 模板与主题工坊

> 版本 v1.6 · 2026-11-27 · 状态：A4 实现完成，待验收；A4.5 模板编辑闭环已落地
> 对应方案：`docs/PLAN-TEMPLATES-20261127.md`（D70–D73、D92–D98）
> 评审记录：`docs/REVIEW-TEMPLATES-P2-20261127.md`
> 前置：一期 3 套版式、布局 token 白名单、`templates.js` 注册表已就绪；截图脚本与基线由 A0 新建，不再假设已存在
> 核心定位：**AI 是可选增强，不是运行时依赖**——生成在离线/本机完成，线上仍是零构建纯静态

> **v1.6 修订**：二期从“一次性批量生成 3 个候选”改为**模板编辑维护闭环**：管理台内 AI 生成 1–5 个候选、人工选 1 个；候选 Spec 可直接手改并存为新版本；批准时可勾选立即上架；已发布 AI 模板可克隆新版本，内置/旧模板可下线归档但文件不动。
> **v1.5 修订**：展示上限改为可配置 `display.max_layouts` / `display.max_themes`（1–20，默认 5）；管理页可改上限、`cli display --max`、`POST /api/display/limit`；A5 试点主题上限先设 8，使 5 套内置 + 3 个 AI 主题全部展示；版式 3+3 超 5 时需先下架一套内置或同步提高版式上限。
> **v1.4 修订**：A4 落地为 `registry / site_store / publish / display / server` 五个本机模块与两个工作台页面；批准按 CSS→docs→review→注册表→sidecar 事务写，管理处只写 `site.yml` display 与 `assets/site.js`。
> **v1.3 修订**：AI 支持两类产物（版式模板 / 主题）；前端默认每类展示 5 套，内置也计入名额；展示清单由本机「AI 设计管理处」控制，设计库可多于展示位。
> **v1.2 修订**：补充「无 AI 基线」硬约束与降级表；删除 AI 模板后，全部一期功能仍须可用。
> **v1.1 修订**：Spec 只保留渲染层已落地的 `nav / lead / bands / toc` 四类能力；删除主题绑定与 `rails / timeline / rail`；补齐 draft 目录、原子发布、`status` 与回退；G3/G4/G6 改用本机 Chrome/CDP + 固定 fixture；增加 6 套版式切换容量策略；工期改为 12–15 人日 + 2–3 人日评审。

---

## 零、评审结论

二期主线成立：模型只产受限 Spec，编译器产 CSS，六道闸门 + 人工审批后入库。v1.0 的主要问题是**把尚未落地的渲染能力写进了 Schema**，并假设截图基线已存在。v1.1 按以下五条收敛：

1. **能力先对齐**：只允许 `nav / lead / bands / toc` 四个已被 `render.js` 与 `index.html` 消费的能力位；`sidebar / rail / timeline / titleLines` 不进 P2。
2. **主题不绑定**：Spec 不含 `theme`；预览主题只走 `?theme=`，不落盘。
3. **草稿先隔离**：候选写 `tools/ai-template/drafts/<key>/`；批准后才原子发布到 `assets/`、注册表与 `docs/templates/`。
4. **闸门可复现**：A0 补 `scripts/shot_matrix.py`、固定 fixture 与三档基线，用本机 Chrome/CDP，不引入 Playwright。
5. **容量先收口**：5 套版式时页脚切换器由按钮改为下拉；下线 key 回退 `standard`，不白屏。

v1.3 追加两条：

6. **AI 不只产版式，也产主题**：主题只填 29 个既有 token，独立成 CSS，不与版式绑定。
7. **设计库与展示位分离**：库可多套，前端默认版式/主题各展示 5 套（内置占名额），可在管理页把上限调至 1–20；展示清单由本机「AI 设计管理处」写入 `site.yml`，运行时只读 `site.js`。

---

## 一、目标与非目标

### 1.1 目标

1. 用自然语言（可附参考截图）描述想要的版式，产出一条可直接上线的版式模板。
2. 用自然语言描述色彩、字体与气质，产出一套只改 token 的主题，不绑定任何版式。
3. 设计库可以同时存在多套版式与主题；前端默认版式/主题各展示 5 套，内置也占名额，展示清单与上限由「AI 设计管理处」控制。
4. 产物必须**结构可控**：不出现外链资源、不出现 `!important`、不改 DOM/JS、不引入依赖。
5. 产物必须**可评审**：候选对比、指标量化、审批留痕、一条命令回滚。
6. 产物必须**可维护**：有设计说明与来源 prompt，后来的人知道它为什么长这样。

### 1.2 非目标

- 不做运行时 AI 换肤、不做"访客一句话换模板"。
- 不让 AI 写 HTML/JS、改 `render.js`、改数据。
- 不做自动合并/自动发布（审批是硬闸门）。
- 不做面向公众的模板市场、不做拖拽编辑器。
- 不用 AI 生成内容文案或采集结果；AI 主题只产 token，不产内容、不绑定版式。

### 1.3 AI 是可选增强，不是运行前提

**硬约束**：P2 的 AI 只用于“生产版式与主题”，不进入访客运行时。没有 AI、没有 API Key、没有 `tools/` 目录，站点仍必须完整可用，且与一期验收一致。

无 AI 时必须保持的能力：

- 3 套内置版式与当前 5 套展示主题正常切换（第 6 套内置主题默认不展示，提高主题上限后可在管理页上架）；
- 首页、合集、列表、详情、`?view=mine`、`mine-io.html` 正常打开；
- 板块导航、`?section=`、置顶、画册大图、统计条、筛选吸顶正常；
- 个人收藏、导入导出、我的设置、我的版式正常；
- 采集页、采集服务、定时任务、数据校验正常；
- GitHub Pages / 本地静态服务 / `file://` 三种打开方式都不依赖模型。

运行时禁止新增：

- 不在页面里请求任何模型端点，不新增模型域名到 CSP / 网络白名单；
- 不把 AI 生成结果做成运行时接口或动态拼装；
- 不因 AI 工坊给 `generate.py`、Pages workflow、静态服务增加必填环境变量；
- 不让 `templates.js` / `theme.js` 依赖远程清单；AI 设计也只是本地静态 CSS + 注册表条目。

降级口径：

| 场景 | 仍可用 | 不可用 | 处置 |
|---|---|---|---|
| 无 API Key / 断网 | 全部一期功能 + 当前展示清单（默认 5+5） | AI 生成、AI 候选评审 | 工坊提示“未配置模型”；站点不受影响 |
| 无 `tools/` 目录 | 全部一期功能 | 工坊、编译器、设计管理处 | 正常发布，不产生 404 或控制台报错 |
| 模型连续失败 | 全部一期功能 | 新模板/主题生成 | 保留上一版；不写注册表 |
| AI 版式/主题下线 | 其余展示项 + 回退默认 | 已下线设计 | 清理本地偏好，不白屏 |
| 截图服务不可用 | 现有站点 | 新模板审批 | 标记“未过视觉闸门”，不得批准 |

**验收方法**：在干净环境里 `unset AI_*`、删除 `tools/`、断网打开 `file://index.html`，跑完整一期回归；任何失败都按阻断项处理，不得用“AI 没配”解释。

---

## 二、为什么"AI 只产 Spec"

让模型直接写 CSS，问题不在"写得丑"，在于**不可控面太多**：外链字体、`position:fixed` 遮挡、`!important`、渐变堆叠、移动端溢出、无对比度。靠 prompt 约束，成功率不稳定；靠 lint 事后拦，返工率高。

版式与主题都改为"模型填表、编译器写 CSS"：

```
版式：{ kind:"layout", archetype:"news", nav.style:"tabs", bands.columns:3, coverRatio:"16:9", … }
主题：{ kind:"theme", mode:"light", tokens:{ "--bg":"#f7f8fa", "--brand":"#2d7ff9", … } }
编译器输出：确定性 CSS；同一 Spec 两次编译字节一致
```

好处：

- **枚举收敛**：版式只能在 3 种原型、4 种封面比例、2–4 列之间选；主题只能填 29 个既有 token，不会发明新变量。
- **数值有界**：栏宽 240–340、副卡 0–3、分节 2–4 列；主题对比度与颜色格式由 schema / lint 拒绝。
- **可解释**：Spec 就是设计说明，评审看 JSON 比看 300 行 CSS 快。
- **可回归**：改了某个参数，diff 只有几个数字/几个色值，不产生"整份 CSS 重写"。

代价：表达力受限。一期 3 个原型 + 参数空间，足够覆盖"简洁/门户/画册"的变体；主题只在既有 token 内换色与字体。真正需要新结构或新 token 的，走人工设计（仍按一期三步）。

---

## 三、系统架构

```
tools/ai-template/
├── cli.py                 入口：generate / compile / validate / preview / approve / rollback / display
├── spec/
│   ├── layout.schema.json  版式 Spec 的 JSON Schema
│   └── theme.schema.json   主题 Spec 的 JSON Schema（29 个 token 白名单）
├── compiler.py            Spec → CSS（按 kind 分派，纯函数、零副作用）
├── prompts/
│   ├── system-layout.md   版式角色、能力矩阵、禁止项
│   ├── system-theme.md    主题角色、token 白名单、对比度要求
│   ├── generate.md         生成候选的指令模板（kind 注入）
│   └── revise.md           按评审意见迭代的模板
├── adapters/
│   ├── openai_compat.py   OpenAI 兼容（含国内兼容端点）
│   ├── local.py           本地模型（可选）
│   └── mock.py            离线测试用固定 Spec（版式 + 主题各一份）
├── preview.py             版式/主题预览 + 样例数据 + 三档截图
├── metrics.py             溢出/对比度/体积/辨识度
├── workbench/
│   ├── review.html        候选对比、批准/驳回
│   └── manage.html        「AI 设计管理处」展示清单与上下架
├── cache/                 prompt 哈希 → 响应（.gitignore）
└── reviews/               审批记录 YYYYMMDD-<key>.json
```

产物落点：

```
assets/layouts/<key>.css        版式编译器输出
assets/themes/<key>.css         主题编译器输出（只含 token）
assets/templates.js             版式注册表追加
assets/theme.js                 主题注册表追加
site.yml                        展示清单（visible_layouts / visible_themes）
assets/site.js                  由 generate.py 生成的展示清单快照
docs/templates/<key>.md         设计说明（来源 prompt、Spec 摘要、审批人）
docs/templates/<key>.json       Spec 原文件（可复现）
```

约束：`pages.yml` 采用白名单拷贝，`tools/` 本就不会进 artifact；CI 断言 `_site/tools`、`_site/docs`、`_site/tests` 不存在。工坊只本机跑。

---

## 四、Design Spec

### 4.1 版式 Spec 字段表

| 字段 | 类型 | 取值 / 区间 | 说明 |
|---|---|---|---|
| `version` | int | 固定 1 | 版本演进用 |
| `kind` | enum | 固定 `layout` | 产物类型；主题见 4.3 |
| `key` | string | `[a-z0-9-]{3,24}` | 版式 id，与 CSS 文件名一致 |
| `name` | string | 2–12 字 | 展示名 |
| `intent` | string | ≤120 字 | 设计意图，进说明文档 |
| `archetype` | enum | `standard` / `news` / `magazine` | 结构原型，只能是已有三种（对应 简洁 / 门户 / 画册） |
| `density` | enum | `comfortable` / `compact` | 密度档 |
| `nav` | object | `{style: none\|tabs, sticky: bool, maxItems: 4–8}` | 导航形态；`rail` 未落地，不支持 |
| `hero` | object | `{type: none\|text\|lead, mainRatio: 0.5–0.7, subCards: 0–3}` | 首屏；时间线未落地，不支持 |
| `bands` | object | `{columns: 2–4, rows: 1–3, showDescription: bool, moreLink: bool}` | 分节 |
| `cards` | object | `{coverRatio: "16:9"\|"4:3"\|"3:2"\|"1:1", showTags: bool}` | 卡片；标题/标语行数由 CSS 固定，不进 Spec |
| `responsive` | object | `{breakpoints:[1080,720,390], mobileColumns: 1–2, leadStack: bool}` | 响应式 |
| `limits` | object | `{maxCssKb: 6–10, maxRules: 60–160}` | 自设预算，不得超过硬上限 |
| `rationale` | array | 3–5 条短句 | 每条设计选择的理由 |

**已删除的字段**：`rails`（侧栏未落地，D80 统一关闭 `sidebar`）、`theme`（模板不绑定主题，D65）。二者都不是“以后再实现”，P2 阶段 schema 直接拒绝。

**能力矩阵（Spec 与 `templates.js` 共用）**：

| `archetype` | `nav` | `lead` | `bands` | `toc` | 固定 DOM |
|---|---|---|---|---|---|
| `standard` | false | false | false | false | 单列 Hero + 卡片网格 |
| `news` | true | true | true | false | 板块导航 + 1 主 3 副 + 分节 |
| `magazine` | true | false | true | true | 单栏宽幅 + 章节编号 + 目录 |

模型只能在这 4 个能力位内调参；`archetype` 决定能力位，生成器不得自行增加 `sidebar` 或 `timeline`。后续要加新结构，先改 `render.js` 与 `templates.js`，再改 schema。

**硬上限（schema 之外再由编译器兜底）**：CSS ≤10KB、规则 ≤160 条、颜色零出现、外链零出现。

画册首篇大图不由 Spec 决定：`hero_image` 属于编辑数据（`site.yml`），模板只定义容器比例与"大图 → 封面 → 占位"的回退规则；Spec 中不得出现任何图片 URL。

主题只用于预览：`?theme=tech` 是临时参数，不进 Spec、不进审批记录、不影响发布 CSS。同一版式 Spec 在当前展示主题（默认 5 套）下结构必须一致。

### 4.2 示例 Spec（门户·紧凑）

```json
{
  "version": 1,
  "kind": "layout",
  "key": "news-dense",
  "name": "门户 · 紧凑",
  "intent": "科技类门户场景：首屏信息密度更高，头条区给 3 张副卡，板块单行即收口",
  "archetype": "news",
  "density": "compact",
  "nav": { "style": "tabs", "sticky": true, "maxItems": 7 },
  "hero": { "type": "lead", "mainRatio": 0.66, "subCards": 3 },
  "bands": { "columns": 4, "rows": 1, "showDescription": false, "moreLink": true },
  "cards": { "coverRatio": "4:3", "showTags": true },
  "responsive": { "breakpoints": [1080, 720, 390], "mobileColumns": 2, "leadStack": true },
  "limits": { "maxCssKb": 8, "maxRules": 120 },
  "rationale": [
    "4 列 + 单行，让 6 个板块在一屏内可扫完",
    "4:3 封面比 16:9 更适合竖屏截图类内容",
    "紧凑密度压缩分节间距，但保留 44px 点击区"
  ]
}
```

### 4.3 主题 Spec 字段表

主题与版式是两类独立产物：主题只换色/字体/圆角/阴影，不改结构；版式不绑定主题。

| 字段 | 类型 | 取值 / 区间 | 说明 |
|---|---|---|---|
| `version` | int | 固定 1 | 版本演进用 |
| `kind` | enum | 固定 `theme` | 产物类型 |
| `key` | string | `[a-z0-9-]{3,24}` | 主题 id，与 CSS 文件名一致 |
| `name` | string | 2–12 字 | 展示名 |
| `intent` | string | ≤120 字 | 设计意图，进说明文档 |
| `mode` | enum | `light` / `dark` | 写入 `color-scheme`，不决定版式 |
| `tokens` | object | 必须且只能覆盖 29 个主题 token | 见下方白名单 |
| `rationale` | array | 3–5 条短句 | 每条设计选择理由 |
| `limits` | object | `{maxCssKb: 2–4, maxRules: 30–40}` | 主题预算 |

主题 token 白名单（与 `assets/themes/default.css` 的 29 个变量一一对应）：

```text
--bg --surface --text --text-sub --text-mute --border --brand --brand-soft
--shadow --radius --radius-sm --radius-pill --font-sans --font-display
--fs-hero --fs-title --fs-body --fs-sm --fs-xs --gap-card --pad-card
--shadow-hover --brand-2 --hero-wash --header-bg
--plat-bilibili --plat-wechat --plat-xhs --plat-multi
```

硬约束：

- 29 个 token 必须齐全，不得新增、改名或带出 `--layout-*`；缺一个直接 schema 拒绝。
- 输出只允许 `:root` + token 声明，不写选择器、不改 DOM、不加页面级覆盖。
- 禁止 `url()`、`@import`、外链字体；`--font-sans` / `--font-display` 只允许系统字体栈。
- 对比度：`--text` / `--bg` ≥4.5，`--text-sub` / `--surface` ≥4.5，`--brand` / `--bg` ≥3；按钮与徽标文字另测。
- 主题不能指定版式，版式 Spec 也不能指定主题；组合只由用户选择。

### 4.4 提示词结构

版式与主题各有一份 system prompt：版式用 `system-layout.md`（角色、能力矩阵、禁止项），主题用 `system-theme.md`（角色、29 token 白名单、对比度要求）。两者都要求“纯 JSON、3 个候选、每个带 `rationale`”。`generate.md` 注入：站点定位、**合成样例数据摘要**（虚构标题/标签/数量）、目标场景、约束。`revise.md` 注入：上一版 Spec + 评审意见 + 指标偏差，要求"只改必要字段"。

**不喂给模型的内容**：`jiye.mine.v1` 收藏、采集单元正文/简介原文、作者主页、来源链接、私有主题清单、账号与口令。默认只用仓库内合成样例；用户显式勾选“使用当前站点样例”时，才发送去作者、去链接、去简介后的标题与标签，并在请求日志里留摘要以便核对。

---

## 五、编译器

### 5.1 映射规则

| Spec 输入 | CSS 输出 |
|---|---|
| `archetype` | 选基座：`standard`（网格）/ `news`（导航+头条+分节）/ `magazine`（目录+章节+通栏）；同时写入 4 个能力位，不接受模型单独改能力位 |
| `density` | 间距组：comfortable `{gap:20,padding:20,section:56}` / compact `{gap:14,padding:14,section:40}` |
| `nav.style` | `none` 不输出；`tabs` 顶部横排；`rail` 不在枚举内 |
| `hero.mainRatio` | `grid-template-columns: minmax(0,{ratio}fr) minmax(0,{1-ratio}fr)` |
| `hero.subCards` | 副卡列数 0–3；0 时不输出副卡区 |
| `bands.columns` | `--layout-band-cols` 与 `repeat()` |
| `cards.coverRatio` | `--layout-cover-ratio` |
| 画册首篇大图 | 只输出 3:2 容器与 `object-fit`，图源取 `EDITORIAL.hero_image`，Spec 不参与 |
| `responsive` | 输出 3 段 `@media`，只改列数与堆叠 |
| `limits` | 编译器自检；超预算直接失败，不裁字段 |

编译器只输出 4 类内容：`:root` 的 `--layout-*` 覆盖、`[data-layout="<key>"]` 下的结构规则、`@media` 段、注释头（Spec 摘要 + 生成时间 + 审批号）。**不含任何颜色/字体/阴影/圆角**。

发布时同时产出一段注册表草稿：

```js
{ label, desc, file, archetype, nav, lead, bands, sidebar:false, toc, status:"published" }
```

`sidebar` 固定 false；`status` 缺省视为 `published`。注册表是编译产物的一部分，不允许手工补字段。

### 5.2 主题编译器

主题编译只做一件事：把 29 个 token 排序、校验、写成一张 CSS。

```css
/* theme: <key> · <mode> */
:root {
  color-scheme: <light|dark>;
  --bg: ...;
  ...
  --plat-multi: ...;
}
```

- 不输出选择器、布局规则、`@media`、页面级覆盖；
- 输出顺序固定为 token 白名单顺序，方便 diff；
- 发布时注册表草稿：

```js
{ label, file, status:"published" }
```

`theme.js` 仍需人工/脚本追加一行；AI 主题与内置主题共用同一套加载逻辑。

### 5.3 确定性

- 输入 Spec 规范化（键排序、数字取整到 1 位）后再渲染。
- 不使用随机数；时间戳只进注释，可 `--no-timestamp` 关闭。
- 断言：同 Spec 两次编译 `sha256` 一致。
- CSS 输出按"变量 → 结构 → 媒体查询"固定顺序，diff 可读。

---

## 六、生成与评审流程

```
1. 输入        选择「新建 AI 模板」或「从已发布 AI 模板克隆」；kind=layout/theme + 自然语言 + 可选约束
2. 生成        模型产出 1–5 个候选 Spec（枚举/区间/白名单内），人可只生成 1 个
3. 人工改      评审页展开 Spec 直接改 JSON；保存为 candidate-N-eN，不覆盖旧候选
4. 校验/编译   每次生成或手改都走 Schema + key 唯一性 + 编译器；写 drafts/<key>/<candidate>/
5. 预览        固定 fixture + 真实页面，1280 / 768 / 390 截图
6. 指标        溢出/对比度/体积/辨识度/控制台错误
7. 评审        人工在 workbench 对比，选 1 个；不满意可按意见重新生成（candidate-N-rN，≤3 轮）
8. 审批        批准 → 草稿转正式：CSS + 注册表 + 说明 + 审批记录；可勾选「批准后立即上架」
9. 推送        上架写 site.yml display 与 assets/site.js；也可在管理处单独上下架
10. 归档       旧模板下线归档只记 published.json.archived 并从展示清单移除，CSS/注册表不动
```

**发布顺序**：先写 CSS 与 `docs/templates/*`，再原子替换 `templates.js` 或 `theme.js`；任何一步失败都不改运行目录。驳回或未批准的候选留在 `drafts/`，不删除，供 prompt 复盘。

**旧模板维护**：内置模板没有可编辑 Spec，只能下线归档；已发布 AI 模板可从 `docs/templates/<key>.json` 的 `spec` 克隆成新 key 草稿，再手改/预览/批准。旧模板文件与注册表不动，避免正在展示的页面被改坏。

候选策略：版式候选必须在**至少 2 个维度**上不同（列数、封面比例、首屏类型、密度）；主题候选必须在**至少 2 项**上不同（主色、背景明度、字体、圆角），否则要求模型重出。候选数量不再固定 3 个，默认 1 个，可在管理台选 1–5 个。

---

## 七、六道闸门

| 闸门 | 检查 | 方法与阈值 | 失败处置 |
|---|---|---|---|
| **G1 Schema** | 版式：字段齐全、枚举合法、区间、拒绝 `rails/theme/sidebar`；主题：29 token 齐全、无 `--layout-*`、无多余键 | `jsonschema` 或同契约手写校验 | 直接拒绝，不回传模型 |
| **G2 编译** | 版式：白名单属性、无色值、无 `!important`/`@import`/`url(`、CSS ≤10KB、规则 ≤160；主题：只允许 `:root` + token、CSS ≤4KB、无 `url()`/外链字体 | 复用 `layout_lint.py` + 主题 lint + 预算 | 编译失败，提示具体字段 |
| **G3 渲染** | 1280/768/390 无横向溢出、卡片可见、导航可点、控制台 0 报错 | 本机 Chrome/CDP + 固定 fixture + DOM 断言 | 记录档位与元素，退回迭代 |
| **G4 无障碍** | 正文对比度 ≥4.5、大字 ≥3.0、点击区 ≥44px、focus 可见、标题层级不乱；主题另测按钮/徽标 | 计算 + DOM 断言 | 必须修复，不能豁免 |
| **G5 性能** | 版式 CSS ≤8KB、主题 CSS ≤4KB、无外部字体/图片、无固定定位遮挡 | 静态统计 | 超预算改字段，不改闸门 |
| **G6 辨识度** | 版式：固定 fixture 截图 dHash ≥10 且结构指纹至少 2 项不同；主题：主色/背景/字体/圆角至少 2 项与当前展示主题明显不同 | Chrome 截图 + 结构指纹 + token 差异 | 视为重复，退回 |

主题的 G3/G4 必须用“同一 fixture 分别套当前展示主题（默认 5 套，A5 为 8 套）”跑；不能只看单一浅色/深色。G6 的对比对象是**当前展示清单**，不是全部库内设计。

截图依赖：`scripts/shot_matrix.py` 由 A0 新建，复用本机 Chrome 与 CDP；不引入 Playwright。基线存 `tests/baselines/*.json`，只存尺寸、溢出、dHash 与结构指纹，不把大图提交进仓库。G3/G4/G6 任一无法运行时，评审标记“未过视觉闸门”，不得批准。

---

## 八、评审工作台

本机页面 `tools/ai-template/workbench/`，`python3 tools/ai-template/cli.py serve --port 8787` 启动，仅监听 127.0.0.1。

```
┌ 候选 A / B / C ───────────────────────────────────┐
│ [1280 预览 iframe]  [390 预览 iframe]             │
│ 指标：CSS 6.8KB · 对比度 5.1 · 溢出 0 · 距基线 14   │
│ Spec 摘要（可折叠，高亮与其它候选不同的字段）       │
│ [批准] [要求迭代：输入意见] [驳回]                 │
└───────────────────────────────────────────────────┘
```

操作约束：

- 批准必须填写 reviewer（下拉/输入），生成 `reviews/<date>-<key>.json`。
- 批准只写工作区文件，**不自动 git commit**；提交由人执行，保持"一个模板一个提交"。
- 驳回也留记录（原因分类：同质化 / 破版 / 观感差 / 不支持该场景），用于 prompt 调优。
- 迭代 ≤2 轮；第 3 轮仍不合格转人工设计，不无限烧调用。
- 新闭环：评审页顶部可直接输入需求、约束与候选数（1–5）生成；每张候选卡可展开 Spec 手动改并保存为新版本，也可勾选「批准后立即上架」。批准仍必须 reviewer。
- 候选数量、生成/手改/迭代都不覆盖旧文件：生成 `candidate-N`，迭代 `candidate-N-rN`，手改 `candidate-N-eN`。

### 8.1 AI 设计管理处

本机页面 `tools/ai-template/workbench/manage.html`，只在 127.0.0.1 打开，不发布到 Pages。它管理**所有版式与主题**，也承接模板维护：已发布 AI 模板可克隆新版本，旧模板可下线归档。

列表字段：

| 列 | 内容 |
|---|---|
| 类型 | 版式 / 主题 |
| 名称 / key | 展示名与文件名 |
| 来源 | 内置 / AI / 人工 |
| 状态 | published / deprecated / archived |
| 展示 | 是否占用展示位 |
| 操作 | 预览、上架、下架、排序、下线归档、克隆新版本 |

展示名额：

- **默认版式最多 5 套、主题最多 5 套**，内置占名额；`standard` 版式与 `default` 主题锁定，不可隐藏，保证回退。
- 管理处可分别设置 `display.max_layouts` / `display.max_themes`（1–20，默认 5）；A5 试点期主题上限设为 8，容纳 5 套内置 + 3 个 AI 主题，先全部展示。
- 设计库可以多于当前上限；只有展示清单里的进入页脚切换器。未展示的设计仍可在管理页预览。
- 首版主题展示清单：`default / dark / tech / campus / classical`；`anime` 暂不展示，提高主题上限后可在管理页上架。
- 超过当前上限时「上架」按钮禁用，提示先下架或提高上限；不允许静默截断。
- 保存后写 `site.yml` 的 `display.visible_*` / `display.max_*`，再生成 `assets/site.js`；不自动 git commit。
- 运行时只读 `site.js` 过滤，不调用模型，不需要 `tools/`。

保存后的布局/主题切换器：

```text
页脚：只渲染 visible_* 中的 key；数量 ≤ 当前上限，5 套即切换为下拉。
个人设置：下拉只列 visible_*，并保留「跟随公开」。
本地偏好指向已隐藏/下线 key：回退到 standard / default，清掉无效值。
```

管理页验收：默认 5+5 时无“第 6 个”入口；提高上限后可继续上架，超过上限仍被拒绝；下架 `standard` 或 `default` 被拒绝；刷新页面后展示清单、上限与 `site.js` 一致。

审批记录：

```json
{
  "key": "news-dense",
  "reviewer": "liyan",
  "decision": "approved",
  "at": "2026-11-27T15:20:00+08:00",
  "spec": "docs/templates/news-dense.json",
  "css_sha256": "…",
  "model": "…",
  "prompt_id": "generate-v1",
  "candidates": 1,
  "rounds": 1,
  "metrics": { "cssKb": 6.8, "contrast": 5.1, "overflow": 0, "dhash": 14 }
}
```

### 8.2 A4 落地边界

- 本机模块：`registry.py`（内置 + `published.json` 合并、JS 标记插入）、`site_store.py`（display 块与 `site.js` 原子读写）、`publish.py`（批准/驳回/迭代）、`display.py`（上下架/排序/可配置上限校验）、`server.py`（127.0.0.1 API）。
- 批准前只读候选：检查 `reviewer`、`metrics.json` 的 `ok=true` 与 `visual=checked`，再编译；不写 `assets/`、`site.yml`、`site.js`。
- 批准事务顺序：CSS → `docs/templates/*.json` / `*.md` → `reviews/*.json` → `templates.js` / `theme.js` 注册表 → `published.json` sidecar；任一步失败按备份回滚，草稿保留。批准不自动 git commit。
- 驳回写 `reviews/<date>-<key>-reject.json`，原因是固定四类；迭代记录 `*-revise-N.json`，第 3 轮返回 `REVISE_LIMIT`。
- 管理处只写 `site.yml` 的 `display.visible_layouts` / `display.visible_themes` / `display.max_layouts` / `display.max_themes` 与 `assets/site.js`，保留 `site.default_layout`、`editorial` 与 `window.EDITORIAL`；默认上限 5，管理页可设 1–20，`standard` / `default` 锁定，超过当前上限返回 `DISPLAY_FULL`。
- 工作台只监听 `127.0.0.1`，页面不发布到 Pages；运行时仍只读 `site.js`，不需要 `tools/`。

### 8.3 A4.5 模板编辑闭环

- 生成：评审页顶部面板 `POST /api/generate`，参数 `kind / request / constraints / count(1–5) / mock`；真实模型不可用时降级 mock，mock 产物不得上线。
- 手改：每张候选卡展开 `spec`，`POST /api/spec/save` 校验后写 `candidate-N-eN`；不覆盖原候选，手改版本仍需预览/批准。
- 迭代：`POST /api/revise` 按意见重新生成 `candidate-N-rN`，旧版保留；服务器上限 3 轮，超过返回 `REVISE_LIMIT`。
- 批准推送：`POST /api/approve` 可带 `push:true`；批准成功后写展示清单与 `site.js`。展示位满/锁定/已归档时返回 `push_message`，不回滚已完成的发布。
- 克隆：`POST /api/clone` 只对已发布 AI 模板有效，从 `docs/templates/<key>.json` 的 `spec` 复制新 key 草稿；内置模板没有 Spec，不能克隆。
- 归档：`POST /api/archive` 先从展示清单移除，再写 `published.json.archived`；不改 CSS、注册表或原 published 条目。归档项不能直接重新上架，需克隆新版本。
- 仍未覆盖：空白手动新建模板。当前“从零新建”走 AI 生成 1 个候选或克隆已有 AI 模板；内置模板只能归档，不直接改其 CSS。

---


## 九、治理

| 规则 | 内容 |
|---|---|
| 注册表最小化 | `templates.js` / `theme.js` 只存 `label/desc/file/能力声明/status`；provenance 放 `docs/templates/*.json` |
| 草稿隔离 | 候选只写 `tools/ai-template/drafts/<key>/`；批准前不碰 `assets/`、`templates.js`、`theme.js` |
| 原子发布 | 先写 CSS 与 docs，再原子替换对应注册表；任一步失败不留半成品 |
| 展示上限 | 默认版式/主题各 5 套，可在管理页按类调到 1–20；内置占名额；设计库可多于上限，只有展示清单进入前端 |
| 锁定回退 | `standard` 版式与 `default` 主题锁定，不可下架；保证任何本地偏好都能回退 |
| 季度复审 | 每季度检查：是否仍被使用、是否与新版式/主题重复、移动端是否仍达标；不用则标 `status:"deprecated"` |
| 下线回退 | `deprecated` / 已隐藏 key 不进入切换器；本地偏好指向它时回退 `standard` / `default`，并清理无效值 |
| 回滚 | revert 单个提交（CSS + 注册表 + docs），不涉及数据与主题 |
| 责任 | 审批人对该设计（版式或主题）的视觉与可用性负责；prompt 与模型版本必须可追溯 |
| 命名 | `key` 与文件名一致，禁止 `new/new2/final` 这类命名 |

### 9.1 展示清单与切换器

当前 `assets/layout.js` / `theme.js` 会把注册表里的每个 key 都渲染成按钮。P2 改为先读 `site.js` 的 `display.visible_layouts / visible_themes`，再渲染：

- 版式/主题默认各自 5 套，可分别配置上限（1–20）；内置占名额，`standard` / `default` 锁定；
- 展示清单为空或字段缺失时，按注册表顺序取前 5 套（保证旧站升级后不空）；
- **≤4 套**：页脚按钮；**≥5 套**：页脚下拉（6 套按钮在 390px 会溢出）；
- 个人设置始终下拉，只列展示清单 + 「跟随公开」；
- 管理页可上架/下架，但不得突破当前上限；达到上限时上架按钮禁用，API 返回 `DISPLAY_FULL`；
- 新增/下线 key 自动同步；未知/已隐藏/已下线 key 回退 `standard` / `default`，不白屏。

切换器与展示清单改造属于 A0，不是 A5 的收尾项。

---

## 十、模型接入与成本

### 10.1 适配层

环境变量（只在本机 shell / CI secret）：

```
AI_BASE_URL=…          # OpenAI 兼容端点
AI_API_KEY=…           # 绝不入库、绝不进浏览器
AI_MODEL=…             # 模型名
AI_TIMEOUT=60
```

`adapters/` 统一接口 `complete(system, user) -> str`；返回后**只做 JSON 解析与 schema 校验**，不执行模型产出的代码。无 Key / 断网时用 `mock.py` 的固定 Spec 走通全链路（CI 用）。

`cli.py compile <spec.json>` 与 `generate` 同级：人工手写 Spec 也走同一套 G1–G6，只是跳过模型调用。`mock` 只用于 CI 冒烟，不得把 mock 产物当可上线模板。

### 10.2 成本估算（按 token，不含单价）

| 项 | 版式 | 主题 |
|---|---|---|
| system + schema | ~1.5k | ~1k |
| 样例数据摘要 | ~1k | — |
| 输出 3 候选 | ~1.5k | ~1.5k |
| 2 轮 + 1 次修订 | ~12k | ~6k–8k |
| 截图视觉复核（3 张） | ~6k | ~3k |
| **单件合计** | **12k–18k tokens** | **6k–10k tokens** |

时间：单件 3–8 分钟（含 3 档截图）。缓存键 = `sha256(system+user+model)`，命中直接复用。

**人工时间另计**：3 个版式 + 3 个主题 × 最多 2 轮评审，加审批、文档与回退演练，约 3–4 人日。token 成本表只统计 API 消耗，不把人工时间折成 token。

### 10.3 降级

| 情况 | 降级 |
|---|---|
| 无 Key / 断网 | `mock` Spec 走通流程；也可人工手写 Spec |
| 模型输出非 JSON | 重试 1 次；仍失败记录原文，人工介入 |
| Schema 连续 3 次不合格 | 停在该设计，提示缩小场景描述 |
| 截图服务不可用 | 只跑静态闸门，评审标"未过视觉闸门"，不得批准 |

---

## 十一、安全与合规

1. **密钥**：只在环境变量；`.gitignore` 排除 `tools/ai-template/cache/`、`.env`；工坊页面不出现 key。
2. **数据最小化**：默认只发合成样例；不发 `jiye.mine.v1`、简介原文、作者主页、采集来源链接。真实样例需显式勾选并二次脱敏。
3. **注入面**：模型输出只当 JSON 解析；禁止 `eval`；CSS 由编译器生成，模型无法写入任意属性。
4. **供应链**：不引入前端框架；Python 依赖仅可选 `jsonschema`（也可手写校验）；截图复用本机 Chrome/CDP，不新增 Playwright 依赖。
5. **上线隔离**：AI 产物先落 `tools/ai-template/drafts/`，人工审批后原子发布；Pages 只发布合入后的静态文件。
6. **可审计**：每个 AI 版式/主题有 Spec、prompt 版本、模型名、审批人、指标；下线时保留记录。

---

## 十二、里程碑与验收

| 里程碑 | 交付 | 验收 |
|---|---|---|
| **A0 契约与基线（1.5d）** | 版式/主题两张 schema 骨架、能力矩阵、固定 fixture、`scripts/shot_matrix.py`、三档基线、展示清单 schema、切换器容量、`drafts/`、无 AI 基线 | 7 板块样例；5+5 展示时不溢出；6 套主题只显示 5；`unset AI_*` + 删 `tools/` 后一期回归全过 |
| **A1 双编译器（4–5d）** | `spec/layout.schema.json`、`spec/theme.schema.json`、`compiler.py`、主题 lint、`cli.py compile` | 同 Spec 两次编译字节一致；版式拒绝 `rails/sidebar`；主题拒绝缺 token/多 token；手工 Spec 可编译 |
| **A2 生成管线（2–3d）** | `cli.py generate`（kind=layout/theme）、适配器、缓存、两类合成样例 | 一条命令产 3 候选；`mock` 双类型离线全通；请求体不含真实收藏 |
| **A3 预览与闸门（2–3d）** | `preview.py`、`metrics.py`、六道闸门、Chrome/CDP 截图 | 每个失败有错误码；版式三档、主题跨 5 套展示主题跑通；G3/G4/G6 可复现 |
| **A4 工作台与设计管理处（2–2.5d）** | 候选对比、批准/驳回/迭代、草稿转正式、`manage.html` 展示清单与最大上架数 | 单次评审 ≤10 分钟；批准前运行目录零变化；默认 5 套时上架第 6 套被拒、提高上限后可继续；`standard/default` 不可下架 |
| **A5 试点与治理（3–4d）** | 3 个 AI 版式 + 3 个 AI 主题入库、说明、展示清单、下线/回滚演练 | 设计均过 G1–G6；前端版式/主题各 ≤5；下线回退 `standard/default`；断网/无 Key 下一期功能全可用；CI 全绿 |

**总计 15–19 人日**，另计 3–4 人日评审/验收。A0 未通过不得进 A1；A1 未通过不得进 A2；A3 未通过不得批准任何设计。

---

## 十三、风险

| 风险 | 表现 | 对策 |
|---|---|---|
| 能力漂移 | Spec 有字段，页面没有对应 DOM，CSS 静默空转 | A0 能力矩阵；schema 拒绝 `rails/sidebar/timeline`；G3 断言关键结构存在 |
| 主题回耦合 | 版式指定主题，用户切主题后观感错位 | 版式 Spec 不含 `theme`；主题独立成 CSS；同一版式跨 5 套展示主题回归 |
| 截图基线缺失 | G3/G4/G6 无法复现，评审靠肉眼 | A0 补 `shot_matrix.py` + fixture + 基线 JSON；未跑截图不得批准 |
| Spec 表达力不足 | 想要的版式/主题"填不出来" | 版式走 3 原型 + 参数；主题只在 29 token 内；新结构/新 token 走人工 |
| 生成同质化 | 10 个候选像 1 个 | 候选强制 2 项差异；G6 截图/结构/token 差异；人工否决 |
| 展示位被内置占满 | 6 套内置主题占 5 个名额，AI 主题无法上架 | 管理页允许换入换出；`default` 锁定，其余内置可下架 |
| 评审疲劳 | 看 3 个 iframe 看不出差别 | 只对比 3 档首屏 + 差异字段高亮；单次 ≤10 分钟 |
| 成本失控 | 反复重生成 | 轮次 ≤2、候选 ≤3、缓存、mock 兜底 |
| 维护断层 | 半年后没人懂为什么这样 | Spec + 说明 + 审批记录三件套；季度复审 |
| 闸门形同虚设 | "先上线再说" | 未过 G1–G6 不允许写入 `templates.js` / `theme.js`（脚本层面拒绝） |
| 工具页误上线 | `tools/` 进了 Pages | `pages.yml` 白名单拷贝；CI 断言 `_site/tools`、`_site/docs`、`_site/tests` 均不存在 |
| 切换器溢出 | 5 套按钮挤爆 390px 页脚 | 5 套即改下拉；A0 用 5+5 假数据实测 |

---

## 十四、待确认

1. 模型与端点（国内兼容 / 海外 / 本地），影响成本与稳定性。
2. 是否接受"参考截图"输入（多模态），会提高还原度也提高成本。
3. 审批人是谁（单人还是双人复核）。
4. 默认 5 套展示位是否长期保留，还是按设备/场景分组（本期只做单套全局清单，上限可配置）。
5. 是否给 AI 设计加 `origin:"ai"` 标记（运行时无用途，仅治理；本文倾向只放 docs，不进注册表）。
