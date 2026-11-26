# 一期详细设计 · 页面版式模板与板块导航

> 版本 v1.2 · 2026-11-27 · 状态：待评审
> v1.2 变更：新增人工置顶、画册大图字段、设置页默认版式三项（见 5.4）；一期工期 9–11 人日
> v1.1 变更：确认板块链接地址用 `?section=` 并补链接规范；切换器文案定为「简洁 / 门户 / 画册」
> 对应方案：`docs/PLAN-TEMPLATES-20261127.md`（D64–D69）
> 范围：只设计，不改代码；评审通过后按 M1→M5 实施
> 前置承诺：不新增页面文件、不引入构建步骤、不改变采集端与数据 schema

---

## 一、范围与验收总则

一期要解决四件事：

1. **版式可替换**：布局从 5 个页面的内联 `<style>` 抽到 `assets/layouts/*.css`，由 `data-layout` 选择。
2. **板块成栏目**：`sections.yml` 的板块按 `order` 升为一级导航，支持 `?section=` 板块视图。
3. **模板可扩展**：新增一套版式 = 1 个 CSS + 1 行注册，不改 HTML/JS；交付 3 套。
4. **编辑可控**：人工置顶、画册大图、站点默认版式三项走 `site.yml → site.js`，不污染采集数据。

验收总则（任一不满足即不算完成）：

- 3 套版式 × 3 套核心主题（default / dark / classical）在 1280 与 390 宽度下无破版、无横向溢出。
- 6 个启用板块全部出现在导航，停用板块不出现，0 单元板块有占位而不是消失。
- 新增第 4 套版式，全程只改 `assets/layouts/`、`assets/templates.js` 与文档。
- 置顶只改首屏与分节排序，不改索引顺序；画册大图缺失时回退封面；设置页改默认版式后新访客生效、老访客保留本机选择。
- 页面内联 `<style>` 中**不再出现任何色值、圆角、阴影、字号**。
- `python3 collector/generate.py --verify`、`scripts/docs_check.py`、`python3 -m unittest discover -s tests`、node 用例全部通过。
- `file://` 双击打开仍可用（不依赖 fetch / 构建产物）。

---

## 二、硬约束（不可协商）

| 编号 | 约束 | 来源 | 一期如何守住 |
|---|---|---|---|
| C1 | 零构建、`file://` 可直接打开 | D26 | 版式用静态 `<link>` + head 内阻塞脚本决定 href，不 fetch、不打包 |
| C2 | 采集只写数据、不写页面 | README 核心原则 | 版式与导航全部前端渲染；`sections.js` 是 `sections.yml` 的派生数据，不算页面 |
| C3 | 页面只有 5 个 | D18 | 板块视图走 `?section=`，不新增 html |
| C4 | 主题只定义 token，不改 DOM/JS | D25 | 主题文件不参与版式；版式文件不允许出现颜色 |
| C5 | 先归一、后抽层 | 本文 D69 | M1 未验收不进 M2 |

---

## 三、目标结构与加载顺序

```
assets/
├── style.css                 结构层：reset、组件骨架、布局 token 默认值
├── site.js                   站点配置与编辑推荐（新增，由 site.yml 生成）
├── templates.js              版式注册表（新增）
├── layout.js                 版式选择与注入（新增，head 内阻塞）
├── layouts/
│   ├── standard.css          简洁版式（基线，无覆盖）
│   ├── news.css              门户版式（新增）
│   └── magazine.css          画册版式（新增）
├── themes/*.css              6 套主题（不动）
├── theme.js / render.js / data-loader.js / personal.js
└── data/
    ├── index.js              采集单元索引（不动）
    ├── sections.js           板块注册表（新增，generate.py 生成）
    └── collections/*.js

site.yml                      站点外观 + 编辑推荐（根目录，设置页维护）
```

**head 加载顺序（5 个页面统一）**：

```html
<link rel="stylesheet" href="assets/style.css">
<script src="assets/site.js"></script>        <!-- 站点默认版式 + 置顶/大图，必须早于 layout.js -->
<script src="assets/templates.js"></script>   <!-- 注册表，必须早于 layout.js -->
<script src="assets/theme.js"></script>       <!-- 已存在：注入 theme-css -->
<script src="assets/layout.js"></script>      <!-- 新增：注入 layout-css，写在 theme 之后 -->
<noscript>
  <link rel="stylesheet" href="assets/themes/default.css">
  <link rel="stylesheet" href="assets/layouts/standard.css">
</noscript>
```

