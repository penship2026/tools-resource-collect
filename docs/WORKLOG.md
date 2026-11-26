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

## 十二、多渠道采集 + 页面结构改造(2026-11-26 07:20–08:35)

### 07:20–08:00 公众号 / 小红书渠道接入(承接上一轮)
- 新增 `collector/platforms.py` 适配层:`detect_platform` 识别 B站 / 公众号 / 小红书;`fetch_wechat` 解析文章页(`msg_title` / `nickname` / `og:` 系列 / 发布时间);小红书走分享链接解析,被风控时抛 `PlatformError` 并提示手工补录;`extract_urls` 从分享文案批量提链接。
- `generate.py`:条目标配 `platform` / `kind` / `key` 三字段,去重键统一为「平台:平台内 ID」;新增 `--batch` 批量链接采集与 `--manual-*` 手工补录参数;存量 9 单元回填三字段(幂等)。
- 页面层:首页平台徽标配色、系列页/详情页平台标识与「图文」标记、采集页新增批量与手工补录面板。

### 08:00–08:10 采集默认方式 + 列表截断 + 首页入口 + 详情页模板
1. **采集任务默认按链接采集**:Tab 顺序改为「按链接 / 批量 / 按主题」,默认选中链接模式,表单初始态与 `setMode('url')` 对齐。
2. **合集页只展示最近 20 条**:`series.html` 按时间倒序取前 20 条渲染,底部虚线提示条「已显示最近 20 条,共 N 条 → 查看全部内容」。
3. **新增 `list.html` 全部内容页**:关键词 / 作者 / 平台三方筛选 + 排序(最新、最早、标题)+ 分页(每页 12 条,首尾页 + 当前页邻页的省略式页码);卡片带平台角标,支持从合集页带 `?q=` 跳转。
4. **首页导航去掉采集入口**:右上角改为「一集一页 · 持续更新」,采集入口链接移到页脚提示文案里。
5. **详情页按渠道分模板**:`single.html` 拆成四套——B站视频(双栏 + 官方 iframe)、公众号文章(单栏阅读版式 + 绿色 CTA)、小红书笔记(图左文右 3:4 + 红色 CTA)、其他渠道兜底(封面 + 双栏);模板内覆盖 `--brand` 跟随渠道色。

### 08:11–08:20 卡片跳站内详情 + 多集导航
- 需求:集合页点卡片不再跳源平台,改为站内详情;多集内容在详情页提供上一集 / 下一集 / 全集列表。
- `series.html` / `list.html` 卡片链接改为 `single.html?id=<单元>&k=<条目键>`。
- `single.html` 支持 `?k=`(条目键)与 `?i=`(下标)定位条目;按发布时间升序作为「第 1 集 → 第 N 集」固定顺序,渲染 `.ep-nav`(上一集 / 第 N / M 集 / 下一集)与 `.ep-list`(全集列表,当前集高亮、容器自动滚到当前集)。
- 顺带修复:`save_collection` 未把 `updated` / `latest` 写进单元数据文件,导致新采集单元在页面显示「采集于 —」——改为写文件前统一回填。
- 顺带修复:小红书模板的渠道胶囊在纵向 flex 里被拉伸成整行,加 `align-self: flex-start`;网格卡片因标题行数不同高度不齐,`.video-card` 改 flex 列 + `.meta` 自动吸底。

### 08:22–08:28 采集页表单收拢
- 必填项(url / 批量 / 关键词)直显;显示标题、单元 ID、UP 主、搜索页数、手工补录、预览模式全部收进「可选设置」折叠区(默认收起)。
- 主按钮上移到必填项下方;采集失败时自动展开可选设置,便于立刻手工补录。

### 08:29–08:35 上下集显示短标题
- `shortTitle()` 去掉开头「【第 N 期】」标记与合集同名前缀(如「每天挖掘一个神奇网站:xxx」→「xxx」),超过 26 字截断。
- 上一集 / 下一集按钮改为两行:方向标签 + 目标集短标题(单行省略),中间保留「第 N / M 集」。

### 验证
- `py_compile` 通过;真实项目路由 index / series / list / single?k / collect / api-health 全部 200。
- DOM 校验:合集页 20 张卡片且 href 为 `single.html?id=…&k=…`;详情页 `第 19 / 24 集`、上下集短标题正确、全集列表 24 条;多平台合集列表页出现平台筛选与作者下拉。
- 截图校验:合集页截断提示、全部内容页分页、公众号文章版式、小红书笔记版式(B站播放器版)、采集页折叠表单、上下集按钮两行布局。

