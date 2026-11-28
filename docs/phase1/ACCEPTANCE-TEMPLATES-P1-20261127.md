# 页面模板一期 · 验收记录

- 日期：2026-11-27
- 分支：`feat/templates-p1-20261127`
- 范围：D64–D80，M1–M6
- 环境：macOS，Chrome Headless（CDP，`file://` 直开），Python 3.14，Node 22

## 一、自动化闸门

| 闸门 | 结果 |
|---|---|
| `python3 -m unittest discover -s tests` | 74 例通过 |
| `node tests/test_render.js` | 17 例通过 |
| `node tests/test_layout.js` | 11 例通过 |
| `python3 collector/generate.py --verify` | 单元 12 / 板块 7 / 主题 7，0 问题 |
| `python3 scripts/layout_lint.py` | 通过（4 公开页、脚本顺序、注册表、17 token） |
| `python3 scripts/docs_check.py` | 通过（0 项） |
| CI | `ci.yml` 已接入 Node 视图/版式测试与 `layout_lint` |

## 二、宽度矩阵

用 Chrome CDP 的 `Emulation.setDeviceMetricsOverride` 实测 `document.documentElement.scrollWidth == window.innerWidth`，覆盖 390 / 768 / 1280 三档与 6 个版式页面组合，全部无横向溢出（`bad 0`）：

- 390：index（标准/门户/画册）、series 门户、list 画册、single 画册
- 768：同上 6 组
- 1280：同上 6 组

视觉抽样：`/tmp/shots/m3`（M3 门户与板块）、`/tmp/shots/m4`（M4 画册/置顶/大图/后台）、`/tmp/shots/m5`（M5 390 复核与坏链回退）。截图为本地验证产物，不入库。

## 三、T1–T15

| 项 | 结果 | 证据 |
|---|---|---|
| T1 | 通过 | CDP：启用板块 6，导航 7 项（含「全部」），顺序与 `order` 一致 |
| T2 | 通过 | `?section=k12`：`document.title` =「中小学教育 · 集页」，hero 标题同步 |
| T3 | 通过 | 空板块在导航/板块视图占位；画册只在目录留 0 入口；停用「人文与通识」两处均不出现 |
| T4 | 通过 | `?layout=magazine` 生效且 `localStorage` 仍为 null；手动切换后刷新保留 |
| T5 | 通过 | CDP：切主题后 `data-layout` 不变；切版式后 `data-theme` 不变 |
| T6 | 通过 | 18 个宽度×页面组合 `scrollWidth == innerWidth` |
| T7 | 通过 | 全部截图与 CDP 均用 `file://` 打开，导航/版式正常，无 fetch 依赖 |
| T8 | 通过 | `layout_lint`：4 页无 `<style>`、页级 CSS 无渠道/品牌硬编码 |
| T9 | 通过 | 临时移走 `sections.js`：导航按索引 section 聚合仍可用（4 个有内容板块） |
| T10 | 通过 | 临时在 `list.css` 注入 `color:#123456`，`layout_lint` 退出码 1；恢复后 0 |
| T11 | 通过 | 临时置顶「跟着动画学古文」：门户主位切换；`index.js` 与列表顺序未变；已清除演示配置 |
| T12 | 通过 | 两个置顶按 `pin_at` 倒序，首屏主位仅 1 个，其余进副位/段首 |
| T13 | 通过 | 有效 `hero_image` 用大图；无效 URL 自动回退封面，无破图图标 |
| T14 | 通过 | 默认版式设 `news`：新会话生效；已有 `jiye.layout=standard` 的会话仍为 standard |
| T15 | 通过 | `POST /api/site`：非法 URL 与不存在单元 id 均 400，`site.yml/site.js` 未被改写 |

## 四、已知取舍

