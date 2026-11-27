# 集页 · 主题内容清单

一集一页,把值得收藏的内容收成清单。纯静态站点 + 配套**纯规则采集程序**:输入主题关键词 → B站 搜索 → 精准匹配 → 去重合并 → 写入数据。全程不调用任何 AI 服务。(原名「神奇网站挖掘机 · 视频聚合站」)

核心原则:**采集只处理数据,不生成、不修改任何静态页面**。页面是四个公开页 + 两个本机采集工具页 + 一个我的导入导出页,由人工单独维护布局与版式;每次采集是一个独立数据单元,可单独更新、单独关闭显示。

## 四个公开页 + 两个工具页 + 我的导入导出页(固定页面,版式可切换)

| 页面 | 用途 | 参数 |
|---|---|---|
| `index.html` | 首页:主题总览,卡片带平台徽标/合集或单条标记/条数/标签/最新日期,支持平台与标签筛选 | — |
| `series.html` | 合集页:只展示**最近 20 条**(按发布者分组、可搜索),超出部分引导到全部内容页 | `?id=<单元ID>` |
| `list.html` | 全部内容页:该单元的全部采集记录,支持关键词/作者/平台筛选、排序与分页(每页 12 条) | `?id=<单元ID>&q=<可选搜索词>` |
| `single.html` | 站内详情页:按渠道切换模板(B站视频页内播放 / 公众号文章版式 / 小红书笔记版式),多集内容带上一集、下一集与全集列表 | `?id=<单元ID>&k=<条目键>`(兼容 `&i=<下标>`) |
| `mine-io.html` | 我的导入导出页:导出 JSON 备份、导入恢复(合并/替换),只读写本机 localStorage | — |
| `collector/collect.html` | 采集页(仅本机使用):填主题关键词/链接发起采集,调 `/api/*`;公网模式需填口令 | — |

公开页不再有 `<style>` 块:公共结构在 `assets/style.css`,页级结构在 `assets/pages/<page>.css`,版式差异在 `assets/layouts/*.css`,主题只定义颜色 token(`assets/themes/`)。数据加载统一在 `assets/data-loader.js`,**渲染统一在 `assets/render.js`**(卡片/条目/详情/多集导航只有一份实现)。

页面跳转链路:首页 → 合集页 → 全部内容页 / 站内详情页。合集页与列表页的卡片**不再直连源平台**,统一进站内详情页;详情页里再提供「前往 B站 观看」「阅读原文」等外链兜底。

## 页面版式与模板

公开页共用同一套 DOM 与数据,只通过 `<html data-layout>` 换版式;主题与版式各自记忆,互不覆盖。

| 版式 | key | 特征 | 能力 |
|---|---|---|---|
| 简洁 | `standard` | 单列 Hero + 卡片网格 | 无导航/头条/分节 |
| 门户 | `news` | 顶部板块导航 + 1 主 3 副头条（副卡即窄侧栏）+ 板块分节 | nav / lead / bands |
| 画册 | `magazine` | 刊头 + 目录 + 章节编号 + 3:2 大图 | nav / bands / toc |

- 切换入口在页脚「版式」三项,文案固定为 **简洁 / 门户 / 画册**;新增版式只需在 `assets/templates.js` 加一行、在 `assets/layouts/` 放一个 CSS,切换器自动出现。
- 优先级:`?layout=<key>`(预览,不写存储) → `localStorage.jiye.layout` → `site.yml` 的 `site.default_layout` → 注册表默认 `standard`。
- 板块视图统一用 `index.html?section=<板块 id>`;导航与板块计数来自 `sections.yml` 生成的 `assets/data/sections.js`。
- 编辑推荐统一写根目录 `site.yml`,由 `generate.py` 生成 `assets/site.js`:设置页改默认版式,采集页给单元加「置顶」或「画册大图」;置顶只改展示顺序,不改 `assets/data/index.js`。
- 画册首页的空章节只保留目录入口,不排正文;板块视图仍显示空态(D79)。

**新增一套版式三步**:① 在 `assets/layouts/` 新增 CSS;② 在 `assets/templates.js` 的 `list` 加 `{label, desc, file, nav/lead/bands/toc...}`;③ 跑 `python3 scripts/layout_lint.py`。不需要改任何页面。