### 08:50–09:08 批量标题必填 + 采集记录回填 + 仅改标题
- **批量采集「显示标题」升为必填**:粘贴链接即按链接数与渠道自动生成默认值(如「公众号 / 小红书 · 3 条合集」),可手动改写;切采集方式时自动生成的旧值会被清掉,不会带到其他方式。
- **记录每次采集的填写信息**:每次采集把表单内容写进单元(`intake` + `runs`,保留最近 20 次)——采集方式、原始输入、显示标题、UP 主、页数、手工补录、时间、本次新增/更新统计;内容无变化时也留一条记录并同步索引里的最近采集时间。
- **采集页拆成「新建采集 / 重新采集」两种状态**:默认新建,只有从已有单元列表点「重新采集」才进入重新采集态——带出上次填写的全部信息,但**不自动提交**,由用户确认后再采;顶部提示条可「退出重新采集」。
- **仅更新标题**:重新采集态下,标题可改后直接重新采集,也可点「仅更新标题(不重新采集)」只改显示标题;列表里不再有改标题入口,也不会一点就重采。
- **表单收拢**:单元 ID 输入框从「可选设置」移除(新建时不手填 ID,避免误覆盖已有单元),新建态下拉起「仅更新标题」按钮。
- **接口**:新增 `GET /api/intake?id=`(上次填写信息 + 最近记录;老单元用现有条目链接回填批量输入)、`POST /api/title`(只改标题,索引与数据文件同步);`/api/collect` 写入 intake,批量缺标题直接 400;`/api/topics` 增加 `last_at` / `last_mode_label`。
- **索引保持精简**:`index.js` 只存最近采集时间与方式,`intake` / `runs` 只落在 `assets/data/collections/<id>.js`。
- **验证**:接口五项通过(读取回填、只改标题、空标题拒绝、缺标题 400、不存在单元 404);页面实测新建态无「仅更新标题」、列表只剩「显示中 / 重新采集」、重新采集态回填正确、默认标题与时间格式(`yyyy.mm.dd HH:MM`)正确。

### 09:20–09:32 重新采集默认展开可选设置 + 下线不显示
- **可选设置默认展开**:进入「重新采集」态时自动展开「可选设置」(UP 主 / 搜索页数 / 手工补录 / 预览模式),方便核对上次补录信息后再执行;「退出重新采集」或「清空」回到新建态时恢复折叠。
- **新增「下线不显示」**:重新采集态按钮行为「确认重新采集 / 清空 / 仅更新标题 / 下线不显示」;点它把该单元从首页与聚合列表撤下,数据完整保留,按钮随即变「重新上线显示」,可一键恢复。走既有 `POST /api/toggle`,不采集、不动内容。
- **回填接口补状态**:`GET /api/intake` 的 `unit` 增加 `enabled`,重新采集态据此决定按钮文案与动作方向。
- **单条单元回填修正**:老单元既无采集记录又无 `keyword` 时,按链接采集改用现有条目的原链接回填,不再留空。
- **验证**:接口实测 `enabled` 随开关变化;页面实测重新采集态 `details.open === true`、四个按钮同排不换行、下线后状态提示与列表项置灰、重新上线恢复、退出后恢复折叠;`py_compile` 与内联 JS `node --check` 通过。

### 09:45–10:42 按主题采集支持渠道多选
- **渠道多选 UI**:「按主题采集」新增 B站 / 公众号 / 小红书 三个可多选项,默认只选 B站;未选任何渠道时前端拦截;渠道选择写入 `intake.channels`,重新采集原样回填(老单元默认 B站),顶部提示条显示本次渠道。
- **公众号主题采集**:`platforms.py` 新增 `search_topic()`——先用搜索引擎 site: 检索拿候选链接,再逐条 `fetch_wechat` 抓真实标题/作者/日期/封面。实测单主题 8 条文章全部解析成功。
- **小红书主题采集**:小红书正文需登录,只收录搜索引擎给的笔记标题 + 原文链接,以笔记 ID 去重;360 搜索能拿到直链,结果相关性有限,日志会提示核对。
- **多引擎兜底**:搜索引擎会间歇性风控——百度移动 / 百度网页 / 搜狗(公众号)、360 / 百度移动 / 百度网页(小红书)顺序尝试,任一有结果即停;全部失败时把各引擎失败原因汇总给用户,引导改用按链接 / 批量采集。
- **合并入库**:`collect_topic` 新增 `topic_channels` 参数,三渠道结果按 key 去重合并进同一个单元;source.platform 单渠道显示平台名、多渠道显示「多平台」,新增 `platforms` 清单供首页按任一渠道筛选;slogan 与标签随图文内容调整;命令行新增 `--channels`。
- **顺带修复**:首页所有 `.chip` 共用一个处理器,导致点平台筛选时把 `currentFilter` 置空、结果永远为空;改成只处理 `[data-filter]`,平台筛选恢复可用。多平台徽标显示「多平台」。
- **验证**:公众号单渠道 / 三渠道混合(15 条:B站 6 + 公众号 8 + 小红书 1)实测写入正确;`py_compile` + 内联 JS `node --check`;浏览器实测多选提交载荷、回填全选、空选拦截、首页平台筛选命中多平台合集;截图检查三选一行排布与按钮行无溢出。

---

## 当前状态(2026-11-26 10:42)

- 站点名:**集页**;支持 B站 / 公众号 / 小红书三渠道采集;线上存量 9 个单元(7 series + 2 single),服务未常驻,采集时运行 `python3 collector/server.py 8765`。
- 四个展示页:首页 → 合集页(最近 20 条)→ 全部内容页(筛选 + 分页) / 站内详情页(按渠道分模板,多集带上下集与全集列表)。
- 采集页默认「按链接采集」,必填项直显、可选设置折叠;分「新建采集 / 重新采集」两态,重新采集只回填不自动执行,可只改标题,也可直接下线不显示(可选设置默认展开);按主题采集可多选 B站 / 公众号 / 小红书。
- 远程仓库:`github.com/penship2026/tools-resource-collect`(main),Pages 自定义域名 `resource-collect.ximyan.com`。
- 已知限制:B站搜索翻页为唯一数据源,排序波动可能漏采旧视频;公众号 / 小红书主题采集依赖搜索引擎,会间歇性风控、结果有噪声,小红书只有标题+链接;视频号仅能跳转微信观看;抖音风控未纳入。
- 待办事项:**见 docs/TODO.md**(旧架构文件清理)。

