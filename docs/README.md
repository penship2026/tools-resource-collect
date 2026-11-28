# docs 文档索引与整理说明

- 整理日期：2026-11-28
- 适用范围：`tools-resource-collect`（集页）全部项目文档
- 目标：把「页面模板一期」和「AI 模板工坊二期」拆成独立目录，项目基线、运维和专项调研各归其位，避免后续按文件名猜阶段、在同一层反复堆文档。

---

## 一、分类原则

按**文档服务的交付阶段**分，不按文件创建时间分：

| 目录 | 放什么 | 不放什么 |
|---|---|---|
| `phase1/` | 页面版式模板一期的设计、排期、验收 | 二期 AI 工坊内容、项目早期基线 |
| `phase2/` | AI 模板/主题工坊二期的设计、评审、排期、使用说明 | 一期版式契约、部署文档 |
| `project/` | 项目早期基线、跨两期的方案决策、TODO/WORKLOG、对外创作记录 | 单一阶段的交付文档 |
| `ops/` | 部署、GitHub Pages 托管与数据更新 | 产品设计与排期 |
| `research/` | 与模板工坊无直接关系、独立立项的专题调研 | 已进入开发的阶段文档 |
| `templates/` | 程序批准后写入的模板说明与 Spec，运行时产物 | 人工维护的项目文档 |

两条补充规则：

1. **跨期文档不硬拆**：`PLAN-TEMPLATES-20261127.md` 同时定义一期 D64–D80 和二期 D70–D73、D92–D98，放 `project/`，保留完整决策链。
2. **阶段文档只迁不改内容**：本次只移动文件、更新路径引用；除新增本索引外，不改写历史结论。需要修订的内容仍按原文档版本流程处理。

---

## 二、目录结构

```text
docs/
├── README.md                          # 本索引与整理说明
├── phase1/                            # 页面版式模板一期
│   ├── DESIGN-TEMPLATES-P1-20261127.md
│   ├── SCHEDULE-TEMPLATES-P1-20261127.md
│   └── ACCEPTANCE-TEMPLATES-P1-20261127.md
├── phase2/                            # AI 模板与主题工坊二期
│   ├── DESIGN-TEMPLATES-P2-20261127.md
│   ├── REVIEW-TEMPLATES-P2-20261127.md
│   ├── SCHEDULE-TEMPLATES-P2-20261127.md
│   └── GUIDE-TEMPLATES-P2-20261127.md
├── project/                           # 项目基线与跨期记录
│   ├── PLAN-20261126.md
│   ├── REVIEW-20261126.md
│   ├── PLAN-TEMPLATES-20261127.md
│   ├── REQUIREMENTS-SECTIONS-SCHEDULE-20261126.md
│   ├── REQUIREMENTS-SETTINGS-PAGE-20261126.md
│   ├── REVIEW-SETTINGS-PAGE-20261126.md
│   ├── TODO.md
│   ├── WORKLOG.md
│   └── CREATION-STORY-20261126.md / .html
├── ops/                               # 部署与托管
│   ├── DEPLOY.md
│   └── GITHUB-PAGES.md
├── research/                          # 独立专题调研
│   └── REPORT-CHANNELS-PLATFORM-20261127.md
└── templates/                         # 程序生成的模板发布产物，勿手改
```

---

## 三、一期文档（`phase1/`）

一期主题是「页面版式模板与板块导航」：把写死在页面里的布局抽成 `assets/layouts/*.css`，交付简洁/门户/画册三套版式、板块一级导航和 `?section=` 板块视图。

| 文档 | 作用 | 当前状态 |
|---|---|---|
| `DESIGN-TEMPLATES-P1-20261127.md` | 一期详细设计 v1.3：范围、版式规格、文件级改动、验收矩阵 | 已评审，签收前整改完成 |
| `SCHEDULE-TEMPLATES-P1-20261127.md` | 一期排期 v1.1：M1–M5、日历排期、进度台账 | 验收整改完成，待签收 |
| `ACCEPTANCE-TEMPLATES-P1-20261127.md` | 一期验收记录：自动化闸门、T1–T15、截图证据 | 已验收 |

