# 待办清单

> 逐条处理,处理完把 `- [ ]` 改为 `- [x]` 并在「处理记录」补一行结果。
> 来源:docs/WORKLOG.md 中遗留的待确认/待执行事项。
> 改造计划(决策与里程碑):docs/PLAN-20261126.md;问题依据:docs/REVIEW-20261126.md。
> 多端并发:本文件只「勾选 + 末尾追加记录」,不重排/不格式化;开工前先看 PLAN 第八章 8.3。

---

## 处理完的条目

### ✅ 1. 页内嵌入播放:B站官方 iframe

- **状态**:已完成(2026-11-26 00:08)
- **提出时间**:2026-11-25 10:39
- **方案**:B站官方 iframe `https://player.bilibili.com/player.html?bvid=<BV号>&autoplay=0&danmaku=0&high_quality=1&as_wide=1`
- **实现**:`single.html` 播放区按平台分支——B站且有 BV 号时渲染 iframe(`.player-frame`),下方加一行兜底提示;其他渠道或缺少编号时仍为封面跳转(图文类内容无播放器)。
- **兜底**:部分 UP 主关闭站外播放时 iframe 无法播放,保留「前往 B站 观看 →」链接。
- **处理记录**:single.html 新增 `.player-frame`/`.player-fallback` 样式与 `playerHtml` 分支逻辑;Chrome 无头截图验证 iframe 区域渲染正常(16:9、无溢出)。

---

### ✅ 2. 网站更名:多渠道定位下定为「集页」

- **状态**:已完成(2026-11-26 00:11)
- **提出时间**:2026-11-25 10:39
- **决策过程**:最初推荐「片单集」,因后续要接公众号、小红书图文(文案页),名字不能只覆盖视频;补充候选 集页 / 拾集 / 集录 / 清单集,用户选定 **「集页」**(一集一页,视频的「集」与图文的「页」双关)。
- **改名范围(已执行)**:
  - `collector/generate.py`:`write_index` 的 `window.SITE.name` = 集页、description = 一集一页,把值得收藏的内容收成清单;
  - `assets/data/index.js`:SITE 块同步更新;
  - `index.html` / `series.html` / `single.html` / `collector/collect.html`:标题、品牌名;
  - `assets/style.css` 文件头注释;
  - `README.md` 标题与简介。
- **文案同步多渠道定位**:首页副标题改为「视频与图文(公众号、小红书等)」;三页面页脚改为「内容来自各平台公开投稿或发布」;采集页「生成子页」改为「写入采集单元」。
- **未改**:`topics/*.html`(旧架构遗留页,已不被任何入口引用)。
- **处理记录**:全站旧名 `神奇网站挖掘机` 与中间名 `片单集` 已无残留(排除 topics/ 遗留页)。

---

### ✅ 3. 接入公众号 / 小红书渠道采集

- **状态**:已完成(2026-11-26 08:05)
- **实现**:新增 `collector/platforms.py` 适配层(B站 / 公众号 / 小红书 的链接识别、抓取解析、批量提链接);采集条目统一带 `platform` / `kind` / `key`;`generate.py` 增加 `--batch` 批量链接采集与 `--manual-*` 手工补录;采集页新增「批量链接采集」Tab 与手工补录面板。
- **页面**:平台徽标配色、系列页/详情页平台标识与「图文」标记、首页平台筛选、详情页按渠道分模板。
- **限制**:小红书对未登录抓取有风控,失败时用「手工补录」填标题即可建单元。

---

### ✅ 4. 页面结构改造(2026-11-26 08:00–08:35)

| # | 需求 | 落点 |
|---|---|---|
| 1 | 采集任务默认按链接采集 | `collect.html` Tab 顺序 + 默认模式 |
| 2 | 合集只显示最近 20 条,更多记录单独页(可筛选可分页) | `series.html` 截断 + 新增 `list.html` |
| 3 | 首页顶部不再显示采集入口,改到页脚 | `index.html` |
| 4 | 详情页按渠道分模板 | `single.html` 四套模板(B站 / 公众号 / 小红书 / 兜底) |
| 5 | 集合页卡片跳站内详情 + 多集上下集与全集列表 | `series.html` / `list.html` / `single.html` |
| 6 | 采集页只显示必填项,其余折叠 | `collect.html`「可选设置」折叠区 |
| 7 | 上下集按钮显示短标题 | `single.html` `shortTitle()` |

- **处理记录**:路由与 DOM 校验通过,截图校验六处视觉改动;顺带修复 `save_collection` 未写 `updated`/`latest`、小红书渠道胶囊被拉伸、网格卡片高度不齐。

---

### ✅ 5. 批量标题必填 / 采集记录回填 / 仅改标题(2026-11-26 08:50–09:08)

