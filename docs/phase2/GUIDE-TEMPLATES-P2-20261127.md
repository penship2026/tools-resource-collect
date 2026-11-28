# 二期使用说明书・AI 生成与模板工坊

> 适用版本：v1.13（2026-11-28）
> 适用对象：站点维护者、模板评审人、设计审批人
> 一句话：二期把「AI 生成 → 人工修改 → 预览闸门 → 评审批准 → 上架展示 → 下线回滚」做成一条可审计的本机工作流；AI 始终是可选增强，线上站点仍只读静态文件。



***

## 一、先看全貌

二期有三类页面，都在本机工作台里，不发布到公网：



| 入口       | 地址                                      | 用途                               |
| -------- | --------------------------------------- | -------------------------------- |
| IDE 工作台  | `http://127.0.0.1:8787/`                | 改页面、改版式 / 主题、AI 对话、历史对比、草稿预览、跑闸门 |
| 旧评审页     | `http://127.0.0.1:8787/review`          | 批量生成候选、逐张评审、批准 / 驳回 / 迭代         |
| AI 设计管理处 | `http://127.0.0.1:8787/manage.html`     | 上架 / 下架、展示上限、克隆新版本、下线归档          |
| 二期站点     | `http://127.0.0.1:8787/repo/index.html` | 工作台内嵌的真实站点预览；部署后即普通静态页           |

标准流程：



```
生成候选 → 进入 IDE 修改 → 草稿预览 → 跑 G1–G6
   → 评审页批准（可立即上架）→ 管理处调整展示 → 站点验收
   → 不满意：驳回/迭代；已上线：下架/归档/回滚
```

三个关键边界：



* **候选只落草稿**：`tools/ai-template/drafts/<key>/`，批准前不写 `assets/`、`templates.js`、`theme.js`。

* **AI 不自动保存、不自动批准**：模型只返回 JSON/HTML，必须人工点「应用到编辑器」再点「保存」。

* **所有写操作不自动 git commit**：需要提交时由人另行执行，保持一个模板一个提交。



***

## 二、启动与准备

### 2.1 启动工作台

在项目根目录执行：



```
cd "/Users/liyan/lark/git/github/AI生成项目/tools-resource-collect"
python3 tools/ai-template/cli.py serve --port 8787
```



* 只给本机用：默认监听 `127.0.0.1`，不要加 `--host`。

* 需要同一 Wi-Fi 下手机 / 另一台电脑访问：



```
python3 tools/ai-template/cli.py serve --host 0.0.0.0 --port 8787
```

然后访问 `http://电脑局域网IP:8787/`。工作台**没有登录鉴权**，只建议在可信局域网短时开启，用完 `Ctrl+C` 停止。

端口被占用时，先查进程再换端口：



```
lsof -nP -iTCP:8787 -sTCP:LISTEN
python3 tools/ai-template/cli.py serve --port 8788
```

### 2.2 配置模型（可选）

不配置模型也能用：生成会自动降级 `mock`，可走通链路，但 **mock 产物不能上线**，只能用来验证界面和流程。

真实生成在项目根 `.env` 或 shell 环境里配置：



```
AI_BASE_URL=...
AI_API_KEY=...
AI_MODEL=...
AI_TIMEOUT=60
```

要求是 OpenAI 兼容端点。Key 只在后端读取，不会进入浏览器；工作台模型下拉可切换 `.env` 当前模型、预设端点或本机 Ollama。自定义模型只存在浏览器 `localStorage`，随单次请求发给本机服务。

### 2.3 首次打开检查



1. 左侧资源三 Tab 能显示「页面文件 / 版式 / 主题」。

2. 页面计数当前为 4，版式 / 主题计数以实际设计库为准（当前约 9 / 13）。

3. 点任一页面能加载源码和预览。

4. 点任一 AI 草稿能编辑 `spec.json`；点内置模板显示「只读模板」。

5. 打开 `/review` 能看到候选列表；打开 `/manage.html` 能看到展示清单。



***

