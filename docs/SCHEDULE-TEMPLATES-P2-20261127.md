# 二期排期与进度 · AI 设计与展示管理

> 版本 v1.3 · 2026-11-27 · 分支 `feat/templates-p2-20261127`（基线 `47d818d`）
> 依据：`docs/DESIGN-TEMPLATES-P2-20261127.md` v1.3、`docs/REVIEW-TEMPLATES-P2-20261127.md`
> 口径：工程 15–19 人日，另计 3–4 人日评审/验收；每轮提交同步更新本表进度列；AI 只是增强，无 AI 基线必须全绿

---

## 一、里程碑

| 里程碑 | 内容 | 工期 | 依赖 | 出口验收 | 状态 |
|---|---|---|---|---|---|
| **A0 契约与基线** | 版式/主题 schema 骨架、能力矩阵、固定 fixture、`shot_matrix.py`、三档基线、展示清单 schema、切换器容量、`drafts/`、无 AI 基线 | 1.5d | 无 | 5+5 展示不溢出；6 套主题只显示 5；`unset AI_*` + 删 `tools/` 后一期回归全过 | 完成，待验收 |
| **A1 双编译器** | `spec/layout.schema.json`、`spec/theme.schema.json`、`compiler.py`、主题 lint、`cli.py compile` | 4–5d | A0 | 两次编译字节一致；版式拒绝 `rails/sidebar`；主题拒绝缺/多 token；手工 Spec 可编译 | 完成，待验收 |
| **A2 生成管线** | `cli.py generate`（kind=layout/theme）、适配器、缓存、两类合成样例 | 2–3d | A1 | 一条命令产 3 候选；`mock` 双类型离线全通；请求体无真实收藏 | 完成，待验收 |
| **A3 预览与闸门** | `preview.py`、`metrics.py`、G1–G6、Chrome/CDP 截图 | 2–3d | A2 | 失败有错误码；版式三档、主题跨 5 套展示主题跑通；G3/G4/G6 可复现 | 待开始 |
| **A4 工作台与设计管理处** | 对比页、批准/驳回/迭代、草稿转正式、`manage.html` 展示清单 | 2–2.5d | A3 | 单次评审 ≤10 分钟；批准前运行目录零变化；上架第 6 套被拒；`standard/default` 不可下架 | 待开始 |
| **A5 试点与治理** | 3 个 AI 版式 + 3 个 AI 主题入库、说明、展示清单、下线/回滚演练 | 3–4d | A4 | 全部过 G1–G6；前端各 ≤5；下线回退默认；断网/无 Key 下一期全可用；CI 全绿 | 待开始 |

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

---

## 四、变更规则

- 每个里程碑完成即更新本表「状态」与「进度台账」，不等收尾统一补。
- A1 之后任何 schema 字段变更，必须先改能力矩阵与本表，再改实现。
- **展示位**：版式/主题各 5 套，内置占名额；设计库可多于 5，但不能全部进前端。
- **锁定项**：`standard` 版式、`default` 主题不可下架；任何回退都必须有落点。
- 回退以单个设计提交为单位，不涉及数据、主题绑定和采集端。