| # | 需求 | 落点 |
|---|---|---|
| 1 | 批量采集的显示标题为必填项,给默认值、可手动编辑 | `collect.html` 标题字段常显,粘贴链接按渠道与条数自动生成(如「公众号 · 3 条合集」),`required` 只在批量生效;`server.py` 批量缺标题返回 400 |
| 2 | 记录每次采集填写的采集信息 | 单元数据新增 `intake`(最近一次填写)与 `runs`(最近 20 次:时间 / 方式 / 输入条数 / 新增更新统计),`generate.attach_intake` 写入 |
| 3 | 重新采集时自动带出、手动确认、不自动采集 | 列表「重新采集」→ `GET /api/intake?id=`,回填后只显示提示条,点「确认重新采集」才执行;可「退出重新采集」 |
| 4 | 显示标题重新采集时可编辑更新 | 重新采集态标题框可改,提交后标题随本次采集更新 |
| 5 | 可选择只更新标题、不重新采集 | 重新采集态出现「仅更新标题(不重新采集)」→ `POST /api/title`,索引与数据文件同步改名 |
| 6 | 默认是新建采集,列表不再有改标题、也不能直接重采 | 新建态隐藏「仅更新标题」;列表只留「显示中 / 重新采集」,点重新采集仅回填表单 |

- **验证**:接口五项通过(回填 / 只改标题 / 空标题 400 / 批量缺标题 400 / 不存在 404);页面实测两态切换、默认标题、`yyyy.mm.dd HH:MM` 时间格式;`index.js` 只存 `last_at`/`last_mode_label` 摘要,未膨胀。

---

### ✅ 6. 重新采集默认展开可选设置 / 新增下线不显示(2026-11-26 09:20–09:32)

| # | 需求 | 落点 |
|---|---|---|
| 1 | 重新采集编辑时默认显示所有可选设置 | `collect.html` `fillFromUnit()` 置 `field-advanced.open = true`;退出/清空恢复折叠 |
| 2 | 除「仅更新标题」外,增加下线不显示功能 | 重新采集态新增「下线不显示」→ `POST /api/toggle`;已下线时变「重新上线显示」 |
| 3 | 回填接口提供当前显示状态 | `GET /api/intake` 的 `unit.enabled` |

- **验证**:重新采集态 `details.open` 为真、四按钮同排;下线后状态提示正确、列表项置灰、可一键重新上线;退出重新采集后按钮隐藏且折叠恢复。

---

### ✅ 7. 按主题采集增加渠道多选(2026-11-26 09:45–10:42)

| # | 需求 | 落点 |
|---|---|---|
| 1 | 按主题采集可勾选多个渠道 | `collect.html` 新增 B站 / 公众号 / 小红书复选项(默认 B站),未选拦截,提交传 `channels` 数组 |
| 2 | 公众号 / 小红书无搜索接口 | `platforms.search_topic()` 多搜索引擎 site: 检索兜底;公众号再抓正文,小红书只收标题+链接 |
| 3 | 多渠道结果合并 | `generate.collect_topic(topic_channels=)` 去重合并同一单元,`source.platform` / `platforms` 标注渠道,命令行 `--channels` |
| 4 | 重新采集恢复渠道选择 | `intake.channels` 回填,老单元默认 B站 |

- **验证**:公众号单渠道 8 条、三渠道混合 15 条(B站 6 / 公众号 8 / 小红书 1)写入正确;浏览器实测多选、空选拦截、回填与首页筛选;顺带修复首页平台筛选被通用 chip 处理器接管导致永远为空的 bug。

---

### ✅ 8. M0 止血:统一转义 / 原子写入 / 索引损坏识别(2026-11-26 13:10–13:30)

- **决策来源**:PLAN 的 D10、D7、D8、D34(改动同批落档)
- **落点**:
  1. `assets/data-loader.js` 新增 `escHtml`(转义 `& < > " '`),5 个页面统一调用;`index.html`/`series.html` 原有裸拼全部包 `esc()`;`collect.html` 新增 `esc()` 与 `safePage()`;首页新增 `cardHref()`,数据里的 `page` 只接受站内路由。
  2. `generate.py` 新增 `write_text_atomic`(临时文件 + fsync + `os.replace` + 异常清理 `.tmp`),索引/单元文件/`--toggle`/迁移写入全部改用它;覆盖前快照到 `backups/auto`,保留最近 10 份。
  3. 新增 `IndexCorrupt` / `load_index(strict=)` / `index_status()`;`/api/health` 增加 `index_ok`/`index_count`/`index_error`;`/api/topics` 损坏时返回 500 与具体原因,采集页显示原因而非「暂无采集单元」。
  4. `.gitignore` 整体忽略 `backups/`,并预置 `个人收藏-*.json`、`personal-*.json`、`topics.local.yml`。
- **验证**:`py_compile` 通过;`--list` 11 个单元;临时目录实测「正常/损坏」两态、严格抛 `IndexCorrupt`、写入无 `.tmp` 残留、快照上限 10;`escHtml` 输出正确;5 页内联脚本 `node --check` 全通过;`/api/health` 返回 `index_ok:true, index_count:11`。

---

### ✅ 9. M1 安全:默认仅本机 / 公网口令 / 静态白名单(2026-11-26 13:30–13:50)

