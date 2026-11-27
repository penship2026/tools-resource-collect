# 设置页开发就绪补充需求（P0 附录）

> 版本：v0.1
> 日期：2026-11-26
> 关联：`REQUIREMENTS-SECTIONS-SCHEDULE-20261126.md`（总需求）、`REVIEW-SETTINGS-PAGE-20261126.md`（评审）
> 状态：**需求补充稿，不进入代码实现**。本文件把评审里的 P0 缺口补成可开发口径。

---

## 一、范围与结论

本文件只补设置页的工程口径，不重复产品背景。目标是把以下 5 类缺口补到可以直接拆任务：

1. 板块/主题数据模型与存量迁移；
2. 混合关键词采集算法；
3. 设置页 API 契约与页面状态；
4. 数据同步 Git 的完整状态机；
5. Pages 发布隔离、测试矩阵与验收映射。

**默认结论**：采用方案一（GitHub Pages 展示 + GitHub Actions 公网采集 + 本机设置页）；设置页不发布。

---

## 二、数据模型与迁移

### 2.1 文件位置

| 文件 | 位置 | 是否进仓库 | 用途 |
|---|---|---|---|
| `sections.yml` | 仓库根 | 是 | 板块注册表（公开配置） |
| `topics.yml` | 仓库根 | 是 | 主题/单元注册表（公开配置） |
| `schedule.local.yml` | 仓库根 | 否，`.gitignore` | 本机可选调度配置 |
| `assets/data/collections/*.js` | 仓库根 | 是 | 采集单元数据 |
| `assets/data/index.js` | 仓库根 | 是 | 索引 |

### 2.2 `sections.yml` schema

```yaml
version: 1
sections:
  - id: infant-care
    title: 婴幼儿养护
    age_min_months: 0
    age_max_months: 36
    order: 1
    enabled: true
    description: 0–3 岁喂养、睡眠、发育、健康护理与居家安全
  - id: preschool
    title: 学前教育
    age_min_months: 36
    age_max_months: 72
    order: 2
    enabled: true
    description: 3–6 岁入园适应、幼小衔接、早期阅读与游戏化学习
  - id: k12
    title: 中小学教育
    age_min_months: 72
    age_max_months: 216
    order: 3
    enabled: true
    description: 6–18 岁学科、启蒙与学习方法
  - id: ai
    title: AI 与智能工具
    age_min_months: null
    age_max_months: null
    order: 4
    enabled: true
    description: 全龄；大模型、Agent、AI 开发与 AI 应用
  - id: tech
    title: 科技前沿
    age_min_months: null
    age_max_months: null
    order: 5
    enabled: true
    description: 全龄；芯片、算力、机器人、航天与新能源
  - id: tools
    title: 工具与效率
    age_min_months: null
    age_max_months: null
    order: 6
    enabled: true
    description: 全龄；网站、软件、效率方法与实用工具
  - id: humanities
    title: 人文与通识
    age_min_months: null
    age_max_months: null
    order: 7
    enabled: false
    description: 全龄；城市、历史、文化与地理
```

校验规则：

- `id` 全局唯一，`[a-z0-9-]`；创建后不可改。
- 三个保留板块必须是 `0–36 / 36–72 / 72–216`，首尾相接，不允许空档/重叠。
- 其余板块 `age_min_months` 与 `age_max_months` 必须同时为 `null`。
- 自定义板块只能全龄；不能设置年龄段、不能删除三个保留板块。
- `enabled=false` 不展示，但历史数据保留；`humanities` 初始关闭，是否上首页另定。
- `description` 最多 60 字。

### 2.3 `topics.yml` schema v2

```yaml
version: 1
topics:
  - id: infant-feeding
    section: infant-care
    title: 喂养与睡眠
    must_keywords: ["婴幼儿", "喂养"]
    any_keywords: ["辅食", "母乳", "配方奶", "宝宝睡眠"]
    channels: [bilibili]
    enabled: true
```

字段规则：