阅读顺序：设计 → 排期 → 验收。需要先看「为什么做版式层」，读设计的范围与总则；需要核对实际交付，读验收记录。

---

## 四、二期文档（`phase2/`）

二期主题是「AI 模板与主题工坊」：AI 只产受限 Spec，编译器产 CSS，人工评审后原子发布；线上仍是零构建纯静态，AI 不是运行时依赖。

| 文档 | 作用 | 当前状态 |
|---|---|---|
| `DESIGN-TEMPLATES-P2-20261127.md` | 二期详细设计 v1.13：双类型 Spec、编译器、生成管线、G1–G6、工作台、管理处、历史与校验 | A4 实现完成，待验收；A5 候选已生成并通过闸门 |
| `REVIEW-TEMPLATES-P2-20261127.md` | 二期设计评审：v1.0 的五个阻断项、范围收敛、验收增量 | 评审基线，保留不改 |
| `SCHEDULE-TEMPLATES-P2-20261127.md` | 二期排期与进度 v1.11：A0–A5、依赖、出口验收、进度台账 | A5 验收进行中 |
| `GUIDE-TEMPLATES-P2-20261127.md` | 二期使用说明书：启动、IDE、历史对比、校验、生成、评审、上架、排障 | 已生成，随 v1.13 维护 |

阅读顺序：

- 第一次上手：直接读使用说明书，按「5 分钟快速上手」跑一遍。
- 查契约或排障：设计文档的 8.4.3–8.4.5 与对应章节；接口、错误码以设计为准。
- 查为什么改：评审文档；查做到哪：排期文档的进度列。

---

## 五、项目基线（`project/`）

这些文档不属于单一模板阶段，也不能删：

| 文档 | 作用 |
|---|---|
| `PLAN-20261126.md` | 项目早期改造方案：采集任务化、单一真源、个人收藏层，决策 D1–D61 |
| `REVIEW-20261126.md` | 全项目评审基线：18 个问题与优先级，冻结不改 |
| `PLAN-TEMPLATES-20261127.md` | 两期模板体系方案：D64–D98，跨一期/二期的决策源头 |
| `REQUIREMENTS-SECTIONS-SCHEDULE-20261126.md` | 板块体系与定时采集设置页总需求 |
| `REQUIREMENTS-SETTINGS-PAGE-20261126.md` | 设置页 P0 补充需求：数据模型、API、Git 同步、发布隔离 |
| `REVIEW-SETTINGS-PAGE-20261126.md` | 设置页开发就绪评审：P0 缺口与拍板记录 |
| `TODO.md` | 执行待办：只勾选、末尾追加处理记录 |
| `WORKLOG.md` | 按时间演进的工作日志：决策、改动、验证与踩坑 |
| `CREATION-STORY-20261126.md` / `.html` | 对外创作过程记录：发布文案、配图分镜、时间线 |

注意：`PLAN-20261126.md`、`TODO.md`、`WORKLOG.md` 有「只增不改 / 只追加」的协作约定，整理目录不改变这些写入规则。

---

## 六、运维与专题（`ops/`、`research/`）

| 文档 | 作用 |
|---|---|
| `ops/DEPLOY.md` | 服务器 / 群晖 DSM / 飞牛 fnOS 部署、Docker、安全基线、故障排查 |
| `ops/GITHUB-PAGES.md` | GitHub Pages artifact 发布、数据更新、定时任务与本地兜底 |
| `research/REPORT-CHANNELS-PLATFORM-20261127.md` | 视频号收藏与播放方案：H5、单链接采集、小程序播放的主体与参数边界 |

`research/` 只放「评估结论、尚未进入模板工坊交付」的专题；如果后续立项开发，再按阶段新建目录，不把调研文档硬塞进 `phase2/`。

---

## 七、原路径 → 新路径

本次移动的全部文件对照如下；仓库内引用已同步改为新路径。

