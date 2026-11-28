# 部署文档

本项目由两部分组成：

- **静态页面 + 数据**：`index.html`（首页）、`series.html`（子集合页）、`list.html`（全部内容页）、`single.html`（站内详情页）、`mine-io.html`（我的导入导出页）、`collector/collect.html`（采集页），加样式与 `assets/data/`。页面是固定模板，浏览器直接打开即可；采集只写数据，不生成、不修改任何页面。
- **采集程序**：`collector/generate.py`（命令行，纯规则采集）与 `collector/server.py`（本机采集台，提供表单与 `/api/*`）。

## 部署形态：先选 A 还是 B（2026-11-26 起）

采集必须由一个真实进程执行——浏览器无法直接跨域抓取平台数据。但从 2026-11-26 起有两种形态：

| 形态 | 组成 | 适用 | 是否常驻 |
|---|---|---|---|
| **A. 静态站 + 定时任务（推荐）** | 展示端：纯静态托管（GitHub Pages / Nginx / 群晖 Web / 对象存储）；采集端：GitHub Actions（每天 07:00）+ 本机 launchd（08:10 兜底） | 日常无人值守更新 | **否**，任务跑完即退出 |
| **B. 本机采集台（可选）** | 本机运行 `python3 collector/server.py`（默认只听 `127.0.0.1`），用网页表单采集 | 临时补采、手工补录、核对结果 | 是，但只在本机 |

**两种形态可以并存**：展示端始终是纯静态；`server.py` 只在需要交互采集时临时启动，不对外暴露。若你确实要让 `server.py` 直接对外提供站点（旧做法），**必须**加口令启动（见「安全基线」）。形态 A 的定时任务配置见 `docs/ops/GITHUB-PAGES.md` 3.2 与本文第十章。

---

## 一、部署前须知（三点必看）

| 项目 | 要求 | 说明 |
|---|---|---|
| Python | 3.8+ | 仅用标准库，无需 `pip install` 任何依赖 |
| 出站网络 | 能访问 `api.bilibili.com` | 采集时要请求 B站公开搜索接口；服务器/NAS 需能出网 |
| 可写目录 | `assets/data/`、`assets/data/collections/` | 采集只写这两个数据目录（索引 + 各采集单元），运行用户必须对其有写权限；页面目录无需写权限 |

**时区（重要）**：`generate.py` 用 `datetime.fromtimestamp()` 按**系统本地时区**格式化发布日期。若服务器/容器是 UTC 时区，日期会显示成北京时间的前一天。部署务必设为东八区：

- Linux 裸机：`timedatectl set-timezone Asia/Shanghai`
- Docker：镜像已内置 `TZ=Asia/Shanghai` 和 tzdata（见 `Dockerfile`），无需额外处理

**端口**：默认 `8765`。可通过命令行参数 `python3 collector/server.py 8080` 或环境变量 `PORT=8080 python3 collector/server.py` 修改。群晖 DSM（5000/5001）、飞牛默认管理端口均不冲突，一般保持 8765 即可。

### 安全基线（2026-11-26 起，务必遵守）

- **默认只监听本机**：直接运行 `python3 collector/server.py` 时绑定 `127.0.0.1:8765`，只有本机能访问，适合日常采集。
- **局域网临时访问**：手机与电脑在同一 Wi-Fi 时，用 `python3 collector/server.py --lan` 绑定 `0.0.0.0`，访问 `http://电脑局域网IP:8765/collector/settings.html`。该模式不要求口令，会把采集和设置接口暴露给同网段设备，只建议在可信网络临时使用；设置页 Origin 白名单已覆盖内网 IP 与 `.local` 主机名。
- **静态托管有白名单**：只放行 5 个展示页、采集页与 `assets/`；`/.git`、`backups/`、`docs/`、`*.py`、`.github` 等一律返回 404。
- **对外访问必须加口令**：需要从公网/其它网络访问时用
  `python3 collector/server.py --public --token <口令>`（或设置环境变量 `COLLECT_TOKEN`）。
  `--public` 会绑定 `0.0.0.0`，所有采集写接口（采集 / 改标题 / 下线 / 切换）都必须带请求头 `X-Collect-Token`，否则返回 401；采集页顶部填一次口令即存在本机 localStorage。
- **反代场景同样加口令**：即使由 Nginx 转发到本机，只要该域名能从公网访问，就应按 `--public --token` 启动，否则任何拿到地址的人都能改站点数据、触发采集。
- **部署后自检**：
  ```bash
  curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/.git/config   # 期望 404
  curl -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/backups/      # 期望 404
  curl -s http://127.0.0.1:8765/api/health                                  # index_ok 应为 true
  ```

