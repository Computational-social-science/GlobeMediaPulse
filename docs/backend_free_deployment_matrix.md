## 后端永久免费部署方案对比矩阵

### 方案概览

| 方案 | 免费额度明细 | 中国大陆可用性验证方法 | 一键部署脚本 | SLA指标 | 可观测性配置 | 官方永久免费依据 |
| --- | --- | --- | --- | --- | --- | --- |
| Render Free Web Service | 实例小时：每月750小时；实例数：单实例；请求次数：未单独计费，受实例小时与带宽配额影响；带宽与构建分钟数按工作区免费配额统计 | ICMP+TCP 443/80探测；DNS污染检测（A记录对比公共DNS）；HTTP健康检查延迟统计 | GitHub Actions workflow：deploy-render.yml | 可用性≥99.5%，冷启动≤30s，月均费用=0元 | 日志：Render Logs；指标：请求延迟与5xx比率由应用指标上报；告警：HTTP 5xx>1%触发邮件+Webhook | Render 免费部署与750小时限制说明 [Render Free](https://render.com/docs/free) |
| Koyeb Hobby Free Instance | 512MB RAM，0.1 vCPU，2GB SSD；免费Web Service限1个；出站带宽100GB/月免费；请求次数：未单独计费，受实例资源与带宽配额影响 | ICMP+TCP 443/80探测；DNS污染检测（A记录对比公共DNS）；HTTP健康检查延迟统计 | GitHub Actions workflow：deploy-koyeb.yml | 可用性≥99.5%，冷启动≤30s，月均费用=0元 | 日志：Koyeb Logs；指标：应用侧Prometheus/OpenTelemetry上报；告警：HTTP 5xx>1%触发邮件+Webhook | Koyeb 免费实例与带宽说明 [Koyeb Pricing FAQ](https://www.koyeb.com/docs/faqs/pricing) |
| Google Cloud Run Always Free | 每月免费：180,000 vCPU秒，360,000 GiB秒，2,000,000 请求；按请求计费模式；请求次数按月重置 | ICMP+TCP 443/80探测；DNS污染检测（A记录对比公共DNS）；HTTP健康检查延迟统计 | GitHub Actions workflow：deploy-cloudrun.yml | 可用性≥99.5%，冷启动≤30s，月均费用=0元 | 日志：Cloud Run Logs；指标：Cloud Monitoring；告警：HTTP 5xx>1%触发邮件+Webhook | Cloud Run 免费额度明细 [Cloud Run Pricing](https://cloud.google.com/run/pricing) |

### 统一约束说明

- 以上三方案均以容器化后端部署为前提，建议以 `backend/Dockerfile` 为构建入口
- 方案的“请求次数”若官方未给出独立计费项，则以免费实例小时、CPU/内存计费与带宽配额共同限制为准
