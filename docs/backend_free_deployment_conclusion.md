## 后端免费部署结论文档

### 排除 Oracle OCI Always Free 的技术依据

- 网络连通性：OCI Always Free 资源必须创建在账号的 Home Region，无法跨区域使用 Always Free 资源，且 Home Region 需在注册时确定并长期固定，导致面向中国大陆访问的路径不可控 [OCI Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) [OCI Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
- 合规性：面向中国大陆用户的后端服务需考虑数据跨境与主体备案要求，OCI Home Region 若不在中国大陆区域将增加合规风险与审批成本
- 性能测试数据：基于测试报告结果，国际区域平均延迟显著高于亚太区域，冷启动峰值接近30秒，无法满足更严格的国内访问体验目标

### 推荐排序与理由

1. Cloud Run Always Free
   - 冷启动与压测指标最优，免费额度包含请求次数与CPU/内存配额 [Cloud Run Pricing](https://cloud.google.com/run/pricing)
   - 适合低到中等流量、需要弹性扩缩的API服务
2. Koyeb Hobby Free Instance
   - 提供明确的免费实例规格与带宽额度，部署与回滚可通过GitHub Actions自动化 [Koyeb Pricing FAQ](https://www.koyeb.com/docs/faqs/pricing)
   - 适合单实例稳定运行的轻量API
3. Render Free Web Service
   - 免费实例小时明确，但会因额度耗尽而暂停服务，需要更严格的配额管理 [Render Free](https://render.com/docs/free)
   - 适合低频访问与测试环境

### 风险缓解措施

- 配额风险：所有方案启用日用量阈值监控，超过80%触发告警并暂停非核心任务
- 冷启动风险：健康探测与定时唤醒策略并行，服务空闲时通过轻量探测保持热度
- 依赖风险：关键环境变量与密钥统一托管在平台Secret与GitHub Secrets，避免本地漂移
- 回滚风险：部署后必须完成健康检查，失败则自动回滚到前一版本

### 可观测性配置

- 日志采集：统一输出结构化JSON日志，平台日志流采集并长期保存
- 指标上报：HTTP状态码、P50/P95延迟、错误率、吞吐量
- 告警阈值：HTTP 5xx > 1% 触发邮件与Webhook通知

### 交付物索引

- 方案对比矩阵：docs/backend_free_deployment_matrix.md
- 测试报告：docs/backend_free_deployment_test_report.md
