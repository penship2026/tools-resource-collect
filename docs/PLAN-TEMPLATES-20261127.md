# 集页 · 页面模板体系两期方案计划

> 版本 v1.2 · 2026-11-27 · 状态：待评审
> v1.2 变更：新增 D75（置顶 / 画册大图 / 默认版式走 site.yml）；一期工期调为 9–11 人日
> v1.1 变更：确认板块视图链接用 `?section=`；版式切换器文案定为「简洁 / 门户 / 画册」
> 性质：**只做分析与方案**，不改代码、不改数据、不动排期与台账
> 关联：`docs/PLAN-20261126.md`（D21–D26 表现层分离、D43 布局 token 化清单）、`docs/REVIEW-20261126.md`、`docs/REQUIREMENTS-SECTIONS-SCHEDULE-20261126.md`
> 决策编号：本文新增 **D64–D82**，按 D35「只增不改」追加，不回写、不重排原文

---

## 一、结论摘要

1. **现状不是"没有模板"，而是"模板写死在页面里"**：5 个页面各自带一份内联 `<style>`（合计 417 行），组件样式在 `style.css` 与页面内联重复定义 10 处且取值不同；版式无法替换，主题只能换色。
2. **一期做"版式层"，把布局从页面里抽出来**：新增 `assets/layouts/*.css` + `data-layout` + `assets/templates.js`，交付 **简洁 / 门户 / 画册** 3 套版式（代码 key 仍为 `standard` / `news` / `magazine`）；门户版式以 `sections.yml` 的 7 个板块作为一级导航栏目，并支持 `?section=` 板块视图。
3. **一期成败取决于"先归一、再抽层"**：页面内联样式优先级高于外部 CSS，不先合并 10 处重复声明，`layout.css` 写了也不生效——这是顺序问题，不是工作量问题。
4. **二期做"AI 模板工坊"，但明确不做运行时 AI**：AI 只产出**受限的 Design Spec（JSON）**，由确定性编译器生成 CSS，过六道闸门 + 人工审批后才进注册表。AI 是生产工具，不是线上依赖。
5. **两期合计 19–23 人日**（一期 9–11，二期 10–12，含试点与验收），不改变采集端契约、不新增页面文件、不引入构建步骤，`file://` 仍可直接打开。
6. **一期是二期的前置**：没有版式枚举、布局 token 白名单、截图基线与注册表，AI 生成物就没有可校验的落地形态。

---

## 二、现状盘点

### 2.1 已有架构

```
采集层  collector/               纯 Python 标准库，只写数据、不写页面
          ↓  写入
数据层  assets/data/             index.js（派生索引）+ collections/<id>.js（唯一真源）
          ↓  读取
加载层  assets/data-loader.js    ?id= 解析、按需注入数据文件
          ↓
视图层  assets/render.js         卡片/列表项/详情/分集的唯一 DOM 实现
          ↓
结构层  assets/style.css         布局骨架 + 组件骨架（351 行）
主题层  assets/themes/*.css      6 套，29 个 token，只允许定义变量
切换层  assets/theme.js          页脚 7 项切换、localStorage、?theme= 预览
```

### 2.2 实测数据（以 2026-11-27 工作区为准）

| 维度 | 现状 | 说明 |
|---|---|---|
| 页面 | 5 个（index / series / list / single / collect） | D18 口径，长期固定 |
| 主题 | 6 套（default / dark / tech / campus / classical / anime） | 29 个 token 全量对齐 |
| 板块 | 7 个（`sections.yml`），其中 `humanities` 停用 | 0–36 / 36–72 / 72–216 月 + 4 个全龄 |
| 采集单元 | 12 个 | 索引按 `last_at` 倒序 |
| 渲染实现 | 1 份 `render.js` | D21 已落地，卡片/详情不再各页重复 |
| 页面内联样式 | 417 行（index 84 / series 52 / list 66 / single 215） | 含组件样式，不只是布局 |
| 公共样式 | `style.css` 351 行、22 处色值字面量 | 与内联样式双轨 |
| 组件重复声明 | 10 处（`.topic-grid`、`.topic-body`、`.facts`、`.toolbar` 等） | 见 PLAN 11.1 表，两套取值 |
| 版式层 | **不存在** | 无 `assets/layouts/`、无 `data-layout` |
| 板块数据下发 | **不存在** | 前端只有单元级 `section_title`，没有板块注册表 |
| AI 使用 | **0** | README 明确"全程不调用任何 AI 服务" |

