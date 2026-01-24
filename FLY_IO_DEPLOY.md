# Fly.io 后端部署指南 (Step-by-Step)

本指南专门针对使用 Fly.io 部署 SpellAtlas 后端服务。

## 前置准备

1.  **安装 Fly CLI**:
    - Windows (PowerShell): `iwr https://fly.io/install.ps1 -useb | iex`
    - Mac/Linux: `curl -L https://fly.io/install.sh | sh`
2.  **注册/登录**:
    - 运行 `fly auth signup` 或 `fly auth login`。
3.  **准备云端资源** (参考 OPS_GUIDE.md):
    - **Supabase**: 获取 PostgreSQL 连接串 (`DATABASE_URL`)。
    - **Backblaze B2**: 获取 S3 兼容的 KeyID, SecretKey, Endpoint (`S3_ENDPOINT_URL`).

---

## 部署步骤

### 第一步：初始化应用

在项目根目录 (`D:\2026-AI4S\SpellAtlas`) 打开终端：

1.  **检查配置文件**:
    我已经为您生成了 `fly.toml` 模板。
    
2.  **启动初始化**:
    运行以下命令，创建一个新的 Fly 应用（如果 `fly.toml` 中的名字已被占用，您需要修改文件中的 `app = "..."`）：
    ```powershell
    fly launch --no-deploy --copy-config
    ```
    *   如果提示是否覆盖 `fly.toml`，选择 **No** (保留我们生成的配置)。
    *   如果提示选择区域 (Region)，选择离您或用户最近的 (如 `hkg` 香港, `nrt` 东京, `sjc` 硅谷)。

### 第二步：设置环境变量 (Secrets)

这是最关键的一步。将所有敏感信息写入 Fly 的加密存储中：

```powershell
fly secrets set ^
    DATABASE_URL="postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres" ^
    AWS_ACCESS_KEY_ID="[YOUR_B2_KEY_ID]" ^
    AWS_SECRET_ACCESS_KEY="[YOUR_B2_APP_KEY]" ^
    S3_ENDPOINT_URL="https://s3.us-west-002.backblazeb2.com" ^
    S3_BUCKET_NAME="spellatlas-data-prod"
```

*注意：Windows PowerShell 中换行符是 `^`，如果使用 CMD 或 Bash 请自行调整。建议在记事本中编辑好一行执行。*

### 第三步：部署上线

执行部署命令：

```powershell
fly deploy
```

Fly.io 将会：
1.  使用 Docker 构建镜像（基于 `backend/Dockerfile`）。
2.  推送镜像到 Fly Registry。
3.  启动虚拟机 (Firecracker VM)。
4.  执行健康检查。

### 第四步：验证状态

1.  **查看状态**:
    ```powershell
    fly status
    ```
2.  **查看日志**:
    如果部署失败或无法启动，第一时间查看日志：
    ```powershell
    fly logs
    ```
3.  **获取访问地址**:
    ```powershell
    fly info
    ```
    记下 Hostname (例如 `spellatlas-backend.fly.dev`)。

---

## 常见问题与高级配置

### WebSocket 连接
Fly.io 自动支持 WebSocket。
- **前端配置**: 确保前端连接地址为 `wss://<your-app>.fly.dev/ws`。
- **超时问题**: 如果 WebSocket 连接频繁断开，可能需要增加超时设置（在 `fly.toml` 中已默认配置较宽松的限制，但需检查代码中的心跳逻辑）。

### 数据库迁移
由于我们使用 Supabase，通常不需要在 Fly 容器内运行迁移命令。建议在本地运行迁移脚本连接到远程数据库，或者通过 Supabase SQL Editor 执行初始化 SQL。

如果必须在部署时运行迁移，可以在 `fly.toml` 中添加：
```toml
[deploy]
  release_command = "python backend/scripts/migrate_json_to_pg.py"
```
*(注意：这需要脚本能正确处理路径和依赖)*

### 扩容 (Scale)
如果需要更多性能：
```powershell
# 增加内存
fly scale memory 1024

# 增加实例数 (高可用)
fly scale count 2
```