首页只展示 `enabled !== false` 的单元;关闭显示的单元数据仍保留,只是不在首页出现。

## 个人收藏(纯本地,无后端)

条目级收藏,数据只存在浏览器 `localStorage`(键 `jiye.mine.v1`),不上传、不采集、不需要账号。

- 在合集页/全部内容页/详情页点条目上的 ☆ 收藏;**首页主题卡片右下角的 ☆ 收藏整个合集/单条主题**(与条目级收藏分开存,key 为 `__series`;「我的」里点合集卡回到合集页);首页头部在**有收藏时**才出现「公开 / 我的」开关,点「我的」进入 `index.html?view=mine`。
- 每条收藏存一份最小快照(标题/链接/封面/日期/作者/单元名),原单元下线或被关闭显示后仍可读。
- 「我的」页只展示本机收藏(不混入公开内容),顶部是与公开首页同构的 hero:标题可点 ✎ 或进「设置」自定义(多行文本框,支持换行,存 `jiye.mine.title.v1`,上限 40 字,留空恢复「我的收藏」,浏览器标签自动压成单行),副标题存 `jiye.mine.subtitle.v1`(多行,上限 120 字,留空恢复默认),不上传、不同步。
- 「我的」页页脚「设置」可改**顶部「公开 / 我的」两个入口的名称**(公开存 `jiye.mine.public.v1`、我的存 `jiye.mine.switch.v1`,各 12 字上限,只显示名称、不显示收藏数)、收藏页名称与**本页专属主题**(存 `jiye.mine.theme.v1`,只在该页生效,公开页仍用页脚主题;选「跟随公开主题」恢复共用)。
- 「我的」页保留与公开首页同一套筛选布局:全部 / 系列合集 / 单条精选 + 标签 chips(按收藏所属单元标签生成)+ 搜索框;筛选时 hero 统计显示「筛选出 N / M 条」。
- 公开首页与「我的」页筛选条都吸顶:滚过筛选区后默认收成一行「筛选条件 / 展开」,点开恢复完整筛选;离开吸顶自动展开(D85)。
- 「我的」页页脚独立:只放「导入导出」「设置」「回到公开页」,不放采集入口,也不放主题/版式切换;公开页脚保持原样(D82)。
- 门户/画册版式下,「我的」页的板块导航会保留 `view=mine`,只在收藏内按板块过滤;导航计数显示本地收藏数,不再跳回公开首页(D81)。
- 我的收藏卡复用公开首页主题卡：合集右上角显示「合集」,单条显示「单条」;右下角星标即取消收藏。从我的页进合集/单条详情会带 `&view=mine`,面包屑和「返回我的收藏」都回到我的页,不会掉回公开首页(D83/D84)。
- 导入导出收进专属页 `mine-io.html`:导出 JSON 备份、导入 JSON(默认合并、按 key 保留较新;「替换」会覆盖当前数据);导入前自动先导出当前收藏,非法文件整体拒绝不写入。收藏软上限 800 条。
- 只收藏站内已有条目,不支持手工录入站外链接。

## 目录结构

