# 二期设计评审 · AI 模板工坊

> 日期：2026-11-27 · 基线：`feat/templates-p2-20261127`（`47d818d`，与 `main` 同点）
> 评审对象：`docs/DESIGN-TEMPLATES-P2-20261127.md` v1.0、`docs/PLAN-TEMPLATES-20261127.md` D70–D73
> 评审方式：通读二期设计与一期契约；核对 `templates.js`、`render.js`、`layout.js`、`layout_lint.py`、`pages.yml` 与测试基线；未改业务代码
> 基线回归：Python 92 例、版式 27 例、视图 21 例、`layout_lint` 均通过

---

## 一、结论

**方向成立，但 v1.0 不能直接开工。**

“AI 只产受限 Spec、编译器产 CSS、人工审批后入库”这条治理链是对的：它把最不可控的模型输出挡在运行时之外，也保住纯静态、零构建、`file://` 可开。问题不在理念，在**设计假设与当前仓库能力对不上**：

1. Spec 里有 4 类字段在页面上没有对应 DOM，生成了也不会生效。
2. Spec 绑定 `theme.source`，与 D65「模板不含主题」直接冲突。
3. 设计声称“截图基线全部就绪”，仓库实际没有截图脚本与基线。
4. “默认 draft”没有落点，批准后直接写运行目录，缺少草稿区与原子发布。
5. 6 套版式会撑爆现有页脚按钮切换器，容量策略未定义。
6. “AI 是可选增强”没有写成硬验收；容易出现“没配 Key 就少一块功能”的依赖回流。

这六项不解决，A1 编译器会先产出一批“合法但无效”的 CSS，A3 闸门也无法复现。建议按本文第五节重排，先做 A0 契约收敛，再进 A1。

---

## 二、阻断项

### R1 · Spec 表达力大于渲染能力（P0）

`DESIGN-TEMPLATES-P2` 的字段表允许：

- `nav.style: rail`（左侧竖排导航）
- `hero.timeline` / `timelineCount`
- `rails.sidebar` / `rails.width` / `rails.blocks`
- `cards.titleLines` / `cards.sloganLines`

但当前渲染层只消费 4 个能力位：

```text
index.html: cap('nav') / cap('lead') / cap('bands') / cap('toc')
render.js:  sectionNav() / lead() / sectionBand() / magazineToc()
templates.js: 3 套版式 sidebar 全部为 false
```

D80 已明确“`sidebar` 能力位统一关闭，避免声明空转”。因此 P2 若照 v1.0 生成 `rails` 或 `timeline`，CSS 会指向不存在的类；更糟的是 G3 可能照样通过——页面不溢出、不报错，但功能**静默不生效**，评审很难发现。

**处置**：P2 只允许 `nav / lead / bands / toc` 四个能力位；`sidebar`、`rail`、`timeline`、`titleLines` 等移出 schema，等渲染层真正落地后再进 P2.1。Spec 与 `templates.js` 共用一张能力矩阵，不能让模型自由发明结构。

### R2 · Spec 绑定主题，违反 D65（P0）

v1.0 的 Spec 有：

```json
"theme": { "mode": "existing", "source": "tech" }
```

D65 已定“模板 = 版式 + 密度，不含主题”，主题与版式各自记忆。Spec 一旦带 `theme.source`，模型就会把某个版式与某个主题绑在一起；预览像“科技风”，用户切到深色主题却得到另一套观感。长期还会把 3 套版式 × 6 套主题重新耦合回 18 份预设。

**处置**：从 Spec 删除 `theme`。预览主题只作为 `?theme=` 临时参数，不写 Spec、不进审批记录、不影响发布 CSS。

### R3 · “截图基线已就绪”与仓库事实不符（P0）

v1.0 开头写“截图基线全部就绪”，G3/G4/G6 又依赖 1280/768/390 三档截图与 dHash。实际仓库：

- `scripts/` 只有 `layout_lint.py`、`docs_check.py`、`launchd/`；
- 没有 `shot_matrix.py`；
- 没有 `tests/baselines/` 或截图归档；
- P1 设计把 `scripts/shot_matrix.py` 标为“可选”，一期并未交付。

