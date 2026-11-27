# 二期排期与进度 · AI 模板工坊

> 版本 v1.0 · 2026-11-27 · 分支 `feat/templates-p2-20261127`（基线 `47d818d`）
> 依据：`docs/DESIGN-TEMPLATES-P2-20261127.md` v1.1、`docs/REVIEW-TEMPLATES-P2-20261127.md`
> 口径：工程 12–15 人日，另计 2–3 人日评审/验收；每轮提交同步更新本表进度列

---

## 一、里程碑

| 里程碑 | 内容 | 工期 | 依赖 | 出口验收 | 状态 |
|---|---|---|---|---|---|
| **A0 契约与基线** | 能力矩阵、Spec schema 骨架、固定 fixture、`scripts/shot_matrix.py`、三档基线、切换器容量、`drafts/` | 1d | 无 | 基线一键复现；3 套现有版式截图一致；6 套假数据页脚不溢出 | 待开始 |
| **A1 Spec + 编译器** | `spec_schema.json`、`compiler.py`、单测、`cli.py compile` | 3–4d | A0 | 两次编译字节一致；`rails/theme/sidebar` 被拒；手工 Spec 可编译 | 待开始 |
| **A2 生成管线** | `cli.py generate`、适配器、缓存、合成样例 | 2–3d | A1 | 一条命令产 3 候选；`mock` 离线全通；请求体无真实收藏 | 待开始 |
| **A3 预览与闸门** | `preview.py`、`metrics.py`、G1–G6、Chrome/CDP 截图 | 2–2.5d | A2 | 失败有错误码；三档截图归档；G3/G4/G6 可复现 | 待开始 |
| **A4 工作台** | 本机对比页、批准/驳回/迭代、草稿转正式 | 1.5–2d | A3 | 单次评审 ≤10 分钟；批准前运行目录零变化 | 待开始 |
| **A5 试点与治理** | 3 个 AI 模板、说明、下线/回滚演练 | 2–3d | A4 | 全过 G1–G6；6 套切换正常；下线回退 `standard` | 待开始 |

**合计**：12–15 人日 + 2–3 人日评审。

---

## 二、开工顺序

A0 是硬前置，未通过不进 A1。A0 拆成五个小步，可按序提交：

1. **能力矩阵**：把 `nav / lead / bands / toc` 写进 schema 骨架与 `templates.js` 对照表，拒绝 `sidebar/rail/timeline`。
2. **固定 fixture**：`tests/fixtures/preview.html`，6 个启用板块 + 1 个空板块，数据虚构。
3. **截图脚本**：`scripts/shot_matrix.py`，本机 Chrome/CDP，输出 1280/768/390 尺寸、溢出、dHash、结构指纹到 `tests/baselines/*.json`。
4. **切换器容量**：`assets/layout.js` 在 ≥5 套时改下拉，≤4 套保持按钮；用 6 套假注册表测 390px。
5. **草稿目录**：`tools/ai-template/drafts/` 与 `.gitignore` 规则，确保未批准候选不进 `assets/`。

A0 的验收命令：

```text
python3 scripts/layout_lint.py
python3 -m unittest discover -s tests
node tests/test_layout.js
node tests/test_render.js
python3 scripts/shot_matrix.py --baseline
```

---

## 三、进度台账

| 日期 | 轮次 | 完成项 | 验证 | 备注 |
|---|---|---|---|---|
| 2026-11-27 | 评审 | 二期设计评审 v1.1、D92–D95、排期建立 | 文档自检、92 例回归 | 未动业务代码 |

---

## 四、变更规则

- 每个里程碑完成即更新本表「状态」与「进度台账」，不等收尾统一补。
- A1 之后任何 schema 字段变更，必须先改能力矩阵与本表，再改实现。
- 模板数量上限 6 套；超过先下线再新增，不允许临时突破。
- 回退以单个模板提交为单位，不涉及数据、主题和采集端。