### 10:30–13:10 全项目评审与改造计划落档
- **评审**:按 README / docs / collector 全量代码 + 5 个页面走查,产出 `docs/REVIEW-20261126.md`(P0–P3 共 18 条,含实测证据)。基线 `HEAD = efff2a2`(多渠道采集已提交),`py_compile` 通过。
- **实测结论(可复现)**:`server.py` 默认静态托管把 `/.git/config`、`/backups/`、`/collector/generate.py` 都返回 200;3 个写接口无鉴权且监听 `0.0.0.0`;`index.html` / `series.html` / `collector/collect.html` 仍无 `esc()`;`.github/workflows` 不存在但 README 声称已内置。
- **评审期间并发事实**:10:01–10:26 另一侧连续修改 `generate.py` / `platforms.py` / `server.py` / `collect.html`,P0「`channels` 形参遮蔽」在评审过程中被修复,该条已标为【已修】并复测通过。
- **后续评估(三轮,均未改代码)**:服务能否取消(结论:可任务化,但浏览器直连平台 API 受 CORS 限制)、个人收藏层(localStorage + 导出导入,1.5–2 人日)、GitHub 同类项目(无完全对应,B站方向多为下载/留档,localStorage 收藏层有大量同构实现)。
- **计划**:产出 `docs/PLAN-20261126.md`,决策 D1–D33、里程碑 M0–M6;7 项待定逐条定稿(见计划第六章);补「页面与数据分离 / 多主题模版」分析(第七章);按「多端并发」要求新增第八章协作约定与 D34–D39。

## 当前状态(2026-11-26 13:10)

- 站点名:**集页**;支持 B站 / 公众号 / 小红书三渠道采集;存量 **11 个单元**(以 `generate.py --list` 与索引/文件一一对应校验为准;上文 10:42 记录的「9 个单元」已过时)。
- 页面共 **5 个**:首页 / 合集页 / 全部内容页 / 站内详情页 + 采集页 `collector/collect.html`;服务未常驻,采集时运行 `python3 collector/server.py 8765`。
- 远程仓库:`github.com/penship2026/tools-resource-collect`(main),Pages 自定义域名 `resource-collect.ximyan.com`。
- 当前文档:`docs/REVIEW-20261126.md`(问题依据)、`docs/PLAN-20261126.md`(决策与里程碑)、`docs/TODO.md`(执行)、本文件(演进记录)。
- 已知限制:B站搜索翻页为唯一数据源;公众号 / 小红书主题采集依赖搜索引擎,会间歇性风控、结果有噪声;小红书只有标题+链接;视频号仅能跳转微信观看;抖音风控未纳入。

### 13:10–13:30 M0 止血(转义 / 原子写入 / 损坏识别)
- **共享转义**:`assets/data-loader.js` 新增 `escHtml`(同时挂 `window.escHtml` 与 `CollectionLoader.esc`),`index.html`、`series.html` 全部字段改走转义;`list.html`、`single.html` 原局部 `esc` 改为调用共享实现(补上单引号);`collect.html` 新增 `esc` 与 `safePage`,单元列表的标题 / 平台 / id / page 全部转义;首页新增 `cardHref`,数据里的 `page` 仅接受站内页面路由。
- **原子写入**:`generate.py` 新增 `write_text_atomic`(同目录临时文件 + `fsync` + `os.replace`,异常清理残留 `.tmp`),`write_index`、`write_collection_file`、`set_enabled`、`--migrate` 全部改用它;覆盖前自动快照到 `backups/auto`,保留最近 10 份。
- **损坏识别**:新增 `IndexCorrupt`、`load_index(strict=)`、`index_status()`;`/api/health` 上报 `index_ok/index_count/index_error`;`/api/topics` 在索引损坏时返回 500 与具体原因,采集页据此显示原因,不再伪装成「暂无采集单元」。
- **忽略项**:`backups/` 整体忽略,并预置个人收藏导出与 `topics.local.yml`。
- **验证**:`py_compile` 通过;`--list` 11 个单元;临时数据目录实测索引正常/损坏两态、严格模式抛 `IndexCorrupt`、写入后无 `.tmp`、快照上限 10;`escHtml` 对 `<img onerror>` 与属性引号转义正确;5 个页面内联脚本 `node --check` 全通过;`/api/health` 返回 `index_ok:true,index_count:11`。

### 13:30–13:50 M1 安全(默认仅本机 / 公网口令 / 静态白名单)
- **启动方式**:`server.py` 改为 argparse,默认 `127.0.0.1:8765`;监听非本机地址但未设口令时打提示;`--api-only` 保留。
- **公网模式**:`--public` 绑定 `0.0.0.0` 且必须提供口令(`--token` / `COLLECT_TOKEN`),否则启动即退出;写接口统一校验 `X-Collect-Token`(兼容 `?token=`),无效返回 401;`/api/health` 增加 `auth` 字段,公网模式不回显本机目录。
- **静态白名单**:只放行 5 个展示页、采集页与 `assets/**`;`/.git`、`backups/`、`docs/`、`*.py`、`.github` 等返回 JSON 404。此前实测这些路径均为 200(源码、备份、git 配置可直接下载),本次已封堵。
- **采集页**:新增口令输入框(仅 `auth=token` 时显示),所有请求改走 `apiFetch` 自动附带头;遇到 401 自动露出输入框。
- **验证**:默认模式 4 个敏感路径 404、3 个正常页面 200;`--public` 无口令 exit 2;带口令时无头/错口令 401、正确口令正常;`py_compile` 与 `node --check` 通过。