- **决策来源**:PLAN 的 D1、D2、D3、D17(顺带)
- **落点**:
  1. `server.py` 改 argparse:`--port/--host/--public/--token/--api-only`,保留数字位置参数;默认 `127.0.0.1`,监听非本机地址且无口令时给出提示。
  2. `--public` 强制口令(`--token` 或 `COLLECT_TOKEN`),缺失直接退出(exit 2);所有 POST 接口校验 `X-Collect-Token`(兼容 `?token=`),失败 401。
  3. 静态白名单:只放行 5 个展示页、`collector/collect.html`、`assets/**`,其余(含 `.git`/`backups`/`docs`/`*.py`/`.github`)一律 JSON 404。
  4. `/api/health` 增加 `auth` 字段;公网模式不回显本机数据目录。
  5. 采集页新增口令输入(仅 `auth=token` 时出现),所有接口调用走 `apiFetch` 自动带头;401 时自动露出一行提示。
- **验证**:默认模式探测 `/.git/config`、`/backups/`、`/collector/generate.py`、`/docs/DEPLOY.md` 均 404,`index.html`/`style.css`/`collect.html` 均 200;`--public` 无口令 exit 2;`--public --token` 下无头 401、错口令 401、正确口令正常返回;`py_compile` 与 collect.html `node --check` 通过。

---

### ✅ 10. M2 任务化:workflow + topics.yml + 本机 launchd 兜底(2026-11-26 13:50–14:20)

- **决策来源**:D4、D5、D27、D18
- **落点**:
  1. `collector/generate.py` 新增 `load_topics_yaml`(受限 YAML 子集解析,零依赖、报错带行号)、`run_topics`(逐条采集、单条失败不影响其余,末尾汇总失败)、CLI `--topics FILE`(可多次指定合并)。
  2. 新增 `topics.yml`:收录 7 个「按主题采集」的已发布单元(keyword + id + channels)。
  3. 新增 `.github/workflows/update-data.yml`:每天 UTC 23:00(= 北京 07:00)、`workflow_dispatch`(可传 pages)、`concurrency: update-data`、`permissions: contents: write`,数据有变化才 `data:` 提交。
  4. 新增 `scripts/launchd/{collect.sh,com.jiye.collect.plist.in,install.sh}`:默认每天 08:10、只采集不提交(`AUTO_PUSH=1` 才推送)、日志写 `logs/`;install.sh 支持 `--hour/--minute/--load/--uninstall`。
  5. `.gitignore` 增加 `logs/`;`DEPLOY.md` 重写为「形态 A 静态站+任务 / 形态 B 本机采集台」并新增 launchd 章节;`GITHUB-PAGES.md` 3.2 删除内嵌 YAML(改为指向真实文件,消除两处漂移)。
- **验证**:`load_topics_yaml` 解析 7 条通过;`generate.py --topics /tmp/topics-test.yml --dry-run --pages 1` 端到端成功(搜索 20 条、合并 26 期、未写盘);`py_compile` 通过;`bash -n` 与 `plutil -lint` 通过;plist 已生成并通过 `launchctl bootstrap` 装载(08:10,state not running)。

### ✅ 11. M3 个人收藏层(localStorage only + 导出/导入)(2026-11-26 14:20–15:10)

- **决策来源**:D11、D12、D28、D30
- **落点**:新增 `assets/personal.js`(约 380 行,无依赖,不落后端):
  1. 存储键 `jiye.mine.v1`,条目级收藏(unit + key),每条存最小快照(标题/链接/封面/日期/作者/kind/单元名),单元下线后仍可读;
  2. 收藏按钮 `☆/★` 在合集页、全部内容页、详情页出现;点击用事件委托,`preventDefault` 不进详情页;
  3. 「公开 / 我的」开关放首页页头,**收藏数为 0 时隐藏**(D28),页脚常驻「导出备份或导入恢复」入口;
  4. `index.html?view=mine` 渲染收藏网格,自动加 `noindex` meta 并改标题;单元已下线时卡片退回原链接;
  5. 导出 JSON(`个人收藏-YYYYMMDD.json`);导入支持 merge(默认,按 key 保留较新)/ replace(覆盖),导入前自动先导出一份,非法文件整体拒绝不写入;800 条软上限;只接受 http(s) 链接。
- **验证**:node 单测 13 项全通过(空态/新增/去重/导出/非法 JSON/缺标题/`javascript:` 链接/合并/幂等/replace/上限);5 个页面 inline 脚本 `node --check` 通过;本地 8898 端口实测 5 页与 `assets/personal.js` 均 200。
- **口径**:不做双站、不做账号、不做自动同步;不收录手工录入的站外链接(D30)。

### ✅ 12. M4 质量闸门:自检 / 回归测试 / 缓存分层 / 文档自检 / legacy 清理(2026-11-26 15:10–16:00)

