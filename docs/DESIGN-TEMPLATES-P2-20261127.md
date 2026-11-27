# 二期详细设计 · AI 模板工坊

> 版本 v1.1 · 2026-11-27 · 状态：评审修订完成，待开发
> 对应方案：`docs/PLAN-TEMPLATES-20261127.md`（D70–D73、D92–D95）
> 评审记录：`docs/REVIEW-TEMPLATES-P2-20261127.md`
> 前置：一期 3 套版式、布局 token 白名单、`templates.js` 注册表已就绪；截图脚本与基线由 A0 新建，不再假设已存在
> 核心定位：**AI 是生产工具，不是运行时依赖**——生成在离线/本机完成，线上仍是零构建纯静态

> **v1.1 修订**：Spec 只保留渲染层已落地的 `nav / lead / bands / toc` 四类能力；删除主题绑定与 `rails / timeline / rail`；补齐 draft 目录、原子发布、`status` 与回退；G3/G4/G6 改用本机 Chrome/CDP + 固定 fixture；增加 6 套版式切换容量策略；工期改为 12–15 人日 + 2–3 人日评审。

---

## 零、评审结论

二期主线成立：模型只产受限 Spec，编译器产 CSS，六道闸门 + 人工审批后入库。v1.0 的主要问题是**把尚未落地的渲染能力写进了 Schema**，并假设截图基线已存在。v1.1 按以下五条收敛：

1. **能力先对齐**：只允许 `nav / lead / bands / toc` 四个已被 `render.js` 与 `index.html` 消费的能力位；`sidebar / rail / timeline / titleLines` 不进 P2。
2. **主题不绑定**：Spec 不含 `theme`；预览主题只走 `?theme=`，不落盘。
3. **草稿先隔离**：候选写 `tools/ai-template/drafts/<key>/`；批准后才原子发布到 `assets/`、注册表与 `docs/templates/`。
4. **闸门可复现**：A0 补 `scripts/shot_matrix.py`、固定 fixture 与三档基线，用本机 Chrome/CDP，不引入 Playwright。
5. **容量先收口**：6 套版式时页脚切换器由按钮改为下拉；下线 key 回退 `standard`，不白屏。

---

## 一、目标与非目标

### 1.1 目标

1. 用自然语言（可附参考截图）描述想要的版式，产出一条可直接上线的版式模板。
2. 产物必须**结构可控**：不出现外链资源、不出现 `!important`、不改 DOM/JS、不引入依赖。
3. 产物必须**可评审**：候选对比、指标量化、审批留痕、一条命令回滚。
4. 产物必须**可维护**：有设计说明与来源 prompt，后来的人知道它为什么长这样。

### 1.2 非目标

- 不做运行时 AI 换肤、不做"访客一句话换模板"。
- 不让 AI 写 HTML/JS、改 `render.js`、改数据。
- 不做自动合并/自动发布（审批是硬闸门）。
- 不做面向公众的模板市场、不做拖拽编辑器。
- 不用 AI 生成内容文案、采集结果或主题数据。

---

## 二、为什么"AI 只产 Spec"

让模型直接写 CSS，问题不在"写得丑"，在于**不可控面太多**：外链字体、`position:fixed` 遮挡、`!important`、渐变堆叠、移动端溢出、无对比度。靠 prompt 约束，成功率不稳定；靠 lint 事后拦，返工率高。

改为"模型填表、编译器写 CSS"：

```
模型输出：{ archetype:"news", nav.style:"tabs", bands.columns:3, coverRatio:"16:9", … }
编译器输出：确定性 CSS（骨架 + 参数注入），同一 Spec 两次编译字节一致
```

好处：

- **枚举收敛**：模型只能在 3 种版式原型、4 种封面比例、2–4 列之间选，不会发明第 4 种结构。
- **数值有界**：栏宽 240–340、时间线条目 3–8，越界直接 schema 拒绝。
- **可解释**：Spec 就是设计说明，评审看 JSON 比看 300 行 CSS 快。
- **可回归**：改了某个参数，diff 只有几个数字，不产生"整份 CSS 重写"。

代价：表达力受限。一期 3 个原型 + 参数空间，足够覆盖"简洁/门户/画册"的变体；真正需要新结构的，走人工设计（仍按一期三步）。

---

## 三、系统架构