**CSS 优先级链（从低到高）**：

```
style.css（骨架 + token 默认值）
  → themes/<theme>.css（只有变量，位置对结果无影响，前置只为防闪烁）
  → layouts/<layout>.css（只覆盖结构；位于 style.css 之后才能生效）
  → 页面内联 <style>（M1 之后只允许容器级布局，不允许组件样式）
```

关键点：`layout.js` 注入的 `<link>` 必须在 `style.css` 之后、页面内联 `<style>` 之前。因此 5 个页面的内联块保留在 `<head>` 末尾不变，`layout.js` 用 `document.head.insertBefore` 插到内联 `<style>` 之前；若页面没有内联块则 append。

**选择优先级（D65）**：

| 优先级 | 来源 | 是否持久化 | 用途 |
|---|---|---|---|
| 1 | `?layout=news` | 否 | 预览、截图矩阵、分享对比 |
| 2 | `localStorage.jiye.layout` | 是 | 用户手动切换 |
| 3 | `SITE_CONFIG.default_layout`（`site.yml` → `site.js`） | — | 站点默认版式（设置页可改） |
| 4 | `TEMPLATES.default`（`templates.js` 一行） | — | 代码级兜底默认 |
| 兜底 | `standard` | — | 注册表缺失/文件 404 |

版式与主题互不覆盖：`?theme=` 与 `jiye.theme` 仍归 `theme.js` 管，两套记忆互不读写。

---

## 四、版式契约

### 4.1 `assets/templates.js` schema

```js
/* 版式模板注册表：新增版式 = 加 1 个 CSS + 在下方加 1 条 */
window.TEMPLATES = {
  default: 'standard',
  list: {
    standard: {
      label: '简洁',
      desc: '单列 Hero + 卡片网格（现行）',
      file: 'assets/layouts/standard.css',
      nav: false,        // 是否渲染板块一级导航
      lead: false,       // 是否渲染头条区
      bands: false,      // 是否按板块分节
      sidebar: false,    // 是否渲染侧栏
      toc: false         // 是否渲染目录
    },
    news: {
      label: '门户',
      desc: '板块导航 + 头条区 + 分节 + 侧栏',
      file: 'assets/layouts/news.css',
      nav: true, lead: true, bands: true, sidebar: true, toc: false
    },
    magazine: {
      label: '画册',
      desc: '单栏宽幅 + 章节编号 + 目录',
      file: 'assets/layouts/magazine.css',
      nav: true, lead: false, bands: true, sidebar: false, toc: true
    }
  }
};
```

能力声明（`nav/lead/bands/sidebar/toc`）是**渲染开关**：`render.js` 只渲染声明为 true 的区块，未声明的版式不需要额外 JS 分支。这就保证了"新增版式不改 JS"。

### 4.2 CSS 白名单

| 类别 | 允许 | 说明 |
|---|---|---|
| 盒模型 | `display`、`width/min/max`、`height/min/max`、`aspect-ratio`、`margin-*`、`padding-*`、`box-sizing` | 版式的本分 |
| 栅格 | `grid`、`grid-template-*`、`grid-auto-*`、`gap`、`column-gap`、`row-gap` | 分栏与密度 |
| 弹性 | `flex*`、`order`、`align-*`、`justify-*`、`place-*` | 排列 |
| 定位 | `position`、`top/right/bottom/left`、`inset`、`z-index` | 吸顶导航、角标避让 |
| 溢出 | `overflow*`、`overscroll-behavior` | 横滑导航 |
| 分隔 | `border-*`，但值内**必须**出现 `var(--border…)` | 章节分隔线 |
| 媒体 | `@media` 固定断点（1080 / 720 / 420） | 变量不能进 `@media`，允许字面量 |
| 变量 | `--layout-*` 默认值、`--ly-*` 版式私有变量 | 命名前缀隔离 |

**禁止**（`layout_lint.py` 会拦）：

- 颜色/背景：`color`、`background*`、`opacity`、`filter`、`mix-blend-mode`
- 字体排版：`font-family`、`font-size`、`font-weight`、`letter-spacing`、`line-height`（字号一律用 `var(--fs-*)`）
- 装饰：`box-shadow`、`border-radius`、`text-shadow`
- 危险写法：`!important`、`@import`、`url(`、`content:`、`position:fixed`（移动端遮挡）

字号不是一刀切禁止：版式允许 `font-size: var(--fs-hero)` 这类**纯 token 引用**，lint 规则为"`font-size` 值必须是 `var(--fs-` 开头"。