也就是说，A3 无法从现有仓库一键复现，G6 没有参照物。

**处置**：A0 先补 `scripts/shot_matrix.py` 与固定 fixture（`tests/fixtures/preview.html`），用本机 Chrome/CDP 完成三档截图；基线保存为 `tests/baselines/*.json`（尺寸、溢出、dHash、结构指纹），不把大图塞进仓库。G6 用“固定 fixture 截图 dHash + 结构指纹”双指标，避免真实内容变化导致误判。

### R4 · draft 没有物理落点，发布不是原子操作（P0）

D71 说“AI 产物默认 draft，未批准不入注册表”，但 v1.0 的流程图第 8 步直接“写 CSS + 注册表 + 说明 + 审批记录”，没有定义：

- 草稿存哪里；
- 驳回/迭代的候选怎么留；
- 批准时 CSS、注册表、说明、审批记录如何一次性落盘；
- 中途失败如何不留下“CSS 已写、注册表没加”的半成品。

**处置**：固定两条目录：

```text
tools/ai-template/drafts/<key>/      # 候选期：spec.json / layout.css / preview/ / metrics.json
assets/layouts/<key>.css              # 仅批准后发布
assets/templates.js                   # 仅批准后追加
docs/templates/<key>.{json,md}        # 仅批准后发布
```

发布用“临时文件 + `os.replace`”，先写 CSS 与 docs，最后改注册表；失败时删除临时文件，草稿保留。驳回记录留在 `reviews/`，不删除候选，便于复盘 prompt。

### R5 · 6 套版式会撑爆页脚切换器（P0）

`assets/layout.js` 的 `renderSwitch()` 对 `Object.keys(LIST)` 全量渲染 `.layout-btn`。3 套时没问题；P2 加到 6 套后，页脚会出现 6 个按钮加“版式”标签，390px 下必然换行或溢出。个人设置里的「我的版式」是 `<select>`，反而没有这个问题。

**处置**：切换器定容量策略：**≤4 套用按钮，≥5 套改用下拉**；个人设置始终下拉。新增/下线 key 自动更新，不手工改页脚。下线 key 时，`layout.js` 对未知 key 回退 `standard`，并写测试防止白屏。

### R6 · AI 不得成为运行前提（P0）

二期定位是“AI 增强”，不是“AI 依赖”。当前设计虽然写了“AI 是生产工具，不是运行时依赖”，但没有可执行的验收口径：很容易在实现时让页面、构建或发布流程隐式依赖模型或 `tools/`。

**处置**：写死“无 AI 基线”：`unset AI_*`、删除 `tools/`、断网打开 `file://index.html`，一期全部功能仍须通过；AI 不可用时只失去“生成/评审新模板”，不得影响 3 套内置版式、主题、板块导航、个人收藏、导入导出、设置、采集。详见设计 1.3。

---

## 三、重要补充（P1）

### R7 · 样例数据默认脱敏

v1.0 说“样例数据摘要（标题/标签/数量，不含正文与作者主页）”，但标题与标签仍可能来自用户真实收藏。个人站数据只在 `localStorage`，不代表可以默认发给外部模型。

**处置**：默认用仓库内合成样例（6 个启用板块 + 1 个空板块，标题与标签全部虚构）；只有用户显式勾选“使用当前站点样例”时才发送真实标题，且去掉作者、来源链接、简介原文。P2 验收要检查请求体不含 `jiye.mine.v1` 内容。

### R8 · `pages.yml` 排除条款已过期

v1.0 写“`pages.yml` 需追加排除 `tools/**`”。实际 `pages.yml` 采用白名单拷贝：

```text
cp index.html series.html list.html single.html mine-io.html _site/
cp -R assets/. _site/assets/
```

`tools/` 本来就不会进 artifact，不需要再加排除。真正需要的是**产物断言**：部署后 `_site/tools/`、`_site/docs/`、`_site/tests/` 均不存在。

**处置**：把“修改 pages.yml 排除”改为“CI 检查 artifact 清单”；不为了一个不存在的目录改发布脚本。