## 三、5 分钟快速上手



1. 打开 IDE，左侧选「页面文件」→ `index.html`，中间改一段文案。

2. 点「保存文件」，先经过语法 / 拼接校验；通过后自动备份旧版并写入。

3. 点工具栏「历史」，勾选「当前版本」和任一历史版本，点「对比差异」看增删行。

4. 点某个历史项的「覆盖当前编辑项」，改完后保存；不保存则点「恢复当前编辑项」退回原内容。

5. 左侧切「版式」或「主题」，选一个 AI 草稿，改 JSON 后点「保存新版本」，生成 `candidate-…-eN`。

6. 点「预览」看效果，点「跑闸门」跑 G1–G6。

7. 去 `/review` 填 reviewer，批准并勾选「批准后立即上架」。

8. 去 `/manage.html` 确认展示位；打开 `/repo/index.html` 验收页脚切换器。



***

## 四、IDE 工作台详解

### 4.1 界面结构



```
顶栏：页面/版式/主题三 Tab · 当前资源下拉 · 评审页/管理处/站点 · 新建模板候选
左栏：资源列表 + 搜索 + 刷新 + 跑闸门
中栏：源码 / 分屏 / 预览 · 文件 Tab（HTML、CSS 或 spec.json）· 设备与适屏
右栏：AI 对话 + 模型 + 发送
底栏：当前文件 / 语法状态 / 模型 / 保存状态
```

三栏可拖动分隔条调宽，左右可互换；宽度和顺序会记住。窄屏会纵向堆叠。

### 4.2 页面文件

页面 Tab 固定四个公开页：



| 页面    | HTML          | CSS                       |
| ----- | ------------- | ------------------------- |
| 首页    | `index.html`  | `assets/pages/index.css`  |
| 合集页   | `series.html` | `assets/pages/series.css` |
| 全部内容页 | `list.html`   | `assets/pages/list.css`   |
| 详情页   | `single.html` | `assets/pages/single.css` |



* HTML 与 CSS 都可直接编辑；`源码 / 分屏 / 预览` 三态切换。

* 页面预览读**已保存版本**；保存成功后自动刷新。未保存修改不会出现在页面预览里，按钮是「刷新预览」。

* 页面里的统计、列表、筛选等带 `data-generated` 的区域由脚本重绘；直接改这些 HTML 不会保留，改 CSS 或结构外层更稳。

* 页面模式没有「草稿预览」；模板模式才有。

### 4.3 页面保存与校验

点「保存文件」后，前端先调 `/api/page/validate`，后端保存时再校验一次；失败会弹「保存校验未通过」，**不写盘**。

HTML 检查：



* 必须有 `<!DOCTYPE html>`，`<html>/<head>/<body>` 齐全且各出现一次。

* 标签必须闭合；不允许意外结束标签。

* 已知页面必须引用自己的页面 CSS；`link/script/img/source/iframe/video/audio` 引用的本地文件必须存在。

* 重复 `id`、`<html>` 缺 `lang` 是警告，不阻止保存。

CSS 检查：



* 块注释、字符串、花括号、圆括号必须配对。

* CSS 里混入 `<html>/<head>/<body>/<style>/<script>` 等标签会报错。

* 空文件和单文件超过 512KB 直接拒绝。

常见错误码：



| 错误码                    | 含义                    | 处理                        |
| ---------------------- | --------------------- | ------------------------- |
| `PAGE_HTML_DOCTYPE`    | 缺 DOCTYPE             | 补 `<!DOCTYPE html>`       |
| `PAGE_HTML_STRUCTURE`  | 缺 / 重复 html、head、body | 补齐结构，确保各一个                |
| `PAGE_HTML_UNCLOSED`   | 标签未闭合                 | 按行号补结束标签                  |
| `PAGE_HTML_UNEXPECTED` | 多余的结束标签               | 删掉或补开始标签                  |
| `PAGE_HTML_CSS`        | 缺当前页面 CSS 引用          | 加回对应 `assets/pages/*.css` |
| `PAGE_HTML_REF`        | 引用的本地资源不存在            | 修路径或补文件                   |
| `PAGE_CSS_BRACE`       | 花括号不配对                | 按行号补齐                     |
| `PAGE_CSS_STRING`      | 字符串引号未闭合              | 补引号                       |
| `PAGE_CSS_COMMENT`     | 注释未闭合                 | 补 `*/`                    |
| `PAGE_CSS_HTML`        | CSS 混入 HTML           | 检查拼接 / 复制错误               |