### 4.3 布局 token（默认值写在 `style.css :root`）

| Token | 默认 | 用途 |
|---|---|---|
| `--layout-wrap` | 1080px | 内容最大宽 |
| `--layout-gutter` | 24px | 左右留白（移动 16） |
| `--layout-header-h` | 60px | 吸顶导航高 |
| `--layout-hero-pad` | 68px 0 34px | 首页 hero 内边距 |
| `--layout-facts-gap` | 32px | hero 统计间距 |
| `--layout-section-gap` | 48px | 板块之间距离 |
| `--layout-grid-min` | 290px | 卡片最小列宽 |
| `--layout-grid-gap` | 18px | 卡片间距 |
| `--layout-card-pad` | 18px | 卡片内边距 |
| `--layout-cover-ratio` | 16 / 9 | 封面比例 |
| `--layout-band-cols` | 3 | 板块内列数 |
| `--layout-lead-cols` | minmax(0,2fr) minmax(0,300px) | 头条区两栏 |
| `--layout-side-w` | 300px | 侧栏宽 |
| `--layout-detail-cols` | minmax(0,1.4fr) minmax(260px,1fr) | 详情页两栏 |
| `--layout-article-max` | 780px | 公众号正文宽 |
| `--layout-search-w` | 320px | 搜索框宽 |

版式文件只覆盖需要的 token（如 news 把 `--layout-wrap` 改 1160、`--layout-band-cols` 改 3、`--layout-grid-gap` 改 16），其余沿用默认。**主题不得覆盖以上任何一个**。

---

## 五、板块数据供给

### 5.1 `assets/data/sections.js`（由 `generate.py` 生成，勿手改）

```js
window.SECTIONS = [
  {
    id: "infant-care",
    title: "婴幼儿养护",
    description: "0–3 岁喂养、睡眠、发育、健康护理与居家安全",
    order: 1,
    enabled: true,
    count: 2,
    age_min_months: 0,
    age_max_months: 36
  }
  /* … 共 7 条，含停用板块，enabled:false */
];
window.SECTIONS_UPDATED = "2026-11-27";
```

规则：

- 与 `sections.yml` **1:1**，包含停用板块（供未来启用，不供导航）；`count` 只统计 `enabled !== false` 的单元。
- 排序按 `order` 升序；`order` 重复时按 `id` 字典序兜底，并在 `--verify` 报警。
- 写入时机：`rebuild_index()` 末尾调用 `write_sections()`，与索引同一把 `WRITE_LOCK`、同一原子写方式。
- 设置页保存板块后走同一重建路径（不额外维护第二条写入链）。
- **前端兜底**：`window.SECTIONS` 不存在时，`layout.js` 从 `COLLECTION_INDEX` 聚合出 `{id,title,order:999,count}`，导航仍可用但不含空板块——保证老部署不炸。
- `--verify` 新增：`sections.js` 与 `sections.yml` id 集合一致、count 一致、order 唯一、`enabled` 一致。

### 5.2 为什么必须下发

现在前端只有单元级 `section_title`：顺序来自单元出现顺序（不是 `order`）、没有说明、0 单元板块消失、停用状态靠单元字段兜。没有注册表就无法做"栏目"。

### 5.3 空板块与停用

| 状态 | 导航 | 首页分节 | `?section=` |
|---|---|---|---|
| `enabled:true, count>0` | 显示 | 正常分节 | 正常列表 |
| `enabled:true, count=0` | 显示（灰字 + 0） | 一行占位"持续收集中" | 空态 + "去全部主题" |
| `enabled:false` | 不显示 | 不显示 | 404 式提示 + 返回 |

空板块保留的理由：导航结构稳定，不随采集数据增减跳动；同时暴露"这个栏目还没内容"，比悄悄消失更诚实。

### 5.4 编辑推荐与站点默认版式（site.yml → site.js）

**为什么单独一层**：置顶和画册大图是编辑决策，不是采集结果。写进 `collections/<id>.js` 会在重新采集时被覆盖，也违反"采集只产数据"的边界。统一放 `site.yml`，由 `generate.py` 生成 `assets/site.js`，前端只读。

`site.yml`（根目录，公开配置，设置页维护）：

```yaml
version: 1
site:
  default_layout: news        # standard / news / magazine
editorial:
  daily-website:
    pin: true
    pin_at: "2026-11-27 10:00"
    hero_image: "https://example.com/cover-1200.jpg"
  guwen-animation:
    pin: false
```