---

## 二、方式一：普通 Linux 服务器（systemd + Nginx 反代）

假设项目放在 `/opt/video-collect`，以 `www` 用户运行。

### 1. 上传代码

```bash
sudo mkdir -p /opt/video-collect
# 把项目文件上传到该目录（保留 assets/ 及其 data/collections 结构）
cd /opt/video-collect
sudo chown -R www:www .
sudo timedatectl set-timezone Asia/Shanghai   # 确认东八区
```

### 2. 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/video-collect.service > /dev/null <<'EOF'
[Unit]
Description=Video Collect Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www
Group=www
WorkingDirectory=/opt/video-collect
Environment=TZ=Asia/Shanghai
ExecStart=/usr/bin/python3 /opt/video-collect/collector/server.py 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now video-collect
sudo systemctl status video-collect    # 确认 active (running)
```

> `ExecStart` 里的 python 路径用 `which python3` 查实际位置；版本需 3.8+。

### 3. Nginx 反向代理（可选，用域名/80/443 访问时需要）

```nginx
server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;   # 采集耗时可能较长
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

关键点：**`location /` 整体转发给 Python**，不要另配 `root` 托管静态文件，否则 `/api/` 又会被静态服务器拦截。若部署在子路径（如 `/app/`），`proxy_pass http://127.0.0.1:8765/;` 配合 `location /app/ { ... }`，接口路径支持任意前缀。

### 4. 防火墙

放行 8765（若走 Nginx 则放行 80/443），云服务器还需在安全组开放。

---

## 三、方式二：群晖 NAS（Synology DSM）

群晖推荐用 Docker 部署，环境隔离、开机自启都省心。DSM 7.x 用「Container Manager（容器管理器）」，DSM 6.x 用「Docker」套件。

### 准备共享文件夹

在 File Station 新建共享文件夹，例如 `docker/video-collect`，把项目文件上传进去，最终目录结构：

```
/docker/video-collect/
├── Dockerfile
├── docker-compose.yml
├── README.md
├── index.html / series.html / list.html / single.html / mine-io.html   # 固定展示页与我的导入导出页
├── assets/      # 含 data/ 与 data/collections/
├── collector/   # 采集管理代码
│   ├── server.py
│   ├── generate.py
│   ├── backup_data.py
│   └── collect.html
└── docs/        # 文档索引、阶段归档与部署文档
```

### 方法 A：图形界面「项目」（推荐，DSM 7.x）

1. 打开 **Container Manager → 项目 → 新增**。
2. 项目名填 `video-collect`，路径选择刚上传的 `docker/video-collect` 文件夹。
3. 来源选择 **使用现有的 docker-compose.yml**（或在编辑框粘贴本仓库 `docker-compose.yml` 的内容）。
4. 勾选「启动项目」。容器会按 `Dockerfile` 自动构建并运行。
5. 浏览器访问 `http://群晖IP:8765/collect.html`。

> 若 DSM 6.x 没有「项目」功能：用 Docker 套件 → 映像 → 新增 → 从 Dockerfile 构建，选中项目文件夹构建镜像；再「启动」容器，本地端口 8765、容器端口 8765，并挂载 `assets/data` 目录（采集单元数据都在其中）。

### 方法 B：SSH 命令行（更灵活）

```bash
# SSH 登录群晖后
cd /volume1/docker/video-collect     # 路径按实际卷号调整
sudo docker compose up -d --build
sudo docker compose ps              # 确认状态 Up
sudo docker compose logs -f         # 查看日志
```

### 群晖反向代理 /  HTTPS（可选）

控制面板 → 登录门户 → 高级 → **反向代理服务器 → 新增**：

- 来源：协议 HTTPS，主机名 `your.domain.com`，端口 443
- 目的地：协议 HTTP，主机名 `localhost`，端口 `8765`

之后也可用群晖自带的 Let's Encrypt 证书给域名签 HTTPS。若不需要域名/HTTPS，直接用 `http://群晖IP:8765` 访问即可，跳过此步。

### 权限注意

群晖上容器默认以 root 运行，通常可写。若你改用非 root 用户运行，需确保 `assets/data` 对运行用户可写（File Station 里调整权限，或 SSH `chmod`）。

---

## 四、方式三：飞牛 NAS（fnOS）

飞牛 NAS 内置 Docker 管理，同样用 `docker-compose.yml` 部署。

