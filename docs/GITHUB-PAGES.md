# GitHub Pages 托管部署与数据更新说明

本文档说明如何把本项目的**静态展示部分**托管到 GitHub Pages,以及在不改变页面结构的前提下更新采集数据。

---

## 一、方案概述

### 1.1 为什么可以直接托管

本站的三个展示页(`index.html` / `series.html` / `single.html`)满足 GitHub Pages 的全部要求:

- 纯静态 HTML/CSS/JS,无服务端渲染;
- 所有本地资源引用均为**相对路径**(`assets/style.css`、`assets/data/index.js` 等),天然兼容 Pages 的子路径 `/<仓库名>/`;
- 数据文件是 `window.COLLECTION_INDEX = ...` / `window.COLLECTION_DATA["id"] = ...` 形式的 JS 赋值,通过 `<script src>` 加载,不依赖 `fetch`,无跨域问题;
- 视频封面使用 B站 HTTPS 外链,与 Pages 的 HTTPS 环境兼容。

### 1.2 必须明确的边界

GitHub Pages **只提供静态文件托管,不能运行 Python**。因此:

| 能力 | 能否在 Pages 上完成 | 说明 |
|---|---|---|
| 浏览首页、子集合页、单链接页 | ✅ 可以 | Pages 直接托管三个 HTML + 数据文件 |
| 点击「开始采集」 | ❌ 不可以 | 采集依赖 `/api/collect`,Pages 无后端,会返回 HTML 导致 JSON 解析报错 |
| 本地采集后更新数据 | ✅ 可以 | 在本地/NAS/服务器采集,把数据文件提交到仓库即可 |
| 定时自动采集 | ⚠️ 用 GitHub Actions | 见第三章方式 B,需注意 B站接口风控 |

**推荐工作流**:本地或 NAS 运行 `generate.py` 采集 → 提交数据文件 → `git push` → Pages 自动重新部署 → 手机/电脑访问公开链接。

采集交互页 `collector/collect.html` 保留在本地使用即可,**不需要上传到 Pages**(上传了也无法采集,属正常现象)。

---

## 二、首次部署到 GitHub Pages

### 2.1 准备仓库

1. 在 GitHub 新建一个仓库,例如 `tools-resource-collect`,可见性按需选择(公开仓库 Pages 免费;私有仓库需 GitHub Pro/Team 或组织版才能用 Pages)。
2. 把项目文件推送到 `main` 分支。

### 2.2 需要上传的文件

**展示必需**(必须提交):

```
index.html
series.html
single.html
assets/style.css
assets/data-loader.js
assets/data/index.js
assets/data/collections/*.js
```

**采集程序与配置**(建议提交,便于版本管理和在其他机器复用,不参与 Pages 展示):

```
collector/generate.py
collector/server.py
collector/backup_data.py
collector/collect.html
.gitignore
Dockerfile
docker-compose.yml
README.md                 # 根目录唯一文档
docs/DEPLOY.md
docs/GITHUB-PAGES.md
```

**GitHub 配置文件**(项目已内置,一并提交即可,无需手动创建):

```
.gitignore                        # 排除缓存/备份压缩包/迁移遗留文件
.github/workflows/update-data.yml # 定时采集并自动提交数据的 Actions workflow
```

**不要提交**:`__pycache__/`、`*.pyc`、`.DS_Store`、`backups/*.zip`(备份含历史数据,体积大且没必要公开)、旧的 `topics/*.html` 与 `assets/data/*.js`(迁移前的遗留文件,已不被页面引用)。

### 2.3 `.gitignore`(项目已内置)

项目根目录已生成 `.gitignore`,提交仓库即可自动生效,无需手动创建。内容如下:

```gitignore
# Python 缓存
__pycache__/
*.py[cod]
*.egg-info/

# 系统文件
.DS_Store
Thumbs.db

# 备份压缩包(含历史数据,另行保管,不提交到仓库)
backups/
*.zip

# 旧版迁移遗留文件已于 2026-11-26 从仓库删除;保留忽略规则,避免本地残留被误提交
topics/*.html
assets/data/*.js
```

