# 项目开发工作日志

> 项目:tools-resource-collect —— 「集页 · 主题内容清单」(原名「神奇网站挖掘机 · 视频聚合站」)
> B站主题视频采集聚合站:三个固定展示页面(index/series/single),采集程序只写数据不生成页面。
> 本文档由内部工作日志整理而来,按时间演进顺序记录关键决策、代码改动与验证结论。
> 各阶段「处理时间」来自会话记录时间戳,精确到分钟,区间为「需求提出 → 本阶段完成(下一需求提出前)」。
>
> 待办事项已单独列出,见 **docs/TODO.md**(逐条处理,处理完勾选)。

---

## 一、前期调研(2026-11-25 01:12 – 01:25)

### 任务背景(01:12 提出)
用户想采集「每天挖掘一个神奇网站」主题视频(B站/抖音/视频号等),整理成聚合页。本阶段只分析,未生成文件。

### 源视频画像
- 账号:草根的异世界(深圳),2026-11-19 发布,本期内容:免费学汉语拼音的网站
- 话题标签:#汉语拼音 #拼音识字 #拼音拼读 #实用工具 #网站推荐
- 链接:`https://weixin.qq.com/sph/AOyHDed7yj` → 重定向到 channels.weixin.qq.com

### 实测结论(01:15–01:25,浏览器自动化 + curl)
- **视频号**:分享页 video 标签数=0,只有封面图+二维码,提示「扫码前往微信观看」。**不能浏览器播放,只能微信内看**。页面是纯前端 SPA,靠 mmfinderopenwebapisvr 接口动态取数。
- **B站**:可浏览器直接播放(video 标签=1,readyState=4,blob 源)。搜索页可直接访问、无需登录。→ 确定为主数据源(01:18 采集渠道分析后确认)。
- **抖音**:搜索页与首页均触发验证码中间页,浏览器自动化被风控拦截,采集难度高,未纳入。
- 搜索引擎对视频号内容几乎无收录。

### 关键发现
同源账号跨平台分发:草根的异世界在 B站 也同步发布该系列,抓到多条真实 BV 链接。

---

## 二、静态站第一版 → 纯规则程序生成(2026-11-25 01:25 – 01:58)

### 演进路径
1. 首版(01:25):手工生成 `index.html` + `topics/daily-website.html` + `assets/data.js` 集中数据。
2. 用户要求「给主题→B站搜索同类→生成聚合页,全程不用 AI」(01:37),改为纯规则程序;01:48 用「跟着动画学古文」验证通过。

### 关键技术决策
- **放弃浏览器自动化**,改用 B站公开搜索 API `api.bilibili.com/x/web-interface/search/type`。必需带 `buvid3` cookie,否则第二次请求被风控。
- **UP主投稿 API 不可用**:`x/space/wbi/arc/search` 需 WBI 签名,请求返回 -352 风控。故以搜索翻页为唯一数据源(上限约 1000 条,排序有波动,已知限制)。
- **数据按主题独立存放**:解决了单 data.js 被新主题覆盖的 bug——根因是 JS 对象键无引号导致 json.loads 失败返回空列表。
- 纯 Python 标准库实现,无第三方依赖。

---

## 三、采集交互页 + 展示优化(2026-11-25 01:58 – 02:35,06:16 – 06:27)

### 程序改造(generate.py,01:58–02:14)
- **精准匹配**(02:14):关键词必须完整出现在标题中(可前后多字,不拆分词)。
- **增量去重**:`merge_videos` 以 BV 号去重,新数据覆盖旧数据,旧有未搜到的保留;报告 新增/更新/未变/合计;无变化跳过写文件。
- **简介采集**:normalize 增加 desc/author/ts 字段;ts 用于正确时间排序(date 字符串排序会把 10 月排在 9 月前)。

### 新增文件(01:58)
- `collect.html` 采集交互页(后移入 collector/):表单 + 实时日志 + 统计报告。
- `server.py` 本地服务(端口 8765):静态托管 + API。

### 部署排障记录
- **采集报 JSON 解析错误**(02:28):根因是 `/api/collect` 请求落到静态托管/网关返回 HTML。修复:接口改相对路径、readJSON 校验 content-type、`/api/health` 健康探测。关键提醒:采集必须有真实 Python 进程,不能只当静态站托管。
- **局域网手机访问 404**(02:35):同属接口未转发到 Python 进程的问题。
- **手机首页不更新**(06:16–06:27):根因是数据 js 无 Cache-Control 被缓存。修复:server.py 统一加 `Cache-Control: no-store`。
- **服务重启 Address already in use**:TCPServer 加 `allow_reuse_address = True` 根治。