### 1. 上传项目文件

在飞牛文件管理器里新建文件夹（如 `Docker/video-collect`），把项目全部文件上传，保留 `assets/`（含 `data/collections`）结构。记下该文件夹的**实际路径**（SSH 下通常是 `/vol1/1000/Docker/video-collect` 之类，以实际为准）。

### 2. 用 Compose 启动

飞牛提供两种方式，任选其一：

- **图形界面**：打开「Docker」应用 → Compose / 项目 → 新建项目 → 项目路径选刚上传的文件夹 → 使用 `docker-compose.yml` → 启动。
- **SSH 命令行**：

  ```bash
  cd /vol1/1000/Docker/video-collect   # 路径按实际调整
  sudo docker compose up -d --build
  sudo docker compose ps
  ```

### 3. 访问

浏览器打开 `http://飞牛IP:8765/collect.html`。若 8765 被占用，改 `docker-compose.yml` 里的 `"8765:8765"` 为 `"其他端口:8765"`（冒号左边是外部访问端口）。

### 4. 域名 / HTTPS（可选）

飞牛若提供反向代理功能，配置来源域名 → 目的地 `http://127.0.0.1:8765`；否则直接用 IP + 端口访问，或在路由器做端口转发。

---

## 五、Docker 通用说明（三种平台通用）

### `Dockerfile` 做了什么

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
EXPOSE 8765
# 采集代码在 collector/,server.py 自动把项目根 /app 作为静态托管根目录
CMD ["python3", "collector/server.py", "8765"]
```

- 无需 `pip install`：程序只用 Python 标准库。
- `TZ=Asia/Shanghai` + tzdata：解决发布日期差 8 小时的问题。

### `docker-compose.yml` 关键点

```yaml
services:
  video-collect:
    build: .
    container_name: video-collect
    ports:
      - "8765:8765"
    volumes:
      - ./assets/data:/app/assets/data   # 索引 + 各采集单元数据(含 collections/)
      - ./backups:/app/backups           # 备份压缩包
    environment:
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
      # 仅跑采集端时加:- SERVER_ROLE=api
    restart: unless-stopped             # 开机自启、崩溃重启
