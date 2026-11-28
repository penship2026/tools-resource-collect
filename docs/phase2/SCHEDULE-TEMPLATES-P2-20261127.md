# 二期排期与进度 · AI 设计与展示管理

> 版本 v1.12 · 2026-11-28 · 分支 `feat/templates-p2-20261127`
> 依据：`docs/phase2/DESIGN-TEMPLATES-P2-20261127.md` v1.4、`docs/phase2/REVIEW-TEMPLATES-P2-20261127.md`
> 口径：工程 15–19 人日，另计 3–4 人日评审/验收；每轮提交同步更新本表进度列；AI 只是增强，无 AI 基线必须全绿

---

## 一、里程碑

| 里程碑 | 内容 | 工期 | 依赖 | 出口验收 | 状态 |
|---|---|---|---|---|---|
| **A0 契约与基线** | 版式/主题 schema 骨架、能力矩阵、固定 fixture、`shot_matrix.py`、三档基线、展示清单 schema、切换器容量、`drafts/`、无 AI 基线 | 1.5d | 无 | 5+5 展示不溢出；6 套主题只显示 5；`unset AI_*` + 删 `tools/` 后一期回归全过 | 完成，待验收 |
| **A1 双编译器** | `spec/layout.schema.json`、`spec/theme.schema.json`、`compiler.py`、主题 lint、`cli.py compile` | 4–5d | A0 | 两次编译字节一致；版式拒绝 `rails/sidebar`；主题拒绝缺/多 token；手工 Spec 可编译 | 完成，待验收 |
| **A2 生成管线** | `cli.py generate`（kind=layout/theme）、适配器、缓存、两类合成样例 | 2–3d | A1 | 一条命令产 3 候选；`mock` 双类型离线全通；请求体无真实收藏 | 完成，待验收 |
| **A3 预览与闸门** | `preview.py`、`metrics.py`、G1–G6、Chrome/CDP 截图 | 2–3d | A2 | 失败有错误码；版式三档、主题跨 5 套展示主题跑通；G3/G4/G6 可复现 | 完成，待验收 |
| **A4 工作台与设计管理处** | 对比页、批准/驳回/迭代、草稿转正式、`manage.html` 展示清单与最大上架数 | 2–2.5d | A3 | 单次评审 ≤10 分钟；批准前运行目录零变化；默认 5 套时上架第 6 套被拒，提高上限后可继续；`standard/default` 不可下架 | 完成，待验收 |
| **A4.5 模板编辑闭环** | 管理台生成 1–5 候选、Spec 手改存新版本、按意见重生成、批准并推送、克隆 AI 模板、旧模板下线归档 | 1–1.5d | A4 | 生成/手改/迭代均不覆盖旧版；批准可显式上架；旧模板归档不改 CSS/注册表 | 已完成，待复验 |
| **A4.6 内置模板抽取** | 从现有 3 套版式 + 6 套主题抽取 Spec，管理页按 `clonable` 显示克隆入口 | 0.5d | A4.5 | 9 份 Spec 校验通过；内置版式/主题克隆出新 key 草稿；原 CSS/注册表不动；主题遗留对比度在预览中标红 | 已完成，待复验 |
| **A5 试点与治理** | 3 个 AI 版式 + 3 个 AI 主题入库、说明、展示清单、下线/回滚演练 | 3–4d | A4.5 / A4.6 | 全部过 G1–G6；版式上限放开到 20，3+3 全部显示；主题上限 8，8 套全部显示；下线回退默认；断网/无 Key 下一期全可用；CI 全绿 | 进行中：6 套候选已生成并过 G1–G6，待人工批准 |
| **A4.7 IDE 工作台** | 三栏 IDE：页面文件（首页/集合页/列表页/详情页）与模板树双模式、HTML/CSS 编辑、`spec.json` 编辑、预览切换、AI 改页面/Spec、模型切换、拖宽/左右互换、局域网 `--host` | 1.5d | A4.5 | 四页加载与 HTML/CSS 切换、页面保存备份、页面 AI 应用、候选加载、源码编辑、草稿预览、保存新版本、AI 应用、模型切换跑通；窄屏不横向溢出 | 已完成，2026-11-28 |
| **A4.8 历史与保存校验** | 页面/版式/主题历史与当前版本、任选两项对比、覆盖/恢复；页面 HTML/CSS 保存校验与错误明细弹窗 | 1d | A4.7 | 三类资源均有历史入口；历史↔历史、历史↔当前可对比；覆盖后可恢复；校验失败不落盘；模板历史不纳入 `studio-preview` | 已完成，2026-11-28 |