> 提示:旧版 `assets/data/<id>.js` 与新版 `assets/data/collections/<id>.js` 文件名不同。若想忽略旧文件,取消最后两行注释即可——`assets/data/*.js` 只匹配一层,不会误伤新版数据。

确认旧数据已迁移且不再需要后,可取消注释并提交这次改动,让仓库更干净。

### 2.4 开启 Pages

1. 进入仓库 → **Settings** → **Pages**(左侧栏)。
2. **Build and deployment**:
   - Source 选择 **Deploy from a branch**;
   - Branch 选择 `main`,目录选择 `/ (root)`;
   - 点击 **Save**。
3. 等待 1–2 分钟,页面顶部会出现访问地址,形如:

```
https://<你的用户名>.github.io/<仓库名>/
```

### 2.5 子路径兼容性

如果仓库不是用户主页仓库(即地址带 `/<仓库名>/` 后缀),本项目的相对路径写法已天然适配:

- `<script src="assets/data/index.js">` 会解析为 `https://<用户>.github.io/<仓库>/assets/data/index.js`;
- 页面间跳转 `href="index.html"` 也会自动带上仓库前缀;
- `data-loader.js` 中 `assets/data/collections/` 同样是相对路径。

因此**无需配置 `base` 或改任何路径**。

### 2.6 自定义域名(可选)

1. 在仓库根目录新建 `CNAME` 文件,内容只有一行域名,例如 `videos.example.com`。
2. 在域名 DNS 处添加一条 `CNAME` 记录指向 `<用户名>.github.io`。
3. Pages 设置页填入该域名并勾选 **Enforce HTTPS**。

> 注意:`CNAME` 文件必须是纯文本单行,不要带 `https://` 或结尾斜杠。

### 2.7 封面图防盗链处理(建议)

B站 CDN 封面对第三方站点有时会校验 `Referer`,表现为首页卡片无封面图。若遇到此问题,在各页面的 `<head>` 中各加一行:

```html
<meta name="referrer" content="no-referrer">
```

该设置让浏览器请求图片时不带来源页地址,通常即可正常显示。

---

## 三、数据更新

采集产出的数据边界只有两处:

```
assets/data/index.js                 # 索引:单元元信息 + 显示开关
assets/data/collections/<id>.js      # 各单元的视频数据
```

页面代码不随采集变化,无需重复提交。以下按推荐程度列出四种更新方式。

### 3.1 方式 A:本地采集后提交(推荐)

适合大多数个人使用场景,最可控。

```bash
# 1. 采集或重新采集某个单元(--id 保证只更新它)
python3 collector/generate.py "每天挖掘一个神奇网站" --id daily-website --pages 30

# 或按链接采集单条
python3 collector/generate.py '【标题-哔哩哔哩】 https://b23.tv/xxx' --url --id bvxxxxxxx

# 2. 只看本次改动了哪些数据文件
git status --short

# 3. 只提交数据文件
git add assets/data/index.js assets/data/collections/
git commit -m "data: 更新 XXX 采集单元"
git push
```

推送后 Pages 会自动重新部署,约 1–3 分钟后生效。

**关闭某个单元的显示**:

```bash
python3 collector/generate.py --toggle daily-website --off
git add assets/data/index.js assets/data/collections/daily-website.js
git commit -m "data: 关闭 daily-website 显示"
git push
```

数据仍保留在文件中,只是首页不再展示;需要恢复时把 `--off` 换成 `--on` 再提交一次。

**回滚到上一版数据**:

```bash
git log --oneline -- assets/data/          # 找到目标提交
git revert <提交哈希>                       # 生成反向提交
git push
```

或使用备份工具还原后再提交(见 3.5)。