```

- **数据卷必须保留**：采集只写容器内 `/app/assets/data`（索引 + `collections/` 各单元），挂载到宿主机后，重建/升级容器数据也不丢。各展示页是固定模板，随代码部署，不需挂载。
- `restart: unless-stopped`：NAS/服务器重启后自动拉起服务。

### 常用运维命令

```bash
docker compose up -d --build   # 构建并启动（改了代码后重新构建）
docker compose restart         # 重启
docker compose down            # 停止并删除容器（数据卷不受影响）
docker compose logs -f         # 实时日志
docker compose ps              # 查看状态
```

---

## 六、采集端与展示端分离部署（可选）

展示端是纯静态文件，不依赖 Python；采集端才需要 Python 进程。两者可各跑各的服务、共享同一份数据目录，这样采集服务能单独启停、展示站能单独做缓存或 CDN。

### 架构与数据边界

- **采集端**：`server.py`（采集专用模式）+ `generate.py` + `collect.html`，提供 `/api/*` 和采集页；只写数据，不碰页面。
- **展示端**：`index.html` / `series.html` / `list.html` / `single.html` / `mine-io.html` 固定页面 + `assets/`，由任意静态 Web 服务器托管（Nginx / 群晖 Web Station / 飞牛静态站点）。页面是固定模板，样式各自独立维护。
- **共享数据目录**（唯一耦合点）：`assets/data/index.js`（索引 + 显示开关）与 `assets/data/collections/*.js`（各采集单元）。采集端写入，展示端读取。

### 1. 启动采集端（专用模式）

```bash
python3 collector/server.py 8765 --api-only
# 或:SERVER_ROLE=api python3 collector/server.py 8765
```

该模式只放行 `/api/*` 和 `collect.html`（含样式表），访问展示页会返回 JSON 提示而非静态页。自检 `/api/health` 会额外返回 `role: "api"` 以及数据目录、采集单元目录各自的可写状态。

### 2. 启动展示端（纯静态）

用任意静态服务器托管展示文件即可，例如 Nginx：

```nginx
server {
    listen 80;
    server_name site.example.com;
    root /opt/video-collect;          # 指向项目目录
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
```

展示端**不需要** Python，也没有 `/api/*`（采集入口链接可指向采集端地址）。

### 3. 共享数据目录

- 同机/同容器部署：两端默认就是同一份目录，无需任何改动。
- 自定义位置：两端用相同的环境变量指向共享卷，路径即一致：

  ```bash
  export VIDEO_DATA_DIR=/srv/share/assets/data
  # 采集端以此变量启动;展示端静态站点的 assets/data 指向同一位置
  ```

  相对路径按程序所在目录解析，绝对路径直接使用。各展示页仍用相对路径引用数据，**加载方式不变**。
- Linux 权限：采集端运行用户对数据目录需有写权限，展示端至少可读。
- Docker 场景：`docker-compose.yml` 已把 `assets/data` 挂载为卷，采集容器和展示容器挂载同一个宿主机目录即可共享。

> 不带 `--api-only` 时仍是全功能模式（静态+接口），前面所有部署方式完全兼容。

---

## 七、部署后自检清单

按顺序确认，任一步失败按第七节排查：

1. **健康接口**：浏览器打开 `http://<地址>/api/health`，应返回 JSON `{"ok": true, "writable": true}`。
   - `writable` 必须为 `true`，否则采集写不了文件。
   - 若返回一段 HTML（`<!DOCTYPE ...`），说明请求被静态托管/网关拦截，没转发到 Python。
2. **单元接口**：`/api/topics` 返回 JSON，且 `topics` 数组里有已收录采集单元（含 id/type/enabled）。
3. **采集页**：`/collect.html` 顶部显示「后端已连接」绿标；右侧列出各单元并可切换显示。
4. **展示页**：`/index.html` 显示主题卡片和封面；`/series.html?id=<单元ID>` 显示合集；`/single.html?id=<单元ID>` 显示单条视频。
5. **实采一条**：在采集页采一条数据，确认首页刷新后出现新单元；再试「重采此单元」与开关显示。
6. **手机验证**：手机连同一网络访问首页，确认采集后刷新能看到更新（服务已设 `no-store`，正常不会缓存旧数据）。

---

## 八、常见故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| 点采集报 `Unexpected token '<' ... is not valid JSON` | `/api/collect` 被静态服务器接走返回 HTML | 确保请求全部转发到 `server.py`；反代用 `location /` 整体转发，不要单独 `root` 托管静态 |
| 手机访问报「接口返回的不是 JSON(HTTP 404)」 | 手机访问的是静态托管地址，不是 `server.py` 服务地址 | 改用运行 `server.py` 的那台机器的 IP:端口；确认 `/api/` 未被拦截 |
| `/api/health` 里 `writable: false` | 运行用户对 `assets/data` 或其 `collections/` 无写权限 | Linux `chown`/`chmod`；群晖/飞牛检查共享文件夹权限；Docker 确认挂载卷权限 |
| 视频日期显示成前一天 | 系统/容器时区是 UTC | Linux `timedatectl set-timezone Asia/Shanghai`；Docker 确认用了内置 `TZ` 的镜像并挂载正确 |
| 采集后手机首页还是旧数据 | 浏览器缓存了 `index.js` | 服务已加 `no-store`，强制刷新（Ctrl/Cmd+F5）或清缓存；确认访问的是 `server.py` 服务 |
| 端口启动失败 `Address already in use` | 端口被占用或旧进程未释放 | 换端口，或停掉旧进程后稍等再启动 |
| 采集超时 / 找不到视频 | B站 搜索接口偶发限流或关键词过于精准 | 稍后重试；精准匹配要求标题完整包含关键词，必要时换词（详见 README 采集规则） |

---

## 九、更新代码与数据备份

**更新程序**：上传新的 `server.py`/`generate.py`/`Dockerfile` 后重启服务。

- systemd：`sudo systemctl restart video-collect`
- Docker：`docker compose up -d --build`

**备份数据**：采集产出只有 `assets/data/index.js`（索引 + 显示开关）和 `assets/data/collections/*.js`（各采集单元）。各展示页和程序不随采集变化，随代码版本管理，无需备份。用内置工具（纯标准库，无需安装依赖）：

```bash
python3 collector/backup_data.py backup                  # 打包到 backups/data-<时间戳>.zip
python3 collector/backup_data.py list                    # 列出备份
python3 collector/backup_data.py restore backups/data-xxx.zip            # 还原（自动先留当前快照）
python3 collector/backup_data.py restore backups/data-xxx.zip --yes      # 跳过确认
python3 collector/backup_data.py backup --out /mnt/nas/backup            # 备份到外部目录
```

- 还原只解包 `.js` / `.html`，拒绝 `..` 路径穿越；默认还原前自动留存当前数据快照，可回退。
- 环境变量 `VIDEO_DATA_DIR` / `VIDEO_BACKUP_DIR` 可覆盖路径，适配分离部署的共享目录。
- 定时备份：配合 cron 或 NAS 计划任务，先 `cd` 到项目目录再执行 `backup`，并把 `VIDEO_BACKUP_DIR` 指向 NAS 共享文件夹。
- 旧版 `topics/*.html` 与根目录 `assets/data/*.js` 已于 2026-11-26 删除并完成迁移,`--migrate` 与 `LEGACY_DIR` 等遗留代码同批移除（需要旧文件时从 git 历史恢复）。还原历史数据后先执行 `--verify` 并访问 `/api/topics` 确认单元数正确、首页封面正常。

**升级不丢数据**：Docker 场景因已挂载 `assets/data`，`down` 再 `up` 数据仍在；直接覆盖代码文件重启亦可。

---

## 十、本机 macOS 定时采集（launchd，形态 A 的兜底）

> **当前状态（2026-11-26）**：本机 launchd 任务已按要求**暂停**——已从 `gui/501` 卸载并 `disable`，下次登录不会自动恢复。需要重启时执行：
>
> ```bash
> launchctl enable gui/$UID/com.jiye.collect
> launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.jiye.collect.plist
> ```
>
> plist 文件仍保留在 `~/Library/LaunchAgents/com.jiye.collect.plist`，无需重新生成。

GitHub Actions 是主力调度（每天 07:00），本机 launchd 作为兜底（默认 08:10），两者**错开时间、不要同时跑**——它们写同一份 `assets/data`，约定「先提交者为准」。

### 1. 安装

```bash
./scripts/launchd/install.sh            # 只生成 ~/Library/LaunchAgents/com.jiye.collect.plist,不装载
./scripts/launchd/install.sh --load     # 生成并装载(默认每天 08:10)
```

安装脚本会校验 plist 格式并打印后续命令；也可以用参数改时间：

```bash
./scripts/launchd/install.sh --hour 9 --minute 0 --load
```

### 2. 试跑与查看

```bash
launchctl kickstart -k gui/$UID/com.jiye.collect     # 立即跑一次(会真实采集)
launchctl print gui/$UID/com.jiye.collect | head -20 # 查看状态与下次执行
tail -f logs/launchd.out.log                          # 采集输出(与 launchd.err.log 同目录)
```

### 3. 行为说明

| 项 | 说明 |
|---|---|
| 采集范围 | 仓库根 `topics.yml`；若存在 `topics.local.yml`（未公开主题，已 gitignore）会一并采集 |
| 页数 | 脚本默认 `PAGES=10`，可在 `scripts/launchd/collect.sh` 改默认值或改 plist 环境变量 |
| 是否提交 | 默认**只采集不提交**；设 `AUTO_PUSH=1` 才会 `git pull --rebase` → commit → push，需要本机 git 凭据（SSH key 或 credential helper） |
| 日志 | `logs/launchd.out.log`、`logs/launchd.err.log`，`logs/` 已加入 `.gitignore` |

### 4. 卸载

```bash
./scripts/launchd/install.sh --uninstall
```

### 5. 常见问题

- **提示无法访问项目目录**：macOS 对后台任务有隐私限制，到「系统设置 → 隐私与安全性 → 完全磁盘访问权限」把 `/bin/bash` 或终端加入；或把仓库放到用户目录下（本项目即在用户目录，一般无需额外授权）。
- **找不到 python3**：脚本已把 `/opt/homebrew/bin`、`/usr/local/bin` 加入 PATH；若用 pyenv/conda，请在 `collect.sh` 里改成绝对路径。
- **每天没变化**：属于正常——采集无新增时不会写盘，日志里会显示「数据无变化」。

## 十一、访问地址速查

| 部署方式 | 采集页 | 首页 | 合集页 | 单条页 |
|---|---|---|---|---|
| 本机 / Linux | `http://127.0.0.1:8765/collect.html` | `/index.html` | `/series.html?id=<ID>` | `/single.html?id=<ID>` |
| 局域网（群晖/飞牛/服务器） | `http://<设备IP>:8765/collect.html` | `/index.html` | `/series.html?id=<ID>` | `/single.html?id=<ID>` |
| 配了反代/域名 | `https://<域名>/collect.html` | `/index.html` | `/series.html?id=<ID>` | `/single.html?id=<ID>` |

> 合集页 / 单条页的 `<ID>` 从首页卡片链接或采集页「已有采集单元」列表里获取。