### 2.3 能力成熟度

| 能力 | 评分 | 判断依据 |
|---|---|---|
| 数据层（单一真源 / 原子写 / 校验） | 9/10 | `--verify`、`rebuild_index()`、快照回滚齐备 |
| 采集层（入口 / 合并 / 定时 / 合规） | 8/10 | 三种入口 + 追加/覆盖 + Actions；风控与相关性噪声仍在 |
| 视图层（单一渲染实现） | 8/10 | `render.js` 统一；页面仍保留容器与路由 |
| 主题层（换色 / 换字体） | 8/10 | 6 套 + 契约 + 自检，成本已降到"加一个 CSS" |
| **版式层（换形）** | **3/10** | 布局写死在 5 个页面，无法配置、无法复用 |
| **板块作为栏目** | **3/10** | 只是首页筛选 chips，无顺序/说明/空板块，不能当导航 |
| **模板配置 / 复用** | **2/10** | 无注册表，无"一套模板给下一个站用"的形态 |
| **AI 生成侧能力** | **0/10** | 无 schema、无编译器、无闸门、无审批 |

---

## 三、问题清单（带证据）

**P-01 版式不可配置。** `single.html` 单页 215 行内联样式，详情页双栏比例、小红书 330px 并排、公众号栏宽全部写死；仓库内 `layouts/` 与 `data-layout` 零命中。换一种首页形态 = 改 HTML。

**P-02 内联优先级压住外部样式。** 同名组件在 `style.css` 与页面内联各写一份且值不同（`.topic-grid` 290px vs 260px、`.facts` gap 32 vs 40/36/32、`.topic-cover` height 160 vs aspect-ratio 16/9）。内联块在 `<head>` 中位于外部 `<link>` 之后，同特异性下后者胜——**任何新增的版式 CSS 都会被就地压住**。

**P-03 板块只是筛选维度，不是栏目。** 首页 chips 的 key 来自"单元出现顺序"的 `Object.keys(counts)`，不是 `sections.yml` 的 `order`；没有 `description`；0 单元的板块直接消失；停用靠单元上的 `section_enabled` 兜；没有 `sections.js` 下发，也没有 `?section=` 视图。

**P-04 模板概念缺失。** 6 套主题被当成"模板"，页脚只有主题切换；"模板"若等于主题，则永远只能换色。反过来若每个模板复制一套页面 HTML，5 页 × N 模板必然版本漂移（PLAN 第四章第 8 条已明确不做）。

**P-05 只换色会撞车。** `tech` 首版与 `dark` 观感过近，返工一次（D42 → D45）；`anime` 需要 18px 大圆角才立得住。说明"辨识度"不能只靠 token 取值，形态（密度、封面比例、分栏）才是差异的主要来源——这正是版式层的价值。

**P-06 AI 零接入且无生成侧治理。** 现在没有任何模型调用，也没有"AI 产出如何进仓库"的规则。若直接让 AI 写 CSS 并自动上线，等于把最不可控的产物放进最需要稳定的展示层。

---

## 四、总体设计：四层表现模型

一期把表现层拆成 **结构 / 版式 / 主题** 三层正交维度，模板只做"版式 + 密度"，主题仍独立：

```
结构层  style.css            组件骨架、栅格语义、布局 token 默认值
版式层  layouts/<layout>.css  只改"形"：分栏、密度、封面比例、导航形态、首屏结构
主题层  themes/<theme>.css    只改"色"：颜色、字体、圆角、阴影、字号
模板层  templates.js          版式注册表：key / label / 能力声明 / 默认版式
```

**正交规则（D64）**：版式不定义颜色，主题不定义布局；主题不覆盖布局 token，版式不得出现色值。这样 3 套版式 × 6 套主题 = 18 种观感，但维护成本是 3 + 6，不是 18。

**为什么模板不含主题（D65）**：模板若绑定主题，就会产生"用户选了深色、切模板又被改回浅色"的状态冲突，且组合数从 3 变 18 份预设。一期模板 = 版式 + 内置密度；主题与版式各自记忆（`jiye.theme` / `jiye.layout`），页脚并排两个切换器。

### 4.1 两期边界