- **D13 `--verify`**:`generate.py` 新增 `verify_data()` 与 CLI `--verify`,检查索引可解析、索引与数据文件一一对应(含反向孤儿文件)、`count == len(videos)`、`key` 唯一、日期格式(`yyyy.mm.dd`,兼容 `yyyy-mm-dd`)、`enabled` 两处一致;有问题返回非 0。已接入 `update-data.yml`(提交前)与 `scripts/launchd/collect.sh`(自检不过不推送)。
- **D14 fixtures + 离线回归**:新增 `tests/fixtures/{baidu_mobile,so360,xhs_state}.html` 与 `tests/test_platforms.py`、`tests/test_generate.py`,共 18 个用例(解析器保留/去重/xsec_token 剥离/小红书状态树/平台识别/链接提取/索引损坏/原子写/快照/自检各失败分支/CLI 冒烟)。顺带修复 `_xhs_state` 对 `};</script>` 尾分号的兼容。
- **D17 缓存分层**:`server.py` 的 `Cache-Control` 改为分层——页面与 `assets/data/**` 一律 `no-store`,其他 `*.css/*.js` 300 秒,图片 1 天;实测四类路径头部正确。
- **D38 docs-check**:新增 `scripts/docs_check.py`,检查关键文档存在、旧口径(「三页/四页」写法)不再出现、文档引用不悬空、workflow 不再写死 `--id`、DEPLOY 覆盖「形态 A/launchd/topics.yml」。已接入 CI。
- **CI**:新增 `.github/workflows/ci.yml`(语法 → 回归测试 → 数据自检 → 文档自检)。
- **D16 legacy 清理(部分)**:删除 `topics/*.html`(9)与根目录 `assets/data/*.js`(9),`--migrate` 保持幂等且空转不报错(旧文件缺失时输出「新增 0 个」);死参数 `min_match`/`match_all` 与 `LEGACY_DIR` 暂留,因为 `server.py` 采集接口仍透传这两个字段,删除需同步改接口与采集页(记入下轮)。
- **验证**:`--verify` 通过(11 单元 0 问题);18 个测试通过;文档自检通过;本地 200 检查 7 个路径全部正常。

### ◑ 13. M5 主题化(第一段已完成:token 拆分 + 双主题 + 页脚三态)(2026-11-26 16:00–16:50)

- **完成(D22 部分 / D23 / D25 / D31 / D33 / D32)**:
  1. 新增 `assets/themes/default.css` 与 `dark.css`,把 `:root` 的 12 个 token 与 4 个渠道色 token 从 `style.css` 迁出;`style.css` 只保留布局/组件骨架,不再定义颜色。
  2. 新增 `assets/theme.js`(零依赖):只定义 `THEMES` 注册表 + 主题解析(本地存储 `jiye.theme` = auto/default/dark、`?theme=dark|light` 预览)、`<head>` 内阻塞注入 `<link id="theme-css">` 防闪烁、系统主题变化联动;页脚自动注入三态开关并持久化选择。
  3. 5 个页面 `<head>` 只加一行脚本 + `<noscript>` 兜底;`PLAT_COLORS` 改为 `var(--plat-*)`,渠道配色随主题走。
  4. D32:单元级 `theme` 字段纳入 `--verify` 校验(取值必须在 `default`/`dark` 内),仅提示不启用渲染。
  5. `scripts/docs_check.py` 新增「两套主题 token 必须完全对齐」检查,防半套主题。
- **验证**:node 单测 6 个主题解析用例通过(系统浅/深、存 dark、`?theme=light` 覆盖存储、非法值回退);本地 8895 端口 9 个路径(含 `assets/theme.js`、两套 CSS、`collect.html`)全 200;19 个 unittest 与 docs-check 通过。
- **未完成(留到下一段)**:D21 抽 `assets/render.js`(卡片/详情渲染函数收拢,目前 4 个页面仍有各写一份的 `cardHtml`);D24 数据侧解耦(去掉数据里的 `page` 字段、`source.platform` 改存稳定 key)。

### ✅ 14. D21 视图层收口:`assets/render.js`(2026-11-26 17:00–18:00)

- **新增 `assets/render.js`**(唯一渲染实现,约 380 行):`topicCard`(首页主题卡片)、`videoCard`(合集/列表条目卡片,支持平台标签、摘要、右侧元信息、收藏按钮插槽)、`detail`(B站/公众号/小红书/兜底四模板,返回 `{tpl, label, html}`)、`episodes`(上一集/下一集 + 全集列表)、`detailHref`/`itemKey`/`fmtDate`/`shortTitle`/`platColor`/`esc`。
- **页面变化**:四个展示页删掉各自的 `cardHtml`/四套详情模板/`row`/`pills`/`shortTitle`/`buildEpisodeNav`/重复的 `PLAT_COLORS` 与 `fmtDate`,只保留容器、路由与数据加载;`index`/`series`/`list`/`single` 依次改为调用 `Render.*`。
- **顺带的收益**:`detailHref` 收敛到一处(站内路由只允许一处实现,天然满足"D24 路由属表现层")；模板/卡片 HTML 不再和页面混写。
- **契约检查**:新增 `tests/test_pages.py`(页面必须在页面脚本前加载 `render.js`、必须调用 `Render.*`、页面内不得再出现卡片 HTML 片段、5 页必须加载 `theme.js`、5 页内联脚本 `node --check`、跑 `tests/test_render.js`)与 `tests/test_render.js`(10 个视图层用例:四模板结构、转义、上/下一集、路由编码、日期格式);`scripts/docs_check.py` 增加页面契约检查。
- **验证**:26 个 Python 用例 + 10 个 node 用例全部通过;`--verify` 通过;本地 8894 端口 9 个路径全 200(`single.html?id=daily-website&k=BV1JUs86EESY` 含详情键)。
- **仍未做**:D24 数据侧解耦(去掉数据里的 `page` 字段、`source.platform` 改存稳定 key)以及 D15/D16 剩余项,按计划放到下一轮。