- 390 截图仍受旧版 Chrome 最小布局宽影响，视觉判断统一用 500 宽；T6 的 390 结论来自 CDP 设备模拟，不依赖截图。
- 置顶只影响展示顺序，不写 `assets/data/index.js`；列表页/合集页语义不变。
- 画册首页不排空章正文（D79），空章只在目录与板块视图出现。
- `site.js` 缺失时默认版式回退 `standard`；`sections.js` 缺失时导航按索引聚合。

## 五、签收前整改复核（2026-11-27）

针对评审提出的 3 个签收前项与 2 个低优先项，按建议顺序处理并复核：

| 项 | 整改 | 结果 | 证据 |
|---|---|---|---|
| R1 子页面包屑 | `Render.breadcrumb()` 增加尾级参数；`series/list/single` 加载 `sections.js`，用 `Render.sectionMeta()` 取板块名 | 通过 | 三页实测：`全部主题 / 工具与效率 / 主题`；列表页多 `/ 全部内容`；板块链接为 `index.html?section=tools` |
| R2 门户 sidebar 口径 | `news.sidebar` 改为 `false`，README、设计 6.4、决策 D80 同步；窄侧栏明确由头条区 300px 副卡承担 | 通过 | 注册表三版式 `sidebar` 均为 false；无空转能力声明 |
| R3 无障碍 | 四页加「跳到主要内容」+ `#main-content`；`.section-tab` 最小高 44px；首页补视觉隐藏 `h1`，主头条改 `h2` | 通过 | Tab 首站聚焦后 `top=12px`；1280 门户 tab 高 44px；首页 `h1=集页`、hero 为 `H2` |
| R4 规格漂移 / 未用 token | 文档按实拍改为 news 1180 / magazine 960；头条 ≤1080 下移；`--layout-band-cols` 接入门户分节栅格，`--layout-lead-cols` 接入头条主栏 | 通过 | `layout_lint` 17 token 齐全；1280 门户 `814px 300px`，768/390 单栏 |
| R5 回归测试 | 补 breadcrumb/sectionMeta、`SITE_CONFIG.default_layout`、skip link/main、首页标题层级、导航 44px 用例 | 通过 | Python 78 例、视图 19 例、版式 15 例 |

**复核结论**：原「有条件通过」的 3 个签收前问题已闭合，低优先项同步处理；18 组 390/768/1280 页面组合仍 `scrollWidth == innerWidth`，`layout_lint`、`docs_check`、`--verify` 均通过。可提交用户做最终签收确认。

**遗留（不阻塞签收）**：`dump_site_yaml` 的引号转义与 `site.yml`/`site.js` 双文件写入仍未做事务化；独立侧栏能力留待后续版式扩展。

## 六、我的页板块导航修复（2026-11-27）

**现象**：`index.html?view=mine` 下点板块导航，会跳到 `index.html?section=<id>`，丢失 `view=mine`，回到公开首页。

**根因**：`Render.sectionNav()` 固定生成 `index.html?section=<id>`，没有携带当前视图参数；`Personal.mountMineView()` 只按 `view=mine` 判断，导航后自然回到公开态。

**处理**：
- `Render.sectionNav` 新增可选 `view` 参数，我的视图链接统一为 `index.html?view=mine` 与 `index.html?view=mine&section=<id>`；公开链接保持原样。
- 「我的」页按收藏所属板块过滤：优先使用快照 `section`，旧收藏回退索引 `section`；导航计数改为本地收藏数，避免显示公开计数。
- 无收藏的板块给明确空态「该板块还没有收藏。」，统计显示「该板块 N / 共 M 条收藏」。

**验证**：CDP 造 2 条收藏（AI、K12），`?view=mine` 显示 2 条；点 K12 后 URL 保持 `view=mine&section=k12`，面板仍为我的页、显示 1 条；点 AI 显示 1 条；点工具与效率显示空态。Python 79 例、视图 20 例、版式 15 例、`layout_lint`、`docs_check` 通过。

## 七、我的页入口收口与专属导入导出页（2026-11-27）

