# 零成本+永久免费部署方案 (Zero-Cost & Forever Free Deployment Strategy)

**版本**: 1.0  
**日期**: 2026-02-03  
**适用项目**: GlobeMediaPulse  
**合规原则**: 严格遵循开源协议，利用顶级云厂商“永久免费”层级，确保 0 元预算下的高可用与 5 年长期运行。

---

## 1. 架构设计与功能清单 (Architecture & Components)

本方案采用 **“静态前端托管 + 动态后端计算 + 边缘网络加速”** 的混合架构，结合本地环境作为数据冷备与繁重计算节点。

### 1.1 架构图 (Mermaid)

```mermaid
graph TD
    User[全球用户] -->|HTTPS/CDN| CF[Cloudflare (DNS/WAF/CDN)]
    
    subgraph "Public Cloud (Remote - Free Tier)"
        CF -->|Static Assets| GHP[GitHub Pages (Frontend)]
        CF -->|API Request| OCI[Oracle Cloud / AWS Free Tier (Backend)]
        
        subgraph "OCI ARM Instance (4 OCPU, 24GB RAM)"
            Nginx[Nginx Reverse Proxy]
            FastAPI[FastAPI Server]
            Scrapy[Scrapy Crawler (Daily Job)]
            PG[PostgreSQL (Dockerized)]
        end
        
        Scrapy -->|Write| PG
        FastAPI -->|Read| PG
    end
    
    subgraph "Local Environment (Dev & Backup)"
        DevPC[本地开发机]
        DevPC -->|Git Push| GH[GitHub Repo]
        DevPC -->|DB Backup| PG
        DevPC -->|Heavy Analysis| LocalAnalysis[本地数据清洗/NLP训练]
    end
    
    GH -->|GitHub Actions| GHP
    GH -->|GitHub Actions (SSH Deploy)| OCI
```

### 1.2 组件功能清单

| 组件 | 部署位置 | 选型 | 费用来源/策略 | 核心职责 |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend** | Remote | **GitHub Pages** | GitHub 公共仓库免费托管 | 承载 Svelte 静态资源，全球 CDN 分发。 |
| **Edge Network** | Remote | **Cloudflare** | Free Plan | DNS 解析、DDoS 防护、SSL 证书、全球加速。 |
| **Backend API** | Remote | **OCI Ampere A1** | Oracle Always Free (4核 24G) | 运行 FastAPI 服务，提供 REST 接口。 |
| **Crawler** | Remote | **OCI Ampere A1** | Oracle Always Free | 每日定时抓取，利用闲置算力。 |
| **Database** | Remote | **PostgreSQL (Docker)** | Oracle Block Volume (200GB 免费) | 核心数据存储，无需购买 RDS。 |
| **CI/CD** | Cloud | **GitHub Actions** | Public Repo 免费无限制 | 自动化构建、测试、部署。 |
| **Local Ops** | Local | **Docker Desktop** | 本地硬件 | 开发调试、冷数据备份、模型训练预处理。 |

---

## 2. 开源软件清单与合规性 (Software & Compliance)

所有组件均采用宽松的开源许可证，允许商业用途与修改，无版权风险。

| 软件/库 | 版本 | 许可证 | 合规性说明 |
| :--- | :--- | :--- | :--- |
| **Svelte** | 5.x | MIT | 允许免费使用、修改、分发，无强制开源义务。 |
| **FastAPI** | 0.109+ | MIT | 允许构建闭源或开源 API 服务。 |
| **Scrapy** | 2.11+ | BSD-3-Clause | 极度宽松，适合爬虫商业化或公益项目。 |
| **PostgreSQL** | 16+ | PostgreSQL License | 类似 MIT，允许自由使用与分发。 |
| **Nginx** | 1.24+ | BSD-2-Clause | 允许作为反向代理免费使用。 |
| **Docker** | CE | Apache 2.0 | 社区版免费，符合个人与中小团队使用协议。 |
| **MapLibre GL** | 4.x | BSD-3-Clause | Mapbox GL JS 的开源分支，无收费风险。 |

---

## 3. 零费用资源配额策略与风险规避 (Quota Management)

### 3.1 GitHub Pages (前端)
- **配额**: 100GB 流量/月，1GB 构建产物存储。
- **利用策略**: 
  - 仅托管编译后的 HTML/JS/CSS。
  - 图片/视频资源走外部图床或 Cloudflare R2 (10GB 免费)。
- **风险规避**: 若流量超限，自动降级至 Vercel Free Tier (100GB) 或 Netlify Starter。

### 3.2 Oracle Cloud Always Free (后端/数据库)
- **配额**: 4 OCPU (ARM), 24GB RAM, 200GB 存储, 10TB 出站流量/月。
- **利用策略**:
  - Docker 容器化部署所有服务，利用 K3s 或 Docker Compose 编排。
  - 200GB 存储划分为：50GB OS, 100GB DB, 50GB Logs/Backup。