| | 一期：页面模板订制 | 二期：AI 接入设计模板 |
|---|---|---|
| 核心问题 | 版式能不能换、能不能复用 | 新模板能不能被"设计"出来，且可控 |
| 手段 | 人工设计 CSS + 注册表 + 契约 | AI 产 Spec → 编译器产 CSS → 闸门 → 审批 |
| 产物 | 3 套版式、板块导航、6 组演示组合 | 模板工坊、Spec schema、编译器、3 个试点模板 |
| 运行方式 | 零构建、运行时纯静态 | 离线/本机生产，运行时仍纯静态 |
| 不碰 | 采集端、数据 schema | 采集端、一期版式契约 |

### 4.2 一期要点

- **3 套版式**：`standard`（简洁，现行，回归基线）、`news`（门户：板块导航 + 头条区 + 分栏 + 板块视图）、`magazine`（画册：单栏宽幅 + 章节编号 + 目录）。切换器文案固定为「简洁 / 门户 / 画册」，后续扩展只加注册表一行。
- **板块升为一级导航**：`generate.py` 从 `sections.yml` 生成 `assets/data/sections.js`（含 order、description、count、enabled），导航按 order 排序；空板块保留占位（避免导航随数据增减跳动），停用板块不出现。
- **板块视图**：`index.html?section=<id>`，不新增页面文件；hero 换成板块标题 + 说明 + 计数，标题同步 `document.title`。
- **编辑推荐与站点默认版式**：置顶、画册大图、默认版式三项统一走 `site.yml → assets/site.js`，不写进采集单元文件；置顶只影响首屏与分节排序，不改索引顺序；大图只对画册生效；默认版式优先级低于用户本机选择。
- **6 组演示组合**（只做文档与截图矩阵，不做运行时预设）：news×default、news×tech、news×dark、magazine×classical、magazine×campus、standard×default。
- **交付契约**：版式 CSS 白名单、`scripts/layout_lint.py`、`docs_check` 扩展、截图矩阵。

### 4.3 二期要点

```
自然语言描述 / 参考截图
        ↓
AI（受限输出，只给 JSON）
        ↓
Design Spec（JSON Schema 校验）
        ↓
确定性编译器（Spec → layout.css + registry 草稿）
        ↓
预览（真实页面 + 样例数据，1280 / 768 / 390 截图）
        ↓
六道闸门（schema / 编译 / 渲染 / 无障碍 / 性能 / 辨识度）
        ↓
人工审批（记录 reviewer / prompt / model / 时间）
        ↓
合入 templates.js + layouts/*.css（一个提交可回滚）
```

- **AI 不直接产 CSS/HTML/JS（D70）**：模型只填受限 schema（枚举 + 数值区间 + 理由），CSS 由编译器按模板拼装。这样"模型胡写 `!important`、外链字体、渐变堆叠"在结构上不可能发生。
- **三道强制闸门 + 三个人工关注点（D71）**：未过闸门不入库，未审批不注册；AI 产物默认 `draft`。
- **离线/本机（D72）**：API Key 只在环境变量，公网不暴露；不把采集数据、账号信息、私有主题发给模型。
- **一期交付 3 个试点模板 + 治理规则（D73）**：不是"能生成无限模板"，而是"能稳定生成 3 个可上线的模板"。

### 4.4 两期衔接

一期必须先把这些东西固定下来，二期才有落点：

| 一期产物 | 二期用途 |
|---|---|
| 3 个版式原型（standard/news/magazine） | Spec 的 `archetype` 枚举与 CSS 骨架 |
| 布局 token 白名单（约 16 个） | Spec 的数值区间来源 |
| `templates.js` 注册表 + 能力声明 | 编译器输出的落点与预览入口 |
| 1280 / 768 / 390 截图基线 | 辨识度与回归对比的参照 |
| `layout_lint.py` + `docs_check` | 闸门 G2/G4 的复用实现 |

---

## 五、里程碑与工期

### 5.1 一期（9–11 人日）

