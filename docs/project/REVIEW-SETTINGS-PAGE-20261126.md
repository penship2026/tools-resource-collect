# 设置页需求评审：开发就绪评估

> 对象：`docs/project/REQUIREMENTS-SECTIONS-SCHEDULE-20261126.md` v0.4
> 基线：`git HEAD = 8d4829f`，需求文档尚未提交
> 方式：通读需求文档 + 现有 `topics.yml`、`collector/generate.py`、`collector/server.py`、两个 workflow、`docs/ops/GITHUB-PAGES.md`
> 结论：**尚未达到可执行开发水平（DoR 未通过）**。方向清楚，但工程侧仍有 7 个 P0 缺口，直接开发会造成数据模型、采集匹配、部署安全返工。
>
> **2026-11-27 更新**：P0 附录已补齐，并已按拍板口径开始实现（数据层/迁移/混合关键词/设置页 API/Git 同步/Pages artifact）。本评审保留为开发前基线，最新实现进度见 `PLAN-20261126.md`、`TODO.md`、`WORKLOG.md`。

---

## 一、总体判断

| 维度 | 评估 | 说明 |
|---|---|---|
| 产品范围 | 基本清楚 | 7 个板块、0–18 分段、混合关键词、设置页职责已定 |
| 页面交互 | 部分清楚 | 有布局和字段，但缺完整状态、错误文案、空态、移动端细节 |
| 数据模型 | 不足 | `sections.yml` 不存在，数据无 `section`，旧单元未迁移 |
| 采集实现 | 不足 | 现有采集只支持单关键词、标题精确匹配；`must + any` 没有落地算法 |
| 调度实现 | 不足 | `run_topics` 任一失败即整体失败；Actions 不会提交已成功数据；页面 cron 导出未定义 |
| Git 同步 | 不足 | 只写了流程，缺 API、锁、仓库定位、身份、失败状态、测试方案 |
| 部署安全 | 不足 | Pages 当前是分支直出，`collector/` 会公开；与“设置页 404”冲突 |
| 测试与验收 | 不足 | 验收条目清楚，但没有测试矩阵和测试数据 |

**结论：需求可以评审，不能直接排开发。**

---

## 二、现状核对（代码事实）

| 项 | 现状 | 与需求的差距 |
|---|---|---|
| Pages 发布 | `docs/ops/GITHUB-PAGES.md` 写明 `Deploy from a branch` / `main` / `/ (root)` | 设置页会随仓库公开，无法满足“线上 404”；必须改 artifact 或拆目录 |
| 主题配置 | `topics.yml` 是扁平结构，只有 `keyword` / `id` / `title` / `channels` | 不支持 `must_keywords` / `any_keywords`；解析器 `load_topics_yaml` 也只支持这四项 |
| 采集匹配 | `collect_topic(keyword=...)` 按单关键词搜索；B站要求关键词完整出现在标题 | 没有“多词 AND + 同义词 OR”的两阶段搜索与本地过滤 |
| 批量结果 | `run_topics` 任一主题失败返回 `ok:false`，CLI `sys.exit(1)` | workflow 采集步骤失败后不会执行 `--verify` 与提交，已成功数据丢掉 |
| 定时 workflow | 只有一个 cron `0 23 * * *`，`pages` 默认 10 | 与需求“默认 3 页”“统一时间槽”等口径不一致，需要统一 |
| 数据字段 | 现有单元没有 `section`；索引也没有板块字段 | 需要新增字段、迁移 12 个存量单元、扩展 `--verify` |
| 板块配置 | 仓库没有 `sections.yml` | 需要定路径、schema、读写权限、与 Actions 的同步方式 |
| 设置页/API | `server.py` 静态白名单只放行 `collect.html`，没有 settings 路由 | 页面、API、静态白名单、CSRF/Origin 校验都未定义 |
| 本机调度 | 仓库没有 `scheduler.py` | 需求写了“可选”，但没有进程模型、状态文件、锁、启动方式 |
| Git 同步 | 仓库没有相关服务/接口 | 只有流程描述，没有 JSON 契约、锁、状态机、测试仓库方案 |

---

## 三、P0 阻断项（开发前必须关闭）

### P0-1 设置页隔离与 Pages 发布

**问题**：当前 Pages 从 `main` 根目录直出，`collector/settings.html` 即使没有后端，也会被公网访问；`collector/collect.html` 现在也已公开。需求要求线上 404，但没有任何发布改造方案。

**需要补**：Pages 改为 artifact 发布，明确白名单（展示页 + `assets/**`）；或把采集端移到独立目录/独立仓库；增加“线上 404”验收脚本。

### P0-2 板块与主题数据模型

**问题**：`sections.yml` 不存在；`section` 字段不存在；旧 12 个单元如何归属、`topic_id` 与 unit `id` 的关系、`topics.yml` 新 schema 如何兼容旧扁平结构，都没有最终定义。