### ⏸ 15. 本机 launchd 兜底:按用户要求暂停(2026-11-26 18:00)

- 已执行 `launchctl bootout gui/501/com.jiye.collect` 卸载,并 `launchctl disable gui/501/com.jiye.collect` 持久禁用(登录不再自动加载);`~/Library/LaunchAgents/com.jiye.collect.plist` 保留,恢复命令见 `docs/DEPLOY.md` 第十章开头。
- 调度侧仅保留 GitHub Actions(每天北京 07:00);`scripts/launchd/collect.sh` 与 `install.sh` 仍作为可选项留在仓库,代码不做改动。

### ✅ 16. D24 数据侧解耦:去掉 `page`,platform 存稳定 key(2026-11-26)

- **数据侧**:`collector/generate.py` 新增 `platform_key()`/`PLATFORM_KEYS`(`bilibili|wechat|xhs|multi`);四个写入点(合集、单条、批量、B站单条)把 `source.platform`、`platforms` 改为 key,不再写 `"page"`;`migrate_legacy` 顺带清理旧 page。
- **一次性归一**:新增 `--normalize`(幂等,`--dry-run` 可预览):剥离数据与索引里的 `page`、把中文 platform 翻成 key;本次实跑 11 个单元全部完成,`--verify` 0 问题。
- **展示侧**:`server.py` 新增 `unit_page()` 按 `type` 推导详情路由,`/api/topics`、`/api/intake` 的 `platform` 由 key 翻成中文;`Render` 新增 `platKey`/`platLabel`,`platColor` 同时接受 key 与旧中文名;首页 chips 用 key 作筛选值、中文作显示;`series`/`list`/`single` 的平台判断改走 `Render`.
- **自检与测试**:`--verify` 增「数据/索引不得含 page」「platform 必须为合法 key」;新增 3 个用例(映射、旧字段检出、归一幂等),Python 用例 26 → 29。
- **验证**:29 个 unittest + 10 个 node 用例通过;`--verify` 11 单元 0 问题;本地 6 个路径 200。

### ◑ 17. M5 样式优化(第二段:统一排版与视觉节奏)(2026-11-26)

- **token 层**:两套主题同步补 `--fs-hero/--fs-title/--fs-body/--fs-sm/--fs-xs`、`--gap-card`、`--pad-card`、`--radius-pill`、`--shadow-hover`、`--brand-2`、`--hero-wash`、`--header-bg`;`docs_check.py` 的主题 token 对齐检查通过。
- **全局样式**:顶部导航改半透明毛玻璃 + 品牌渐变标;hero 字号改 `clamp`、字重/字距收紧;卡片 hover 抬升 + 阴影/边框/封面轻微放大;输入框聚焦加柔和外环;`focus-visible` 统一轮廓;补 `prefers-reduced-motion` 与移动端断点;页脚改为纵向两行紧凑排版。
- **页面内联**:首页 chips 改 pill + hover、徽标统一 pill;列表页 chips/filters 聚焦环、平台角标对齐;详情页主按钮 hover 反馈。
- **修掉的实际问题**:收藏星标与卡片右下角日期/作者重叠 → `.video-info .meta` 右侧预留 34px。
- **验证**:Chrome 无头截图(首页/列表页/首页深色)目视检查通过;29 个 unittest + 10 个 node 用例 + docs-check 全通过。

### ✅ 18. D15 采集单元收口抽 `_finalize_unit()`(2026-11-26)

- 新增 `_finalize_unit()`:统一组装 `id/type/title/slogan/source/keyword/tags/count/videos`(可选 `platforms`)→ 记录填写信息与统计 → 原子写文件并重建索引,返回 `(data_path, index)`。
- 四个采集分支(合集、图文单条、批量、B站单条)全部改调用它,删除各自重复的 collection dict + `attach_intake` + `save_collection` 三连;批量分支顺带补写 `platforms`(多渠道合集可被渠道筛选命中)。
- 新增用例 `test_finalize_unit_writes_contract` 校验字段与落盘结果。

### ✅ 19. D16 剩余:删死参数与 legacy 代码(2026-11-26)

