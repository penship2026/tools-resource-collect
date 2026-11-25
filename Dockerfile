FROM python:3.12-slim

# 时区设为东八区:generate.py 用 datetime.fromtimestamp() 按系统时区格式化发布日期,
# 容器默认 UTC 会导致日期比北京时间早 8 小时(显示成前一天)。
ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装时区数据,让 TZ=Asia/Shanghai 真正生效
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

EXPOSE 8765

# 采集代码位于 collector/;server.py 会把项目根作为静态托管根目录
CMD ["python3", "collector/server.py", "8765"]