`assets/site.js`（生成物，勿手改）：

```js
window.SITE_CONFIG = { default_layout: "news" };
window.EDITORIAL = {
  "daily-website": { pin: true, pin_at: "2026-11-27 10:00", hero_image: "https://example.com/cover-1200.jpg" }
};
window.SITE_CONFIG_UPDATED = "2026-11-27";
```

规则：

- 只有显式配置的单元才出现在 `EDITORIAL`；缺省即"未置顶、无大图"。
- **置顶只影响首屏头条与板块内排序**，不改 `index.js` 的 `last_at` 排序，不影响列表页"最新"语义，也不改采集数据。
- 排序：置顶单元按 `pin_at` 倒序排在未置顶之前；同一板块内同样"先置顶、后最新"，置顶数不限但首屏主位只取第一个。
- `hero_image` 只在画册版式生效；缺省回退 `cover`，加载失败再回退占位渐变；`alt` 用单元标题。
- 校验：`id` 必须存在于采集单元；`default_layout` 必须在注册表内；URL 只允许 `https://`（本机调试可放行 `http://127.0.0.1`）；`pin` 必须布尔；`pin_at` 形如 `yyyy-mm-dd hh:mm`；`hero_image` ≤500 字符。
- 写入：设置页保存 → 校验 → 原子写 `site.yml` → 重新生成 `site.js`；与 `sections.js` 共用 `WRITE_LOCK`。
- 不参与采集：重新采集既不读也不写 `site.yml`，编辑字段天然不会被覆盖。
- 降级：`site.js` 缺失退回 `TEMPLATES.default`；单条 editorial 非法只忽略该条并 `console.warn`，不整站失败。

**入口分工**（沿用现有两个后台页，不新开页面）：

| 配置 | 入口 | 交互 |
|---|---|---|
| 默认版式 | `collector/settings.html` 新增「站点外观」面板 | 三选一下拉（简洁/门户/画册）+ 保存；提示"只影响未手动切过版式的浏览器" |
| 置顶 | `collector/collect.html` 的单元卡片 | 「置顶 / 取消置顶」按钮，写入 `pin` + `pin_at` |
| 画册大图 | 同上，单元卡片展开区 | URL 输入 + 「使用封面」清除；带 3:2 缩略预览 |

接口：`GET /api/site` 返回当前配置，`POST /api/site` 接受部分字段（`default_layout` 或 `{id, pin, hero_image}`），沿用现有 CSRF / Origin 校验；`POST` 成功后重新生成 `site.js` 并返回新版配置。

---

## 六、门户版式（news）规格

### 6.1 桌面 ≥1080px 线框（1280 实拍口径）

```
┌──────────────────────────────────────────────────────────────────────┐
│ ◈ 集页   婴幼儿 学前教育 中小学 AI科技 科技前沿 工具效率   [公开|我的]│ 60px 吸顶
├──────────────────────────────────────────────────────────────────────┤
│ 头条区                                                                │
│ ┌──────────────────────────────────────┬───────────────────────────┐ │
│ │ 主头条（置顶优先，其次最新）           │ 最新更新（5 条）           │ │
│ │ 16:9 封面 + 标题 2 行 + 摘要 2 行      │ 11.27 主题名              │ │
│ │ 平台徽标 · 作者 · N 条 · 日期          │ 11.26 …                   │ │
│ ├───────────────┬──────────────────────┤ ─────────────────         │ │
│ │ 副头条 2        │ 副头条 3             │ 热门标签（8 个）           │ │
│ │ 4:3 封面 + 标题 │ 4:3 封面 + 标题       │ [工具][AI]…               │ │
│ └───────────────┴──────────────────────┴───────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│ 筛选条（类型 / 平台 / 标签 / 搜索；板块筛选隐藏，由导航承担）           │
├──────────────────────────────────────────────────────────────────────┤
│ AI 与智能工具   4 个主题 · 大模型、Agent、AI 开发        查看全部 →   │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                              │
│ │ card     │ │ card     │ │ card     │  3 列 × 最多 2 行              │
│ └──────────┘ └──────────┘ └──────────┘                              │
├──────────────────────────────────────────────────────────────────────┤
│ 科技前沿 …（同结构，最多 6 张）                                        │
├──────────────────────────────────────────────────────────────────────┤
│ 页脚：主题 7 项 · 版式 3 项 · 合规说明                                 │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 区块规格

| 区块 | 规格 | 数据来源 | 空态 |
|---|---|---|---|
| 顶部导航 | 品牌 + 6 个启用板块 + 视图开关；`order` 排序；横向滚动不换行；`aria-current="page"` | `SECTIONS` | 启用板块 <2 时整条隐藏 |
| 头条区 | 两栏 `2fr / 300px`；主头条 1 + 副头条 2；封面 16:9 与 4:3 | 置顶单元（`pin_at` 倒序）优先，其余按 `last_at`；主位只取 1 个 | 无单元时整块显示引导文案 |
| 最新更新 | 5 条，日期 + 标题，可点进合集/详情 | 索引 `last_at` 前 5 | 隐藏 |
| 热门标签 | 前 8 个标签 chips | 索引 `tags` 词频 | 隐藏 |
| 板块分节 | 每板块一段：标题 + 说明 + 计数 + "查看全部"；3 列 × 2 行（最多 6 张）；置顶排在段首并带「置顶」角标 | `SECTIONS` + 按 `section` 过滤 + `EDITORIAL` 排序 | 一行占位 |
| 筛选条 | 保留类型/平台/标签/搜索；`#section-group` 隐藏 | 现有逻辑 | 无数据隐藏 |
| 页脚 | 主题切换 + 版式切换（简洁 / 门户 / 画册）+ 合规文案 | `theme.js` / `layout.js` | — |