保存成功后，旧文件进入 `backups/pages/<时间戳>/<相对路径>`，同一页面最多保留 20 个历史快照。

### 4.4 页面历史与版本对比

点工具栏「历史」打开弹窗，列表结构是：



```
[复选框] [版本预览按钮] [覆盖当前编辑项]
```



* 首项固定是磁盘上的「当前版本」，也会参与对比，所以既能历史↔历史，也能历史↔当前。

* 历史项默认只读预览：编辑器不可编辑，保存 / AI 应用 / 元素选取被拦截；HTML 历史用旧 HTML + 当前 CSS，CSS 历史用当前 HTML + 旧 CSS。

* 勾选任意两个版本后「对比差异」启用，弹窗显示 `+N 行 / -N 行`、hunk 和增删行。

* 点「覆盖当前编辑项」把历史内容载入编辑器，可继续改；未保存时按钮变「恢复当前编辑项」，一键载回原保存内容。

* 只有**保存成功**才生成新的当前版本，原当前版本进入历史；只覆盖不保存不会改变磁盘。

* 切换页面、切换版式 / 主题时，会清空已载入历史和已勾选对比，避免串资源。

CSS 历史独立于 HTML 历史：在 `index.css` 文件 Tab 打开「历史」，看到的是该 CSS 的备份；对比也按 CSS 文本进行。

### 4.5 版式与主题资源

左侧「版式」「主题」列出全量设计，不限于 AI 草稿。每行显示来源与状态：



* 来源：内置 / AI 草稿 / 已发布 / 已归档。

* 状态：展示中 / 未上架 / 锁定 / N 个候选。

* 内置项：只读，保存按钮显示「只读模板」，AI 改 Spec 会提示先克隆；历史入口不显示。

* AI 草稿：可编辑 `spec.json`，可保存新版本、草稿预览、跑闸门、AI 改 Spec。

* 已发布 AI 模板：可查看 Spec，但修改仍走「克隆新版本」或新候选，不直接改线上 CSS。

打开模板后的文件 Tab：



* `spec.json`：可编辑；JSON 必须合法，状态栏显示 JSON ✓/✗。

* `styles.css`：只读，是 Spec 的编译产物；不要手改。

### 4.6 版式 / 主题保存

点「保存新版本」会先做 Spec Schema 校验，再编译 CSS，然后写入新候选目录：



```
tools/ai-template/drafts/<key>/candidate-...-eN/
```



* **不覆盖旧候选**；旧当前候选自动成为历史。

* 连续保存会出现 `candidate-1-e2-e2` 这类链式后缀，这是当前候选模型的正常结果，历史列表会原样展示。

* 保存成功只代表候选生成成功，**不代表过闸门或已上架**；还要预览、跑闸门、评审批准。

### 4.7 版式 / 主题历史与对比

对可编辑的 AI 候选，点「历史」会列出同一 `key` 下所有候选目录：



* 当前候选第一，标「当前」；其余按修改时间倒序。

* `studio-preview` 临时目录被排除，不会混进历史。

* 不设 20 条上限，保留全部候选。

* 支持只读预览、覆盖当前编辑项、恢复、历史↔当前对比；对比内容是 `spec.json` 文本。

* 历史预览会用 `/api/preview-draft` 实时编译，不会写正式 `assets/`。

* 把历史 Spec 载入编辑器后保存，会再生成一个新候选；旧当前候选仍在历史里。

### 4.8 预览、设备与闸门



