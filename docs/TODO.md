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

---

## 新增待办

- [ ] **清理旧架构遗留文件**:`topics/*.html`(9 个)与 `assets/data/*.js`(9 个旧根数据文件)已不被任何页面引用,建议确认后删除,减少仓库噪音(删除后可从 git 历史恢复)。