| 字段 | 规则 |
|---|---|
| `id` | 必填；主题 ID，同时作为采集单元 `id`；全局唯一、创建后不可改 |
| `section` | 必填；必须存在于 `sections.yml` |
| `title` | 必填；显示标题 |
| `must_keywords` | 必填；1–4 个，全部命中 |
| `any_keywords` | 选填；0–5 个，至少命中一个；为空时只按 must 判断 |
| `channels` | 至少一个，默认 `bilibili` |
| `enabled` | 停用不参与采集，历史数据保留 |

**兼容旧配置**：现有 7 条扁平 `keyword` 主题迁移为 `must_keywords: ["原 keyword"]`、`any_keywords: []`、`section` 按第 2.4 节归属；现有 `id` 保留。新主题不再允许省略 `id`，页面创建时生成 `slug + 6 位短 hash`。

**主题与单元的关系**：一个主题对应一个采集单元；`id` 既是主题 ID，也是单元 ID，不再引入第二套 `topic_id`。

### 2.4 存量 12 个单元迁移表

| 单元 ID | 主板块 |
|---|---|
| `bv1uks66oeeh` | `ai` |
| `topic-4e6ee53f` | `ai` |
| `topic-205064a1` | `ai` |
| `topic-df282732` | `ai` |
| `bv1j4w16reys` | `ai` |
| `guwen-animation` | `k12` |
| `topic-621ae722` | `k12` |
| `bv1wg39zpetl` | `k12` |
| `topic-e5b5c763` | `k12` |
| `topic-d9744f1c` | `tech` |
| `daily-website` | `tools` |
| `wx-nxpxhhghan9dvfzoat5avg` | `humanities` |

迁移规则：每个单元文件增加 `section`；索引派生 `section` 与 `section_title`；只改字段，不重采；迁移前备份 `assets/data/`；写入原子替换；迁移后 `--verify` 为 0 问题。

### 2.5 `--verify` 新增校验

- 所有单元 `section` 必须存在且非空；
- 所有主题 `section` 必须存在；
- 三个保留板块必须连续；
- 主题 `id` 唯一；`must_keywords` 1–4；`any_keywords` 0–5；
- 索引中的 `section` 必须与单元文件一致。

---

## 三、混合关键词采集算法

### 3.1 两阶段流程

1. **宽搜**：用 `must_keywords[0]` 作为平台搜索词，按 `pages` 取候选；B站沿用现有聚类，公众号/小红书沿用现有搜索引擎找链接。
2. **本地过滤**：对候选的 `title` + `description`（无 description 时只用 title）做归一化后匹配：
   - `must_keywords` 全部出现；
   - `any_keywords` 为空则跳过，否则至少一个出现；
   - 不通过则丢弃。
3. **去重**：沿用现有 `item_key`；同一视频/文章只保留一条。
4. **截断**：按 must 命中数、any 命中数、发布时间排序，最多写入 `max_new` 条。
5. **空结果**：返回 `no_match`，不算网络错误；日志记录候选数、must 过滤后数、any 过滤后数。

### 3.2 文本归一化

Unicode NFKC；英文小写；全角转半角；去多余空白与常见标点；中文按子串匹配。

### 3.3 各渠道字段

| 渠道 | 搜索词 | 过滤字段 | 说明 |
|---|---|---|---|
| B站 | `must_keywords[0]` | 系列标题 + 系列简介 + 分集标题 | 先聚类，再按系列级文本过滤；系列级不通过则整组丢弃 |
| 公众号 | `must_keywords[0]` | 文章标题 + 正文摘要 | 正文抓取失败时只用标题，日志标记 `title_only` |
| 小红书 | `must_keywords[0]` | 笔记标题 + 搜索摘要 | 不抓正文；摘要为空时只用标题，日志标记 `title_only` |

### 3.4 预览与测试

- `--dry-run` 输出：候选数、must 通过数、any 通过数、最终可写入数、前 10 条命中样例。
- 测试覆盖：全部 must 命中、缺一个 must、any 全不命中、同义词命中、英文大小写/全角、空 description。
- 不允许把同义词放进 must；页面保存时检测到 must 中有明显同义词重复要警告。

---

## 四、设置页 API 契约

### 4.1 通用约定

