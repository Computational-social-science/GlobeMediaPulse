# Globe Media Pulse 运维与部署操作指南 (Operations Guide)

本指南详细说明了如何配置云端基础设施（对象存储、数据库、备份）以及如何部署 Globe Media Pulse 的生产环境。

## 1. 对象存储配置 (Backblaze B2)

我们使用 Backblaze B2 存储原始新闻数据（JSON快照），利用其兼容 AWS S3 的 API 和免费额度（10GB）。

### 步骤 1.1: 注册与创建 Bucket
1. 访问 [Backblaze B2](https://www.backblaze.com/b2/cloud-storage.html) 并注册账户。
2. 登录控制台，点击 **"Buckets"** -> **"Create a Bucket"**。
3.12. **Bucket Name**: 输入唯一名称（例如 `globemediapulse-data-prod`）。
13. **Privacy**: 设置为 **Private**（私有）。
5. **Default Encryption**: 建议开启 (SSE-B2)。
6. **Object Lock**: 建议开启（防止误删），或者开启 **Bucket Settings** 中的 **Lifecycle Settings** 以保留旧版本。
7. 点击 **"Create a Bucket"**。

### 步骤 1.2: 获取 Endpoint
在 Buckets 列表中找到刚创建的 Bucket，查看其 **"Endpoint"**。
- 格式通常为: `s3.us-west-00X.backblazeb2.com`
- **记录下来**，这将是环境变量 `S3_ENDPOINT_URL` 的值（注意加上 `https://` 前缀，如 `https://s3.us-west-002.backblazeb2.com`）。

### 步骤 1.3: 创建 Application Keys
1. 点击左侧菜单 **"App Keys"**。
2. 点击 **"Add a New Application Key"**。
3. **Name**: `SpellAtlas-Backend`
4. **Allow access to Bucket(s)**: 选择刚才创建的 `spellatlas-data-prod`。
5. **Type of Access**: Read and Write。
6. 点击 **"Create New Key"**。
7. **重要**: 立即复制 **keyID** 和 **applicationKey**。
   - `keyID` -> 对应环境变量 `AWS_ACCESS_KEY_ID`
   - `applicationKey` -> 对应环境变量 `AWS_SECRET_ACCESS_KEY`

---

## 2. 数据库配置 (Supabase)

使用 Supabase 托管 PostgreSQL 数据库。

### 步骤 2.1: 创建项目
1. 访问 [Supabase](https://supabase.com/) 并新建项目。
2. 设置数据库密码（**务必记录**）。
3. 等待项目初始化完成。

### 步骤 2.2: 获取连接字符串
1. 进入 **Project Settings** -> **Database** -> **Connection string**。
2. 选择 **URI** 模式，复制字符串。
3. 替换密码部分 `[YOUR-PASSWORD]`。
4. **记录下来**，这将是环境变量 `DATABASE_URL`。

### 步骤 2.3: 配置备份 (Point-in-Time Recovery)
1. 进入 **Database** -> **Backups**。
2. 确认 **Daily Backups** 已启用（默认）。
3. (可选/付费) 启用 **PITR** 以支持按时间点恢复。

---

## 3. 后端部署 (Render / Fly.io)

### 选项 A: Render (推荐新手)
1. 连接 GitHub 仓库，选择 `backend` 目录。
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**:
   - `PYTHON_VERSION`: `3.11.0`
   - `DATABASE_URL`: (步骤 2.2 获取的 URI)
   - `AWS_ACCESS_KEY_ID`: (步骤 1.3 的 keyID)
   - `AWS_SECRET_ACCESS_KEY`: (步骤 1.3 的 applicationKey)
   - `S3_ENDPOINT_URL`: (步骤 1.2 的 Endpoint，带 https://)
   - `S3_BUCKET_NAME`: `spellatlas-data-prod`
   - `ALLOWED_ORIGINS`: 前端域名 (如 `https://spellatlas.vercel.app`)

### 选项 B: Fly.io (推荐高性能/WebSocket)
1. 安装 `flyctl` 命令行工具。
2. 在项目根目录运行 `fly launch`。
3. 修改生成的 `fly.toml`，确保端口配置正确。
4. 设置 Secrets:
   ```bash
   fly secrets set DATABASE_URL=... AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
   ```
5. 部署: `fly deploy`。

**关于 WebSocket**: Fly.io 自动支持 WebSocket，无需特殊配置。确保前端连接的是 `wss://your-app.fly.dev/ws`。

---

## 4. 前端部署 (Vercel)

1. 导入 GitHub 仓库。
2. **Framework Preset**: Vite。
3. **Build Command**: `npm run build`。
4. **Output Directory**: `dist`。
5. **Environment Variables**:
   - `VITE_API_URL`: 后端完整 URL (如 `https://globemediapulse-backend.onrender.com`)，**不要**带末尾斜杠。
   - `VITE_WS_URL`: 后端 WebSocket URL (如 `wss://globemediapulse-backend.onrender.com/ws`)。

---

## 5. 验证与维护

### 5.1 验证部署
1. 打开前端页面，检查控制台无报错。
2. 触发一次抓取任务 (POST `/api/trigger-pipeline`)。
3. 检查 Backblaze B2 Bucket，确认是否生成了新的 JSON 文件 (`raw_news/news_YYYY-MM-DD...json`)。
4. 检查 Supabase `news_snapshots` 表，确认是否有新记录。

### 5.2 数据恢复 (Disaster Recovery)
如果数据库损坏，但对象存储中的 JSON 文件完好：
1. 重置数据库（清空表）。
2. 使用脚本从对象存储重新导入数据（需编写 `restore_from_s3.py`，逻辑类似于 `detect_errors.py` 的 fetch 逻辑，但遍历所有 key）。

### 5.3 本地模拟生产环境
使用 Docker Compose 可以在本地完全模拟上述环境（MinIO 替代 S3，本地 Postgres 替代 Supabase）：
```bash
docker-compose up --build
```
访问 `http://localhost:9001` (MinIO Console) 查看模拟的 Bucket。