### 3.2 方式 B:GitHub Actions 定时自动采集(无人值守)

适合希望"放着自动更新"的场景。因为 `generate.py` 只用 Python 标准库、无第三方依赖,可直接在 Actions 里运行。

**第一步:打开写权限**

仓库 → **Settings** → **Actions** → **General** → 最下方 **Workflow permissions**,选择 **Read and write permissions** 并保存。不然后续 `git push` 会报 `Permission denied`。

**第二步:确认 workflow 已就位**

项目已内置 `.github/workflows/update-data.yml`,随仓库提交即自动生效。当前配置:

- 定时:每天 **北京时间 07:00**(UTC `0 23 * * *`)跑一次;
- 内容:按仓库根目录 `topics.yml` 的清单逐条采集,默认每个主题搜 10 页;
- 手动:`Run workflow` 时可填 `pages` 覆盖页数;
- 提交:数据有变化才 commit 并 push,提交信息前缀 `data:`。

完整内容以仓库里的实际文件为准(本文件不再重复贴 YAML,避免两处漂移)。本地可先用同一份清单验证解析与抓取:

```bash
python3 collector/generate.py --topics topics.yml --dry-run --pages 1
```

并发由 `concurrency: update-data` 保证,同一时间只跑一个采集任务;本机 launchd 兜底见 `docs/DEPLOY.md` 的「本机 macOS 定时采集」。

**关键注意点**:

| 事项 | 说明 |
|---|---|
| 时区 | workflow 里必须设 `TZ: Asia/Shanghai`,否则视频发布日期会差 8 小时 |
| cron 时区 | GitHub 的 `schedule` 用 UTC;北京时间 = UTC+8,按需换算 |
| 触发延迟 | GitHub 定时触发在高峰期可能延迟数十分钟,且空闲仓库可能暂停定时任务 |
| B站风控 | Actions 使用共享出口 IP,可能偶发限流;失败时先手动运行一次观察日志,或改用方式 A |
| 自动部署 | 用 `GITHUB_TOKEN` 推送的提交**不会**再次触发本 workflow,不会形成死循环 |
| 手动补采 | 在 Actions 页面点 **Run workflow** 可随时手动触发 |

**多主题维护建议**:要增减采集单元,直接编辑仓库根目录的 `topics.yml`(字段 `keyword` / `id` / `title` / `channels`),**不要改 workflow**。`id` 确保续采同一单元,`--pages` 在 workflow 里统一控制页数。改完提交后下次运行即生效。

**改时间**:编辑 `.github/workflows/update-data.yml` 顶部 `schedule` 下的 `cron` 表达式(UTC 时间)。当前 `0 23 * * *` = 北京时间 07:00;常用换算:`0 0 * * *` = 北京时间 08:00,`0 10 * * *` = 北京时间 18:00。

### 3.3 方式 C:NAS / 服务器采集后同步推送

已按 `docs/DEPLOY.md` 在群晖、飞牛或 Linux 服务器部署了采集服务的场景:

```bash
# 在 NAS/服务器上采集(数据写在共享目录)
VIDEO_DATA_DIR=/volume1/docker/video-collect/assets/data \
  python3 collector/generate.py "主题关键词" --id my-unit

# 同步到 GitHub 仓库目录后提交
rsync -av /volume1/docker/video-collect/assets/data/ /path/to/repo/assets/data/
cd /path/to/repo
git add assets/data/ && git commit -m "data: NAS 采集更新" && git push
```

可把上述步骤写成脚本,配合 NAS 的计划任务定时执行,避免在 Actions 里受 B站风控影响。

### 3.4 方式 D:网页手动编辑(应急)

GitHub 网页可直接编辑 `assets/data/*.js` 文件并 commit,适合临时改标题、开关或删除某条数据。但数据文件格式是 JS 对象,手动改容易出错,**仅建议应急使用**。

### 3.5 备份与还原配合