- 基地址 `http://127.0.0.1:8765`；只在 `127.0.0.1`。
- JSON UTF-8；请求体上限 1 MB。
- 所有写接口要求 `X-CSRF-Token`，并校验 `Origin` 为 `http://127.0.0.1:8765` 或 `http://localhost:8765`；不匹配返回 403。
- 统一错误格式：

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "0–18 岁板块存在空档",
    "fields": ["sections[2].age_min_months"]
  }
}
```

错误码：`VALIDATION_ERROR` 400、`CSRF_FAILED` 403、`CONFLICT` 409、`LOCKED` 423、`NOT_FOUND` 404、`GIT_NOT_REPO` 409、`GIT_REMOTE_AHEAD` 409、`GIT_IDENTITY_MISSING` 409、`GIT_PUSH_FAILED` 502、`INTERNAL` 500。

### 4.2 接口

| 方法 | 路径 | 用途 | 主要返回 |
|---|---|---|---|
| GET | `/api/settings` | 读取板块/主题/本机调度/状态 | `sections`、`topics`、`schedule`、`csrf_token` |
| PUT | `/api/settings` | 校验并原子保存本机配置 | 保存结果 + `warnings[]` |
| POST | `/api/scheduler/toggle` | 开关本机调度 | `enabled`；Actions schedule 存在时 409 |
| POST | `/api/run-now` | 本机立即执行 | `202` + `job_id` |
| GET | `/api/jobs/{id}` | 查询本机任务 | `state`、`progress`、`log_tail` |
| GET | `/api/actions/export` | 生成 cron 片段 | `cron_text`、`utc_times` |
| GET | `/api/git/status` | Git 状态 | `branch`、`ahead/behind`、`changes` |
| POST | `/api/git/preview` | 预检与文件清单 | `files[]`、`units`、`items`、`blockers[]` |
| POST | `/api/git/push` | 数据提交并推送 | `202` + `job_id` |
| GET | `/api/git/jobs/{id}` | 推送进度 | `state`、`log_tail`、`commit` |

`PUT /api/settings` 只保存本机配置，不写 GitHub；页面显示“本机已保存，线上需提交后生效”。

---

## 五、数据同步 Git 状态机

### 5.1 固定参数

- 仓库根：`Path(collector/server.py).resolve().parents[1]`；必须存在 `.git`。
- remote：`origin`；branch：`main`；不提供修改入口。
- 提交路径白名单：`assets/data/collections/*.js`、`assets/data/index.js`。
- 禁止提交删除；只允许新增/修改。
- Git 身份必须已在本地配置；缺失报 `GIT_IDENTITY_MISSING`，不自动设置。
- 所有命令用 `subprocess.run([...], shell=False)`；不接受页面传命令。

### 5.2 状态

`idle → preflight → fetching → verifying → committing → pushing → success`

失败分支：`blocked`（远端领先/校验失败/身份缺失）、`committed_not_pushed`（提交成功但推送失败）、`failed`。

### 5.3 流程

1. 预检：无采集/Git 任务、分支 `main`、无 merge/rebase/cherry-pick、存在数据变更、Git 身份存在。
2. `git fetch origin main`；检查 `origin/main` 是 HEAD 祖先；不是则 `GIT_REMOTE_AHEAD`，不自动 rebase。
3. `python3 collector/generate.py --verify`；失败则 `blocked`，不提交。
4. 通过 `git status --porcelain --untracked-files=all` 计算白名单文件清单。
5. `git add -- <explicit files>`；`git commit -m "data: 本机采集同步 ..."`。
6. `git -c http.version=HTTP/1.1 push origin main`；网络失败重试 1 次。
7. 推送超时：`git ls-remote origin main` 与本地 HEAD 比较；相同则成功，不同则 `committed_not_pushed`。
8. 推送被拒：保留本地 commit，提示人工 `git pull --rebase`，不自动合并、不 force。
9. 成功后显示 commit hash、文件数、单元数；下一次 Actions 基于新 HEAD 继续。

### 5.4 测试

临时 bare repo + 两个 clone，覆盖正常推送、远端领先、push 失败、超时、无变更、代码文件存在但只提交数据；断言不 force、不 reset、不提交白名单外文件。

---

## 六、Pages 发布隔离

当前 Pages 文档写的是 `Deploy from a branch / main / root`，`collector/` 会公开。开发前必须改为 artifact：

```text
.github/workflows/pages.yml
  build -> 生成只含展示页与 assets 的 artifact -> upload-pages-artifact
  deploy -> deploy-pages
```

artifact 白名单：`index.html`、`series.html`、`list.html`、`single.html`、`mine-io.html`、`assets/**`、`CNAME`、`.nojekyll`。

排除：`collector/**`、`docs/**`、`tests/**`、`scripts/**`、`.github/**`、`backups/**`、`README.md`、`topics.yml`、`sections.yml`。

验收：部署后访问 `/collector/settings.html` 返回 404；`/collector/collect.html` 也不公开。

---

## 七、页面状态与交互

| 状态 | 页面表现 | 操作 |
|---|---|---|
| 加载中 | 骨架/禁用保存 | 不可编辑 |
| 无板块 | 空态 + 新增板块 | 可新增 |
| 板块无主题 | 提示“需至少一个启用主题” | 可新增主题 |
| 有未保存改动 | 顶部“未保存”标记 | 保存/放弃 |
| 保存成功 | 顶部“已保存”+ 时间 | 可继续编辑 |
| 校验失败 | 字段级红字 + 顶部汇总 | 定位字段 |
| 远端领先 | Git 区黄色提示 | 禁用推送，给 rebase 提示 |
| 推送中 | 按钮转圈，日志滚动 | v1 不取消 |
| 推送失败 | 红色摘要 + 错误码 | 重试/查看日志 |
| 本机离线 | 调度区“无心跳” | 自动开关禁用 |

移动端：390px 下板块列表与 Git 日志折叠，按钮全宽；确认用页面内 modal，不用浏览器 `confirm`。

---

## 八、测试矩阵与验收映射

| 验收 | 测试 |
|---|---|
| 7 板块 + 自定义全龄保存 | `test_sections_validation` |
| 0–18 空档/重叠拒绝 | 同上，边界 0/36/72/216 |
| must + any 匹配 | `test_keyword_match` 样例集 |
| 部分主题失败仍提交 | `test_run_topics_partial` + workflow 断言 |
| 本机调度需心跳且 Actions 停用 | `test_scheduler_gate` |
| Git 只提交数据白名单 | `test_git_paths`（临时 bare repo） |
| 远端领先阻止推送 | `test_git_remote_ahead` |
| 推送超时不重复提交 | `test_git_timeout_idempotent` |
| 设置页线上 404 | Pages artifact 清单测试 + 部署后 curl |
| 存量 12 单元迁移 | `test_migrate_sections` + `--verify` |
| 390px 无溢出 | Playwright 截图断言 |

新增测试统一放 `tests/`；Git 测试不联网，用临时目录；CI 继续执行 `python3 -m unittest`。

---

## 九、开发顺序（仅规划）

1. 数据模型 + 存量迁移 + `--verify`；
2. 关键词匹配算法 + dry-run 样例；
3. API 契约 + 页面状态 + CSRF；
4. Git 状态机 + 临时仓库测试；
5. Pages artifact + 线上 404；
6. 本机调度（可选）最后做，默认关闭。

---

> 本文件只补需求口径，不实现代码。

---

## 十、开发口径确认（2026-11-27）

以下三项在开发启动时已拍板，后续实现与测试以此为准：

| 待定项 | 决策 | 理由 |
|---|---|---|
| `pages` 默认值 | **3** | 与设置页/文档一致；降低 Actions 采集耗时与 B站风控概率 |
| `humanities` 是否默认上首页 | **否，`enabled: false`** | 现阶段无稳定主题，先保留历史数据，避免首页出现空板块 |
| Actions 统一 cron | **保持 `0 23 * * *`（北京 07:00）** | 单一时间槽，v1 不做板块错峰；设置页只读展示 |

补充契约：`run_topics()` 返回 `ok / partial / failed`。至少一个主题成功时返回 `ok: true, status: partial`，CLI 退出 0，workflow 继续 `--verify` 与提交；全部失败才退出 1。