**需要补**：字段表 + 文件路径 + 旧数据迁移表（12 个单元逐一归属）+ 索引派生规则 + `--verify` 校验规则 + 回滚方式。

### P0-3 混合关键词的采集算法

**问题**：需求定义 `must_keywords` 全命中 + `any_keywords` 任一命中，但现有采集只把单个 `keyword` 传给平台。B站要求标题完整包含关键词；公众号/小红书走搜索引擎，标题和正文可用性不同。没有说明“平台搜索用什么词、在哪里做 AND/OR 过滤”。

**需要补**：明确两阶段流程：用 `must_keywords[0]`（或组合查询）宽搜 → 对标题/简介做 must 全匹配 → 对 any 做任一匹配 → 去重；各渠道使用哪些字段；无结果时如何降级/提示；是否保留“标题精确匹配”。

### P0-4 Actions 部分成功与提交

**问题**：`run_topics` 当前“一个主题失败 = 整批失败”，workflow 不会执行 `--verify` 和 `git add`。需求写了“部分成功也提交”，但没有接口契约和退出码约定。

**需要补**：`run_topics` 返回 `ok/partial/failed` 与 `failed[]`；CLI 在“至少一个成功”时退出 0；workflow 无论 partial 都执行 verify + commit；失败摘要写入日志/提交信息；明确“全部失败才退出 1”。

### P0-5 API 与页面状态契约

**问题**：需求列了 API 名称，但没有请求/响应 JSON、HTTP 状态码、错误码、异步任务 ID、轮询方式、CSRF/Origin 校验。页面也没有 loading/empty/error/dirty/confirm 状态定义。

**需要补**：一份 API 契约（每个 endpoint 的入参、出参、错误码）；一份页面状态表；本地写接口加 Origin/CSRF 校验，不能只依赖 `127.0.0.1`。

### P0-6 Git 同步的可执行细节

**问题**：需求写了“fetch + fast-forward + 不 force”，但没有定义仓库根如何定位、Git 身份、remote/branch、提交路径集合、锁、任务状态持久化、commit 成功但 push 失败如何重试、超时如何校验。

**需要补**：固定 `repo_root` 与 `origin/main`；固定 data 白名单；`GIT_LOCK` 状态机；job 状态文件；错误码；用临时 bare repo 做集成测试；明确“已提交未推送”可重试且不重复提交。

### P0-7 测试矩阵与验收映射

**问题**：验收 16 条是产品语言，没有对应单元/集成/E2E 测试；Git 同步、cron 导出、Pages 404 都很难靠人工每次验证。

**需要补**：验收条目 → 测试文件/命令映射；至少覆盖：配置校验、0–18 边界、关键词匹配、partial 提交、API 错误码、Git 临时仓库、390px 布局、线上 404。

---

## 四、P1 缺口（可与开发并行，但不能漏）

- 页面交互状态：空板块、无主题、保存失败、远端领先、推送中、超时、权限错误的具体文案与按钮状态。
- 移动端：390px 下板块列表、cron 预览、Git 日志的折叠方式。
- 定时口径：需求默认 `pages=3`，workflow 默认 10；需要统一。
- 板块页面：设置页只管配置，首页板块筛选/落地页属于 P3，需明确不阻塞设置页。
- 内容种子：10 个主题的 must/any 是否可直接上线，需要先做 1–2 个 dry-run 验证召回。
- 文档联动：README、DEPLOY、GITHUB-PAGES、PLAN/TODO/WORKLOG 需要同批更新。

---

## 五、Definition of Ready 检查

- [x] 板块范围与 0–18 分段明确
- [x] 设置页职责边界明确
- [x] 关键词匹配模式明确（must + any）
- [ ] `sections.yml` / `topics.yml` schema 最终
- [ ] 12 个存量单元迁移表
- [ ] 混合关键词采集算法
- [ ] Actions partial 成功契约
- [ ] 设置页 API/错误码/CSRF
- [ ] Git 同步状态机与测试方案
- [ ] Pages artifact 发布与 404 验证
- [ ] 验收 → 测试矩阵
- [ ] 页面空/错/加载/移动端状态

**当前 3/12 项关闭，未达到开发启动条件。**

---

## 六、评审结论与下一步

**不通过，不建议现在写代码。**

下一轮只需要补文档，不写实现，按以下顺序关闭 P0：

1. **数据模型附录**：`sections.yml`、`topics.yml`、`section` 字段、12 单元迁移表；
2. **采集算法附录**：两阶段搜索 + must/any 过滤 + 各渠道字段 + 空结果降级；
3. **接口契约附录**：API JSON、错误码、CSRF、任务轮询；
4. **Git 同步附录**：repo/branch/identity/path/lock/job/重试/测试仓库；
5. **部署与测试附录**：Pages artifact、线上 404、验收到测试映射。

这五项关闭后，再做一次同样的 DoR 复核；通过后才进入 P1 页面与接口开发。

> 本轮只新增评审文档，未改代码、配置、数据，也未提交。