- **死参数**:`min_match`/`match_all` 从 CLI → `collect_topic` → `pick_series` → `title_match` 全链路删除;`title_match(title, keyword)` 只保留「关键词完整出现在标题」这一条真实规则。`server.py` 不再透传这两个字段(采集页本来就没有输入项)。
- **legacy 代码**:删除 `LEGACY_DIR`、`migrate_legacy()`、CLI `--migrate` 与用法说明;`load_collection_data()` 不再回退读取根目录旧数据文件(只读 `collections/`)。
- **文档**:README「从旧版迁移」改为「已结束」,DEPLOY 旧版说明改为「已清理,需要时从 git 历史恢复」。
- **验证**:31 个 Python 用例 + 10 个 node 用例通过;`--verify` 11 单元 0 问题;`--help` 已无 `--migrate/--min-match/--match-all`;服务端 `/api/topics`、`/api/intake`、`/api/collect`(dry-run)响应正常。

### ✅ 20. 主题扩展:科技 / 学院 / 古典(D40/D41)(2026-11-26)

- **新增三套主题**:`assets/themes/tech.css`(深空底 + 青紫霓虹、锐角、发光阴影)、`campus.css`(米白纸张 + 藏青 + 衬线标题)、`classical.css`(宣纸 + 墨色 + 朱砂、小圆角、宋体);与 `default/dark` 共 5 套,29 个 token 完全对齐。
- **token 扩展**:新增 `--font-sans`(正文)与 `--font-display`(标题),`style.css` 的 `body` 与 `h1/h2/h3` 改为引用变量;两套既有主题同步补齐。
- **切换器**:`theme.js` 注册表扩到 5 套,页脚「跟随系统 + 五套」6 个按钮(可换行);`?theme=` 支持全部 key。
- **校验**:`generate.py` 的 `THEME_NAMES` 同步为 5 个;`docs_check.py` 的主题检查改为「themes 下所有 css 逐 token 对齐 + 必须被 theme.js 注册」;新增 `tests/test_pages.py::test_all_theme_files_registered`。
- **验证**:32 个 Python 用例、10 个 node 用例、`--verify`、docs-check 全通过;Chrome 截图检查 tech/campus/classical 首页与页脚切换器,排版正常。

### ✅ 21. 科技风重做 + 二次元主题(D42)(2026-11-26)

- **科技风重做**:首版与深色过于接近 → 改为深空靛蓝底(`#05060d`)+ 青/品红双霓虹 + 细网格底纹 + 4px 近直角 + 卡片霓虹描边/发光 hover,与 `dark` 一眼可辨。
- **二次元主题**:新增 `assets/themes/anime.css`,樱花粉 + 天蓝渐变、18px 大圆角、柔和彩影、圆体标题;`theme.js` 注册为第 6 套,页脚 7 项切换。
- **校验同步**:`generate.py` 的 `THEME_NAMES` 增至 6 个;`tests/test_pages.py` 的主题数量基线改为 6;docs-check 的 token 对齐与注册表检查自动覆盖新文件。
- **文档**:PLAN 追加 10.5(D42),README/GITHUB-PAGES 五套→六套同步。
- **验证**:32 个 Python 用例、10 个 node 用例、`--verify`、docs-check 全通过;截图对比 `tech`/`dark`、`anime`/`classical`,区分明显。

### ✅ 22. 布局 token 化清单落档 + 我的页仅收藏与自定义标题(D43/D44)(2026-11-26)

- **清单落档**:PLAN 追加第十一章,含重复声明冲突表(10 处)、五组布局 token 建议值、哪些进主题/哪些走独立布局维度、实施顺序与验收矩阵、成本风险。
- **我的页内容**:`?view=mine` 只渲染 `localStorage` 收藏,不混入公开主题/条目;修复 `.topic-grid` 等 `display` 覆盖 `[hidden]` 导致公开网格仍然显示的缺陷(新增全局 `[hidden]` 兜底)。
- **自定义标题**:标题旁 ✎ → 行内输入,Enter/失焦保存、Esc 取消(抑制 blur 回写),上限 20 字、留空恢复默认;存 `jiye.mine.title.v1`,同步 `document.title`;新增 `test_pages.py::test_mine_title_hooks`。
- **验证**:33 个 Python 用例、10 个 node 用例、`--verify`、docs-check 通过;截图确认 `?view=mine` 不再出现公开网格。

### ✅ 23. 科技风改为拉勾风格(D45)(2026-11-26)

- `tech.css` 重做为拉勾视觉:浅灰底 + 纯白卡片 + 拉勾绿 `#00b389` + `#e5e6eb` 分隔线 + 8px 圆角 + 轻阴影;间距收紧到 16px,标题回归系统无衬线。
- 与 default(蓝/14px)和 dark(深色)形成三套明确区分;token 仍 29 个且与 default 完全对齐。
- PLAN 追加 10.6(D45);截图对比 tech/default 通过,32 个 Python + 10 个 node 用例、docs-check、`--verify` 全通过。

### ✅ 24. 我的页「设置」:名称 + 我的专属主题(D46)(2026-11-26)