### R9 · 工期漏了人工评审与基线建设

v1.0 的 10–12 人日只覆盖工程实现，未计：

- A0 的三档截图基线与 fixture；
- 每轮候选的人工对比（设计说“单次评审 ≤10 分钟”，但 3 个模板 × 2 轮仍需 2–3 人日）；
- 驳回、返工、文档与审批记录。

**处置**：工程 12–15 人日，另计 2–3 人日评审/验收；成本表只算 token，不把人工时间折成 token。

### R10 · 手工 Spec 应是一等入口

如果只有 `generate` 走模型，断网或没有 Key 时工坊就退化成 `mock`，无法真正产出模板。设计虽然写了“也可人工手写 Spec”，但 CLI 清单没有独立的 `compile` 入口。

**处置**：`cli.py compile <spec.json>` 与 `generate` 同级；手工 Spec 同样过 G1–G6，只是跳过模型调用。`mock` 只用于 CI 冒烟，不冒充“可上线模板”。

### R11 · 下线与回退要覆盖本地偏好

模板数量上限 6 套，必然遇到“下线一套”。当前 `layout.js` 只判断 key 是否存在，没有“deprecated 不显示”的注册表状态。

**处置**：注册表增加可选 `status`（缺省视为 `published`）；`deprecated` 不进入切换器，但保留 CSS 一个季度；用户本地 `jiye.layout` / `jiye.mine.layout.v1` 指向已下线 key 时回退 `standard`，并清理无效值。加一条 Node 用例覆盖。

---

## 四、建议的 P2 边界

保留原方向，不把二期改成“再手写 3 套 CSS”。但把二期拆成两段：

| 阶段 | 内容 | 目的 |
|---|---|---|
| **P2-A 契约收敛（1d）** | 能力矩阵、Spec 收敛、固定 fixture、三档基线、切换器容量策略、draft 目录、无 AI 基线 | 让后续每一步可验证 |
| **P2-B 生成与闸门（7–9d）** | schema/编译器、CLI、Chrome 截图、六道闸门、工作台 | 产出可评审候选 |
| **P2-C 试点与治理（3–4d）** | 3 个 AI 模板、审批记录、下线/回退演练、文档 | 证明可上线、可维护 |

明确不做：

- 不把 `sidebar` / `timeline` / `rail` 塞进 Spec 假装支持；
- 不让 Spec 绑定主题；
- 不引入 Playwright、模板引擎、构建步骤；
- 不为 AI 模板新增页面文件；
- 不自动合并、不自动发布；
- 不把真实个人收藏默认发给模型。

---

## 五、验收增量

在 v1.0 的 G1–G6 之外，补六条：

1. **能力对齐**：任何 Spec 字段都能在 `render.js` / `index.html` 找到消费点；schema 拒绝 `sidebar/rail/timeline`。
2. **主题解耦**：编译产物零颜色；同一 Spec 在 6 套主题下结构不变，审批记录不含 `theme.source`。
3. **草稿隔离**：批准前 `assets/layouts/` 与 `assets/templates.js` 无变化；批准后一次原子发布，失败无半成品。
4. **容量与回退**：6 套版式下页脚不溢出（390px 实测）；删除一套后旧本地偏好回退 `standard`，首页不白屏。
5. **隐私**：默认请求体不含真实收藏标题/标签/作者；开启真实样例需显式操作，日志可核对。
6. **无 AI 基线**：`unset AI_*`、删除 `tools/`、断网打开 `file://index.html`，一期全部功能与现有 3 套版式仍通过；AI 不可用不得影响站点。

---

## 六、结论与下一步

1. 接受 P2 的“离线生成 + Spec 编译 + 人工审批”主线。
2. 先按本评审修订 `DESIGN-TEMPLATES-P2` 为 v1.2，并追加 D92–D96。
3. 开发从 A0 开始：能力矩阵、fixture、三档基线、切换器容量、draft 目录、无 AI 基线；A0 不通过不进 A1。
4. A1 编译器只接受本文收敛后的字段；未落地能力一律拒绝，不做“先写着以后再说”。