```
.
├── README.md                       # 根目录唯一文档(项目总览)
├── index.html / series.html / list.html / single.html / mine-io.html   # 固定展示页与我的导入导出页(人工维护)
├── list.html                       # 全部内容页(筛选 + 分页)
├── mine-io.html                    # 我的导入导出页(本机数据专用)
├── site.yml                        # 站点外观 + 编辑推荐(默认版式/置顶/画册大图)
├── assets/
│   ├── style.css                   # 公共基础样式 + 17 个布局 token
│   ├── site.js                     # site.yml 的前端产物(默认版式/编辑推荐)
│   ├── templates.js / layout.js    # 版式注册表 / 版式解析与注入
│   ├── pages/                      # 页级结构:index/series/list/single.css
│   ├── layouts/                    # 版式:standard/news/magazine.css
│   ├── data-loader.js              # 各页面共用的单元数据加载器
│   └── data/
│       ├── index.js                # 采集单元索引(元信息+显示开关)
│       ├── sections.js             # 板块注册表(由 sections.yml 生成)
│       └── collections/
│           ├── daily-website.js    # 每次采集独立一个数据文件
│           └── ...
├── collector/                      # 采集管理代码(独立于展示页)
│   ├── generate.py                 # 采集数据程序(纯标准库,不写页面)
│   ├── server.py                   # 采集服务(--api-only 可只跑采集端)
│   ├── settings_store.py           # 设置页配置读写与校验
│   ├── git_sync.py                 # 数据同步 Git(只提交采集数据)
│   ├── backup_data.py              # 数据备份/还原工具
│   ├── collect.html                # 采集交互页(表单入口)
│   ├── settings.html               # 采集设置页(仅本机/局域网)
│   └── settings-guide.html         # 设置页填写说明
├── sections.yml                    # 板块注册表(0–18 岁分段 + 全龄)
├── topics.yml                      # 主题清单(v2: must/any + section)
├── scripts/                        # docs_check / layout_lint 自检
├── docs/                           # 部署、过程与对外文档
│   ├── DEPLOY.md                   # 服务器 / 群晖 / 飞牛部署
│   ├── GITHUB-PAGES.md             # GitHub Pages 托管与数据更新
│   ├── PLAN-20261126.md            # 需求、决策与里程碑
│   ├── REVIEW-20261126.md          # 全项目评审
│   ├── TODO.md / WORKLOG.md        # 执行记录与工作日志
│   └── CREATION-STORY-20261126.*   # 对外创作过程记录（Markdown + HTML）
├── .github/workflows/              # 采集与 Pages artifact workflow
├── backups/                        # 备份压缩包(自动生成)
└── Dockerfile / docker-compose.yml # Docker 部署
```

> 路径约定:所有采集命令从**项目根**执行,脚本统一带 `collector/` 前缀(如 `python3 collector/generate.py`)。程序自动把项目根作为数据目录基准,无需额外配置;也可用 `VIDEO_PROJECT_ROOT` 显式指定项目根。

## 数据模型:采集单元

每次采集 = 一个独立单元,单独存一个 JS 文件,互不覆盖。重新采集命中同一 id 时**只更新该单元**,不动其他单元;每个单元有 `enabled` 开关控制是否在首页显示。

单元数据(`assets/data/collections/<id>.js`)字段:

| 字段 | 说明 |
|---|---|
| `id` | 唯一标识(单元 ID) |
| `type` | `series`(主题合集) / `single`(单链接) |
| `title` / `slogan` | 标题 / 副标题 |
| `enabled` | 是否在首页显示(true/false) |
| `source` | 来源平台、UP 主名称与主页。`platform` 只存稳定 key(`bilibili`/`wechat`/`xhs`/`multi`),中文展示名由前端 `Render.platLabel` 映射;详情路由不存数据,由页面按 `type` 推导 |
| `keyword` | 采集关键词或原链接(便于重新采集) |
| `intake` | 最近一次采集的**填写信息**(方式 / 原始输入 / 显示标题 / UP 主 / 页数 / 手工补录 / 时间),用于重新采集时回填 |
| `runs` | 最近 20 次采集记录(时间、方式、输入条数、本次新增/更新/未变/合计) |
| `created` / `updated` | 首次 / 最近采集日期 |
| `videos` | 视频列表(标题、BV、封面、播放量、日期、作者、简介);B站条目可带 `parts`(分P 目录)与 `season`(视频所属合集) |
| `season` | 单元级合集目录(单链接采集命中所属合集时写入,`{title,id,episodes[]}`;索引不收录该字段,避免膨胀) |
| `platforms` | 多渠道合集的平台 key 列表(可选,如 `["bilibili","wechat"]`) |

索引(`assets/data/index.js`)汇总每个单元的元信息(不含视频列表、`intake`、`runs`、`season`,只留 `last_at` / `last_mode_label` 摘要)+ 显示开关,供首页渲染;写入时按 `last_at` 倒序,新采集单元在最前。索引只是**派生缓存**:任何写入都以 `collections/<id>.js` 为唯一事实源,由 `rebuild_index()` 重算 `title/count/cover/latest/created/enabled/updated`,不再手工双写。

## 使用方式

### 采集交互页(推荐)

```bash
python3 collector/server.py 8765
```

浏览器打开 `http://127.0.0.1:8765/collect.html`,页面顶部三个模式 Tab(**默认「按链接采集单条」**):