- **风险规避**: 
  - **账号回收风险**: 配置脚本每 7 天产生少量 CPU 负载（如压缩日志），避免被判定为“闲置资源”回收。
  - **备选方案**: 若 OCI 不可用，自动切换至 Google Cloud e2-micro (长期免费) + Supabase Free Tier (500MB DB)。

### 3.3 GitHub Actions (CI/CD)
- **配额**: 公共仓库免费无限制；私有仓库 2000 分钟/月。
- **利用策略**: 保持仓库 Public（代码脱敏），享受无限构建时长。
- **超限方案**: 使用本地 Runner (Self-hosted Runner) 部署在 OCI 实例上，消耗服务器算力而非 GitHub 配额。

---

## 4. 自动化 CI/CD 配置示例 (Zero-Cost CI/CD)

完全基于 GitHub Actions，不依赖任何付费插件。

### `.github/workflows/deploy.yml` 示例

```yaml
name: Zero-Cost Deploy

on:
  push:
    branches: [ main ]

jobs:
  # 1. 前端构建与部署 (GitHub Pages)
  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install & Build
        run: |
          cd frontend
          npm install
          npm run build
      - name: Deploy to GH Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./frontend/dist

  # 2. 后端部署 (SSH to OCI)
  deploy-backend:
    needs: deploy-frontend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy via SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.OCI_HOST }}
          username: ${{ secrets.OCI_USER }}
          key: ${{ secrets.OCI_SSH_KEY }}
          script: |
            cd /home/ubuntu/GlobeMediaPulse
            git pull origin main
            # 重建并重启服务，利用 Docker 缓存加速
            docker-compose up -d --build --remove-orphans
            # 清理无用镜像，节省磁盘空间
            docker image prune -f
```

---

## 5. 可量化的成本对照表 (Cost Comparison)

| 项目 | 传统付费方案 (AWS/Aliyun) | 本方案 (Zero-Cost) | 5年节省预估 |
| :--- | :--- | :--- | :--- |
| **计算实例** | t3.medium (2vCPU/4G) ≈ $30/月 | OCI Ampere (4vCPU/24G) = $0 | $1,800 |
| **数据库** | RDS PostgreSQL (db.t3.micro) ≈ $18/月 | Self-hosted Docker PG = $0 | $1,080 |
| **流量带宽** | NAT Gateway + Egress (100GB) ≈ $15/月 | OCI (10TB Free) + CF CDN = $0 | $900 |
| **CI/CD** | Jenkins Server / GH Paid ≈ $20/月 | GitHub Actions Public = $0 | $1,200 |
| **SSL证书** | 单域名证书 ≈ $50/年 | Let's Encrypt / CF = $0 | $250 |
| **总计** | **约 $1,000 / 年** | **$0 / 年** | **$5,230+** |

**结论**: 采用本方案，在获得比入门级付费实例更强算力（4核24G vs 2核4G）的同时，实现了真正的零资金投入。

---

## 6. 长期运维与验证 (Maintenance & Verification)

### 6.1 部署步骤 (Reproducible)
1.  **资源申请**: 注册 Oracle Cloud Free Tier，创建 Ampere A1 实例，开放 80/443/22 端口。
2.  **环境初始化**:
    ```bash
    # 在 OCI 服务器上执行
    sudo apt update && sudo apt install -y docker.io docker-compose git
    git clone https://github.com/YourRepo/GlobeMediaPulse.git
    cd GlobeMediaPulse
    # 配置环境变量
    cp .env.example .env
    ```
3.  **启动服务**:
    ```bash
    docker-compose up -d
    ```
4.  **配置域名**: 在 Cloudflare 后台将域名 A 记录指向 OCI 实例 IP，开启 "Proxied" (小橙云) 模式。

### 6.2 监控指标 (Zero-Cost Monitoring)
- **服务存活**: 使用 UptimeRobot (免费版) 每 5 分钟检测一次 API 接口。
- **资源监控**: 在 OCI 实例上运行 `glances` 或简单脚本，每日记录 CPU/内存使用率到日志文件。
- **错误报警**: 前端集成 Sentry (Free Tier)，后端利用 Python `logging` 结合简单的邮件发送脚本（SMTP 使用 Gmail/Outlook）。

### 6.3 第三方验证
- **Oracle Always Free Policy**: [官方文档](https://www.oracle.com/cloud/free/) 承诺 "Always Free" 资源永久有效。
- **Cloudflare Free Plan**: [官方页面](https://www.cloudflare.com/plans/) 明确核心安全与加速功能免费。

---

**承诺**: 本文档所述方案完全基于 2026 年当前主流云服务商的公开服务条款设计，只要不违反（如挖矿、滥用），即可保证至少 5 年的零成本稳定运行。
