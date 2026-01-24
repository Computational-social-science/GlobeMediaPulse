# 生产环境部署与优化指南 (Deployment & Optimization Guide)

本指南旨在帮助您将 SpellAtlas 从开发环境迁移到生产环境（如 Render, Fly.io, Vercel），并进行关键的架构优化。

## 1. 数据库连接池 (Database Connection Pooling)

在生产环境（特别是使用 Supabase 等托管数据库时），频繁创建和销毁数据库连接会导致性能瓶颈甚至耗尽连接数。我们已经在后端实现了连接池。

### 实现细节
- **代码位置**: `backend/storage.py`
- **机制**: 使用 `psycopg2.pool.ThreadedConnectionPool`。
- **配置**:
  - `minconn=1`: 最小保持1个连接。
  - `maxconn=20`: 最大允许20个连接（适应免费层限制）。
- **用法**:
  ```python
  # 使用上下文管理器自动获取和归还连接
  with self.get_connection() as conn:
      cursor = conn.cursor()
      # 执行查询...
  ```

## 2. 实时性与 WebSocket (Real-time Updates)

为了向前端实时推送新检测到的错误，我们集成了 FastAPI WebSocket。

### 优化点
- **心跳机制 (Heartbeat)**: 每5秒发送一次心跳，防止负载均衡器（Load Balancer）因连接空闲而切断连接。
- **断线重连**: 前端 `GameController.svelte` 已包含自动重连逻辑。
- **模拟模式**: 当数据库为空时，后端自动切换到模拟模式，发送随机数据以供展示。

## 3. 异步任务队列 (Async Task Queue)

数据密集型任务（如抓取新闻、NLP分析）不应阻塞主 API 线程。我们采用了 **FastAPI BackgroundTasks** + **Subprocess** 模式。

### 架构
- **触发端点**: `POST /api/trigger-pipeline`
- **执行流程**:
  1. API 立即返回 `202 Accepted`。
  2. 后台启动子进程运行 `backend.fetch_news`。
  3. 完成后，启动子进程运行 `backend.detect_errors`。
  4. 最后，热重载内存中的数据存储 (`storage.load_data()`)。

这种方式实现了任务的异步执行和进程隔离，避免了复杂的 Celery/Redis 依赖，非常适合中小型项目。

## 4. 部署检查清单 (Deployment Checklist)

### A. 数据库 (Supabase)
1. [ ] 创建 Supabase 项目。
2. [ ] 获取 Connection String (URI 模式)。
3. [ ] 在 Render 环境变量中设置 `DATABASE_URL`。

### B. 对象存储 (AWS S3 / Cloudflare R2 / MinIO)
1. [ ] 创建存储桶 (Bucket)。
2. [ ] 获取 Access Key, Secret Key, Endpoint URL。
3. [ ] 在后端配置相关环境变量。

### C. 后端 (Render)
1. [ ] **Build Command**: `pip install -r backend/requirements.txt`
2. [ ] **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. [ ] **Environment Variables**:
   - `PYTHON_VERSION`: `3.11.0`
   - `DATABASE_URL`: `postgresql://...`
   - `ALLOWED_ORIGINS`: `https://your-frontend.vercel.app`
   - `AWS_ACCESS_KEY_ID`: `...`
   - `AWS_SECRET_ACCESS_KEY`: `...`
   - `S3_ENDPOINT_URL`: `...` (可选，如果是 AWS S3 可省略)
   - `S3_BUCKET_NAME`: `spellatlas-data`

### D. 前端 (Vercel)
1. [ ] **Framework Preset**: Vite
2. [ ] **Build Command**: `npm run build`
3. [ ] **Output Directory**: `dist`
4. [ ] **Environment Variables**:
   - `VITE_API_URL`: `https://your-backend.onrender.com`
   - `VITE_WS_URL`: `wss://your-backend.onrender.com/ws`

## 5. 本地端到端测试 (Local End-to-End Testing)

我们已经完全移除了 SQLite，并配置了本地 PostgreSQL + MinIO (S3) + Docker Compose 环境。

### 步骤 1: 启动服务
```bash
# 构建并启动所有服务（包括本地 Postgres 和 MinIO）
docker-compose up --build
```
这将启动：
- **db**: Postgres 15 数据库 (端口 5432)
- **minio**: S3 兼容对象存储 (控制台端口 9001, API 端口 9000)
- **backend**: FastAPI 后端 (端口 8000)
- **frontend**: Svelte 前端 (端口 8080)

### 步骤 2: 验证连接
- 访问前端: `http://localhost:8080`
- 访问后端 API: `http://localhost:8000/docs`
- 访问 MinIO 控制台: `http://localhost:9001` (User/Pass: `minioadmin`)
- 验证数据库: 后端日志应显示 "PostgreSQL Connection Pool initialized."

### 步骤 3: 数据迁移 (Data Migration)
虽然后端在首次启动时会尝试自动导入数据，但建议使用专用脚本进行可控迁移：

```bash
# 在 Docker 容器中运行迁移脚本
docker-compose run --rm backend python backend/scripts/migrate_json_to_pg.py
```
该脚本会将 `data/detected_errors.json` 中的数据批量导入 PostgreSQL。

## 6. 备份与恢复 (Backup & Recovery)

- **Supabase**: 每日自动备份（取决于套餐，免费版通常保留7天）。
- **手动备份**:
  ```bash
  pg_dump "your-connection-string" > backup.sql
  ```
- **数据恢复**:
  ```bash
  psql "your-connection-string" < backup.sql
  ```

## 7. 生产环境高级配置

### WebSocket 实时推送 (Real-time Updates)
本项目使用 **FastAPI WebSocket** (后端) + **Native WebSocket API** (前端) 实现实时错误推送。
- **Fly.io 配置**: 在 `fly.toml` 中，通常标准 HTTP 服务已支持 WebSocket。如果遇到连接问题，请确保 `[services.ports]` 配置正确，且未设置过短的超时时间。
- **负载均衡**: 确保 Load Balancer 支持 WebSocket 协议升级 (Connection: Upgrade)。

### 备份策略 (Backup Strategy)
- **Supabase**: 默认开启每日备份。建议在 "Database" -> "Backups" 中检查并开启 Point-in-Time Recovery (PITR) 以获得更细粒度的恢复能力。
- **Fly.io Postgres**: 使用 `fly pg create` 创建的集群会自动配置每日快照。可以使用 `fly volume snapshots list` 查看。
- **对象存储 (S3/B2)**: 对于存储在 S3/Backblaze B2 中的原始 JSON 数据，建议开启 Bucket 的 **Versioning (版本控制)** 功能，以防止意外覆盖或删除。

### 对象存储推荐 (Object Storage)
正如架构所示，我们已将原始数据归档迁移至对象存储。
- **推荐**: **Backblaze B2**
- **理由**: 拥有 10GB 免费额度，且 API 与 AWS S3 完全兼容 (`boto3` 可直接使用)。
- **配置**: 在 B2 控制台生成 Application Keys，填入上述环境变量 (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 等)。`S3_ENDPOINT_URL` 需填写 B2 提供的 Endpoint (如 `https://s3.us-west-002.backblazeb2.com`)。

---

**下一步**: 按照上述清单配置环境变量，并推送到 GitHub 触发部署。