* 预览三态：`源码` 只看编辑器，`分屏` 左源码右预览，`预览` 只看页面。

* 设备预设：自适应、iPhone SE、iPhone 14 Pro、Pixel 7、iPad mini 等；也可手填宽高、交换宽高。

* 「适屏」默认开启，按预览容器自动缩放；关闭后按真实像素显示。

* 「选取」开启后，分屏点预览元素可定位到源码行；只用于定位，不修改文件。

* 「自动刷新」默认关闭；开启后源码变更会更新实时预览或草稿预览，但仍未保存。

* 「新标签打开」用独立标签查看当前预览。

* 「跑闸门」跑 G1–G6 和 15 张截图；结果落在候选目录 `metrics.json`。视觉闸门没跑过时不能批准。

### 4.9 右侧 AI 助手

页面模式和模板模式都支持自然语言修改：



1. 在输入框写需求，例如「把首屏大图去掉，改成两列图文，移动端单列」。

2. 点「发送」或 `⌘/Ctrl + Enter`。

3. 模型返回完整结果，不会自动改文件；点「应用到编辑器」才进入源码。

4. 页面模式再点「保存文件」；模板模式再点「保存新版本」。

5. AI 不会自动保存、自动批准、自动上架。

模型下拉来自 `/api/models`；可切 `.env` 当前模型、OpenRouter 预设、本机 Ollama。无 Key 或断网时自动 mock，界面会提示。



***

## 五、生成新候选

### 5.1 两个入口

**IDE 快捷生成**：左侧「＋ 新建模板候选」打开弹窗，填类型（版式 / 主题）、需求、可选约束、候选数量，点「生成」。适合边看现有资源边生成。

**评审页批量生成**：打开 `/review`，顶部填类型、需求、约束、候选数（1–5），点「生成候选」。适合一次出多版对比。

需求写法建议：



* 版式：写清列数、首屏形态、封面比例、密度、移动端要求。例：`两列图文，首屏不用大图，移动端单列，卡片紧凑`。

* 主题：写清主色、背景明度、字体气质、圆角、使用场景。例：`暖纸背景，深墨绿文字，衬线标题，适合长文阅读`。

* 约束只写必要项；约束越多，模型越容易同质化或超预算。

### 5.2 候选目录与命名



```
tools/ai-template/drafts/<key>/
  candidate-1/            # 首次生成
  candidate-1-r1/         # 按意见重新生成（迭代）
  candidate-1-e2/         # 手动保存的新版本
  candidate-2/            # 第 2 个候选
  studio-preview/         # 临时草稿预览，不进历史、不批准
```



* 生成和迭代都不覆盖旧目录。

* 候选之间至少要在 2 个维度上不同（版式：列数 / 封面 / 首屏 / 密度；主题：主色 / 背景 / 字体 / 圆角），否则闸门 G6 会判重复。

### 5.3 评审页

打开 `/review`：



* 顶部填 `reviewer`（审批人），会记到 `reviews/<date>-<key>.json`。

* 每张候选卡可展开 Spec、改 JSON、点「保存手动版本」生成 `-eN`。

* 点「跑预览 / G1–G6」查看指标与截图。

* 「批准发布」必须填 reviewer；可勾选「批准后立即上架并推送到前台」。

* 「驳回」必须选原因：同质化 / 破版 / 观感差 / 不支持该场景。

* 「按意见重新生成」会写 `-rN`，最多 3 轮；超过返回 `REVISE_LIMIT`，转人工设计。

批准不是 “发布候选”，而是**草稿转正式**：写 CSS、`docs/templates/*`、`reviews/*`、`templates.js`/`theme.js`、`published.json`。任一步失败会按备份回滚，草稿保留。

### 5.4 管理处

打开 `/manage.html`：



| 操作      | 说明                                         |
| ------- | ------------------------------------------ |
| 上架 / 下架 | 只改展示清单，不改 CSS / 注册表                        |
| ↑ / ↓   | 调整展示顺序                                     |
| 预览      | 打开该设计预览                                    |
| 下线归档    | 先从展示清单移除，再写 `published.json.archived`；不改文件 |
| 克隆新版本   | 从已发布 AI 模板或内置 Spec 复制新 key 草稿；旧文件不动        |
| 保存上限    | 分别设置版式 / 主题最大上架数（1–20）                     |

