# 集页 · 主题内容清单

一集一页,把值得收藏的内容收成清单。纯静态站点 + 配套**纯规则采集程序**:输入主题关键词 → B站 搜索 → 精准匹配 → 去重合并 → 写入数据。全程不调用任何 AI 服务。(原名「神奇网站挖掘机 · 视频聚合站」)

核心原则:**采集只处理数据,不生成、不修改任何静态页面**。页面是三个固定模板,由人工单独维护布局样式;每次采集是一个独立数据单元,可单独更新、单独关闭显示。

## 四个页面(固定模板,单独维护样式)

| 页面 | 用途 | 参数 |
|---|---|---|
| `index.html` | 首页:主题总览,卡片带平台徽标/合集或单条标记/条数/标签/最新日期,支持平台与标签筛选 | — |
| `series.html` | 合集页:只展示**最近 20 条**(按发布者分组、可搜索),超出部分引导到全部内容页 | `?id=<单元ID>` |
| `list.html` | 全部内容页:该单元的全部采集记录,支持关键词/作者/平台筛选、排序与分页(每页 12 条) | `?id=<单元ID>&q=<可选搜索词>` |
| `single.html` | 站内详情页:按渠道切换模板(B站视频页内播放 / 公众号文章版式 / 小红书笔记版式),多集内容带上一集、下一集与全集列表 | `?id=<单元ID>&k=<条目键>`(兼容 `&i=<下标>`) |

四个页面各自把**本页专属布局样式内联在 `<style>` 块**里,改某页布局只动该页文件;公共基础样式在 `assets/style.css`。数据加载逻辑统一在 `assets/data-loader.js`。

页面跳转链路:首页 → 合集页 → 全部内容页 / 站内详情页。合集页与列表页的卡片**不再直连源平台**,统一进站内详情页;详情页里再提供「前往 B站 观看」「阅读原文」等外链兜底。

首页只展示 `enabled !== false` 的单元;关闭显示的单元数据仍保留,只是不在首页出现。

## 目录结构

```
.
├── README.md                       # 根目录唯一文档(项目总览)
├── index.html / series.html / single.html   # 固定展示页(人工维护样式)
├── list.html                       # 全部内容页(筛选 + 分页)
├── assets/
│   ├── style.css                   # 公共基础样式
│   ├── data-loader.js              # 三页面共用的单元数据加载器
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
| `source` | 来源平台、UP 主名称与主页 |
| `keyword` | 采集关键词或原链接(便于重新采集) |
| `created` / `updated` | 首次 / 最近采集日期 |
| `videos` | 视频列表(标题、BV、封面、播放量、日期、作者、简介) |

索引(`assets/data/index.js`)汇总每个单元的元信息(不含视频列表)+ 显示开关,供首页渲染。

## 使用方式

### 采集交互页(推荐)

```bash
python3 collector/server.py 8765
```

浏览器打开 `http://127.0.0.1:8765/collect.html`,页面顶部三个模式 Tab(**默认「按链接采集单条」**):

- **按链接采集单条**:粘贴 B站 分享文案 / 视频链接 / b23.tv 短链 / BV 号,或公众号文章、小红书笔记链接(type=`single` 或单条合集)。
- **批量链接采集**:一次粘贴多条链接(可混合渠道),逐条解析后合成一个合集。
- **按主题采集**:填关键词,到 B站 搜索并聚类同系列(type=`series`)。

表单默认只显示当前模式的**必填项**,标题、单元 ID、UP 主、搜索页数、手工补录、预览模式都收在「可选设置」折叠区里(采集失败时会自动展开,方便手工补录)。

右侧「已有采集单元」列出全部单元,每个单元可:
- 点「显示中 / 已关闭」按钮切换首页显示(数据保留,仅控制展示);
- 点「重采此单元」把该单元 ID 填入表单,之后填关键词采集即**只更新这个单元**。

表单里的「单元 ID」即上面的 id:填已有 id → 重新采集该单元;留空 → 按标题匹配或新建。

### 命令行

```bash
python3 collector/generate.py "每天挖掘一个神奇网站"                 # 按主题采集(series)
python3 collector/generate.py "某主题" --up "UP主名" --id my-topic   # 指定单元ID采集
python3 collector/generate.py "https://b23.tv/xxx" --url             # 按链接采集(single)
python3 collector/generate.py '【标题-哔哩哔哩】 https://b23.tv/xxx' --url
python3 collector/generate.py "某主题" --dry-run                     # 预览,不写数据
python3 collector/generate.py --list                                 # 列出所有采集单元
python3 collector/generate.py --toggle daily-website --off           # 关闭显示
python3 collector/generate.py --toggle daily-website --on            # 开启显示
python3 collector/generate.py --migrate                              # 从旧版 topic 数据迁移(幂等)
```

### 部署到服务器

采集功能依赖一个**真实运行的 Python 进程**,不能只把 HTML 当静态站点托管,否则点「开始采集」会报 `Unexpected token '<' ... is not valid JSON`——因为 `/api/collect` 被静态服务器接走返回了 HTML。

```bash
PORT=8080 python3 collector/server.py          # 监听 0.0.0.0;端口也可命令行传入
python3 collector/server.py 8080 --api-only    # 采集端专用:只提供 API + 采集页,静态展示交给独立 Web 服务
```

部署后自检 `<地址>/api/health`,应返回 JSON 且 `writable: true`。反向代理需把 `/api/*` 转发到该进程,并用 `location /` 整体转发;详见 `docs/DEPLOY.md`。静态站托管到 GitHub Pages 见 `docs/GITHUB-PAGES.md`。

采集端与展示端可分离部署(同机/同容器共享数据目录,或不同机器挂载同一共享卷),两端用相同的环境变量 `VIDEO_DATA_DIR` 指向共享目录即可。

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

采集产出 = `assets/data/index.js` + `assets/data/collections/*.js`;三个页面和程序不随采集变化,无需备份。

```bash
python3 collector/backup_data.py backup                  # 打包到 backups/data-<时间戳>.zip
python3 collector/backup_data.py list                    # 列出备份
python3 collector/backup_data.py restore backups/data-xxx.zip            # 还原(自动先留当前快照)
python3 collector/backup_data.py restore backups/data-xxx.zip --yes      # 跳过确认
python3 collector/backup_data.py backup --out /mnt/nas/backup            # 备份到外部目录
```

- 还原只解包 `.js`,拒绝 `..` 路径穿越;默认还原前自动留存当前快照,可回退。
- 环境变量 `VIDEO_DATA_DIR` / `VIDEO_BACKUP_DIR` 可覆盖路径,适配共享目录与定时备份。

## 从旧版迁移

旧版是「每个主题一个 `topics/<slug>.html` + `assets/data/<slug>.js`」。执行 `python3 collector/generate.py --migrate` 会把旧数据转成采集单元格式(创建 `collections/<id>.js` 并重建索引),BV 号 id 归为 `single`、其余为 `series`。迁移幂等,旧文件不删除。迁移后页面改由三个固定模板提供,旧 `topics/` 目录不再被引用。

## 说明

- 本站仅做公开视频的链接聚合,不托管视频文件,版权归各创作者所有。
- 程序只读取 B站 公开接口,不涉及登录、私有数据或绕过付费内容。
- 视频号因无法在浏览器播放、抖音因验证码风控,当前均未纳入。