### 6.3 板块视图 `?section=<id>`

- 不新增页面文件；`index.html` 内根据参数切换渲染模式。
- hero 替换为：板块标题（`--fs-hero`）、说明（≤640px）、`N 个主题 · M 条内容`、"← 全部主题"。
- 页签：`document.title = "<板块名> · 集页"`；`meta[name=description]` 同步板块说明。
- 列表：该板块全部单元，3 列网格，不分页（当前 12 单元量级足够；单板块 >30 时再议分页）。
- 导航高亮当前板块；切换板块走整页跳转（`location.href`），保证可分享、可前进后退。
- 非法/停用板块：显示"该栏目暂未开放"+ 返回链接，HTTP 仍是 200（静态站，不做 404 伪装）。

**链接地址规范（2026-11-27 已确认采用 `?section=`）**

| 场景 | 地址 | 规则 |
|---|---|---|
| 首页 | `index.html` | 不传 `section` 即全站视图 |
| 板块 | `index.html?section=<id>` | `id` 用 `sections.yml` 的稳定英文 id（如 `k12`、`ai`），不用中文标题 |
| 全部 | `index.html?section=all` | 等价首页，给"全部主题"一个明确出口 |
| 分享/复制 | 地址栏原样复制 | 不追加 `#` 锚点、不拼筛选参数，保证同一板块只有一个规范地址 |
| 筛选 | 页内交互，不进 URL | 刷新回到该板块默认列表，避免 `?section=&tag=&q=` 变体膨胀 |

实现顺序：先解析 `section` → 校验存在且 `enabled` → 渲染板块视图 → 同步高亮与 `document.title`；参数不合法一律落到提示态，不静默回首页。整页跳转（`location.href`）保证浏览器前进/后退与分享可用。

### 6.4 画册版式（magazine）差异

| 维度 | standard | news | magazine |
|---|---|---|---|
| **切换器文案** | **简洁** | **门户** | **画册** |
| 内容宽 | 1080 | 1160 | 920 |
| 首屏 | Hero 文案 + 统计 | 头条区 + 侧栏 | 刊头 + 目录 + 首篇大图 |
| 分节 | 无 | 板块分节（卡片网格） | 章节编号 01–06，每章 1 主 + 2 次 |
| 封面 | 16:9 网格卡 | 16:9 / 4:3 | 3:2 通栏大图；优先 `hero_image`，缺省 `cover` |
| 导航 | 无 | 顶部板块 tabs | 顶部 + 文内目录锚点 |
| 详情页 | 双栏 | 双栏 | 单栏 780，正文优先 |

每章首篇的"大图"取自 `EDITORIAL[id].hero_image`，没有则回退该单元封面；大图只做 `object-fit: cover` 裁切，不做拉伸变形。图片加载失败时 `onerror` 换成封面，仍失败则隐藏图、保留文字（不出现破图图标）。

magazine 只改"形"：封面比例、单栏、章节间距、编号排版，全部来自 `--layout-*` 与 `--ly-*`，不涉及任何颜色。

### 6.5 移动端（390 基线）