**目标**：把我的页顶部的导出、导入、设置收进页脚；导入方式（合并/替换）从主页面移走，单独做我的专用导入导出页；我的页脚独立，不含采集入口。

**处理**：
- `index.html` 的 `.mine-tools` 与 `.mine-mode` 移除，我的面板只保留标题、说明、统计、筛选与收藏卡片。
- 新增 `mine-io.html`：导出 JSON、导入 JSON、合并/替换选择、导入前自动备份、状态反馈；数据仍只读本机 `localStorage`，不访问服务器。
- 新增我的独立页脚 `#mine-footer`：只放「导入导出 / 设置 / 回到公开页」，不含采集入口；公开页脚 `#public-footer` 保持原样。
- 我的视图下公开首页的头条/分节/目录/全部标题一并收起，避免公开内容残留在个人页背后。
- 主题/版式切换器只注入公开页脚（`:not(.mine-footer)`），我的页脚不出现这两组切换。

**验证**：CDP 实测 `?view=mine` 顶部无导出/导入/设置按钮，公开页脚隐藏、我的页脚显示且无「采集入口」；页脚设置可打开原设置面板；`mine-io.html` 显示当前收藏数，模拟导入 1 条后计数从 2 变为 3，状态提示成功。Python 81 例、视图 20 例、版式 15 例、`layout_lint`、`docs_check` 通过。

## 八、我的卡片同构与详情视图延续（2026-11-27）

**目标**：我的收藏卡与公开首页主题卡同构，合集卡右上角显示「合集」；从我的页进入合集/单条详情时保留 `view=mine`，面包屑与返回链接能回到我的收藏，而不是公开首页。

**处理**：
- `assets/personal.js` 的 `snapshotCard` 改为复用 `Render.topicCard`，收藏网格改用 `.topic-grid`；单条以 `single` 类型输出「单条」，合集输出「合集」；右下角星标在我的页作为取消收藏。
- 旧 `.fav-card / .fav-thumb / .fav-body / .fav-title / .fav-meta / .fav-note / .fav-act / .fav-del` 样式和删除按钮逻辑下线，避免两套卡片结构并存。
- `Render.detailHref` / `Render.episodes` 增加 `view` 选项；`Render.breadcrumb` 在我的视图输出「我的收藏」及 `index.html?view=mine[&section=id]`。
- `series.html` / `list.html` / `single.html` 读取 `view=mine`，品牌入口、页脚返回改为「返回我的收藏」；合集页的单条卡、全量列表入口、单条页的上下集链接均透传 `&view=mine`。
- 我的收藏卡进入详情时固定带 `&view=mine`；公开详情不带该参数，面包屑仍为「全部主题」。

**验证**：CDP 从 `?view=mine` 点 SpringAI 合集卡，URL 为 `series.html?id=topic-df282732&view=mine`，面包屑「我的收藏 / AI 与智能工具 / SpringAI」，板块链接 `index.html?view=mine&section=ai`；点单条后 URL 与上下集链接继续带 `view=mine`；点板块层回到 `index.html?view=mine&section=ai`，我的面板保持显示。公开 `series.html?id=topic-df282732` 面包屑仍为「全部主题 / …」。Python 83 例、视图 21 例、版式 15 例、`layout_lint`、`docs_check`、`--verify` 均通过。

## 九、筛选条吸顶与默认收缩（2026-11-27）

**目标**：主站与「我的」首页向下滚动时，筛选条件吸顶可用；吸顶后默认收成一行，不长期占用大幅版面，点「展开」恢复完整筛选。

**处理**：
- `.filter-bar` 改为 `position: sticky`，层级低于站点头与板块导航；偏移由 `syncFilterSticky()` 按站点头高度 + 导航实际高度写入 `--layout-filter-top`，窗口尺寸变化时重算。
- 两个筛选条各加一行「筛选条件 / 展开」按钮；进入吸顶时自动加 `is-stuck` 与 `is-collapsed`，只显示这一行；点按钮展开，按钮文案变「收起」；离开吸顶自动恢复完整筛选并复位。
- 简洁版式与 ≤600px 窄屏的导航本身不吸顶，偏移自动只算站点头；画册版式筛选条补 `var(--bg)` 不透明底色，避免滚动内容穿透。
- 展开状态在吸顶期间保持，不因继续滚动再次自动收起；重新进入吸顶时回到默认收缩。