- **按链接采集单条**:粘贴 B站 分享文案 / 视频链接 / b23.tv 短链 / BV 号,或公众号文章、小红书笔记链接(type=`single` 或单条合集)。
- **批量链接采集**:一次粘贴多条链接(可混合渠道),逐条解析后合成一个合集。

**采集规则**:

- **排序**:采集单元索引按采集时间(`last_at`)倒序,新采集的排最前;缺时间的老单元按更新日期排在后面。
- **单元 ID**:显式 `--id` 永远优先;单条 B站 默认用 BV 号,公众号/小红书用链接派生的稳定 id,批量采集用链接集合派生的稳定 id(重跑同一批链接更新同一单元);按主题才保留「同名标题复用」兼容回退,并会打印提示。单元 id 只允许 `[A-Za-z0-9_-]`,服务端读写入口统一校验。
- **单条采集带合集**:按链接采集 B站 视频且命中所属合集时,一次 view 响应就把合集内每一集都作为记录入库(封面/日期/播放数/作者取自合集响应),单元自动变为合集页;合集目录挂在单元级数据上,每集详情页都能看到。
- **B站分P/合集目录**:采集 B站 时顺带读取 view 接口的 `pages`(多分P)与 `ugc_season`(合集),写进单元数据;视频详情页在播放区正下方展示「所属合集」与「分P 目录」:横向滑动的分集按钮,「展开全部」切网格,点分集/分P 直接在当前页内嵌播放器切播(不跳站内详情页)。老数据用 `--enrich-bili`(可配 `--id` 限定单元)补齐,页面上不再需要实时请求 B站(避免 CORS 与风控)。
- **重新采集的采集方式**:采集页在「重新采集」状态下出现「追加 / 覆盖」选择——追加(默认)保留旧条目只补新的;覆盖只保留本次结果,旧条目全部丢弃(前端二次确认,建议先预览)。CLI 对应 `--replace`。
- **按主题采集**:填关键词并勾选渠道(**可多选**:B站 / 公众号 / 小红书,默认 B站),结果合并为一个合集(type=`series`)。B站走官方搜索并聚类同系列;公众号借搜索引擎找文章后逐条抓正文、作者、日期;小红书只收录搜索标题与原文链接(正文需登录)。各渠道借搜索引擎找工作,存在间歇性风控与相关性噪声,失败会在日志里说明,可稍后重试或改用按链接 / 批量采集。

表单默认只显示当前模式的**必填项**;UP 主、搜索页数、手工补录、预览模式收在「可选设置」折叠区里(采集失败时会自动展开,方便手工补录)。

**显示标题**:批量采集时必填——粘贴链接后会按链接数与渠道自动生成默认值(如「公众号 / 小红书 · 3 条合集」),可手动改写;其他模式的标题可选,留空时用内容原标题或主题关键词。

**两种表单状态**:

- **新建采集**(默认):标题可选、没有「仅更新标题 / 下线不显示」按钮,可选设置默认折叠,采完即为新单元。
- **重新采集**:只有从右侧列表点「重新采集」才进入。会把该单元上次填写的采集信息(方式、链接/关键词、标题、手工补录)原样带回表单,**并默认展开全部可选设置**(方便核对上次的补录信息),但**不会自动采集**,确认无误后再点「确认重新采集」;期间标题可改,也可不采集直接做两件事:
  - 「仅更新标题(不重新采集)」→ 只改显示标题;
  - 「下线不显示」→ 把该单元从首页/聚合列表撤下(数据保留,按钮变「重新上线显示」可随时恢复)。
  勾选的采集渠道也会原样带回(老单元默认只选 B站)。
  顶部提示条可「退出重新采集」回到新建态(可选设置恢复折叠)。

右侧「已有采集单元」列出全部单元,每个单元可:
- 点「显示中 / 已关闭」按钮切换首页显示(数据保留,仅控制展示);
- 点「重新采集」把上次填写信息带回左侧表单(仅回填,不执行)。

老单元没有采集记录时,批量采集会用该单元现有条目的原链接回填,其余用当初的关键词,可自行调整。

### 命令行