| 断点 | 变化 |
|---|---|
| ≤1080 | 头条区侧栏下移，主栏满宽 |
| ≤720 | 导航横向滑动、吸顶；副头条 2 列；板块 2 列；筛选条压缩，搜索占满整行 |
| ≤420 | 副头条 1 列；板块 1 列；头条标题降至 `--fs-title` |

硬性断言：`document.documentElement.scrollWidth === window.innerWidth`（390 / 768 / 1280 三档）。

### 6.6 可访问性与语义

- `<nav aria-label="板块导航">`；当前项 `aria-current="page"`；导航项高度 ≥44px。
- 跳过链接"跳到主要内容"，聚焦可见。
- 标题层级：`h1` 为站点名（视觉隐藏）；主头条 `h2`；板块标题 `h2`；卡片标题 `h3`（沿用 `render.js`）。
- 封面图 `alt` 用单元标题；装饰性图标 `aria-hidden`；星标按钮 `aria-pressed`。
- 不依赖 hover：所有 hover 才出现的信息（播放按钮）在 `@media (hover:none)` 下常显。

---

## 七、组件归一清单（M1 的施工图）

来源 PLAN 11.1，取值口径按"现行视觉最稳 + 便于 token 化"定：

| 组件 | 现 `style.css` | 现页面内联 | **统一为** |
|---|---|---|---|
| `.topic-grid` | minmax(290px,1fr) | index 260px | `minmax(var(--layout-grid-min),1fr)`，默认 290；news 覆盖 260 |
| `.topic-body` padding | 20/20/22 | index 16/18/18 | `var(--layout-card-pad)` 四周 + 底部 +2px |
| `.topic-cover` | height:160px | index aspect-ratio 16/9 | `aspect-ratio: var(--layout-cover-ratio)`，删 height |
| `.video-grid` | minmax(272px,1fr) | series 256px | 272 默认，series 页容器可覆盖 |
| `.video-info` padding | 14/16/16 | series 12/14/14 | 14/16/16 |
| `.facts` | gap 32 / margin-top 26 | 首页 40/24、合集 36/14、列表 32/16 | gap 32 / margin-top 24，页面不再覆盖 |
| `.toolbar input` | padding 10/14 | series 10/12、max-width 420 | padding 10/14；宽度走 `--layout-search-w` |
| `.topic-cover .badge` | top:14px | index bottom:10px | 统一 **左下 10px**，删 `top` |
| `.video-thumb .play` | hover 才显示 | series 常显 | hover / focus-visible 显示；`hover:none` 常显 |
| `.site-footer` padding | 30/0/44 | 无 | 30/0/44 走 `--ly-footer-pad` |

执行顺序：

1. 在 `style.css :root` 增加 17 个 `--layout-*` 默认值（不动颜色 token）。
2. 按上表把页面内联的组件规则**移入** `style.css`，同名规则只留一份。
3. 把 `style.css` 里 43 处布局字面量替换为 token（媒体查询断点保留字面量）。
4. 页面内联只保留"本页独有容器"（`.lead`、`.band`、`.mine-*`、`.parts-*` 等）。
5. 截图对比改造前后（5 页 × 1280/390），允许字体渲染差异，不允许布局位移。

---

## 八、文件级改造清单

### 新增

| 文件 | 作用 | 规模预估 |
|---|---|---|
| `assets/templates.js` | 版式注册表 + 默认版式 | ~40 行 |
| `assets/layout.js` | 选择/注入/`?layout=`/事件 | ~90 行 |
| `assets/layouts/standard.css` | 基线（仅注释与必要兜底） | <20 行 |
| `assets/layouts/news.css` | 门户版式 | 250–300 行 |
| `assets/layouts/magazine.css` | 画册版式 | 180–220 行 |
| `assets/data/sections.js` | 板块注册表（生成物） | 由数据决定 |
| `site.yml` | 站点外观 + 编辑推荐（根目录） | ~20 行起 |
| `assets/site.js` | `site.yml` 的前端产物（生成物） | 由配置决定 |
| `scripts/layout_lint.py` | 版式 CSS 白名单校验 | ~120 行 |
| `scripts/shot_matrix.py` | 截图矩阵（可选，复用 playwright-core） | ~150 行 |
| `docs/DESIGN-*` | 本文与二期设计 | — |

### 修改

