# AI CRM V1.0 实施计划（按垂直功能切片）

> 版本：1.0 · 对照 `docs/PRD.md` §15 的 7 步顺序。每个切片必须同时交付：迁移、API、前端、权限、测试、文档。DoD 见 `AGENTS.md` §6。

执行顺序（与团队 task 依赖一致）：

| 序号 | PRD §15 步骤 | 团队 task | 依赖 |
|---|---|---|---|
| S0 | 架构/契约/验收/计划（本切片） | #1 | — |
| S1 | 基础工程与登录鉴权 | #4 | #1 |
| S2 | 线索纵向切片 | #7 | #4 |
| S3 | 跟进纵向切片 | #8 | #7 |
| S4 | 客户与商机切片 | #3 | #8 |
| S5 | 任务及统计（含 Excel 导入） | #2 | #3 |
| S6 | AI 增强能力 | #6 | #2 |
| S7 | 生产加固、部署与交付验收 | #5 | #6 |

---

## S0 架构与契约（已完成，本文）

产出：`AGENTS.md`、`README.md`、`docs/{PRD,architecture,api-contract,acceptance,decisions,deployment}.md`、仓库骨架、`compose.yaml`、`.env.example`。

---

## S1 基础工程与登录鉴权（task #4）

**范围**：仓库工程化、数据库连接、Alembic 初始迁移、登录/登出/会话、角色模型、全局布局与路由守卫、CI。

- 迁移：`users` 表 + 初始管理员种子（仅 admin，无虚构客户）。
- API：`/auth/login`、`/auth/logout`、`/auth/me`、`/auth/change-password`、`/admin/users`（创建/禁用/重置密码/赋角色）。
- 前端：统一布局（侧边导航 + 顶栏）、路由守卫、Pinia auth store、登录页、首次改密页。
- 权限：会话 Cookie（HttpOnly/SameSite，生产 Secure）、CSRF 防护、登录限流、禁用撤销会话。
- 测试：Pytest 认证/权限/越权、Vitest auth store、Playwright 登录改密。

---

## S2 线索纵向切片（task #7）

**范围**：线索创建/列表/详情/查重/分配/状态变更/关闭重开。

- 迁移：`customers`、`contacts`、`leads`、`lead_assignments`、`channel_sources`（预置来源字典）、`audit_logs`。
- API：`GET/POST /leads`、`GET/PATCH /leads/{id}`、`POST /leads/{id}/assign|close|reopen`。
- 前端：线索列表（筛选/分页/排序）、新建线索（查重提示）、线索详情、分配抽屉、状态操作。
- 权限：market 全部、sales 仅自己负责；服务端 ID 枚举防护。
- 测试：真库持久化、查重、分配生成待联系任务、越权、Pytest+Vitest+Playwright。

---

## S3 跟进纵向切片（task #8）

**范围**：电话 +1/+2/+3、微信、内容、时间、累计、历史时间线、幂等、撤销审计。

- 迁移：`followups`（含 `idempotency_key`、`voided_at`、`phone_count_delta` 约束）。
- API：`GET/POST /followups`、`POST /followups/{id}/void`（admin）。
- 前端：线索/商机详情的「+ 跟进」弹窗（电话快捷 +1/+2/+3、微信）、跟进时间线（逆序、累计次数）。
- 权限：sales 仅自己负责对象、market 必要时补记、void 仅 admin。
- 测试：累计 +6、微信不计电话、幂等防重、时间排序与补录、撤销审计。

---

## S4 客户与商机切片（task #3）

**范围**：客户/联系人维护、转商机事务、商机看板、阶段推进、赢单/输单。

- 迁移：`opportunities`、`opportunity_stage_history`（其余表 S2/S3 已建）。
- API：`GET/POST /customers`、`GET/PATCH /customers/{id}`、`GET/POST /customers/{id}/contacts`；`GET/POST /opportunities`、`GET/PATCH /opportunities/{id}`、`POST /opportunities/{id}/transition`；`POST /leads/{id}/convert`。
- 前端：客户列表/详情（多联系人、时间线）、商机看板（按阶段分组）、商机详情、阶段推进抽屉、赢单/输单。
- 权限：market 只读商机、sales 仅自己负责商机、客户范围见 PRD §2。
- 测试：转商机事务回滚、多线索多商机、赢单金额/输单原因、阶段日志、越权。

---

## S5 任务与统计（含 Excel 导入）（task #2）

**范围**：任务（分配生成待办、工作台）、基础报表、Excel 导入。

- 迁移：`tasks`、`import_batches`、`import_row_results`、`source_records`。
- API：`GET/POST/PATCH /tasks`、`POST /tasks/{id}/complete`；`GET /dashboard/summary`、`GET /reports/leads`、`GET /reports/opportunities`；`GET /imports/leads/template`、`POST /imports/leads/preview|commit`、`GET /imports/{id}/result`。
- 前端：工作台（统计卡片 + 我的任务，逾期优先）、数据分析页、系统设置（来源字典、分配 SLA 设置）、导入向导（模板/预览/错误报告）。
- 权限：sales 仅本人任务/报表、market/admin 全部。
- 测试：首次分配唯一待办、超期排序、报表口径、导入幂等/逐行错误/防公式注入。

---

## S6 AI 增强能力（task #6）

**范围**：AI Provider 配置、客户摘要、跟进建议与话术草稿、故障兜底。

- 迁移：AI 输出存储（生成时间 + 人工确认状态，如 `ai_outputs` 或复用审计字段）。
- API：`POST /ai/customer-summary`、`POST /ai/followup-suggestion`；`/settings/ai`（admin 配置连接）。
- 前端：系统设置「AI 配置」、详情页可编辑摘要/建议面板（显式人工确认）。
- 权限：仅授权对象；限流；AI 未配置返回 `AI_UNAVAILABLE`，不影响其他业务。
- 测试：故障注入（AI 停机时 CRUD 正常）、无文字时提示信息不足、不推断需求。

---

## S7 生产加固、部署与交付验收（task #5）

**范围**：越权/审计/并发与幂等补强、备份恢复、性能、部署文档与验收。

- 交付：`docs/deployment.md` 补全、Nginx HTTPS 配置、日志轮转、备份恢复演练、健康检查。
- 验收：逐条完成 `docs/acceptance.md` 全部 F1–F15 / E1–E6，记录证据。
- 测试：两名销售越权全矩阵、并发修改 409、幂等、输入边界、备份恢复演练。

---

## 跨切片约定

- 所有结构变更走 Alembic；每次切片结束更新 `architecture.md` 数据模型、`api-contract.md`、`acceptance.md` 证据表。
- 所有 API 返回统一错误/分页/时间/幂等/409 约定（见 `api-contract.md` §1）。
- 禁止 Mock；空库展示空状态；初始化仅管理员账号。