```bash
python3 collector/generate.py --enrich-bili --id guwen-animation    # 为已有 B站单元补分P/合集目录
python3 collector/generate.py "每天挖掘一个神奇网站"                 # 按主题采集(series)
python3 collector/generate.py "某主题" --up "UP主名" --id my-topic   # 指定单元ID采集
python3 collector/generate.py "某主题" --channels wechat,xhs        # 按主题多渠道(逗号分隔)
python3 collector/generate.py "https://b23.tv/xxx" --url             # 按链接采集(single)
python3 collector/generate.py '【标题-哔哩哔哩】 https://b23.tv/xxx' --url
python3 collector/generate.py "某主题" --dry-run                     # 预览,不写数据
python3 collector/generate.py --list                                 # 列出所有采集单元
python3 collector/generate.py --toggle daily-website --off           # 关闭显示
python3 collector/generate.py --toggle daily-website --on            # 开启显示
```

### 部署到服务器

采集服务已改为多线程(ThreadingMixIn):一次长采集不会阻塞页面/健康检查;采集任务本身仍串行(`COLLECT_LOCK`),索引与单元文件写入共用 `WRITE_LOCK`,避免并发覆盖。

采集功能依赖一个**真实运行的 Python 进程**,不能只把 HTML 当静态站点托管,否则点「开始采集」会报 `Unexpected token '<' ... is not valid JSON`——因为 `/api/collect` 被静态服务器接走返回了 HTML。

```bash
python3 collector/server.py                    # 默认只监听 127.0.0.1:8765(仅本机)
python3 collector/server.py --lan              # 局域网模式:绑定 0.0.0.0,同一 Wi-Fi 下手机可访问
python3 collector/server.py --port 8080        # 改端口
python3 collector/server.py 8080 --api-only    # 采集端专用:只提供 API + 采集页,静态展示交给独立 Web 服务
python3 collector/server.py --public --token <口令>   # 对外访问:绑定 0.0.0.0,写接口必须带 X-Collect-Token
```

局域网模式下，启动日志会打印本机局域网 IP；手机与电脑连同一个 Wi-Fi，访问：

```text
http://电脑局域网IP:8765/collector/settings.html
```

`--lan` 会把采集与设置接口暴露给同一局域网，只建议在可信网络临时使用，用完 `Ctrl+C` 关闭。设置页的 Origin 白名单已覆盖本机、内网 IP 和 `.local` 主机名，手机访问时保存、立即执行和 Git 推送不会被 CSRF 校验误拦。

部署后自检 `<地址>/api/health`,应返回 JSON 且 `writable: true`、`index_ok: true`。反向代理需把 `/api/*` 转发到该进程,并用 `location /` 整体转发;只要该地址能从公网访问,就应使用 `--public --token` 启动,详见 `docs/DEPLOY.md` 的「安全基线」。静态站托管到 GitHub Pages 见 `docs/GITHUB-PAGES.md`。

采集端与展示端可分离部署(同机/同容器共享数据目录,或不同机器挂载同一共享卷),两端用相同的环境变量 `VIDEO_DATA_DIR` 指向共享目录即可。

### 定时采集(推荐)与本机采集台

- **定时采集**:主题清单在仓库根目录 `topics.yml`(`--topics` 批量执行),由 GitHub Actions 每天 07:00 跑一次;本机 launchd 兜底自 2026-11-26 起**暂停**(脚本与 plist 保留,恢复见 `docs/DEPLOY.md` 第十章)。展示端始终是纯静态,不需要 `server.py` 常驻。
- **本机采集台**:需要表单交互、重新采集回填、下线开关时,临时运行 `python3 collector/server.py`(默认只听 `127.0.0.1`),用完关掉即可。

```bash
python3 collector/generate.py --topics topics.yml --dry-run --pages 1   # 本地验证清单解析
```

## 采集规则

### 精准匹配

**关键词必须完整出现在视频标题中**——标题可比关键词多字,但程序**不会把关键词拆成片段**匹配。

- ✅ 关键词「每天挖掘一个神奇网站」匹配「每天挖掘一个神奇网站:一个免费学英语的网站」
- ❌ 不匹配「一个神奇网站推荐」「每天挖掘 神奇网站」

### 增量更新与去重