| 文件 | 改动 |
|---|---|
| `assets/style.css` | 布局 token 默认值、合并 10 处重复、替换 43 处布局字面量 |
| `index.html` | 移除组件内联、加 `site.js`/`templates.js`/`layout.js`、加导航容器/头条容器/分节容器、`?section` 路由 |
| `series.html` / `list.html` / `single.html` | 移除组件内联、加两个脚本、内页面包屑（板块 › 主题） |
| `assets/render.js` | 新增 `sectionNav()`、`lead()`、`sectionBand()`、`breadcrumb()`；置顶角标与画册大图；能力开关判断 |
| `collector/generate.py` | `write_sections()`、`write_site_config()`、`rebuild_index()` 调用、`--verify` 新增板块与 `site.yml` 校验 |
| `collector/server.py` | 板块保存触发重建；新增 `GET/POST /api/site`（默认版式、置顶、画册大图），沿用 CSRF/Origin |
| `collector/settings.html` | 新增「站点外观」面板：默认版式三选一 |
| `collector/collect.html` | 单元卡片新增「置顶 / 取消置顶」与「画册大图」URL 输入、3:2 预览 |
| `scripts/docs_check.py` | 新增版式文件/注册表/内联样式检查，调用 `layout_lint` |
| `tests/test_pages.py` | 5 页均加载 `templates.js`+`layout.js`；内联无色值；注册表 3 条 |
| `tests/test_render.js` | 导航/头条/分节/面包屑的 DOM 断言 |
| `README.md` / `docs/DEPLOY.md` | 版式层目录与契约、切换方式 |

### 不新增、不修改

- 不新增 `section.html`；不改 `assets/data/collections/*.js`；不改 `themes/*.css`；不改采集解析器。

---

## 九、实施步骤

### M1 归一（1–1.5 人日）

1. 建 token，合并 10 处，替换 43 处，清内联组件。
2. `test_pages.py` 加"内联无 `#hex`/`rgb(`/`font-size: 数字`"断言。
3. 5 页 × 2 宽度截图对比，人工过一遍。

**退出条件**：`grep` 页面内联块无颜色/字号字面量；截图无位移。

### M2 版式层（2 人日）

1. `templates.js` + `layout.js`；`<html data-layout>`；`?layout=` 预览不落盘。
2. `layouts/standard.css`（基线）；页脚加"版式"切换（与主题切换并排，三项文案：简洁 / 门户 / 画册）。
3. 5 页接入；`collect.html` 不接入（本机工具页）。

**退出条件**：切 standard 与"完全不加载版式 CSS"视觉一致；`?layout=news` 在 news.css 未完成时安全降级为 standard（文件 404 检测）。

### M3 门户版式（2.5–3 人日）

1. `generate.py` 产出 `sections.js` + `--verify` 校验 + 设置页联动。
2. `Render.sectionNav/lead/sectionBand`；能力声明驱动渲染。
3. `index.html` 结构重排；筛选条保留、板块 chips 在 news 下隐藏。
4. `?section` 路由：hero/标题/空态/非法参数。
5. 移动端与无障碍；390 断言。

**退出条件**：6 板块可导航；空板块占位；停用板块消失；`?section` 分享可复现。

### M4 多模板与编辑推荐（2.5–3 人日）

1. `magazine.css` + 能力声明（toc）；章节首篇大图走 `hero_image` → `cover` → 占位的三级回退。
2. 页脚三选一切换器定稿（简洁 / 门户 / 画册，后续扩展只在注册表加一行）；`?layout` 与 localStorage 双通道。
3. `site.yml` + `site.js`：`write_site_config()`、校验、原子写；`layout.js` 读取默认版式。
4. 设置页「站点外观」面板：默认版式选择与保存。
5. 采集页单元卡片：置顶开关（`pin` + `pin_at`）、画册大图 URL 与预览。
6. 首屏/分节置顶排序与角标；6 组演示组合截图；README 补"新增版式三步"与"置顶/大图"。

**退出条件**：置顶后首屏主位变化且索引顺序不变；画册有/无大图均正常；设置页改默认版式后新开浏览器生效、已切过版式的浏览器保留本机选择；新增第 4 套版式演练只加 CSS + 1 行注册。

### M5 自检（1–1.5 人日）

1. `layout_lint.py`：白名单、`!important`、`@import`、`url(`、token 覆盖、注册表一致性。
2. 接入 CI；`docs_check` 增加 `layouts/` 目录与页面脚本检查。
3. 验收矩阵跑完并归档截图。

---

## 十、验收矩阵

### 10.1 视觉矩阵