规则：



* `standard` 版式、`default` 主题锁定，不可下架，保证本地偏好能回退。

* 展示位满时「上架」禁用，先下架或提高上限；不会静默截断。

* 归档项不能直接重新上架，要克隆新版本再走评审。

* 保存后写 `site.yml` 的 `display.*` 和 `assets/site.js`，不自动 git commit。

### 5.5 站点展示

运行时只读 `assets/site.js`：



* 页脚 / 个人设置只列 `visible_layouts` / `visible_themes`。

* 本地偏好指向已隐藏 / 下线 key 时，回退 `standard` / `default` 并清掉无效值。

* 展示套数 ≤4 时页脚按钮，≥5 时变下拉，避免手机溢出。

* 展示清单为空或字段缺失时，按注册表顺序取前 5 套，保证旧站升级后不空。



***

## 六、命令行（适合批处理 / CI）

所有命令在项目根执行：



```
python3 tools/ai-template/cli.py generate --kind layout --request "两列图文，首屏不用大图" --count 2
python3 tools/ai-template/cli.py validate --spec tools/ai-template/drafts/<key>/candidate-1/spec.json
python3 tools/ai-template/cli.py compile  --spec tools/ai-template/drafts/<key>/candidate-1/spec.json --print
python3 tools/ai-template/cli.py preview   --spec tools/ai-template/drafts/<key>/candidate-1/spec.json
python3 tools/ai-template/cli.py approve   --spec tools/ai-template/drafts/<key>/candidate-1/spec.json --reviewer liyan
python3 tools/ai-template/cli.py reject    --spec tools/ai-template/drafts/<key>/candidate-1/spec.json --reviewer liyan --reason 同质化
python3 tools/ai-template/cli.py revise    --spec tools/ai-template/drafts/<key>/candidate-1/spec.json --comments "首屏太挤，减少一列"
python3 tools/ai-template/cli.py display   --kind layout --key <key> --on
python3 tools/ai-template/cli.py display   --kind theme  --max 6
```

说明：



* `generate` 默认 1 个候选，`--count 1–5`；无 Key 自动 mock，`--mock` 可强制。

* `preview --no-shot` 只跑静态闸门，视觉标记 skipped，**不能据此批准**。

* `approve` 只转正式，不会自动上架；上架用 `display --on`。

* `reject` 原因固定四类；`revise` 超过 3 轮会拒绝。

* 所有命令不自动 git commit。



***

## 七、常见问题



| 现象                   | 原因                               | 处理                                      |
| -------------------- | -------------------------------- | --------------------------------------- |
| 打开工作台还是旧界面 / 新接口 404 | 服务进程没重启，或旧进程仍占端口                 | 用 `lsof -iTCP:8787` 找 PID，停掉后重新 `serve` |
| 页面保存弹「校验未通过」         | HTML/CSS 结构或引用有问题                | 按弹窗错误码和行号修；不要绕过前端直接写文件                  |
| 页面缺 CSS 引用被拒         | 已知页面必须引用自己的 `assets/pages/*.css` | 加回对应 `<link>`                           |
| 模板显示「只读模板」           | 选的是内置模板                          | 去管理处「克隆新版本」，再改草稿                        |
| 保存按钮灰着               | 当前是只读文件、历史预览、或没改内容               | 切回 `spec.json` / 当前编辑版，改一处再保存           |
| 历史里只有「当前版本」          | 该文件 / 候选还没有旧快照                   | 先保存一次，旧版才会进入历史                          |
| 候选名出现 `-e2-e2`       | 连续手动保存叠加后缀                       | 当前候选模型的正常现象；历史会原样展示                     |
| 展示位已满，无法上架           | 达到 `max_layouts` / `max_themes`  | 管理处下架一个，或提高上限（1–20）                     |
| 批准按钮不可用              | 闸门未过 / 没填 reviewer / 指标未 checked | 先「跑闸门」，确认 `metrics.json` 通过，再填 reviewer |
| AI 一直返回 mock         | 没配 `AI_*` 或端点不可达                 | 配 `.env` 后重启服务；mock 只能验证链路，不能上线         |
| 局域网打不开               | 只监听了 127.0.0.1 / 防火墙             | 用 `--host 0.0.0.0`，同 Wi-Fi，检查防火墙        |
| 视觉闸门没跑               | 本机 Chrome/CDP 不可用                | 修好截图环境重跑；标记 “未过视觉闸门” 时不得批准              |