**合计**：15–19 人日 + 3–4 人日评审。

---

## 二、开工顺序

A0 是硬前置，未通过不进 A1。A0 拆成六个小步，可按序提交：

1. **能力矩阵**：把 `nav / lead / bands / toc` 写进版式 schema 骨架与 `templates.js` 对照表，拒绝 `sidebar/rail/timeline`；主题 schema 锁定 29 token。
2. **固定 fixture**：`tests/fixtures/preview.html`，6 个启用板块 + 1 个空板块，数据虚构；主题预览复用同一 fixture。
3. **截图脚本**：`scripts/shot_matrix.py`，本机 Chrome/CDP，输出 1280/768/390 尺寸、溢出、dHash、结构指纹到 `tests/baselines/*.json`。
4. **展示清单**：`site.yml` 增 `display.visible_layouts` / `display.visible_themes`，`generate.py` 写入 `assets/site.js`；`layout.js` / `theme.js` 读快照过滤。
5. **切换器容量**：5 套时改下拉，≤4 套保持按钮；个人设置始终下拉；用 5+5 假注册表测 390px。
6. **草稿与无 AI 基线**：`tools/ai-template/drafts/` 与 `.gitignore`；固定“`unset AI_*` + 删除 `tools/` + 断网 `file://`”回归，先跑通一期全部用例。

首版展示清单：

```text
版式：standard / news / magazine（3 套）
主题：default / dark / tech / campus / classical（5 套，anime 暂隐藏）
```

`standard` 与 `default` 锁定不可下架；其余内置可由管理页换出，给 AI 设计腾出展示位。

A0 的验收命令：

```text
python3 scripts/layout_lint.py
python3 -m unittest discover -s tests
node tests/test_layout.js
node tests/test_theme.js
node tests/test_render.js
python3 scripts/shot_matrix.py --baseline
python3 scripts/shot_matrix.py --check
python3 scripts/check_switch_fit.py
env -u AI_BASE_URL -u AI_API_KEY -u AI_MODEL python3 -m unittest discover -s tests
```

---

## 三、进度台账