**验证**：CDP 在简洁/门户/我的页滚动验证：简洁主站筛选条停在站点头下 61px，门户与我的页停在导航下 122px；吸顶时高度由 270/217/164px 收至 50px，分组 `display:none`；点「展开」恢复完整高度并显示「收起」，回滚到顶部恢复完整筛选。已用 1280 宽截图复核吸顶收缩态。Python 84 例、视图 21 例、版式 15 例、`layout_lint`、`docs_check`、`--verify` 通过。

## 十、我的导入导出页发布白名单修复（2026-11-27）

**现象**：本地访问 `mine-io.html` 返回 `{"ok": false, "error": "未对外开放的路径"}`；部署到 GitHub Pages 时该页也不在发布产物中，线上会 404。

**根因**：`mine-io.html` 是在「我的」入口收口时新增的页面，但两处白名单仍停留在旧页面清单：
- `collector/server.py` 的 `STATIC_EXACT` 只有 `/index.html`、`/series.html`、`/list.html`、`/single.html` 和采集页；
- `.github/workflows/pages.yml` 生成 artifact 时只 `cp` 了四个展示页。

**处理**：
- 本地静态白名单加入 `/mine-io.html`，404 提示同步改为「展示页、我的导入导出页与 assets/」。
- Pages artifact 清单加入 `mine-io.html`；`assets/pages/mine-io.css` 已在 `assets/**` 内，无需单独放行。
- `docs/ops/GITHUB-PAGES.md`、`docs/ops/DEPLOY.md`、README 页面清单同步。

**验证**：本地 `python3 collector/server.py --port 18087` 实测 `/mine-io.html` 返回 200、`/collector/settings.html` 仍返回 200（本机白名单内）；Python 85 例、视图 21 例、版式 15 例、`layout_lint`、`docs_check`、`--verify` 通过。线上需等 Pages 重新部署后访问确认。

## 十一、重新采集支持移除当前链接（2026-11-27）

**目标**：重新采集时，按链接/批量链接输入框里的链接也可以表示「要移除的条目」，不必为删一条内容单独改数据文件；按主题采集没有明确单条链接，不提供移除。

**处理**：
- 采集方式增加第三项「移除当前链接」（`merge_mode=remove`），只在按链接/批量链接显示；切到按主题采集时自动回到「追加」。
- 前端提交前二次确认，并显示「已移除 N 条，剩余 M 条」；预览模式下只报告将移除数量，不写文件。
- 后端新增 `generate.remove_links()`：按 B站 BV、公众号文章短链末段、小红书笔记 ID、原文地址做本地匹配；只删除匹配条目，不重新抓取内容，不改原 `intake`，另记一条 `runs` 移除记录。
- 主题采集或未指定单元时直接返回明确错误；没有匹配项时提示核对链接，不误删。

**验证**：Python 用例覆盖单链接移除、批量移除、主题采集拒绝；临时数据目录实测 `POST /api/collect` 返回 `removed=1, total=1`，数据文件 `count` 与 `latest` 同步，原 `intake` 保留。

## 十二、主站页脚与采集单元体验收口（2026-11-27）

**目标**：主站页脚只承担版权说明，不再重复采集与导入导出入口；采集单元列表缩短默认分页、可直接搜索，单条操作不再挤在右侧竖排，说明文字与采集页面板字体统一。