---

## 四、日期年份、单片采集与部署(2026-11-25 06:27 – 08:09)

### 日期显示加年份(06:27)
时间只显示月日,往年数据难区分。normalize date 改为带年份格式;批量回填全部数据文件的 date(用 ts 精确还原年份);实际存在跨年数据(古文主题 2026/2025/2024/2023 等)。

### 按链接采集单片(06:31)
- `extract_bvid()` 解析链接/BV号/b23.tv 短链(跟随重定向);`extract_share_title()` 从「【标题-哔哩哔哩】」提取标题(06:37 支持分享文案);`fetch_video_by_bvid()` 调 `x/web-interface/view` 详情 API。
- 单片单元默认 id 用 BV 号(稳定);标题优先级:用户指定 > 分享文案标题 > 视频原标题。
- CLI 加 --url 开关,collect.html 加 Tab 切换。

### 服务重启与部署文档(06:58–07:58)
`docs/DEPLOY.md`(现结构)覆盖普通 Linux 服务器(systemd + Nginx)、群晖 DSM、飞牛 fnOS 三种部署;含自检清单、故障排查表。
Dockerfile(python:3.12-slim,**必须 TZ=Asia/Shanghai + tzdata** 解决 fromtimestamp 日期差 8 小时)与 docker-compose.yml。

### 采集端/展示端分离 + 备份(07:58–08:09)
- 数据目录支持环境变量覆盖:`VIDEO_DATA_DIR`、`VIDEO_TOPICS_DIR`、`VIDEO_BACKUP_DIR`、`VIDEO_PROJECT_ROOT`。
- server.py 新增 `--api-only` / `SERVER_ROLE=api` 采集端专用模式。
- `backup_data.py`(纯标准库):backup/list/restore 子命令;还原拒绝路径穿越。
- 结论:不做物理分离(数据仍是 .js 靠相对路径 script 加载),同机进程分离 + 逻辑集中数据 + 备份脚本。

---

## 五、采集单元数据模型重构(2026-11-25 08:09 – 08:29,重大架构改动)

用户要求:三个独立页面便于单独维护样式;采集只处理数据不动页面;数据按采集独立存放、可局部重采、可关闭显示。

### 数据架构
- 每次采集=独立单元,存 `assets/data/collections/<id>.js`;`assets/data/index.js` 存索引元信息 + enabled 开关。
- **关键坑:必须用 `window.X =` 赋值**(浏览器里 const 全局声明不挂 window,页面 `window.COLLECTION_INDEX` 读不到导致首页 0 主题)。
- 字段:id / type(series|single) / title / slogan / enabled / source{platform,name,url} / keyword / created / updated / page / count / videos。

