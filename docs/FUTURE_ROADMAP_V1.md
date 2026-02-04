# 后续建议清单 (Future Roadmap V1.0)

**日期:** 2026-02-03  
**规划周期:** Q2 2026 (Apr - Jun)

---

## 1. 功能迭代清单 (Feature Iteration)

| 优先级 | 功能模块 | 描述 | 预期收益 | 资源需求 |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | **多语言支持** | 前端 i18n 框架集成 (English/Chinese/Spanish) | 拓展 Global South 用户群 | 1 Frontend (2w) |
| **P1** | **实时协作** | 允许多人同时操作地图与标注 (WebSocket sync) | 提升团队研判效率 | 1 Fullstack (3w) |
| **P2** | **高级分析** | 引入 LLM 进行新闻摘要与情感倾向自动打标 | 数据价值提升 10x | 1 AI Eng (4w) |

---

## 2. 技术债务偿还 (Tech Debt Paydown)

### 2.1 前端状态管理重构
- **现状:** `stores.js` 逐渐庞大，状态逻辑分散。
- **计划:** 引入 XState 或 Redux Toolkit 进行状态机管理，特别是针对复杂的向导与地图交互。

### 2.2 测试覆盖率提升
- **现状:** 仅有基础 E2E 测试。
- **计划:** 补充后端单元测试 (PyTest) 覆盖率至 80%，前端组件测试 (Vitest) 覆盖率至 70%。

---

## 3. 监控升级方案 (Monitoring 2.0)

### 3.1 全链路追踪 (Distributed Tracing)
- **方案:** 在 Sentry 中串联前端与后端的 Trace ID，实现用户点击到数据库查询的全链路可视化。

### 3.2 业务指标看板
- **方案:** 基于 Grafana + Prometheus 构建业务大盘：
    - 每日新增文章数
    - 实体识别准确率
    - API 平均响应时间 (P95/P99)

---

## 4. 成本预估
- **LLM API:** 预计 $50/月 (基于 1M tokens)
- **CI/CD:** 维持免费 (GitHub Actions)
- **人力:** 内部团队消化，无需新增 Headcount。