**处理**：
- `index.html` 的 `#public-footer` 只保留版权说明，删除「采集入口」链接与「导出备份 / 导入恢复」提示；个人页脚 `#mine-footer` 保持「导入导出 / 设置 / 回到公开页」不变。
- `collector/collect.html` 的 `UNIT_PAGE_SIZE` 由 10 改为 5；新增 `#unit-search`、清除按钮与计数，按标题、ID、作者、平台、关键词、页面做本地多词匹配，过滤后重置到第 1 页并重算分页，不发新请求。
- `.unit-row .topic-item` 改为 `display:block`，`.topic-actions` 改为底部横排换行；「显示中 / 置顶 / 画册大图 / 重新采集」落在信息文本下方一排。
- 说明段改为 `.unit-note` 三段粗体导语，字号 `--fs-xs`、行距 1.85，顶部虚线分隔，与采集页面板的 12–13px 辅助文字一致。

**验证**：Python 91 例通过（新增页脚与采集单元契约 3 项）；Node 版式 27 例、视图 21 例通过。CDP 1280 宽复核：主站页脚仅版权与主题/版式切换；采集单元 6 条数据首屏 5 条、分页「第 1 / 2 页」；搜索「前端」显示「匹配 1 / 共 6 个」且只剩「前端周刊」；说明三段行距与面板字体一致。

## 十三、「我的」页专属版式设置（2026-11-27）

**目标**：个人页设置面板可以单独选择版式，不再只能跟随公开页脚；选择结果只影响 `?view=mine` 的个人视图，公开页保持自己的版式。

**处理**：
- 设置面板新增「我的版式」下拉：跟随公开版式 / 简洁 / 门户 / 画册，选项由 `JiyeLayout.list()` 动态生成，新增版式只需注册表加一行。
- `assets/layout.js` 新增 `jiye.mine.layout.v1` 与 `mineChoice` / `setMineChoice`；解析优先级为 `?layout` 预览 > 我的版式（仅 `?view=mine`）> `jiye.layout` > `site.yml default_layout` > `standard`。
- 选「跟随公开版式」删除本键并回落到公开版式；保存时清掉 `?layout` 预览参数，避免刷新被预览值覆盖；公开页不读取本键。

**验证**：Node 版式用例新增 6 组（我的优先、跟随公开、公开页忽略、保存/删除、预览覆盖），27 例通过；CDP 写入 `jiye.mine.layout.v1=magazine` 后刷新，`data-layout=magazine`、`layout-css=assets/layouts/magazine.css`，设置下拉显示「画册」；Python 91 例通过。

## 十四、顶部统计条统一与版式适配（2026-11-27）

**目标**：首页 hero 的统计数字、来源渠道与最近更新时间不再是默认小字堆叠；合集/列表子页顶部统计也复用同一套语言，并随简洁/门户/画册三套版式切换对齐方式、线宽与宽度。

**处理**：
- 首页、`series.html`、`list.html` 的 `.facts` 统一加 `facts-hero`；日期类字段（最近更新 / 最新发布 / 最近采集 / 时间跨度）加 `fact-date`，数字保持主字号，日期降一档。
- 共用样式移入 `assets/style.css`：`facts-hero` 顶部细线、竖向分隔、`width: fit-content` 且 `min-width: 540px`，数字用 `clamp(21px, 2.2vw, 25px)`，日期用 `clamp(17px, 1.6vw, 19px)`；新增 `--layout-facts-pad` 控制列间距。
- 版式适配：门户改为 2px 品牌色顶线、620px 基线；画册居中并保持 540px 基线；窄屏（≤600px）取消竖分隔、允许换行，数字/日期分别降到 20/16px。
- 合集与列表四项统计在 1280px 下保持单行，时间跨度不再掉到下一行；列表页统计条与筛选栏的间距沿用原有布局。

**验证**：Python 92 例通过（新增统计条跨页契约 1 项）；Node 版式 27 例、视图 21 例通过。CDP 1280 宽无缓存复核：首页简洁/门户/画册分别为左对齐 1px 线、品牌色 2px 线 620px、居中 540px；`series.html` 与 `list.html` 四项统计单行显示，时间跨度完整；日期字号小于数字，窄屏断点规则已写入。