```
tools/ai-template/
├── cli.py                 入口：generate / compile / validate / preview / approve / rollback
├── spec_schema.json       Design Spec 的 JSON Schema（唯一契约）
├── compiler.py            Spec → CSS（纯函数，零副作用）
├── prompts/
│   ├── system.md          角色、可用枚举、禁止项
│   ├── generate.md        生成候选的指令模板
│   └── revise.md          按评审意见迭代的模板
├── adapters/
│   ├── openai_compat.py   OpenAI 兼容（含国内兼容端点）
│   ├── local.py           本地模型（可选）
│   └── mock.py            离线测试用固定 Spec
├── preview.py             真实页面 + 样例数据 + 三档截图
├── metrics.py             溢出/对比度/体积/辨识度
├── workbench/             评审页（本机）
├── cache/                 prompt 哈希 → 响应（.gitignore）
└── reviews/               审批记录 YYYYMMDD-<key>.json
```

产物落点：

```
assets/layouts/<key>.css        编译器输出（唯一代码产物）
assets/templates.js             注册表追加 5 行
docs/templates/<key>.md         设计说明（来源 prompt、Spec 摘要、审批人）
docs/templates/<key>.json       Spec 原文件（可复现）
```

约束：`tools/` 不进 Pages 构建（`pages.yml` 需追加排除 `tools/**`）；工坊只本机跑。

---

## 四、Design Spec

### 4.1 字段表

| 字段 | 类型 | 取值 / 区间 | 说明 |
|---|---|---|---|
| `version` | int | 固定 1 | 版本演进用 |
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

主题只用于预览：`?theme=tech` 是临时参数，不进 Spec、不进审批记录、不影响发布 CSS。同一 Spec 在 6 套主题下结构必须一致。

### 4.2 示例 Spec（门户·紧凑）