### 13:50–14:20 M2 任务化(workflow + topics.yml + launchd 兜底)
- **清单驱动**:`generate.py` 新增 `--topics`(可多次指定合并)、`load_topics_yaml` 受限解析(零依赖,报错带行号)、`run_topics` 逐条执行并汇总失败;新增 `topics.yml`,收录 7 个按主题采集的已发布单元。
- **GitHub Actions**:新增 `.github/workflows/update-data.yml`——每天 UTC 23:00(北京 07:00)、可手动触发并传 pages、`concurrency: update-data` 串行、仅数据有变化时提交 `data:`。
- **本机兜底**:新增 `scripts/launchd/collect.sh` 与 `install.sh`(模板 `com.jiye.collect.plist.in`),默认每天 08:10、只采集不提交,`AUTO_PUSH=1` 才 pull/commit/push;日志进 `logs/`(已 gitignore)。plist 已生成并装载(`launchctl bootstrap`,state=not running),未立即触发采集。
- **文档**:`DEPLOY.md` 改为「形态 A 静态站+任务(推荐)/ 形态 B 本机采集台」两段式并新增 launchd 章节;`GITHUB-PAGES.md` 3.2 删除内嵌 YAML,改为指向真实文件,消除「文档说已内置、仓库缺失」的漂移。
- **验证**:清单解析 7 条;`--topics /tmp/topics-test.yml --dry-run --pages 1` 端到端通过(搜 20 条、合并 26 期、未写盘);`py_compile`、`bash -n`、`plutil -lint` 全通过。

### 14:20–15:10 M3 个人收藏层
- **新增 `assets/personal.js`**:localStorage 单键 `jiye.mine.v1`,条目级收藏 + 最小快照,单元下线仍可读;导出/导入 JSON(导入前自动导出、默认合并、替换覆盖、非法文件整体拒绝、800 条软上限、只收 http(s))。
- **页面接入**:`series.html` / `list.html` / `single.html` 卡片与详情加 ☆ 按钮(事件委托 + `preventDefault`);`index.html` 页头「公开 / 我的」开关仅在收藏 > 0 时出现,`?view=mine` 进入收藏网格并加 `noindex`,页脚常驻导入导出入口。
- **样式**:`assets/style.css` 追加收藏层样式(不新增第三方依赖,主题化时只需改 CSS 变量)。
- **验证**:13 项 node 单测通过;5 页 inline 脚本 `node --check` 通过;本地服务实测 5 页与 `assets/personal.js` 全 200。

### 15:10–16:00 M4 质量闸门
- **D13 自检**:新增 `verify_data()` / `--verify`,六类检查(索引可解析、索引↔数据文件双向对应、count、key 唯一、日期格式、开关一致)。接入 Actions 提交前与 launchd 推送前,自检失败不提交。
- **D14 回归**:新增 3 个页面结构 fixtures 与 18 个 unittest 用例(含解析器保留/去重、小红书状态树、索引损坏、原子写、自检各失败分支、CLI 冒烟);修复 `_xhs_state` 尾分号兼容。
- **D17 缓存**:页面与数据 `no-store`、CSS/JS 300 秒、图片 1 天,实测头部正确。
- **D38 文档自检**:`scripts/docs_check.py`(文件存在/口径/引用/workflow/部署章节),接入新增的 `ci.yml`。
- **D16 清理**:删 `topics/*.html`(9)与根 `assets/data/*.js`(9);`--migrate` 空转正常。`min_match`/`match_all`/`LEGACY_DIR` 因接口透传暂留,记入下轮。
- **验证**:`--verify` 11 单元 0 问题;18 测试通过;docs-check 通过;7 个本地路径 200。

### 16:00–16:50 M5 主题化(第一段)
- **token 拆分**:`:root` 的 12 个基础 token + 4 个 `--plat-*` 从 `style.css` 移到 `assets/themes/default.css` / `dark.css`;`style.css` 只保留布局。
- **切换机制**:新增 `assets/theme.js`——注册表 `THEMES`、解析顺序「`?theme=` 预览 > 本地存储 > 系统偏好」、`<head>` 阻塞注入 `<link id="theme-css">` 防闪烁、系统深色变化联动、页脚三态开关(跟随系统/浅色/深色)。
- **页面接入**:5 个页面 `<head>` 加脚本与 `<noscript>` 兜底;`PLAT_COLORS` 改用 `var(--plat-*)`。
- **校验**:`--verify` 增加单元级 `theme` 取值校验;`docs_check.py` 增加两套主题 token 对齐检查。
- **验证**:6 个主题解析用例(node)通过;本地 9 个路径 200;19 个 unittest 与 docs-check 通过。