- 我的页头部新增「设置」,面板内可改收藏页名称(复用 `jiye.mine.title.v1`,20 字上限,留空恢复默认)与我的页主题。
- 我的主题存 `jiye.mine.theme.v1`,仅在 `?view=mine` 生效,与公开主题 `jiye.theme` 及页脚切换完全分离;可选跟随公开 / 跟随系统 / 6 套主题。
- 主题下拉由 `JiyeTheme.THEMES` 动态生成;保存时同步标题与浏览器标签,支持取消与 Esc。新增 1 个页面钩子用例,共 34 个 Python 用例 + 10 个 node 用例通过。

### ✅ 25. 我的页 hero:可自定义标题 + 副标题(D47)(2026-11-26)

- 我的页顶部改成与公开首页同构的 hero:大标题 + 副标题 + 收藏数,右上仍是导出/导入/设置,窄屏堆叠。
- 副标题新增 `jiye.mine.subtitle.v1`(60 字上限,留空恢复默认),设置面板新增「页面副标题」行;保存时标题/副标题/主题一并生效,Esc 不落盘。
- 补充页面钩子用例(34 Python + 10 node 全通过),README/PLAN 12.2/WORKLOG 同步。本次只本地提交,不推送。

### ✅ 26. 我的页标题/副标题支持换行(D48)(2026-11-26)

- 标题与副标题编辑控件改为多行 `<textarea>`,上限 40 / 120 字(含换行),支持纵向拖拽调整高度。
- hero 用 `white-space: pre-line` 保留换行;✎ 改为绝对定位到标题右上,避免多行时图标错位;行内编辑 Enter 换行、⌘/Ctrl+Enter 保存。
- `document.title` 自动压成单行;存储键和导出包结构不变。34 Python + 10 node 用例、docs-check 通过;仅本地提交,不推送。

### ✅ 27. 我的页 hero 与公开首页对齐(D49)(2026-11-26)

- 修复标题/副标题间隙过大:根因是 `pre-line` 挂在 `h2` 上把 HTML 缩进保留成空行;改为只作用于 `#mine-title` 文本。
- 标题字号/行高/字距对齐 `.hero h1`(`var(--fs-hero)` / 1.22 / -.8px),副标题对齐 `.hero .sub`(14px 间距、16px/1.65)。
- 与公开首页并排截图验证一致;34 Python + 10 node 用例、docs-check 通过。仅本地提交,不推送。

### ✅ 28. 「我的」入口名称可自定义、不再显示收藏数(D50)(2026-11-26)

- 顶部开关「公开 / 我的」里「我的」只显示名称;新增 `jiye.mine.switch.v1`(默认「我的」,12 字上限,留空恢复)。
- 设置面板新增「「我的」入口名称」;保存后立即刷新开关文本;显隐规则不变,收藏数仍显示在 hero。
- 补充钩子断言(34 Python + 10 node 全通过);README/PLAN 12.5/WORKLOG 同步。仅本地提交,不推送。

### ✅ 29. 「公开」入口名称也可配置(D51)(2026-11-26)

- 顶部开关两个按钮都可改名:「公开」`jiye.mine.public.v1`、「我的」`jiye.mine.switch.v1`,各 12 字上限、留空恢复默认。
- 设置面板新增「「公开」入口名称」;保存后同时刷新两个按钮;静态 HTML 里的「我的 0」也改成「我的」。
- 补充钩子断言;34 Python + 10 node 用例、docs-check 通过。仅本地提交,不推送。

### ✅ 30. 我的页恢复筛选功能(D52)(2026-11-26)

- 我的页新增 `#mine-filter-bar`,复用公开首页 `.filter-bar` 布局:全部/系列合集/单条精选 + 标签 chips + 搜索。
- 类型按收藏所属单元 `type` 判定;标签从单元 `tags` 汇总取前 8;搜索覆盖标题/主题名/作者/备注。
- hero 统计在筛选后显示「筛选出 N / M 条」,空结果显示提示;筛选状态只存内存,不影响收藏数据。用例与 docs-check 通过。仅本地提交,不推送。

### ✅ 31. 合集整卡收藏(D53)(2026-11-26)

- 确认合集此前无收藏入口;首页主题卡片右下角新增 ☆,通过 `Personal.seriesButton(t)` 写入 `key='__series'`、`kind='series'` 的快照。
- 星标放封面右下角避开「合集/单条」标记;「我的」里合集卡链接回 `series.html?id=`,并显示「合集」胶囊。
- 整卡与条目收藏互不覆盖,导出/导入复用现有结构;新增 1 个 node 用例(共 11),34 Python、docs-check 通过。仅本地提交,不推送。

### ✅ 32. B站视频详情页展示分P / 所属合集(D54)(2026-11-26)