GitHub 的提交历史本身就是一种版本备份,但本地压缩包备份仍建议保留:

```bash
python3 collector/backup_data.py backup                 # 打包 index.js + collections/*.js
python3 collector/backup_data.py list                   # 列出备份
python3 collector/backup_data.py restore backups/data-xxx.zip   # 还原(自动先留当前快照)
```

还原后如需同步到线上,再执行一次 `git add` / `commit` / `push` 即可。备份压缩包不要提交到仓库,请存到本地磁盘或 NAS(`.gitignore` 已排除)。

---

## 四、生效时间与缓存

| 环节 | 典型耗时 | 说明 |
|---|---|---|
| `git push` → Pages 重新部署 | 1–3 分钟 | 可在仓库 Actions 页观察部署状态 |
| 浏览器缓存 | 取决于浏览器 | 数据文件是 `.js`,Pages CDN 有缓存;更新后若仍是旧数据,等待几分钟或强制刷新(`Cmd/Ctrl + Shift + R`) |
| 手机缓存 | 可能更久 | 关闭页面重开,或在浏览器设置里清缓存 |

---

## 五、部署后验证清单

按顺序确认:

1. 访问 `https://<用户>.github.io/<仓库>/`,首页显示主题卡片(有封面、合集/单条标签、期数、日期),顶部主题数为实际单元数;
2. 点任一「合集」卡片,进入 `series.html?id=...`,视频列表按作者分组正常显示;
3. 点任一「单条」卡片,进入 `single.html?id=...`,大图与观看按钮正常;
4. 打开浏览器开发者工具 → Network,确认 `assets/data/index.js` 与 `assets/data/collections/<id>.js` 均返回 **200**;
5. 关闭某单元后推送,确认首页不再显示该卡片,但直接访问其 `series.html?id=...` 仍能看到数据。

---

## 六、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 首页显示「主题数 0」、卡片为空 | `index.js` 用了 `const` 声明,未挂到 `window` | 确认文件头部为 `window.COLLECTION_INDEX = [...]`;用 `python3 collector/generate.py --verify` 自检,必要时按 `.github/workflows/update-data.yml` 手动跑一次采集重建索引 |
| 数据文件 404 | 文件未提交,或大小写/路径不符 | 检查仓库中是否存在 `assets/data/collections/<id>.js`;确认 `.gitignore` 没有误伤 |
| 封面图不显示 | B站 CDN 校验 `Referer` | 各页面 `<head>` 加 `<meta name="referrer" content="no-referrer">`(见 2.7) |
| 点击采集报错 `Unexpected token '<'` | 在 Pages 上访问了 `collect.html`,无后端 | 正常现象;请回到本地/服务器运行 `python3 collector/server.py` 后使用采集页 |
| Actions 推送报 `Permission denied` | Workflow 权限为只读 | Settings → Actions → General → Workflow permissions 改为 Read and write |
| Actions 里日期差 8 小时 | 容器默认 UTC | workflow 的 `env` 加 `TZ: Asia/Shanghai` |
| Actions 采集失败、无结果 | B站接口对共享 IP 限流 | 手动点 Run workflow 重试;仍失败则改用方式 A/C 本地采集 |
| 推送后页面仍是旧数据 | CDN / 浏览器缓存 | 等待 3–5 分钟,强制刷新;确认 Actions 部署成功 |
| 页面样式错乱 | `assets/style.css` 未提交 | 确认该文件已在仓库根目录的 `assets/` 下 |

---

## 七、安全与合规提醒

- 仓库若设为公开,数据文件与页面对所有人可见;采集内容仅为公开视频的标题、链接与封面,不含登录或私有信息。
- 不要把 B站 Cookie、Token 或任何凭据写进仓库或 workflow;本项目采集不需要登录态。
- 定时采集频率建议控制在每天 1–2 次以内,避免对公开接口造成压力。
- 站点只做链接聚合,不托管视频文件,版权归各创作者所有。
