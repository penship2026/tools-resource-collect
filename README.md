# 集页 · 主题内容清单

一集一页,把值得收藏的内容收成清单。纯静态站点 + 配套**纯规则采集程序**:输入主题关键词 → B站 搜索 → 精准匹配 → 去重合并 → 写入数据。全程不调用任何 AI 服务。(原名「神奇网站挖掘机 · 视频聚合站」)

核心原则:**采集只处理数据,不生成、不修改任何静态页面**。页面是五个固定模板,由人工单独维护布局样式;每次采集是一个独立数据单元,可单独更新、单独关闭显示。

## 五个页面(固定模板,单独维护样式)

| 页面 | 用途 | 参数 |
|---|---|---|
| `index.html` | 首页:主题总览,卡片带平台徽标/合集或单条标记/条数/标签/最新日期,支持平台与标签筛选 | — |
| `series.html` | 合集页:只展示**最近 20 条**(按发布者分组、可搜索),超出部分引导到全部内容页 | `?id=<单元ID>` |
| `list.html` | 全部内容页:该单元的全部采集记录,支持关键词/作者/平台筛选、排序与分页(每页 12 条) | `?id=<单元ID>&q=<可选搜索词>` |
| `single.html` | 站内详情页:按渠道切换模板(B站视频页内播放 / 公众号文章版式 / 小红书笔记版式),多集内容带上一集、下一集与全集列表 | `?id=<单元ID>&k=<条目键>`(兼容 `&i=<下标>`) |
| `collector/collect.html` | 采集页(仅本机使用):填主题关键词/链接发起采集,调 `/api/*`;公网模式需填口令 | — |

五个页面各自把**本页专属布局样式内联在 `<style>` 块**里,改某页布局只动该页文件;公共基础样式在 `assets/style.css`。数据加载统一在 `assets/data-loader.js`,**渲染统一在 `assets/render.js`**(卡片/条目/详情/多集导航只有一份实现),主题在 `assets/themes/`。

页面跳转链路:首页 → 合集页 → 全部内容页 / 站内详情页。合集页与列表页的卡片**不再直连源平台**,统一进站内详情页;详情页里再提供「前往 B站 观看」「阅读原文」等外链兜底。

首页只展示 `enabled !== false` 的单元;关闭显示的单元数据仍保留,只是不在首页出现。

## 个人收藏(纯本地,无后端)

条目级收藏,数据只存在浏览器 `localStorage`(键 `jiye.mine.v1`),不上传、不采集、不需要账号。

- 在合集页/全部内容页/详情页点条目上的 ☆ 收藏;首页头部在**有收藏时**才出现「公开 / 我的」开关,点「我的」进入 `index.html?view=mine`。
- 每条收藏存一份最小快照(标题/链接/封面/日期/作者/单元名),原单元下线或被关闭显示后仍可读。
- 「我的」页可导出 JSON 备份、导入 JSON(默认合并、按 key 保留较新;「替换」会覆盖当前数据);导入前自动先导出当前收藏,非法文件整体拒绝不写入。收藏软上限 800 条。
- 只收藏站内已有条目,不支持手工录入站外链接。

## 目录结构

```
.
├── README.md                       # 根目录唯一文档(项目总览)
├── index.html / series.html / single.html   # 固定展示页(人工维护样式)
├── list.html                       # 全部内容页(筛选 + 分页)
├── assets/
│   ├── style.css                   # 公共基础样式
│   ├── data-loader.js              # 各页面共用的单元数据加载器
│   └── data/
│       ├── index.js                # 采集单元索引(元信息+显示开关)
│       └── collections/
│           ├── daily-website.js    # 每次采集独立一个数据文件
│           └── ...
├── collector/                      # 采集管理代码(独立于展示页)
│   ├── generate.py                 # 采集数据程序(纯标准库,不写页面)
│   ├── server.py                   # 采集服务(--api-only 可只跑采集端)
│   ├── backup_data.py              # 数据备份/还原工具
│   └── collect.html                # 采集交互页(表单入口)
├── docs/                           # 部署与运维文档
│   ├── DEPLOY.md                   # 服务器 / 群晖 / 飞牛部署
│   └── GITHUB-PAGES.md             # GitHub Pages 托管与数据更新
├── .github/workflows/              # 定时采集 workflow
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
| `videos` | 视频列表(标题、BV、封面、播放量、日期、作者、简介) |

索引(`assets/data/index.js`)汇总每个单元的元信息(不含视频列表、`intake`、`runs`,只留 `last_at` / `last_mode_label` 摘要)+ 显示开关,供首页渲染。

## 使用方式

### 采集交互页(推荐)

```bash
python3 collector/server.py 8765
```

浏览器打开 `http://127.0.0.1:8765/collect.html`,页面顶部三个模式 Tab(**默认「按链接采集单条」**):

- **按链接采集单条**:粘贴 B站 分享文案 / 视频链接 / b23.tv 短链 / BV 号,或公众号文章、小红书笔记链接(type=`single` 或单条合集)。
- **批量链接采集**:一次粘贴多条链接(可混合渠道),逐条解析后合成一个合集。
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

采集功能依赖一个**真实运行的 Python 进程**,不能只把 HTML 当静态站点托管,否则点「开始采集」会报 `Unexpected token '<' ... is not valid JSON`——因为 `/api/collect` 被静态服务器接走返回了 HTML。

```bash
python3 collector/server.py                    # 默认只监听 127.0.0.1:8765(仅本机)
python3 collector/server.py --port 8080        # 改端口
python3 collector/server.py 8080 --api-only    # 采集端专用:只提供 API + 采集页,静态展示交给独立 Web 服务
python3 collector/server.py --public --token <口令>   # 对外访问:绑定 0.0.0.0,写接口必须带 X-Collect-Token
```

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
- 内置两套:浅色 `default`、深色 `dark`;默认**跟随系统**,页脚三态切换(跟随系统 / 浅色 / 深色),选择存 `localStorage`(`jiye.theme`)。`?theme=dark` 只做预览,不写入存储、不进索引。
- 新增主题 = ①复制 `assets/themes/default.css` 改名 → ②只改变量值 → ③在 `assets/theme.js` 的 `THEMES` 注册一行。**不需要改任何 HTML/JS**。
- 契约:主题只允许定义 token 与最多一份页面级局部样式,不得改 DOM 或写业务逻辑;`default.css` 与 `dark.css` 的变量必须完全对齐(否则会出现"半套主题",`scripts/docs_check.py` 会拦)。
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
