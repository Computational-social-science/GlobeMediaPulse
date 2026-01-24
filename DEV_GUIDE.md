# Globe Media Pulse 开发指南 (Development Guide)

本文档介绍如何使用 Docker Compose 进行高效的本地开发、测试，以及如何部署到生产环境。

## 1. 核心工作流 (Workflow)

我们采用了 **Local Dev with Docker** 模式。所有服务（前端、后端、数据库、S3）都在 Docker 中运行，但通过 Volume 挂载实现了代码的**实时热重载 (Hot Reload)**。

### 架构图
- **Frontend**: localhost:5174 (Svelte + Vite)
- **Backend**: localhost:8002 (FastAPI)
- **Database**: localhost:5433 (PostgreSQL)
- **Object Storage**: localhost:9002 (MinIO - S3 compatible)

## 2. 本地开发 (Local Development)

### 启动开发环境
只需一条命令即可启动整个堆栈：
```bash
docker-compose up --build
```
*   `--build`: 确保镜像重新构建（如果有依赖变更）。
*   首次运行可能需要几分钟下载镜像。

### 开发操作
1. **前端开发**: 编辑 `frontend/src` 下的文件。保存后，浏览器会自动刷新 (HMR)。
2. **后端开发**: 编辑 `backend/` 下的文件。保存后，后端服务会自动重启。
3. **访问应用**: 打开 [http://localhost:5174](http://localhost:5174)。
4. **API 文档**: 打开 [http://localhost:8002/docs](http://localhost:8002/docs) 查看 Swagger UI。
5. **MinIO 控制台**: 打开 [http://localhost:9003](http://localhost:9003) (账号/密码: `minioadmin` / `minioadmin`)。

### 停止环境
```bash
docker-compose down
```
若要同时删除数据卷（重置数据库）：
```bash
docker-compose down -v
```

## 3. 测试 (Testing)

### 运行后端测试
进入后端容器运行 pytest：
```bash
docker-compose exec backend pytest
```

### 运行前端测试
进入前端容器运行测试（如果有）：
```bash
docker-compose exec frontend npm run check
```

## 4. 远程部署 (Remote Deployment)

我们使用 **Fly.io** 进行生产环境部署。

### 部署配置
*   **配置文件**: `fly.toml`
*   **Dockerfile**: `backend/Dockerfile` (注意：生产环境只部署后端，前端通常托管在 Vercel/Netlify 或通过 Nginx 容器)
    *   *当前配置*: Fly.io 仅部署了后端 API。
    *   *前端部署*: 建议将前端构建产物 (`npm run build`) 部署到静态托管服务，或配置 Fly.io 同时托管静态文件。

### 部署命令
```bash
fly deploy
```

### 生产环境密钥设置
如果新增了环境变量，记得同步到 Fly.io：
```bash
fly secrets set NEW_VAR=value
```

## 5. 常见问题 (FAQ)

**Q: 为什么前端连不上后端？**
A: 检查 `docker-compose.yml` 中的 `VITE_API_URL` 是否为 `http://localhost:8000`。在 Docker 内部通信用服务名，但浏览器是运行在宿主机的，所以用 localhost。

**Q: 数据库怎么连接？**
A: 本地连接字符串: `postgresql://postgres:password@localhost:5432/spellatlas`