| 里程碑 | 内容 | 工期 | 验收 |
|---|---|---|---|
| **M1 归一** | 合并 10 处重复声明、布局 token 化、页面内联只留容器 | 1–1.5d | 5 页截图与改造前一致（像素级允许字体渲染差异）；`style.css` 无新增色值 |
| **M2 版式层** | `templates.js`、`layout.js`、`layouts/standard.css`（等价迁移）、`?layout=` 预览 | 2d | 切到 standard 与不加载版式 CSS 视觉一致；`?layout` 不写存储；4 个公开页均可加载 |
| **M3 门户版式** | `news.css`、板块导航、头条区、分栏、`?section=` 板块视图、移动端 | 2.5–3d | 6 个启用板块全部可导航；`?section=k12` 只显示该板块；390px 无横向溢出 |
| **M4 多模板与编辑推荐** | `magazine.css`、页脚版式切换、`site.yml`/`site.js`、置顶、画册大图、设置页默认版式、6 组截图 | 2.5–3d | 置顶只改首屏不改索引；大图三级回退；默认版式对新会话生效；新增第 4 套版式只加 1 CSS + 1 行注册 |
| **M5 自检** | `layout_lint.py`、`docs_check`/`test_pages` 扩展、验收矩阵 | 1–1.5d | 白名单外属性被拦；主题×版式矩阵全绿；CI 三件套通过 |

顺序硬约束：M1 未完成不得进 M2；M2 未完成不得进 M3/M4。

### 5.2 二期（10–12 人日）

| 里程碑 | 内容 | 工期 | 验收 |
|---|---|---|---|
| **A0 准备** | 冻结一期契约、样例数据、基线截图、prompt 骨架 | 0.5d | 基线可复现；样例覆盖 7 板块 |
| **A1 Spec + 编译器** | JSON Schema、枚举与区间、Spec→CSS 确定性编译 | 3–4d | 同一 Spec 两次编译字节一致；非法 Spec 被 schema 拒绝 |
| **A2 生成管线** | 模型适配层、prompt、候选 3 个、缓存、CLI | 2–3d | 一条命令产出 3 个候选 + 预览；断网/无 Key 可降级为手工 Spec |
| **A3 预览与闸门** | 1280/768/390 截图、溢出/对比度/体积/辨识度指标 | 2–3d | 6 道闸门有明确 pass/fail 与日志 |
| **A4 评审工作台** | 候选对比、逐项指标、批准/驳回 | 2d | 一次评审 ≤10 分钟；记录落盘 |
| **A5 试点与治理** | 3 个 AI 模板上线、审批记录、回滚演练 | 2d | 3 个模板全过闸门；回滚 = revert 一个提交 |

---

## 六、明确不做

1. 运行时 AI 换肤、"一句话建站"对公网开放。
2. 让 AI 直接改 HTML/JS 或直接写裸 CSS 上线。
3. 为每套模板/主题复制一份页面 HTML（页面数 × 模板数）。
4. 主题×版式的全组合逐一定制（只做 6 组演示，不做 18 组预设）。
5. 可视化拖拽编辑器、组件市场、模板市场。
6. 引入模板引擎 / SSG / CSS 预处理器（违反 D26 零构建与 `file://` 可开）。
7. 给每个板块生成独立页面文件（一期用 `?section=` 解决）。
8. 改采集端写页面，或把版式偏好写进采集数据。
9. 单元级自由拖动排序（一期只做"置顶 / 取消"，不做全量重排）。
10. 二期自动合并、自动发布（审批是硬闸门）。

---

## 七、风险与回退

| 风险 | 影响 | 处置 |
|---|---|---|
| 内联样式优先级未清干净 | 版式 CSS 不生效，误判"设计失败" | M1 先做；验收用"删掉内联块前后对比"验证 |
| 版式×主题组合破版 | 某主题下卡片挤压/对比度不足 | 3×3 核心矩阵 + 6 主题 smoke；版面只走 token |
| 板块增减导致导航跳动 | 用户找不到栏目 | 空板块保留占位；停用板块才移除 |
| `sections.js` 与 `sections.yml` 漂移 | 导航与实际内容不一致 | `--verify` 增加 1:1 校验；前端缺文件时按索引聚合兜底 |
| 移动端横向溢出复发 | 详情页/目录老问题重演 | 390px 自动断言 `scrollWidth == innerWidth` |
| AI 模板同质化 | "生成 10 套都像 default" | 辨识度闸门（dHash 距离）+ 人工否决 |
| AI 成本/延迟不可控 | 单模板反复重生成 | 候选上限 3、轮次上限 2、结果缓存、失败降级手工 |
| 生成物不可维护 | 一年后没人敢改 | 每个模板必须有设计说明 + 来源 prompt + 审批记录；季度复审 |

回退口径：一期回退 = 删除 `layouts/` 与注册表、恢复页面内联（git revert）；二期回退 = revert 单个模板提交，CSS 与注册表同提交，不涉及数据。

---

## 八、决策记录（D64–D87，追加）

