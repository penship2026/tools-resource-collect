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