### 17:00–18:00 D21 视图层收口
- **新增 `assets/render.js`**:`topicCard` / `videoCard` / `detail`(四渠道模板)/ `episodes` + 路由与格式化辅助函数,全部转义、配色走主题 token。
- **四页改写**:删掉各自的卡片与详情模板、`row`/`pills`/`shortTitle`/`buildEpisodeNav`、重复的 `PLAT_COLORS`/`fmtDate`,只留容器、路由、数据加载;`detailHref` 统一走 `Render.detailHref`。
- **回归**:新增 `tests/test_render.js`(10 个视图层用例)与 `tests/test_pages.py`(渲染层引用/无重复实现/内联脚本语法/node 用例);`docs_check.py` 增加页面契约检查。
- **验证**:26 个 Python 用例 + 10 个 node 用例通过;`--verify` 通过;8894 端口 9 个路径 200。

### 18:00 launchd 兜底暂停
- 按用户要求暂停本机定时任务:`launchctl bootout gui/501/com.jiye.collect` + `launchctl disable gui/501/com.jiye.collect`(持久禁用,登录不再自动加载);plist 保留,恢复方式写入 `docs/DEPLOY.md`。

### 18:30–19:30 D24 数据侧解耦 + 样式优化一轮
- **D24 生产端**:`generate.py` 增 `platform_key()`(中文名/旧值 → `bilibili|wechat|xhs|multi`);四个采集分支写 key,不再写 `page`;`migrate_legacy` 清理旧 page 字段。
- **D24 归一**:新增 `--normalize`(幂等 + `--dry-run`),对现有 11 个单元/索引执行一次,剥离 page、platform 转 key;`--verify` 增「不得含 page」「platform 必须合法 key」两类检查。
- **D24 展示端**:`server.py` 用 `unit_page()` 按 type 推导路由、API 把 key 翻成中文;`render.js` 增 `platKey`/`platLabel`,`platColor` 同时兼容 key 与旧中文;首页 chips 值用 key、显示用中文;`series`/`list`/`single` 平台判断全部走 `Render.*`。
- **样式优化(M5 第二段)**:两套主题补字号/间距/圆角/悬停阴影/顶栏底色/hero 光晕 token;`style.css` 改毛玻璃顶栏、渐变品牌标、hero `clamp` 排版、卡片 hover(阴影+封面轻微放大)、聚焦外环、`prefers-reduced-motion` 与移动端断点、页脚紧凑化;四页内联样式同步 chips/徽标/角标/主按钮;修复收藏星标压住卡片右下日期的问题(`.video-info .meta` 预留 34px)。
- **验证**:29 个 Python 用例、10 个 node 用例、`--verify`(11 单元 0 问题)、`docs_check.py` 全通过;Chrome 无头截图检查首页/列表页/深色模式渲染正常;本地 6 个路径 200。

### 19:40–20:30 D15 收口 + D16 剩余清理
- **D15**:新增 `_finalize_unit()` 作为采集单元写盘唯一出口(组装字段 + 记录填写信息 + 原子写 + 重建索引);合集/图文单条/批量/B站单条四个分支改为调用,删掉各自重复的 dict 与 `attach_intake`/`save_collection` 调用。
- **D16 死参数**:`min_match`/`match_all` 全链路删除(CLI、`collect_topic`、`pick_series`、`title_match`、`server.py`);`title_match` 收敛为单一规则。
- **D16 legacy**:删 `LEGACY_DIR`、`migrate_legacy()`、`--migrate`;`load_collection_data()` 去掉旧根目录回退;README/DEPLOY 旧版迁移章节同步改为「已清理」。
- **验证**:31 个 Python 用例(新增 2 个)、10 个 node 用例、`--verify`、docs-check 全通过;`--help` 无遗留参数;服务端三个接口冒烟正常(collect 返回业务错误而非崩溃)。

### 20:40–21:30 主题扩展(科技 / 学院 / 古典)
- 新增 `assets/themes/tech.css` / `campus.css` / `classical.css`,与 default/dark 共用 29 个 token;新增 `--font-sans`/`--font-display`,正文与标题分别引用,学院/古典风启用衬线标题。
- `theme.js` 注册 5 套主题、页脚 6 项切换并允许换行;`generate.py` 的 `THEME_NAMES` 同步;`docs_check.py` 主题检查改为全量 token 对齐 + 注册表覆盖;新增页面测试防「加了 css 切不到」。
- 验证:32 个 Python 用例、10 个 node 用例、`--verify`、docs-check 通过;截图检查三套新主题与页脚切换器渲染正常。

### 21:40–22:20 科技风重做 + 二次元主题
- 反馈 `tech` 与 `dark` 太像 → 科技风改为靛蓝黑底 + 青/品红霓虹 + 网格底纹 + 近直角 + 霓虹描边,与深色明确区隔。
- 新增 `assets/themes/anime.css`:樱花粉/天蓝渐变、大圆角、柔和彩影、圆体标题;注册为第 6 套,页脚 7 项切换。
- 同步 `THEME_NAMES`、页面主题数量基线、README/GITHUB-PAGES 文案;PLAN 追加 10.5(D42)。
- 验证:32 个 Python + 10 个 node 用例、`--verify`、docs-check 通过;截图对比通过。