### 程序与页面
- generate.py:write_collection_file / save_collection(只更新命中单元)、set_enabled(--toggle)、migrate_legacy(幂等迁移)、CLI 加 --id / --list / --toggle / --migrate。
- 三页面:index.html(筛选+搜索)、series.html(?id= 按作者分组)、single.html(?id= 大图详情),公共 `assets/data-loader.js`(动态注入 script,兼容 file://,safeId 防路径穿越)。
- server.py:新增 POST /api/toggle;/api/collect 支持 mode=url。

---

## 六、GitHub Pages 托管与目录整理(2026-11-25 08:29 – 10:25)

### 托管文档(docs/GITHUB-PAGES.md,08:29)
- 三页面全相对路径 + script 标签加载数据,天然兼容 Pages 子路径。
- Pages 不能跑 Python,采集仍需本地/NAS/Actions;采集后只提交 index.js 与 collections/*.js。
- 防盗链:`<meta name="referrer" content="no-referrer">`。

### 配置落成真实文件(09:47–09:52)
- `.github/workflows/update-data.yml`(**必须设 TZ=Asia/Shanghai 且开启 Actions 写权限**)、`.gitignore`(assets/data/*.js 只匹配一层以免误伤 collections)。
- 注意标准目录是 `.github/workflows`,非 workers。

### 目录结构整理(09:52)
- 采集管理代码全部移入 `collector/`(generate.py、server.py、backup_data.py、collect.html);部署文档移入 `docs/`。
- 根目录只保留 README.md 一个文档,展示页三模板与 assets 保留根目录(否则 GitHub Pages 失效)。
- server.py 静态托管根=项目根,`/collect.html` 映射到 `collector/collect.html`(旧链接不失效)。

---

## 七、页面体验迭代(2026-11-25 10:25 – 11:09)

### 封面遮挡修复(10:25–10:33)
首页卡片封面左下角日期 badge 与底部日期重复且遮挡封面 → 封面不再放日期标签,日期统一由卡片底部显示。内联 badge 需显式覆盖公共 style.css 旧规则(top+bottom 同时生效会把徽标拉成竖条)。

### 多渠道结构优化(10:33)
- 主页:统计区加「来源渠道」数;封面左下角平台徽标(B站);平台筛选 chips 动态生成(单渠道隐藏、多渠道自动出现);标签筛选 chips(单元 tags 并集按次数取前 8)。
- 子页面:统计/详情加「最近采集」(updated 字段);「来源:平台·UP主」行;「标签」行;页脚文案改「各平台」。
- 多渠道预留全部数据驱动,接入抖音/视频号等新渠道零代码改动。

### 嵌播分析与命名(10:39)
- 嵌入播放分析:推荐 B站官方 iframe(`player.bilibili.com/player.html?bvid=xxx`),合规、改动小;需保留跳转兜底(部分创作者关闭外链权限)。→ 待办,见 TODO.md
- 命名推荐:「片单集」最贴定位(主题→一页清单),备选 拾集 / 主题片单志 / 合集小站 / 猎片。→ 待办,见 TODO.md

### 播放量隐藏 + 标签采集(10:48)
- 播放量是渠道平台数据,全站隐藏不显示(series 卡片角标、single 大图角标与播放量详情行删除;数据仍保留在 videos 里仅不展示)。
- 采集时获取标签:collect_by_url 调标签接口取视频标签(失败不阻断);collect_topic 暂用关键词兜底;标签用于首页筛选。

---

## 八、正式标签 + 日期格式统一(2026-11-25 11:09 – 11:26)

### 标签体系升级
- **接口修正**:`x/web-interface/archive/tags` 已失效(404),改用 `x/web-interface/view/detail/tag?bvid=`(主)+ `x/tag/archive/tags?bvid=`(备)双端点依次尝试。
- **series 取真实标签**:采集时对系列最新一期视频请求一次标签接口(仅 1 次避免限流),单元 tags=正式视频标签(空则关键词兜底)。
- **存量回填**:9 个单元全部按各自最新一期视频抓取正式标签(如 文言文/动画文言文;拼音拼读/实用工具/网站推荐;Spring AI/大模型开发 等)。
- **首页卡片**:标签独立成一行(`.tag-line`,胶囊样式,`-webkit-line-clamp:2` 最多两行截断),底部行只留期数+日期。

### 日期格式全站统一 yyyy.mm.dd
- generate.py normalize:date 改 `%Y.%m.%d`(零填充);merge_videos sort_key 正则兼容新旧两种格式。
- 存量迁移:全部 videos[].date 与单元/索引 latest 由「X年X月X日」转「YYYY.MM.DD」。
- 页面:首页「最近更新」`replace(/-/g,'.')`;series/single 的 fmtDate 输出 yyyy.mm.dd(补零)。

### 验证(11:26 完成)
Chrome 无头截图三页面全部正常:首页卡片标签独立行两行截断、日期正确;series 统计/标签行/时间跨度正确;single 发布/采集日期与正式标签正确。数据一致性检查无异常项。

---

## 九、文档化(2026-11-25 11:28 – 11:34)

- 11:28:工作日志落地为 `docs/WORKLOG.md`(即本文档)。
- 11:34:待办单列为 `docs/TODO.md`;全文补充精确到分钟的处理时间。

---

## 十、待办闭环:页内播放 + 网站更名(2026-11-26 00:05 – 00:12)

### 页内嵌入播放(00:08)
- `single.html` 播放区按平台分支:B站且有 BV 号 → 官方 iframe
  `player.bilibili.com/player.html?bvid=<BV>&autoplay=0&danmaku=0&high_quality=1&as_wide=1`;
  其他渠道或缺少编号 → 保留封面跳转(图文类内容无播放器)。
- 新增 `.player-frame`(16:9 自适应容器)与 `.player-fallback`;兜底链接「前往 B站 观看 →」,应对部分 UP 主关闭站外播放。
- 合规说明:只用官方嵌入播放器,不解析视频流。

### 网站更名 → 「集页」(00:11)
- 需求变化:后续要接公众号、小红书图文(文案页),原名偏视频定位。
- 候选:集页 / 拾集 / 集录 / 清单集,用户选定 **集页**(一集一页,「集」对应视频合集、「页」对应图文页面)。
- 替换范围:generate.py 的 `window.SITE`、`assets/data/index.js` 的 SITE 块、三页面 title/品牌、collect.html、style.css 注释、README 标题简介。
- 文案同步多渠道:首页副标题「视频与图文(公众号、小红书等)」;三页面页脚「内容来自各平台公开投稿或发布」;采集页「生成子页」→「写入采集单元」。
- 遗留:`topics/*.html` 旧架构页面未改(不被引用,计划随旧数据一起清理)。

### 新增待办
- 接入公众号 / 小红书渠道采集(数据模型与页面层已就绪,需补各渠道采集适配)。

---

## 十一、开发进度与完整性审计(2026-11-26 00:23)

### 检查范围与结果
- **代码**:generate.py / server.py / backup_data.py 语法检查通过;三页面与采集页标题、品牌名均为「集页」,旧名无残留(除旧架构 topics/ 目录)。
- **数据**:9 个单元全部通过一致性校验——索引与数据文件的 count / type / latest / tags 完全一致;日期均为 yyyy.mm.dd;播放地址均为干净 BV 链接;无缺封面、无空标签。
- **页面逻辑**:single 页 iframe 分支、页脚文案、动态 title 已更新;series 动态 title 补站名。
- **文档**:README、WORKLOG、TODO、DEPLOY、GITHUB-PAGES 齐全;TODO 两条历史待办已闭环。
- **路由与接口**:index / series / single / collect / 样式 / 索引 / 单元数据 / api/health / api/topics 全部 200。

### 发现并修复的问题
1. **采集页与接口全部 404(严重)**:`server.py` 重构时把 `translate_path / log_message / end_headers / do_GET / do_POST` 等请求处理方法误放进 `ReusableTCPServer`(服务器类),`Handler` 只剩 `__init__`,实际请求走的是 `SimpleHTTPRequestHandler` 默认行为 → `/collect.html`、`/api/health`、`/api/topics`、`/api/collect` 全部 404,采集页不可用。
   - 修复:把全部处理方法移回 `Handler`,`ReusableTCPServer` 只保留 `allow_reuse_address = True`。
   - 验证:8 条路由全部 200,`/api/health` 返回 `writable:true`、`role:full`,`/api/topics` 正常返回 9 个单元。
2. **`.gitignore` 缺失**,导致 `__pycache__/*.pyc`、`.DS_Store`、`backups/*.zip` 共 11 个文件被仓库跟踪 → 重建 `.gitignore` 并 `git rm --cached`(本地文件保留)。
3. **动态 title 不带站名**:series 为「· 视频合集」、single 为「· 单条精选」→ 统一为「系列合集 · 集页」「单条精选 · 集页」。
4. **远程多出 1 个提交**:`Create CNAME`(自定义域名 `resource-collect.ximyan.com`),已 `pull --ff-only` 快进合并;CNAME 文件保留在仓库根目录,勿删。

### 遗留(未处理,已记入 TODO)
- `topics/*.html`(9 个旧架构页面)与 `assets/data/*.js`(9 个旧根数据文件)已不被引用,建议后续清理。

---

## 当前状态(2026-11-26 00:24)

- 站点名:**集页**;9 个采集单元(7 series + 2 single),数据齐全;服务未常驻,采集时运行 `python3 collector/server.py 8765`。
- single 页支持 B站官方 iframe 页内播放,附跳转兜底。
- 远程仓库:`github.com/penship2026/tools-resource-collect`(main),Pages 自定义域名 `resource-collect.ximyan.com`。
- 已知限制:B站搜索翻页为唯一数据源,排序波动可能漏采旧视频;视频号仅能跳转微信观看;抖音风控未纳入。
- 待办事项:**见 docs/TODO.md**(公众号/小红书渠道采集、旧架构文件清理)。