- 确认 view 接口可拿到 `pages`(分P)与 `ugc_season`(合集);采集端新增 `bili_parts/bili_season`,`normalize` 按需写入。
- 新增 `--enrich-bili [--id]` 补全老数据(0.35s 节流、失败跳过);已为 `guwen-animation` 10 条视频补齐分P。
- 详情页新增「分P 目录」与「所属合集」:站内已收录的集内链,未收录走 B站外链;无数据不渲染。
- 新增 1 个 node 用例(共 12)与 1 个 Python 用例(共 35),`--verify` 11 单元 0 问题、docs-check 通过。仅本地提交,不推送。

### ✅ 33. 存量数据补全合集并推送(D54 执行,2026-11-26)

- 全量跑 `--enrich-bili`:9 个 B站单元 / 46 条视频,6 个单元有新增,2 条命中合集(53 集、35 集)。
- 详情页实测显示「所属合集 · 鬼畜热点」共 53 集,可滚动;`--verify` 11 单元 0 问题,35 Python + 12 node 用例通过。
- 数据文件与索引一并提交并推送。

### ✅ 34. 重新采集支持追加 / 覆盖(D55)(2026-11-26)

- 新增 `merge_for_mode()` 收口四种采集路径;`replace` 只保留本次结果并报告 `removed`,默认 append 行为不变。
- `/api/collect` 增加 `merge_mode`,仅带 `unit_id` 时允许覆盖;新建误传按追加处理。
- 采集页重新采集时显示「追加 / 覆盖」单选,覆盖非预览需二次确认,退出重采自动复位。
- CLI 增加 `--replace`;新增单测,共 36 Python 用例通过。仅本地提交,不推送。

### ✅ 35. 详情页分集目录移到播放区下方(D56)(2026-11-26)

- `Render.parts()` 改为横向 chip 列表 + 「展开全部」网格;播放器下方新增 `.parts-slot` 挂载,有目录时不再重复页底全集列表。
- `mountPartsPlayer()` 支持点分集/分P 直接改 iframe src 切播,高亮当前集,兜底外链与「正在播放」文案同步。
- `guwen-animation` 12 P 与「鬼畜热点」53 集截图验证滑动/展开/切播;node 12 例、Python 36 例、verify 0 问题、docs-check 通过。

### ✅ 36. 索引按采集时间排序 + 单条采集展开合集(D57)(2026-11-26)

- `unit_sort_key()` + `write_index()` 统一按 `last_at` 降序,新采集排最前;无时间老单元按 updated 兜底。
- `bili_season_records()` 从一次 view 响应的 `ugc_season` 直接生成全集合集记录,单条采集命中合集时自动入库并转为 series。
- 合集目录提升为单元级 `season`(索引不含该字段),每集详情页通过 `opts.season` 兜底展示目录。
- 实测 53 集合集单链采集;补全 `bv1uks66oeeh` 的 21 P;38 Python + 12 node、verify/docs-check 全通过。仅本地提交,不推送。

### ✅ 37. 采集页单元列表分页(D58)(2026-11-26)

- 已有采集单元每页 10 条,底部「第 X / Y 页 · 共 N 个单元」+ 上一页/下一页,首末页禁用。
- 开关/重新采集后保留当前页码;事件随每次渲染重新绑定。
- 修复 `server.py` 缺失的 `unit_page()`,/api/topics 不再 500;新增 1 个 Python 用例。

### ✅ 38. 详情页移动端自适应 + 筛选分组(D59)(2026-11-26)

- 修复网格子项 min-width:auto 导致的播放器横向溢出;窄屏播放区/图文卡片 100% 宽,目录紧跟播放器。
- 首页/我的筛选改为类型、平台、标签分区 + 虚线分隔,搜索独立成行。
- 搜索框改胶囊样式 + 内联放大镜图标 + 聚焦光环;移动端占满整行。
- 类型 chip 清 active 限定在本组,不再误清标签/平台筛选。截图与全部用例通过,仅本地提交。

---

## 新增待办

- [x] **清理旧架构遗留文件**:`topics/*.html`(9 个)与旧根 `assets/data/*.js` 已在 D16 删除;当前 `assets/data/` 仅保留 `index.js` 与 `collections/`。本项关闭(2026-11-26)。

### 遗留问题(2026-11-26 盘点,详见 PLAN 第十五章)

- [ ] **采集服务单线程**:长采集期间页面/其它请求阻塞;改 `ThreadingMixIn` + 写入串行锁。
- [ ] **单元身份标题匹配**:新建采集标题重名会复用旧 id;改为显式 `unit_id` 优先,标题匹配只做兼容回退并提示。
- [ ] **索引/单元双写字段**:`count/enabled/updated` 两处维护;收敛为单元文件单一事实源。
- [ ] **存量 slogan 统一**:9 个单元仍是「点击卡片跳转 B站观看」,批量替换为当前交互文案。
- [ ] **`/api/intake` id 白名单**:非法 id 直接 400,避免路径拼接探测。
- [ ] **`intake.input` 超长截断**:8000 字符以上批量链接回填不完整。
- [ ] **移动端真机复验**:无头仅验证 500px,补 390px 设备模式回归。
- [ ] **推送待办**:本地领先 `origin/main` 5 个功能提交 + 本次文档提交,确认后推送并复查 Pages。