| 版式 | 主题 | 1280 | 390 |
|---|---|---|---|
| standard | default / dark / classical | ✓ | ✓ |
| news | default / dark / classical | ✓ | ✓ |
| magazine | default / dark / classical | ✓ | ✓ |
| news | tech / campus / anime | ✓（smoke） | — |

smoke 只断言无溢出、无控制台报错、导航可点，不做像素比对。

### 10.2 功能断言

| 编号 | 断言 |
|---|---|
| T1 | 导航项数 = `enabled:true` 板块数；顺序 = `order` |
| T2 | `?section=k12` 只渲染 k12 单元；`document.title` 含板块名 |
| T3 | 0 单元板块在导航与分节占位均出现；停用板块两处都不出现 |
| T4 | `?layout=magazine` 刷新后回到 `jiye.layout`；`?layout` 不写存储 |
| T5 | 主题切换后版式不变；版式切换后主题不变 |
| T6 | 390 / 768 / 1280 三档 `scrollWidth == innerWidth` |
| T7 | `file://` 打开 index，导航与版式生效（无 fetch 报错） |
| T8 | 内联 `<style>` 中无 `#hex`、`rgb(`、`font-size:` 数字、`box-shadow` |
| T9 | 删除 `sections.js` 后导航从索引聚合，仍可用（兜底） |
| T10 | `layout_lint.py` 对含 `color:` 的假 CSS 返回非 0 |
| T11 | 置顶单元排在首屏主位，取消后回到最新；`index.js` 顺序与列表页顺序始终不变 |
| T12 | 置顶多个时按 `pin_at` 倒序，首屏主位只取 1 个，其余进副位或段首 |
| T13 | 画册有 `hero_image` 用大图、无则用 `cover`、坏链回退且不出现破图 |
| T14 | 设置页改默认版式：清空 localStorage 的新会话生效；已有 `jiye.layout` 的会话不被覆盖 |
| T15 | `site.yml` 写入非法 URL / 不存在的单元 id 被 400 拒绝，`site.js` 不被改写 |

### 10.3 回归

`python3 collector/generate.py --verify`（新增板块校验）、`python3 scripts/docs_check.py`、Python/Node 用例、GitHub Actions CI 全绿。

---

## 十一、风险与对策

| 风险 | 说明 | 对策 |
|---|---|---|
| 内联优先级 | 版式 CSS 被页面内联压住 | M1 先做；lint 检查内联；验收对比"删内联前后" |
| 主题×版式破版 | 6×3 组合不可穷举 | 只保证 3×3 核心矩阵；主题侧不改布局，破版面收敛 |
| 导航与数据不同步 | sections.js 过期 | 与索引同批生成；`--verify` 1:1 校验；前端兜底 |
| 板块空窗 | 新板块无内容像坏页 | 占位文案 + 计数 0 + "去全部主题" |
| SEO 变化 | 板块视图标题变化影响收录 | `?section` 给独立 title/description；不做伪静态 |
| 详情页面包屑 | 需要板块名，索引已有 `section_title` | 直接读索引，不新增字段 |
| 版式文件膨胀 | 每个版式写全套 | 只写差异；默认值在 `style.css`；lint 限 8KB |
| 置顶滥用 | 首屏长期不换、编辑忘记取消 | 设置页显示置顶数与 `pin_at`；超过 5 个给黄色提示；首屏角标明示「置顶」 |
| `site.yml` 与 `site.js` 漂移 | 默认版式/置顶不生效 | 保存即重建；`--verify` 做 1:1 校验；缺失时回退代码默认 |

---

## 十二、评审结论（2026-11-27）

**已确认（用户拍板，按此实施，共 5 项）**

1. 板块视图链接采用 **`index.html?section=<稳定 id>`**，不新增 `section.html`；规范见 6.3 的"链接地址规范"表。
2. 页脚版式切换器文案定为 **简洁 / 门户 / 画册**（对应 standard / news / magazine），后续新增版式只加注册表一行、切换器自动出现。
3. **支持人工置顶**：采集页单元卡片加「置顶 / 取消置顶」，写 `site.yml` 的 `pin` + `pin_at`；只影响首屏与分节排序。
4. **画册单开大图字段**：`hero_image` 只对画册版式生效，缺省回退封面；在采集页单元卡片填写。
5. **设置页暴露默认版式**：`settings.html` 新增「站点外观」面板，三选一写 `site.yml`，生成 `site.js` 供首屏读取。

无遗留待定项。
</content>