### 22:40–23:30 布局 token 化清单落档 + 我的页仅收藏/自定义标题
- PLAN 追加第十一章「布局 token 化清单」:重复声明冲突 10 处、五组 token 建议值、主题级与结构级边界、实施顺序与验收矩阵。
- `?view=mine` 只渲染本机收藏;修复组件 `display:grid/flex` 盖掉 `[hidden]` 导致公开网格仍显示的缺陷,新增 `[hidden] { display:none !important }`。
- 我的页标题可自定义(✎ 行内编辑,Enter/失焦保存、Esc 取消,上限 20 字,存 `jiye.mine.title.v1`,同步浏览器标题);新增页面契约测试。
- 验证:33 个 Python + 10 个 node 用例、`--verify`、docs-check 通过;截图确认我的视图无公开内容。

### 23:40–24:10 科技风改为拉勾风格
- 按反馈把 `tech` 从赛博霓虹改为拉勾式浅色科技风:浅灰底、白卡片、拉勾绿 `#00b389`、细分隔线、8px 圆角、轻阴影,间距收紧。
- 与 default 的差异集中到主色/圆角/间距/阴影,和 dark 不再同色系;token 数量与对齐检查不变。
- 验证:截图对比 tech/default 通过;32 个 Python + 10 个 node 用例、`--verify`、docs-check 全通过。

### 00:10–00:50 我的页设置(名称 + 专属主题)
- 我的页头部在导出/导入后新增「设置」面板:收藏页名称 + 我的主题。
- 我的主题独立存储 `jiye.mine.theme.v1`,只在 `?view=mine` 覆盖公开主题;公开页与页脚主题切换不受影响,`?theme=` 预览优先级最高。
- 面板下拉由主题注册表生成,保存同步标题与 document.title,支持取消/Esc;补充页面钩子用例(34 Python + 10 node 全通过)。本次仅本地提交,未推送。

### 01:00–01:35 我的页 hero(标题/副标题可自定义)
- 我的页顶部改为公开首页同构 hero:大标题 + 副标题 + 收藏数,右侧导出/导入/设置,≤720px 上下堆叠并加分隔线。
- 副标题落 `jiye.mine.subtitle.v1`(60 字上限,留空恢复默认);设置面板增加「页面副标题」与恢复默认;保存后 hero 即时刷新。
- 验证:自定义标题/副标题截图通过,面板回填正确;34 Python + 10 node 用例、docs-check 通过。仅本地提交,未推送。

### 01:45–02:15 我的页标题/副标题支持换行
- 设置与行内编辑由单行 input 改成 textarea;标题上限 40 字、副标题 120 字(含换行),可纵向拖拽。
- hero 加 `white-space: pre-line` 保留换行;✎ 绝对定位到标题右上,修复多行时图标落在末行右侧;Enter 换行、⌘/Ctrl+Enter 保存。
- 浏览器标签用 docTitle() 压成单行;截图验证两行标题/副标题布局正常;全套用例与 docs-check 通过。仅本地提交,未推送。

### 02:20–02:45 我的页 hero 对齐公开首页
- 定位间隙过大根因:`white-space: pre-line` 加在 h2 上,把 HTML 缩进换行渲染成空行。
- 改为只在 `#mine-title` 上保留换行;标题字号/行高/字距与 `.hero h1` 一致,副标题间距/字号/行高与 `.hero .sub` 一致。
- 与公开首页并排截图比对通过;用例与 docs-check 全通过。仅本地提交,未推送。

### 02:50–03:10 「我的」入口名称可自定义
- 顶部「公开 / 我的」开关去掉收藏数,只显示名称;名称落 `jiye.mine.switch.v1`(12 字上限,留空恢复「我的」)。
- 设置面板新增「「我的」入口名称」行与恢复默认;保存后同步刷新开关按钮文本。
- 收藏数仅在 hero 统计展示;显隐仍按收藏数为 0 时隐藏。用例与 docs-check 通过。仅本地提交,未推送。

### 03:15–03:35 「公开」入口名称也可配置
- 顶部开关两个按钮都支持改名:公开 `jiye.mine.public.v1`、我的 `jiye.mine.switch.v1`,各 12 字、留空恢复默认。
- 设置面板新增「「公开」入口名称」一行并带恢复默认;保存后两个按钮文本同步刷新;静态按钮文案去掉「0」。
- 截图验证「全部 | 待看」;用例与 docs-check 通过。仅本地提交,未推送。

### 03:40–04:10 我的页恢复筛选
- 我的页加回与公开首页同构的筛选条:类型(全部/系列/单条)+ 标签 chips + 搜索,复用 `.filter-bar/.chip` 样式。
- 类型与标签从 `COLLECTION_INDEX` 对应单元推导;筛选只作用于渲染,统计切换为「筛选出 N / M 条」,不写 localStorage。
- 3 条测试收藏验证 系列=2、标签计数、统计正确;用例与 docs-check 通过。仅本地提交,未推送。

### 04:20–05:00 合集整卡收藏
- 确认合集没有收藏入口;在线首页主题卡片右下角加 ☆,快照 key 用 `__series`、kind 用 `series`,与条目收藏互不覆盖。
- 「我的」对 kind=series 渲染为合集卡(链接 series.html?id=,meta 加「合集」胶囊);星标避开右上角「合集/单条」标记。
- 点击验证写库与切星正常;node 用例 11 个、Python 34 个、docs-check 通过。仅本地提交,未推送。