| 原文件名（docs/ 根目录） | 新路径 |
|---|---|
| `ACCEPTANCE-TEMPLATES-P1-20261127.md` | `docs/phase1/ACCEPTANCE-TEMPLATES-P1-20261127.md` |
| `DESIGN-TEMPLATES-P1-20261127.md` | `docs/phase1/DESIGN-TEMPLATES-P1-20261127.md` |
| `SCHEDULE-TEMPLATES-P1-20261127.md` | `docs/phase1/SCHEDULE-TEMPLATES-P1-20261127.md` |
| `DESIGN-TEMPLATES-P2-20261127.md` | `docs/phase2/DESIGN-TEMPLATES-P2-20261127.md` |
| `REVIEW-TEMPLATES-P2-20261127.md` | `docs/phase2/REVIEW-TEMPLATES-P2-20261127.md` |
| `SCHEDULE-TEMPLATES-P2-20261127.md` | `docs/phase2/SCHEDULE-TEMPLATES-P2-20261127.md` |
| `GUIDE-TEMPLATES-P2-20261127.md` | `docs/phase2/GUIDE-TEMPLATES-P2-20261127.md` |
| `PLAN-20261126.md` | `docs/project/PLAN-20261126.md` |
| `REVIEW-20261126.md` | `docs/project/REVIEW-20261126.md` |
| `PLAN-TEMPLATES-20261127.md` | `docs/project/PLAN-TEMPLATES-20261127.md` |
| `REQUIREMENTS-SECTIONS-SCHEDULE-20261126.md` | `docs/project/REQUIREMENTS-SECTIONS-SCHEDULE-20261126.md` |
| `REQUIREMENTS-SETTINGS-PAGE-20261126.md` | `docs/project/REQUIREMENTS-SETTINGS-PAGE-20261126.md` |
| `REVIEW-SETTINGS-PAGE-20261126.md` | `docs/project/REVIEW-SETTINGS-PAGE-20261126.md` |
| `TODO.md` | `docs/project/TODO.md` |
| `WORKLOG.md` | `docs/project/WORKLOG.md` |
| `CREATION-STORY-20261126.md` | `docs/project/CREATION-STORY-20261126.md` |
| `CREATION-STORY-20261126.html` | `docs/project/CREATION-STORY-20261126.html` |
| `REPORT-CHANNELS-PLATFORM-20261127.md` | `docs/research/REPORT-CHANNELS-PLATFORM-20261127.md` |
| `DEPLOY.md` | `docs/ops/DEPLOY.md` |
| `GITHUB-PAGES.md` | `docs/ops/GITHUB-PAGES.md` |

`docs/templates/` 未移动：它由 `tools/ai-template/publish.py` 在批准时写入，是运行产物目录，不属于人工文档分类。

---

## 八、维护约定

1. **新阶段文档**：先建 `phaseN/`，不要继续放 `docs/` 根目录；文件名保持 `<类型>-<阶段>-<日期>.md`，例如 `DESIGN-TEMPLATES-P3-20261201.md`。
2. **跨期方案**：放 `project/`；如果一份文档只在某一期有效，放对应 `phaseN/`。
3. **路径写法**：文档内引用统一用仓库相对路径 `docs/<目录>/<文件>`；不要写本机绝对路径。
4. **冻结文档**：`REVIEW-20261126.md` 与 `REVIEW-TEMPLATES-P2-20261127.md` 是一次性评审记录，修订另开新文件，不原地改历史结论。
5. **运行产物**：`docs/templates/` 只由程序写；手改会在下次批准时被覆盖，也会让 Spec 与 CSS 不一致。
6. **自检**：移动或新增文档后跑 `python3 scripts/docs_check.py`，确认关键文档存在、引用路径可达。

---

## 九、本次校验

- `python3 scripts/docs_check.py`：通过
- `python3 -m unittest tests.test_server tests.test_pages tests.test_studio`：通过（文档移动不影响业务代码）
- 仓库内 `docs/<旧文件名>` 引用：已全部替换为新路径
- 原目录完整备份：`/tmp/tools-resource-collect-docs-backup-20261128`（仅本机临时备份，不提交）
