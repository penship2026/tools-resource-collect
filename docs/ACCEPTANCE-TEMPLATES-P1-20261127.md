# 页面模板一期 · 验收记录

- 日期：2026-11-27
- 分支：`feat/templates-p1-20261127`
- 范围：D64–D79，M1–M5
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