### 常用排查命令



```
# 服务与端口
lsof -nP -iTCP:8787 -sTCP:LISTEN

# 接口是否为新版
curl -s "http://127.0.0.1:8787/api/page/history?path=index.html" | head
curl -s "http://127.0.0.1:8787/api/design/history?path=tools/ai-template/drafts/<key>/candidate-1/spec.json" | head

# 校验一个页面（不会写盘）
curl -s -X POST http://127.0.0.1:8787/api/page/validate \
  -H 'Content-Type: application/json' \
  -d '{"path":"index.html","content":"<html><body>x</body></html>"}'

# 相关测试
python3 -m unittest tests.test_studio -v
python3 -m unittest tests.test_server tests.test_pages tests.test_studio
```



***

## 八、安全与边界



* 工作台和管理处**没有登录鉴权**，只在本机或可信局域网使用；不要直接暴露公网。

* `AI_API_KEY` 只放 `.env`/ 环境变量，不写进页面、不提交仓库；工坊页面不会展示 Key。

* `/repo` 只放行站点页面、`assets/` 和 `tools/ai-template/drafts/`；`.env`、`tools/` 其他文件、文档一律 404。

* 模型输出只当 JSON/HTML 文本解析，不执行模型生成的代码；CSS 由编译器生成。

* 页面单文件 ≤512KB；页面路径有白名单，不能写白名单外文件。

* 批准前运行目录零变化；历史快照只用于恢复，不是正式发布。

* 当前不支持 “完全空白手动新建模板”：从 AI 生成 1 个候选，或从内置 / 已发布模板克隆。

* 内置模板和已发布模板不能直接改线上 CSS；要么克隆新 key，要么新候选走审批。



***

## 九、验收清单



* [ ] `serve` 启动后 `/`、`/review`、`/manage.html` 都能打开。

* [ ] 页面四个 HTML/CSS 都能加载、编辑、保存；保存失败会弹校验明细。

* [ ] 页面历史包含「当前版本」，能历史↔历史、历史↔当前对比。

* [ ] 历史「覆盖」后能改、能保存成新当前版本；不保存能「恢复」。

* [ ] 版式 / 主题 AI 草稿能保存新候选，旧候选进入历史。

* [ ] 模板历史能预览、覆盖、恢复、对比；`studio-preview` 不出现。

* [ ] 内置模板只读，克隆后才能改。

* [ ] 跑闸门能出 G1–G6 和截图结果；未过闸门不能批准。

* [ ] 评审页批准必须填 reviewer；驳回必须选原因。

* [ ] 管理处上下架、上限、锁定、归档、克隆行为正确。

* [ ] 站点页脚只显示展示清单；隐藏后本地偏好回退正常。

* [ ] 无 Key / 断网时一期功能和当前展示不受影响，AI 明确提示 mock。



***

## 十、相关文档



* 设计与接口：`docs/phase2/DESIGN-TEMPLATES-P2-20261127.md`

* 方案与决策：`docs/project/PLAN-TEMPLATES-20261127.md`

* 评审记录：`docs/phase2/REVIEW-TEMPLATES-P2-20261127.md`

* 排期：`docs/phase2/SCHEDULE-TEMPLATES-P2-20261127.md`

* 部署：`docs/ops/DEPLOY.md`