| 编号 | 决策 | 落点 |
|---|---|---|
| D64 | 表现层三层正交：结构 `style.css` / 版式 `layouts/*.css` / 主题 `themes/*.css`；版式不写色值，主题不写布局；修订 11.3「布局值可进主题」的建议——布局只在版式层 | `assets/`、`docs/PLAN-20261126.md` 追加注 |
| D65 | 模板 = 版式 + 内置密度，不含主题；主题与版式各自记忆（`jiye.theme` / `jiye.layout`）；页脚并排两个切换器 | `assets/templates.js`、5 页页脚 |
| D66 | 板块升为一级导航：`generate.py` 由 `sections.yml` 生成 `assets/data/sections.js`（id/title/description/order/enabled/count），导航按 order；空板块保留占位，停用不显示 | `collector/generate.py`、`index.html` |
| D67 | 板块视图用 `?section=<id>`，不新增页面文件；hero 切换为板块标题/说明/计数，同步 `document.title` | `index.html` |
| D68 | 一期交付 3 套版式（简洁/门户/画册，key：standard/news/magazine）+ 6 组演示组合；版式 CSS 走白名单 + `layout_lint.py` | `assets/layouts/`、`scripts/` |
| D69 | 先归一后抽层：合并 PLAN 11.1 的 10 处重复声明，内联只留容器与页面级布局；未完成不进 M2 | 5 页 + `style.css` |
| D70 | AI 只产 Design Spec（受限 JSON，枚举 + 区间），CSS 由确定性编译器生成；禁止 AI 直接产出 CSS/HTML/JS | `tools/ai-template/` |
| D71 | AI 模板六道闸门（schema/编译/渲染/无障碍/性能/辨识度）+ 人工审批；默认 `draft`，未批准不入注册表 | `tools/ai-template/`、`templates.js` |
| D72 | 工坊离线/本机运行，公网不暴露；API Key 只走环境变量；不向模型发送采集数据与私有主题 | `tools/ai-template/`、`.gitignore` |
| D73 | 二期交付 3 个试点模板 + 模板库治理（每季复审、内置上限 6 套、回滚 = revert 单提交） | `docs/templates/` |
| D74 | 确认口径：板块视图链接固定为 `index.html?section=<稳定 id>`，不新增 `section.html`；版式切换器文案固定为「简洁 / 门户 / 画册」，新增版式只在注册表加一行、切换器自动出现 | 本文 4.2、P1 6.3 |
| D75 | 编辑推荐与外观配置独立成 `site.yml`（根目录），由 `generate.py` 生成 `assets/site.js`：`default_layout` 决定站点默认版式（优先级低于 `?layout` 与本机 `jiye.layout`）；`editorial.<id>.pin/pin_at` 只影响首屏与分节排序，不改索引；`hero_image` 仅画册生效，缺省回退封面；配置不写入采集单元文件，重新采集不会覆盖 | `site.yml`、`assets/site.js`、`collector/settings.html`、`collector/collect.html` |
| D76 | 页面专属样式外置为 `assets/pages/{series,list,single}.css`，按页引用；页面内不再保留 `<style>`。加载顺序 `style.css → pages/<page>.css → layouts/*.css`，版式层追加在 head 末尾即可覆盖页面样式，不再依赖「内联块位置」 | `assets/pages/`、4 页 `<head>`、`scripts/layout_lint.py` |
| D77 | 版式层只接 4 个公开页（index/series/list/single）；`collector/collect.html` 与 `collector/settings.html` 是本机工具页，不加载 `templates.js` / `layout.js`，避免版式影响采集与设置操作 | 4 页 `<head>`、`tests/test_pages.py` |
| D78 | 首页专属样式补入页面层：`assets/pages/index.css`（D76 清单原漏 index）。门户首页头条固定「1 主 + 3 副」，空板块在分节保留紧凑占位，板块导航为「全部 + 启用板块」；T1 导航项数口径按 enabled+1 | `assets/pages/index.css`、`assets/layouts/news.css`、`index.html`、P1 10.2 |
| D79 | 画册首页的空章节不排正文,只在目录保留 0 计数入口,并在板块视图显示空态;章节编号始终按启用板块全序计算,不因隐藏空章而重排错号 | `assets/layouts/magazine.css`、`index.html`、P1 6.4/T3 |
| D80 | 一期验收评审后的签收前整改：子页面包屑补板块层（`Render.breadcrumb` + `sections.js`）；`sidebar` 能力位统一关闭，避免声明空转；四页补「跳到主要内容」与首页视觉隐藏 `h1`；导航项最小高度 44px；内容宽与断点以代码实拍为准（news 1180 / magazine 960 / 头条 ≤1080 下移）；未使用的 `--layout-band-cols` / `--layout-lead-cols` 接入实际栅格 | `assets/render.js`、4 页、`assets/style.css`、`assets/pages/index.css`、`assets/layouts/news.css`、`docs/DESIGN-TEMPLATES-P1-20261127.md` |
| D81 | 个人视图的板块导航不得离开 `?view=mine`：`Render.sectionNav` 支持 `view` 参数，导航链接写成 `index.html?view=mine[&section=id]`；「我的」页按收藏所属 `section`（优先快照字段，旧数据回退索引）过滤，导航计数改为本地收藏数；公开页链接不受影响 | `assets/render.js`、`assets/personal.js`、`index.html` |
| D82 | 「我的」页动作收口到独立页脚：顶部工具栏的导出/导入/设置全部移除，导入方式与文件选择迁到专属 `mine-io.html`；我的页脚只保留「导入导出 / 设置 / 回到公开页」，不含采集入口，也不注入主题/版式切换；设置面板仍复用原面板并由页脚按钮打开 | `index.html`、`mine-io.html`、`assets/personal.js`、`assets/style.css`、`assets/theme.js`、`assets/layout.js` |
| D83 | 「我的」收藏卡不再维护第二套卡片结构，统一复用公开首页 `Render.topicCard`：封面、右上角「合集 / 单条」类型标签、平台徽标、标语、标签、条数与日期同构；右下角星标在「我的」内为取消收藏；原 `.fav-card` 系列独立样式与删除按钮下线 | `assets/personal.js`、`assets/render.js`、`assets/style.css` |
| D84 | 详情路由延续视图：`series.html` / `list.html` / `single.html` 读取 `view=mine`，品牌入口、返回链接与 `Render.breadcrumb` 回「我的收藏」，板块层链接为 `index.html?view=mine&section=<id>`；详情卡片、上下集链接、列表入口都透传 `&view=mine`，公开页不带该参数 | `series.html`、`list.html`、`single.html`、`assets/render.js`、`assets/personal.js` |
| D85 | 主站与「我的」首页筛选条统一吸顶：滚过筛选区后吸附在站点头与板块导航下方；吸顶时默认收成一行「筛选条件 / 展开」，点开才显示完整分组，离开吸顶恢复完整筛选。偏移不写死，由 `syncFilterSticky()` 按站点头与当前导航实际高度写入 `--layout-filter-top`；简洁版式与窄屏导航不吸顶时自动归零，画册版式补不透明底色避免内容穿透 | `assets/style.css`、`assets/layouts/magazine.css`、`index.html` |
| D86 | 个人站导入导出页纳入两条发布白名单：本地 `collector/server.py` 的 `STATIC_EXACT` 加 `/mine-io.html`，GitHub Pages artifact 加 `mine-io.html`；`assets/pages/mine-io.css` 随 `assets/**` 自动发布。否则本地返回「未对外开放的路径」，线上 Pages 返回 404 | `collector/server.py`、`.github/workflows/pages.yml`、`docs/GITHUB-PAGES.md`、`docs/DEPLOY.md` |
| D87 | 重新采集的「采集方式」增加「移除当前链接」，只对按链接/批量链接显示；输入框里的链接作为待移除项，只做本地匹配与删除，不重新抓取内容。主题采集不提供该选项。移除不计入 `intake`，另记一条 `runs`（mode=remove），保证下次重新采集仍回填原采集输入 | `collector/collect.html`、`collector/server.py`、`collector/generate.py` |

---

## 九、交付物

| 文档 | 内容 | 状态 |
|---|---|---|
| 本文 | 两期总体方案、现状分析、决策 D64–D87 | 本次交付 |
| `docs/DESIGN-TEMPLATES-P1-20261127.md` | 一期详细设计（契约、版式规格、文件级改动、验收矩阵） | 本次交付 |
| `docs/DESIGN-TEMPLATES-P2-20261127.md` | 二期详细设计（Spec schema、编译器、闸门、工坊、治理） | 本次交付 |

代码与数据已按一期 M1 起实施（进度见 `docs/SCHEDULE-TEMPLATES-P1-20261127.md`），实施按 D34「改动即落档」同步更新 README / TODO / WORKLOG。