### 05:10–06:20 B站分P/合集目录
- 核实 view 接口字段:pages 提供分P,ugc_season 提供合集与分节集列表;浏览器直连受 CORS/风控限制,故走采集端落数据。
- 采集端加 bili_parts/bili_season 与 --enrich-bili;guwen-animation 10 条视频补全(最多 15 P)。
- 详情页全集列表下方新增分P目录/所属合集,内链已收录集、外链未收录集;无数据不渲染。node 12 例、Python 35 例、verify/docs-check 通过。仅本地提交,未推送。

### 06:30–07:10 存量数据补全合集
- 全量执行 --enrich-bili(9 个 B站单元 / 46 条视频),2 条命中 ugc_season:「鬼畜热点」53 集、「词汇学习系列」35 集。
- 截图验证详情页「所属合集」渲染正常(滚动容器与全集列表一致);测试/verify/docs-check 全通过;提交 `9b718cf` 并推送。
- 数据与文档一并提交并推送。

### 07:20–08:10 重新采集支持追加/覆盖
- 数据层新增 merge_for_mode(append 走原 merge_videos,replace 只留本次并带 removed),四处采集路径统一接入。
- /api/collect 支持 merge_mode,仅重新采集(带 unit_id)允许覆盖;CLI 增加 --replace。
- 采集页重新采集状态下出现「追加/覆盖」单选,覆盖非预览二次确认,退出重采复位为追加;单测覆盖两模式。仅本地提交,未推送。


### 08:20–09:05 详情页分集目录上移到播放区
- 重写 Render.parts 为横向 chip 条(序号/标题/时长 + data-play-*),B站模板播放器下方插入 parts-slot;有目录时不再渲染页底全集列表。
- single.html 增加 mountPartsPlayer:点分集改 iframe src 切播、当前集高亮、兜底链接与「正在播放」同步,history 记 pen;「展开全部」切两列网格。
- 12 P 与 53 集两条真实数据截图验证滑动/展开/切播;parts 的 node 用例改为 chip 断言;顺带把 3 处旧 slogan 文案改掉,并 normalize 掉一个未归一化的本地单元。仅本地改动,未推送。

### 09:10–10:05 索引排序与单条采集展开合集
- 索引写入前按 last_at 降序(缺省用 updated),新采集单元置顶;现有 12 个单元重排一次。
- 单链采集 B站 命中 ugc_season 时,用同一次 view 响应的 arc 字段生成全集合集记录,不额外请求;单元转 series、标题取合集名。
- 合集目录改存单元根 season(索引剔除),详情页用 opts.season 兜底,保证每集都能看到目录。
- 实测 53 集单链采集无重复;补全新单元 21 个分P;测试/verify/docs-check 通过。仅本地提交,未推送。

### 10:10–10:55 采集页单元列表分页
- 「已有采集单元」改为每页 10 条,底部页码与上一页/下一页;翻页滚回列表顶部,开关/重采后页码保持。
- 启动本机采集服务验证时发现 /api/topics 因 `unit_page` 未定义而 500,补齐该函数(按 type 推导 single/series 路由)。
- 12 个单元实测「第 1 / 2 页」,第一页 10 条;39 Python 用例通过。仅本地提交,不推送。

### 11:00–12:00 详情页移动端自适应与筛选区改版
- 复现 500px 下详情页播放器横向溢出:网格子项 min-width:auto 被横向分集目录撑宽;加 min-width:0、窄屏 minmax(0,1fr) 与宽度约束后播放器恢复 16:9。
- 首页/我的筛选条改为卡片式分组:类型/平台/标签各一行、虚线分隔;搜索独立一行,胶囊输入框加放大镜与聚焦光环。
- 修正类型 chip 会清掉全部筛选 active 的旧逻辑;平台/标签分组按数据自动显隐。node/Python/verify/docs-check 全通过,仅本地提交。

### 12:00–12:40 开发进度盘点
- 核对 git 历史、TODO、PLAN 与工作区:数据层/采集/展示/个人收藏/主题/工程化主线均已落地,当前 12 单元、39 Python + 12 node 用例、verify 0 问题。
- 识别遗留:采集服务单线程、单元身份靠标题匹配、索引双写、9 个存量 slogan 旧文案、intake id 未白名单、超长输入截断、移动端仅 500px 验证、5 个提交待推送。
- PLAN 新增第十五章(D60)记录完成度与收尾顺序;TODO 关闭已完成的 legacy 清理并登记遗留;README/REVIEW 同步当前状态。

### 13:00–14:10 遗留问题顺序清理(D61)
- 推送 D55–D60 的 6 个提交;直接推送仍遇 HTTP2 framing,改用 `http.version=HTTP/1.1` 成功。
- 9 个存量单元 slogan 按类型替换为「点击分集在当前页播放」/「点击进入详情页」。
- 采集服务 `ThreadingMixIn` 化;采集任务由 `COLLECT_LOCK` 串行,索引/单元/开关/改名共用 `WRITE_LOCK`。
- 单条/批量 id 改为链接派生稳定值,B站默认 BV;按主题标题匹配降为兼容回退并打印提示。
- 新增 `rebuild_index()`:索引以单元文件为唯一事实源,`created/enabled` 随单元文件保存,老数据沿用旧索引兜底。
- `/api/intake`、开关、改名入口补 `valid_unit_id()` 白名单;超长 `intake.input` 保留最近 8000 字并标注。
- Playwright 390×844 复验:详情页无横向溢出,播放器 358×201,目录在下方;首页筛选/搜索正常。44 Python + 12 node + verify/docs-check 全通过;提交 `9b718cf` 并推送。

