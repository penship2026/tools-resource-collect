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

---

## 当前状态(2026-11-26 09:10)

- 站点名:**集页**;支持 B站 / 公众号 / 小红书三渠道采集;线上存量 9 个单元(7 series + 2 single),服务未常驻,采集时运行 `python3 collector/server.py 8765`。
- 四个展示页:首页 → 合集页(最近 20 条)→ 全部内容页(筛选 + 分页) / 站内详情页(按渠道分模板,多集带上下集与全集列表)。
- 采集页默认「按链接采集」,必填项直显、可选设置折叠;分「新建采集 / 重新采集」两态,重新采集只回填不自动执行,可只改标题。
- 远程仓库:`github.com/penship2026/tools-resource-collect`(main),Pages 自定义域名 `resource-collect.ximyan.com`。
- 已知限制:B站搜索翻页为唯一数据源,排序波动可能漏采旧视频;小红书未登录抓取有风控,需手工补录;视频号仅能跳转微信观看;抖音风控未纳入。
- 待办事项:**见 docs/TODO.md**(旧架构文件清理)。