- 以**条目唯一键**去重:B站=BV 号,公众号=原文地址,小红书=笔记 ID;同一内容只保留一条。
- 旧有但本次未搜到的视频**保留**,避免搜索排序波动导致数据丢失;新数据覆盖旧数据(刷新播放量/简介)。
- 结果报告:新增 N / 更新 N / 未变 N / 合计 N 期;数据无变化时跳过写文件。
- 重新采集命中已有单元 id 时,只改这一个单元的数据文件与索引条目,**其他单元和显示开关不受影响**。

### 其他

- 播放链接统一为干净地址 `https://www.bilibili.com/video/BV号/`,无追踪参数。
- B站 搜索 API 最多约 1000 条结果且排序有波动,偶尔超时重跑即可。
- 日期统一 `yyyy.mm.dd`(如 `2026.11.19`),避免往年数据混淆。

## 数据备份与还原

采集产出 = `assets/data/index.js` + `assets/data/collections/*.js`;各展示页和程序不随采集变化,无需备份。

```bash
python3 collector/backup_data.py backup                  # 打包到 backups/data-<时间戳>.zip
python3 collector/backup_data.py list                    # 列出备份
python3 collector/backup_data.py restore backups/data-xxx.zip            # 还原(自动先留当前快照)
python3 collector/backup_data.py restore backups/data-xxx.zip --yes      # 跳过确认
python3 collector/backup_data.py backup --out /mnt/nas/backup            # 备份到外部目录
```

- 还原只解包 `.js`,拒绝 `..` 路径穿越;默认还原前自动留存当前快照,可回退。
- 环境变量 `VIDEO_DATA_DIR` / `VIDEO_BACKUP_DIR` 可覆盖路径,适配共享目录与定时备份。

## 从旧版迁移(已结束)

旧版「每个主题一个 `topics/<slug>.html` + `assets/data/<slug>.js`」已于 2026-11-26 完成迁移并清理,`--migrate` 与相关旧目录常量一并移除;需要旧文件时从 git 历史恢复,页面统一由五个固定模板提供。

## 主题与换肤(页面/数据分离)

- 分层:`assets/data/`(纯数据) → `assets/data-loader.js`(加载) → 页面(容器 + 路由) → `assets/style.css`(布局骨架) → `assets/themes/<name>.css`(设计 token)。
- 内置六套:浅色 `default`、深色 `dark`、科技 `tech`、学院 `campus`、古典 `classical`、二次元 `anime`;默认**跟随系统**,页脚 7 项切换(跟随系统 / 六套主题),选择存 `localStorage`(`jiye.theme`)。`?theme=tech` 等只做预览,不写入存储、不进索引。
- 新增主题 = ①复制 `assets/themes/default.css` 改名 → ②只改变量值 → ③在 `assets/theme.js` 的 `THEMES` 注册一行。**不需要改任何 HTML/JS**。
- 契约:主题只允许定义 token 与最多一份页面级局部样式,不得改 DOM 或写业务逻辑;所有主题的变量必须与 `default.css` 完全对齐、且都在 `theme.js` 注册(否则会出现"半套主题"或切不到,`scripts/docs_check.py` 与 `tests/test_pages.py` 会拦)。
- 字体也走 token:正文 `--font-sans`、标题 `--font-display`;学院/古典风用衬线标题,科技风用等宽拉丁字形。
- 防闪烁:`theme.js` 是 `<head>` 内的阻塞脚本,在首次绘制前同步插入 `<link id="theme-css">`。

## 自检与测试(不需要联网)

```bash
python3 collector/generate.py --verify    # 索引/数据文件/count/key/日期/开关/page/platform 合法性
python3 collector/generate.py --normalize # 数据侧解耦:剥离 page、platform 统一为稳定 key(幂等,可加 --dry-run 预览)
python3 scripts/docs_check.py             # 文档口径与引用有效性
python3 -m unittest discover -s tests -v  # 解析器 fixtures + 数据层回归 + CLI 冒烟
```

CI(`.github/workflows/ci.yml`)在每次推送/PR 跑上述三项;定时采集 workflow 在提交前也会跑 `--verify`,自检不过不提交。

## 说明

- 本站仅做公开视频的链接聚合,不托管视频文件,版权归各创作者所有。
- 程序只读取 B站 公开接口,不涉及登录、私有数据或绕过付费内容。
- 视频号因无法在浏览器播放、抖音因验证码风控,当前均未纳入。