```json
{
  "version": 1,
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

### 4.3 提示词结构

`system.md` 固定四段：角色（版式设计师）、可用原型与能力矩阵、禁止项（不写 CSS/HTML/JS、不发明字段）、输出格式（纯 JSON，3 个候选，每个带 `rationale`）。`generate.md` 注入：站点定位、**合成样例数据摘要**（虚构标题/标签/数量）、目标场景、约束。`revise.md` 注入：上一版 Spec + 评审意见 + 指标偏差，要求"只改必要字段"。

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

### 5.2 确定性

- 输入 Spec 规范化（键排序、数字取整到 1 位）后再渲染。
- 不使用随机数；时间戳只进注释，可 `--no-timestamp` 关闭。
- 断言：同 Spec 两次编译 `sha256` 一致。
- CSS 输出按"变量 → 结构 → 媒体查询"固定顺序，diff 可读。

---

## 六、生成与评审流程

```
1. 输入        自然语言 + 可选参考截图 + 目标场景（简洁/门户/画册）
2. 生成        模型产出 3 个候选 Spec（枚举内、数值在区间内）
3. 校验        JSON Schema + key 唯一性 + 与已有模板的字段重复度
4. 编译        3 份 CSS（<8KB），写入 tools/ai-template/drafts/<key>/<candidate>/
5. 预览        固定 fixture + 真实页面，1280 / 768 / 390 截图
6. 指标        溢出/对比度/体积/辨识度/控制台错误
7. 评审        人工在 workbench 对比，选 1 个或要求迭代（≤2 轮）
8. 审批        批准 → 草稿转为正式：CSS + 注册表 + 说明 + 审批记录
9. 回归        CI（lint + 截图矩阵 + 现有用例）
10. 合入       一个提交（CSS + 注册表 + docs），可单提交回退
```

**发布顺序**：先写 CSS 与 `docs/templates/*`，再原子替换 `templates.js`；任何一步失败都不改运行目录。驳回或未批准的候选留在 `drafts/`，不删除，供 prompt 复盘。

候选策略：3 个候选必须在**至少 2 个维度**上不同（列数、封面比例、首屏类型、密度），否则要求模型重出，避免"三个几乎一样"。

---

## 七、六道闸门

| 闸门 | 检查 | 方法与阈值 | 失败处置 |
|---|---|---|---|
| **G1 Schema** | 字段齐全、枚举合法、数值区间、key 格式、`rationale` ≥3 条；拒绝 `rails/theme/sidebar` | `jsonschema` 或同契约手写校验 | 直接拒绝，不回传模型 |
| **G2 编译** | 白名单属性、无色值、无 `!important`/`@import`/`url(`、CSS ≤10KB、规则 ≤160 | 复用 `layout_lint.py` + 预算 | 编译失败，提示具体字段 |
| **G3 渲染** | 1280/768/390 无横向溢出、卡片可见、导航可点、控制台 0 报错 | 本机 Chrome/CDP + 固定 fixture + DOM 断言 | 记录档位与元素，退回迭代 |
| **G4 无障碍** | 正文对比度 ≥4.5、大字 ≥3.0、点击区 ≥44px、focus 可见、标题层级不乱 | 计算 + DOM 断言 | 必须修复，不能豁免 |
| **G5 性能** | CSS 字节 ≤8KB、无外部字体/图片、无固定定位遮挡 | 静态统计 | 超预算改字段，不改闸门 |
| **G6 辨识度** | 固定 fixture 三档截图 dHash 汉明距离 ≥10，且结构指纹与现有 3 套至少 2 项不同（列数/首屏/导航/密度） | Chrome 截图 + 结构指纹 | 视为"重复造 default"，退回 |

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
  "candidates": 3,
  "rounds": 2,
  "metrics": { "cssKb": 6.8, "contrast": 5.1, "overflow": 0, "dhash": 14 }
}
```

---

## 九、治理

| 规则 | 内容 |
|---|---|
| 注册表最小化 | `templates.js` 只存 `label/desc/file/archetype/能力声明/status`；provenance 放 `docs/templates/*.json` |
| 草稿隔离 | 候选只写 `tools/ai-template/drafts/<key>/`；批准前不碰 `assets/layouts/` 与 `templates.js` |
| 原子发布 | 先写 CSS 与 docs，再原子替换注册表；任一步失败不留半成品 |
| 数量上限 | 内置版式 ≤6 套（人工 3 + AI 3）。超限必须下线一套，不许无限膨胀 |
| 季度复审 | 每季度检查：是否仍被使用、是否与新版式重复、移动端是否仍达标；不用则标 `status:"deprecated"` |
| 下线回退 | `deprecated` 不进入切换器；本地偏好指向已下线 key 时回退 `standard`，并清理无效值 |
| 回滚 | revert 单个提交（CSS + 注册表 + docs），不涉及数据与主题 |
| 责任 | 审批人对该模板的视觉与可用性负责；prompt 与模型版本必须可追溯 |
| 命名 | `key` 与文件名一致，禁止 `new/new2/final` 这类命名 |

### 9.1 版式切换器容量

当前 `assets/layout.js` 的 `renderSwitch()` 会把注册表里的每个 key 都渲染成按钮。3 套时可用，6 套时 390px 必然拥挤。P2 定为：

- **≤4 套**：页脚继续用按钮；
- **≥5 套**：页脚改为 `<select>`，与「我的」设置里的「我的版式」一致；
- 个人设置始终下拉，不因套数变化改结构；
- 新增 key 自动出现，下线 key 自动消失；
- 未知/已下线 key 回退 `standard`，不白屏。

切换器改造属于 A0，不是 A5 的收尾项；否则 6 套模板上线当天才发现页脚放不下。

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

| 项 | 单次 | 单模板 |
|---|---|---|
| system + schema | ~1.5k | — |
| 样例数据摘要 | ~1k | — |
| 输出 3 候选 | ~1.5k | — |
| 单轮合计 | ~4k | — |
| 2 轮 + 1 次修订 | — | ~12k |
| 截图视觉复核（可选 3 张） | ~2k | ~6k |
| **合计** | — | **12k–18k tokens** |

时间：单模板 3–8 分钟（含 3 档截图）。缓存键 = `sha256(system+user+model)`，命中直接复用。

**人工时间另计**：3 个试点模板 × 最多 2 轮评审，加审批、文档与回退演练，约 2–3 人日。token 成本表只统计 API 消耗，不把人工时间折成 token。

### 10.3 降级

| 情况 | 降级 |
|---|---|
| 无 Key / 断网 | `mock` Spec 走通流程；也可人工手写 Spec |
| 模型输出非 JSON | 重试 1 次；仍失败记录原文，人工介入 |
| Schema 连续 3 次不合格 | 停在该模板，提示缩小场景描述 |
| 截图服务不可用 | 只跑静态闸门，评审标"未过视觉闸门"，不得批准 |

---

## 十一、安全与合规

1. **密钥**：只在环境变量；`.gitignore` 排除 `tools/ai-template/cache/`、`.env`；工坊页面不出现 key。
2. **数据最小化**：默认只发合成样例；不发 `jiye.mine.v1`、简介原文、作者主页、采集来源链接。真实样例需显式勾选并二次脱敏。
3. **注入面**：模型输出只当 JSON 解析；禁止 `eval`；CSS 由编译器生成，模型无法写入任意属性。
4. **供应链**：不引入前端框架；Python 依赖仅可选 `jsonschema`（也可手写校验）；截图复用本机 Chrome/CDP，不新增 Playwright 依赖。
5. **上线隔离**：AI 产物先落 `tools/ai-template/drafts/`，人工审批后原子发布；Pages 只发布合入后的静态文件。
6. **可审计**：每个 AI 模板有 Spec、prompt 版本、模型名、审批人、指标；下线时保留记录。

---

## 十二、里程碑与验收

| 里程碑 | 交付 | 验收 |
|---|---|---|
| **A0 契约与基线（1d）** | 能力矩阵、Spec schema 骨架、固定 fixture、`scripts/shot_matrix.py`、三档基线、切换器容量策略、`drafts/` 目录 | 基线可一键复现；7 板块样例（6 启用 + 1 空）；6 套假数据下页脚不溢出；现有 3 套版式截图与改造前一致 |
| **A1 Spec + 编译器（3–4d）** | `spec_schema.json`、`compiler.py`、单测、`cli.py compile` | 同 Spec 两次编译字节一致；`rails/theme/sidebar` 被拒；输出无颜色；手工 Spec 可编译 |
| **A2 生成管线（2–3d）** | `cli.py generate`、3 适配器、缓存、合成样例 | 一条命令产 3 候选 + 3 份 CSS；`mock` 离线全通；请求体不含真实收藏 |
| **A3 预览与闸门（2–2.5d）** | `preview.py`、`metrics.py`、六道闸门、Chrome/CDP 截图 | 每个失败有错误码与定位；3 档截图归档；G3/G4/G6 可复现 |
| **A4 工作台（1.5–2d）** | 本机对比页、批准/驳回/迭代、草稿转正式 | 一次评审 ≤10 分钟；记录落盘；批准前运行目录零变化 |
| **A5 试点与治理（2–3d）** | 3 个 AI 模板上线、说明文档、下线/回滚演练 | 3 个模板全过 G1–G6；6 套上限内切换正常；下线 key 回退 `standard`；CI 全绿 |

**总计 12–15 人日**，另计 2–3 人日评审/验收。A0 未通过不得进 A1；A1 未通过不得进 A2；A3 未通过不得批准任何模板。

---

## 十三、风险

| 风险 | 表现 | 对策 |
|---|---|---|
| 能力漂移 | Spec 有字段，页面没有对应 DOM，CSS 静默空转 | A0 能力矩阵；schema 直接拒绝 `rails/sidebar/timeline`；G3 断言关键结构存在 |
| 主题回耦合 | 模板指定主题，用户切主题后观感错位 | Spec 删除 `theme`；预览只走 `?theme=`；同一 Spec 跨 6 主题回归 |
| 截图基线缺失 | G3/G4/G6 无法复现，评审靠肉眼 | A0 补 `shot_matrix.py` + fixture + 基线 JSON；未跑截图不得批准 |
| Spec 表达力不足 | 想要的版式"填不出来" | 一期原型 + 参数空间覆盖 80%；新结构先改渲染层，二期不硬造 |
| 生成同质化 | 10 个候选像 1 个 | 候选强制 2 维差异；G6 截图 + 结构指纹；人工否决 |
| 评审疲劳 | 看 3 个 iframe 看不出差别 | 只对比 3 档首屏 + 差异字段高亮；单次 ≤10 分钟 |
| 成本失控 | 反复重生成 | 轮次 ≤2、候选 ≤3、缓存、mock 兜底 |
| 维护断层 | 半年后没人懂为什么这样 | Spec + 说明 + 审批记录三件套；季度复审 |
| 闸门形同虚设 | "先上线再说" | 未过 G1–G6 不允许写入 `templates.js`（脚本层面拒绝） |
| 工具页误上线 | `tools/` 进了 Pages | `pages.yml` 已是白名单拷贝；CI 断言 `_site/tools`、`_site/docs`、`_site/tests` 均不存在 |
| 切换器溢出 | 6 套按钮挤爆 390px 页脚 | ≥5 套改下拉；A0 用 6 套假数据实测 |

---

## 十四、待确认

1. 模型与端点（国内兼容 / 海外 / 本地），影响成本与稳定性。
2. 是否接受"参考截图"输入（多模态），会提高还原度也提高成本。
3. 审批人是谁（单人还是双人复核）。
4. 模板数量上限 6 套是否合适（当前人工 3 + AI 3）。
5. 是否给 AI 模板加 `origin:"ai"` 标记（运行时无用途，仅治理；本文倾向只放 docs，不进注册表）。