### 14:20–15:10 对外创作过程记录（D62）
- 通读 PLAN（需求分析、D1–D61、M0–M6）、REVIEW（18 个问题）、TODO（39 项）与 WORKLOG（11-25 01:12 起时间线），抽取可公开发布的事实。
- 新增 `docs/CREATION-STORY-20261126.md`：600 字小红书文案、9 图分镜、完整创作过程、排期理由、做对/踩坑、资料依据。
- 新增同名单文件 HTML：阅读进度、吸顶目录、统计卡、一键复制文案、时间线、里程碑表；Playwright 1280/390 实测无横向溢出，复制按钮通过。
- README 文档索引补充；docs-check 通过。

### 15:20–17:00 设置页与板块体系开发启动（D63）
- 拍板 `pages=3`、`humanities` 默认关闭、Actions 保持 `0 23 * * *`；`run_topics` 增加 `ok/partial/failed` 契约。
- 新增 `sections.yml`（7 板块）与 `topics.yml` v2（section + must/any + enabled）；12 个存量单元补 `section` 并重建索引。
- 实现 `keyword_match` / `pick_series_multi`：must 全命中 + any 任一命中；B站与图文渠道共用。
- 新增设置页 `collector/settings.html` 及 API：保存配置、CSRF/Origin、cron 导出、立即执行、Git 预览/推送、任务查询；Actions schedule 生效时本机调度 409。
- 新增 `git_sync.py`：白名单只提交 `assets/data`，固定 `origin/main`，fetch 后 fast-forward，不 force/reset/clean。
- 新增 `pages.yml` artifact；Pages 不再直出 `collector/`，线上设置页/采集页 404。
- 验收：Python 54 例、node 12 例、verify 12 单元 0 问题、docs-check 通过；本机 HTTP 冒烟通过；Playwright 390/1280 无横向溢出、无 JS 报错。

### 17:10–17:40 真实 dry-run 联调（D63.1）
- `pages=1`：3 成功 / 4 失败；发现 `daily-website` 命中另一个 UP 主，存在作者漂移风险。
- 修复：已有单元重采时从 `source.name` 取原作者并锁定；原作者无命中时本次不更新，不切换到其他作者。
- `pages=3` 复跑：3 成功 / 4 失败，作者漂移已阻止；`daily-website`、`英语启蒙必备`、`SpringAI` 均锁定原作者。
- 仍失败：`大模型对比`、`跟着动画学古文`、`最好的AI数字人项目`（60 条候选中无 must 全命中）；`数学思维启蒙动画` 原作者无命中，按作者锁阻止更新。
- 全程 `--dry-run`，未写数据；Python 55 例通过。

### 18:05–18:20 放宽三个主题关键词（D63.2）
- `大模型对比` → must `大模型` + any `对比/评测/横评`；`跟着动画学古文` → must `古文` + any `动画/小古文/动画片`；`最好的AI数字人项目` → must `AI数字人` + any `项目/虚拟人/数字人`。
- 数学主题关键词不动，作者锁保持严格，不提供解锁入口。
- `pages=3` 复跑：仍是 3 成功 / 4 失败；4 个失败均变为“原作者本次无命中，作者锁阻止切换”，关键词不再是唯一原因。
- 结论：在作者锁严格模式下，这 4 个存量单元只能等原作者更新；未写盘。

### 18:35–18:50 设置页支持局域网访问（D64）
- 新增 `--lan`：绑定 `0.0.0.0`，启动时打印局域网 IP 与设置页地址。
- 修复设置页 Origin 白名单：原来只允许 127.0.0.1/localhost，手机用局域网 IP 打开后会保存/执行 403；现允许内网 IP 和 `.local` 主机名。
- 更新设置页提示、README 与部署文档；新增 `tests/test_server.py`，共 59 例通过。
- 冒烟：`GET /api/settings` 7 板块/7 主题；带 `Origin: http://192.168.1.23:8765` 的 `POST /api/git/preview` 正常返回。
- 安全边界：`--lan` 无口令，只适合可信 Wi-Fi 临时使用；公网仍用 `--public --token`。

### 19:20 设置页卡片收缩/展开（D65）
- 板块卡片与主题卡片支持点击标题栏收起/展开，折叠状态写入 localStorage，刷新后保留。
- 顶部新增“全部收起 / 全部展开”，同时控制所有板块与主题卡片。
- 手机端顶栏自动换行；折叠后隐藏板块说明等元信息，避免标题挤压。
- 内联脚本 `node --check` 通过，服务页面可正常读取新结构。

### 19:55 设置页默认收起与填写说明（D66）
- 折叠状态模型改为“默认全部收起，只记录展开项”；首次打开或清除本地状态后，板块与主题卡片全部收起。
- 顶部按钮默认显示「全部展开」，可一次展开所有板块与主题。
- 新增独立填写说明页 `collector/settings-guide.html`，覆盖板块、主题、关键词、作者锁、保存、定时、Git 与常见问题。
- 设置页顶部增加「填写说明」入口；服务静态白名单同步放行说明页及 `/settings-guide.html` 别名。
- 浏览器验证：说明页与设置页均 200，设置页默认输出 `is-collapsed` 卡片。