| 日期 | 轮次 | 完成项 | 验证 | 备注 |
|---|---|---|---|---|
| 2026-11-27 | 评审 | 二期设计评审 v1.3、D92–D98、排期建立 | 文档自检、92 例回归 | 未动业务代码；AI 仅增强；5 套展示位待 A0 固化 |
| 2026-11-27 | A0 | 双类型 schema、能力矩阵、固定 fixture、45 张基线、展示清单、5+5 容量、drafts、无 AI 基线 | Python 101、版式 34、主题 12、视图 21、`layout_lint`、基线 45、5+5 0 溢出 | 完成，待验收 |
| 2026-11-27 | A1 | 手写 Spec 校验、双编译器、主题 lint、`cli validate/compile/lint` | Python 110、版式 34、主题 12、视图 21、基线 45、CLI 冒烟 | 两次编译字节一致；完成，待验收 |
| 2026-11-27 | A2 | 适配层（OpenAI 兼容 + mock）、生成管线、3 候选、缓存、`cli generate`、合成样例边界 | 新增 9 例；mock 版式/主题各 3 候选、主题 lint 全过、缓存命中、非法 JSON 重试 | 完成，待验收；本机采集数据 `topic-35bc9a90` 缺 section 导致既有数据自检 1 失败，与 A2 代码无关 |
| 2026-11-27 | A3 | 指标与六道闸门、固定 fixture 预览、5 套展示主题 × 三档截图、`cli preview` | Python 132、版式 34、主题 12、视图 21、45 张基线、5+5；6 个 mock 候选各 15 张全过 | 完成，待验收；G3/G4 每个失败带错误码 |
| 2026-11-27 | A4 | 评审/管理处页面、批准/驳回/迭代、草稿转正式、展示清单上下架、`cli serve/approve/reject/revise/display` | 新增 8 例；Python 141、版式 34、主题 12、视图 21、45 张基线、5+5；批准前资产哈希不变、事务回滚、第 6 套/锁定项拒绝 | 完成，待验收；只写工作区，不自动提交 |
| 2026-11-27 | A4 收尾 | 最大上架数可配置：`display.max_layouts/max_themes`、管理页输入、`/api/display/limit`、`cli display --max`、测试 9 例 | 默认 5+5 不回退；本机设版式 5、主题 8；`DISPLAY_LIMIT_TOO_SMALL` 拒绝降到当前展示数以下 | 完成；A5 前需决定版式 3+3 超 5 的处理 |
| 2026-11-27 | A4.5 | 管理台交互生成 1–5 候选、Spec 手改存 `-eN`、按意见重生成 `-rN`、批准并推送展示、克隆 AI 模板、旧模板归档 | Python 全量 151 例；新增生成/手改/迭代/归档/克隆/推送冒烟；手改不覆盖旧候选 | 已完成，待复验；真实模型 Key 未配置，仅 mock |
| 2026-11-27 | A4.6 | 抽取 3 套内置版式 + 6 套内置主题 Spec，管理页标记可克隆 | 9 份 Spec 校验通过；内置版式/主题均可克隆新草稿；旧 CSS/注册表不动 | 已完成，待复验；tech/anime 品牌对比度低于 G4 |
| 2026-11-27 | A5 | 3 个 AI 版式 + 3 个 AI 主题入库、说明、展示清单、下线/回滚演练 | 待开始；`max_layouts=20`、`max_themes=8`，版式 3+3 不再受 5 套限制 | 待开始 |
| 2026-11-28 | A5 | 3 套 AI 版式 + 3 套 AI 主题候选生成完成，15 张截图与 G1–G6 全部通过；`7efbff4` 已推送 | 六套候选各 15 shots 通过；未批准、`published.json` 仍为空 | 待人工确认后批准上架 |
| 2026-11-28 | A4.7 | IDE 工作台：左模板树/工具、中 `spec.json` 编辑+预览、右 AI 对话+模型切换；三栏拖宽、左右互换；`serve --host` 局域网 | Python 全量 161 例通过；Chrome 实测候选加载、主题/版式切换、草稿预览、真实 AI 改 Spec；`/` 与 `/ide` 200 | 提交 `07c1ae6`，已推送；`/review` 保留旧评审页；8787 已用 `0.0.0.0` 重启 |
| 2026-11-28 | A4.7+ | IDE 补页面文件：四页 2×2 选择、HTML/CSS 双标签、页面保存备份、页面 AI、`/api/pages` 与 `/repo` 白名单 | Python 全量 164 例通过；四页预览 200；Chrome 实测首页/集合页/详情页加载与切换；真实 AI 改页面 CSS/HTML 成功；`.env` 与 docs 被 404 | 提交 `8df66ce`，已推送；页面 AI 未限制 `max_tokens`，大文件需继续观察截断 |
| 2026-11-28 | A4.7+ 资源三 Tab | 左栏「页面文件 / 版式 / 主题」同组三 Tab；`/api/designs` 合并内置、已上架与 AI 草稿，版式 6 套、主题 10 套全量列出；内置只读真实预览，草稿仍可编辑 | Python 全量 165 例通过；`node --check` 通过；Chrome 实测计数 4/6/10、版式 6 行、主题 10 行、`standard/dark` 只读预览、`news-grid-compact` 改字符后保存启用 | 代码提交 `2a4fbc7`，文档随后提交；推送因 GitHub 443 超时待重试；内置项需在管理处克隆后才可编辑 |
| 2026-11-28 | A4.8 + 文档 | 页面/版式/主题历史、当前版本、任选两项对比、覆盖/恢复；页面 HTML/CSS 保存校验；二期使用说明书；docs 按一期/二期归档并补索引 | `tests.test_server/test_pages/test_studio` 55 例通过；`docs_check` 通过；Chrome 实测页面历史对比/恢复、主题历史、保存校验弹窗、版式历史入口 | 提交 `bf3e338`；A5 仍待人工批准上架 |

---

## 四、变更规则

- 每个里程碑完成即更新本表「状态」与「进度台账」，不等收尾统一补。
- A1 之后任何 schema 字段变更，必须先改能力矩阵与本表，再改实现。
- **展示位**：默认版式/主题各 5 套，内置占名额；上限可在管理页调到 1–20；设计库可多于上限，但不能全部进前端。
- **锁定项**：`standard` 版式、`default` 主题不可下架；任何回退都必须有落点。
- 回退以单个设计提交为单位，不涉及数据、主题绑定和采集端。
