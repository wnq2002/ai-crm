# AI CRM V1.4 系统架构（市场部线索优先管理系统）

> 版本：1.4 · 状态：开发基线 · 关联需求：`docs/PRD.md`（V1.4 唯一需求源）
> 本文定义整体架构、分层、数据模型、状态机、权限与安全、测试与部署蓝图。实现必须与本文件及 `docs/api-contract.md` 保持一致。
> 与 V1.3 的关键差异：联系事件重构为每次独立事件（`lead_activities` 废 `phone_count`、加 `result`，微信三态）；新增 AI 智能新增（`POST /leads/parse`）与 `lead_parse_records`/`lead_event_revisions`/`app_settings` 三表；`leads` 新增 `next_follow_up_at`（工作台待办依据）；`outcome_status` 新增 `deferred`（暂缓）；数据统计「线索数量」与「事件数量」口径分离。

## 1. 系统定位与目标

单体前后端分离的「市场部线索优先管理系统」：前端 SPA 由 Nginx 托管并反代 `/api` 到后端 FastAPI；后端单服务承载全部业务逻辑与权限校验；数据统一落 PostgreSQL。AI 为可选增强（客户/交接摘要草稿），失败不影响主流程。

设计原则：线索优先（先保存线索、后自动关联企业）、真实持久化、服务端权限强制、结构变更强制迁移、关键写操作事务化、可观测（审计/日志/请求 ID）、可恢复部署、禁 Mock 数据。

## 2. 总体架构

```
浏览器 ──HTTPS──▶ Nginx ──/──▶ 前端静态资源（Vue SPA）
                     └──/api──▶ FastAPI ──▶ PostgreSQL
                                  │
                                  └──▶ AI Provider（可选，仅摘要/交接草稿）
```

- Nginx：TLS 终结、静态资源、`/api` 反向代理、请求体大小限制、健康检查不泄露配置。
- FastAPI：REST、Pydantic v2 校验、依赖注入鉴权与 RBAC、SQLAlchemy 2.x 同步事务、Alembic 迁移。
- PostgreSQL 16：唯一正式数据源，UUID 主键，外键参照完整性，归档/带审计撤销（不硬删除）。

## 3. 后端架构（分层）

```
app/
├── main.py                 # 应用装配、中间件、异常处理器、路由注册
├── api/                    # 路由层：路径、依赖注入、请求/响应绑定（薄）
├── services/               # 业务层：业务规则、状态机、事务边界、幂等、企业匹配
├── repositories/           # 数据访问层：SQLAlchemy 查询与写入
├── models/                 # ORM 实体（对应 §5 数据模型）
├── schemas/                # Pydantic v2 请求/响应模型
├── core/                   # config / security / db / logging / idempotency
├── auth/                   # 登录会话、密码、依赖注入的当前用户与权限
└── ai/                     # Provider 抽象（摘要/交接草稿），超时与错误兜底
```

依赖方向：`api → services → repositories → models`；`api → schemas`；`services → auth/core`；禁止反向依赖。业务规则（状态机、权限范围、幂等键、企业匹配）集中在 `services`。

## 4. 前端架构

```
frontend/src/
├── api/        # Axios 封装：统一错误处理、请求 ID、身份过期拦截、CSRF 头
├── router/     # 路由表 + 全局守卫（基于角色/登录态）
├── stores/     # Pinia：auth（身份/角色）、UI 状态
├── layouts/    # 统一布局（侧边导航 + 顶栏）
├── views/      # 页面（工作台/线索管理/客户管理/数据分析/系统设置）
├── components/ # 复用组件（快捷跟进、企业匹配、交接抽屉、时间线等）
├── types/      # 与 api-contract 对齐的 TS 类型
└── utils/      # 时间时区、格式化、幂等键生成、脱敏展示等
```

主导航 5 项：工作台、线索管理（默认业务入口）、客户管理、数据分析、系统设置。不设独立商机管理/销售任务中心/跟进中心。时间统一 Asia/Shanghai 展示、DB 存 UTC、请求携带 ISO 8601 UTC。

## 5. 数据模型（对齐 PRD §7，UUID 主键）

主键 `UUID` 字符串形式；时间戳 UTC；关键外键/状态/时间/规范化字段建索引；PII 按授权读取并日志脱敏。兼容迁移：7 个 revision 线性单链 `cdff02953343 → e62b96822f83 → 7ad73d5f13fb → 3c5c7d4916c9 → b1e974ca9835 → a3f1e2d4c5b6 → f1a2b3c4d5e6`；不 drop/truncate 任何现有表，历史表结构与账号/字典均保留。

| 实体 | 关键字段 | 说明 |
|---|---|---|
| `users` | id, username, password_hash, display_name, role(admin/market), is_active, must_change_password, created_at, updated_at | 已建；role 去 sales（String 兼容，仅不再创建 sales 账号） |
| `user_sessions` | id, user_id, token_hash, csrf_token, created_at, last_activity_at, expires_at | 已建；服务端会话 |
| `audit_logs` | id, actor_id, action, resource_type, resource_id, before_json?, after_json?, occurred_at, request_id | 已建；敏感字段脱敏 |
| `companies` | id, canonical_name, normalized_name, aliases, industry?, phone?, website?, created_at, updated_at, merged_into_id? | 轻量企业档案；可被合并（merged_into_id 指向保留企业） |
| `contacts` | id, company_id?, name?, phone?, email?, wechat_id?, created_at | 人员；可暂不归属企业 |
| `lead_source_categories` | id, code, name, active | 来源分类（精简为：官网 / 其他） |
| `lead_source_details` | id, category_id, name, active | 具体活动/来源详情 |
| `lead_need_types` | id, name, active | 需求类型（AI Agent、OPC Team…可配置，不等于部门） |
| `leads` | id, company_id?, contact_id?, company_name_raw?, contact_name_raw?, phone_raw?, email_raw?, wechat_raw?, need_type_id?, inquiry_text?, notes?, occurred_at, source_category_id, source_detail_id?, source_detail_text?, intake_method, external_source_event_id?, idempotency_key?, source_payload_json?, qualification_status, handoff_status, outcome_status, department_id?, department_contact_id?, created_by, created_at, updated_at, archived_at?, next_follow_up_at?, version | 核心实体；企业名选填；`company_name_raw` 为原文不可被覆盖；`next_follow_up_at` 为下次计划跟进时间（工作台待办依据，记录沟通时设/清空）；待办分类 `follow_up_status`（overdue/first_follow/today/no_progress/stale/handed_off_pending/normal）由服务端实时派生，不落列 |
| `lead_activities` | id, lead_id, kind(phone/wechat_request/wechat_approved/wechat_chat/note), result?, content?, happened_at, created_at, created_by, revoked_at?, revoked_by?, revoke_reason?, idempotency_key | 联系事件；电话 result=connected/unconnected/rejected，微信/备注 result 为 NULL |
| `lead_parse_records` | id, lead_id?, raw_text, parsed_json?, created_by, created_at | AI 智能新增解析记录；原文 + 字段/置信度 JSON，创建后回填 lead_id |
| `lead_event_revisions` | id, activity_id, before_json?, after_json?, reason, revised_by, created_at | 联系事件修正历史；保留修改前后值/操作人/原因 |
| `departments` | id, name, active | 业务部门（GDC / Token 供应链 / 润效营，初始化可编辑） |
| `department_contacts` | id, department_id, name, is_default, active | 部门默认对接人 |
| `lead_handoffs` | id, lead_id, from_department_id?, to_department_id, to_contact_id, note?, happened_at, created_by, reason? | 交接历史与当前部门 |
| `lead_outcome_events` | id, lead_id, from_outcome, to_outcome, note?, feedback_at, created_by, created_at | 反馈事件（推进中/成交/未成交/暂缓/暂无反馈） |
| `lead_events` | id, lead_id, event_type, before_json?, after_json?, created_by, created_at | 判断/企业关联/属性变更的业务事件前后值 |
| `import_jobs` | id, created_by, filename, status, idempotency_key, total_rows, success_rows, failed_rows, created_at | 导入批次 |
| `import_rows` | id, job_id, row_number, status, message?, lead_id? | 行级结果与错误报告 |
| `app_settings` | id, key(唯一), value, updated_by?, updated_at? | 键值配置（AI 服务等）；密钥仅写入不读回（响应 mask） |

约束要点：
- 企业/联系人外键可空；来源/需求字典停用不破坏历史。
- `lead_activities.result` 仅电话写入（connected/unconnected/rejected），微信/备注为 NULL；`idempotency_key` 唯一（按用户/事件作用域）。
- 唯一外部事件 ID 以渠道为作用域；并发写用 `version`/事务约束。
- 电话总次数 = 有效 `phone` 活动数；微信互动数 = 有效微信（申请/通过/沟通）活动数；由服务端聚合，不信任前端累计值。
- 微信关系 `wechat_relationship`（none/pending/approved）由最新一条有效微信事件实时派生（ADR-028），不落冗余列；`wechat_chat` 仅在关系为已通过时允许。
- 统一时间线聚合「线索创建 / 电话 / 微信申请 / 微信通过 / 微信沟通 / 备注 / 有效性变化 / 部门移交 / 部门反馈」，按实际发生时间倒序，每项含清晰 `type` 字段（见 api-contract §4）。
- 联系事件修正写 `lead_event_revisions`（before/after/reason/revised_by）留痕，系统 `created_at` 不可改；未来时间禁止。

## 6. 去重与规范化的三个层次（PRD §3.1）

1. **技术幂等**：相同渠道事件 ID、导入任务唯一键或同一幂等键 → 阻止重复写入，不算新线索。
2. **疑似重复录入**：同一联系人、同一需求、相近时间 → 仅提示疑似重复，员工可保留新线索或关联既有记录，不擅自删除。
3. **同企业多次不同需求**：允许保留多条线索并关联同一企业；不能以公司相同为由拦截新线索。

规范化：邮箱小写去空格、电话去格式符保留国际区号、企业名去多余空白。手机号/邮箱只是辅助匹配证据，不能单独证明两家企业相同；企业名做规范化候选匹配，人工确认跨企业合并（限管理员，需预览影响 + 保留原始快照 + 审计）。不要把一次公司匹配当作必然正确的客户事实。

## 7. 状态机（三个正交维度，PRD §6）

线索不再是一条线性状态链，而是三个正交状态：

- `qualification_status`（需求真实性）：`pending`(待确认，默认) / `valid`(有效) / `invalid`(无效，必填原因)。
- `handoff_status`（交接）：`not_handed_off`(默认) / `handed_off`。
- `outcome_status`（进展反馈）：`unknown`(暂无反馈，默认) / `in_progress`(推进中) / `won`(已成交) / `lost`(未成交) / `deferred`(暂缓)。

约束：新线索无需部门/客户；**只有有效（valid）线索可交接**；未交接不得填写正式部门结果；撤销有效或改派必须审计并保持字段一致；交接后市场部仍可查看、更新业务进展；部门对接人是记录对象，不要求其登录。`company_id` 可空；企业归属变化不能覆盖 `company_name_raw` 与来源快照。

判定有效（`qualification_status → valid`）的数据流：若线索 `company_id` 为空且含 `company_name_raw`，`services/decision_service.qualify` 先做规范化企业匹配（`company_service.match_company`）——命中则关联既有企业；未命中则自动创建企业并关联（`company_service.create_company`）。该自动关联在同一事务内提交，不覆盖 `company_name_raw` 与来源快照，且不单独写企业关联事件（随 `lead.qualification` 事件落 `lead_events`）。

## 8. 权限模型（RBAC，PRD §2）

两角色：`admin`（管理员）、`market`（市场部）。服务端逐条校验，不依赖前端隐藏按钮。market 零隔离：查看范围覆盖全部线索与全部报表数据，不按部门/归属人过滤。

| 资源 | market | admin |
|---|---|---|
| 线索 | 全部：创建/导入/查看/跟进/判断/交接/反馈（看全部线索） | 全部 + 归档/撤销误操作 |
| 企业 | 查看/非阻塞关联（可选创建候选） | 全部 + 合并（审计 + 影响预览） |
| 联系人 | 查看/新增 | 全部 |
| 跟进活动 | 新增/查看；修正与撤销仅限本人创建 | 全部 + 修正/撤销任意记录（审计留痕） |
| 交接/反馈 | 有效线索可交接；补录反馈 | 全部 + 授权更正（保留历史） |
| 字典/来源/需求类型/AI 配置 | 只读（AI 密钥不可见） | 全部（写/删 + 审计） |
| 用户管理 | 无 | 全部 |
| 报表/导出 | 看全部数据（无部门隔离）；导出受控 + 审计 | 全部 |

约束：不设「初筛负责人」字段；仅记录创建人/操作人；跟进活动撤销与修正权限 = 创建者本人或 admin（ADR-031）；无公开注册；管理员创建账号设初始密码并强制改密；禁用账号立即撤销会话。

## 9. 幂等、并发与事务

- 创建/跟进/交接/反馈请求接受幂等键，重复提交返回首次结果，不重复计数。
- 并发更新用 `version`/`updated_at` 乐观锁，冲突返回 `409`。
- 关键写操作（判断、交接、反馈、企业关联/合并、撤销、归档）在事务内完成并写 `lead_events`/`audit_logs`。
- 计数（电话/微信）由有效事件实时聚合或由事务维护，避免计数与明细不一致。

## 10. AI 增强（可选非阻塞，PRD §9）

`backend/app/ai/` 提供统一 Provider 适配层（OpenAI 兼容 Chat Completions），V1.4 用于「智能新增线索」字段提取（`POST /leads/parse`）：从粘贴原文抽取公司名称/姓名/手机号/邮箱/需求描述/需求类型/来源渠道并附置信度（high/medium/low）。**AI 只提取、不落库、不创建客户/线索**；需求类型仅在系统字典 `lead_need_types` 匹配时才返回，否则置空。

配置从 `app_settings`（键 `ai_provider`，JSONB：endpoint/model/api_key/timeout_seconds，密钥仅写入不读回，响应 mask）或环境变量 `AI_PROVIDER_ENDPOINT`/`AI_PROVIDER_MODEL`/`AI_PROVIDER_API_KEY`/`AI_PROVIDER_TIMEOUT` 读取，密钥绝不硬编码、绝不落日志。未配置/超时/解析失败返回 503 `AI_UNAVAILABLE`，不影响任何 CRM 基础业务。识别失败仍可手动创建线索（ADR-029）。

## 11. 审计与日志

关键动作审计：判断（有效/无效）、部门交接、进展反馈、企业关联/解除/合并、活动撤销、用户权限变更、受控导出。审计含操作人、时间、对象、前后值（`lead_events`）与 `request_id`；敏感字段（手机号/邮箱/API Key）脱敏；日志不记录明文 PII 与会话密钥。请求 ID 贯穿前端→Nginx→后端→审计。

## 12. 安全

- 会话：HttpOnly + SameSite Cookie；生产 `Secure=true`；CSRF 双提交 Cookie（ADR-016，全环境强制）；服务端会话可撤销、空闲/绝对超时。
- 密码：Argon2id；登录限流；密钥从环境/密钥管理注入。
- 输入：Pydantic 校验、SQL 参数化、输出转义；导入限格式（.xlsx/.csv）、大小与行数；导出转义 Excel 公式注入前缀。
- 边界：Nginx HTTPS；CORS 限制来源；数据库不暴露公网；健康检查不泄露配置与客户信息。

## 13. 测试策略（PRD §9）

- 后端 Pytest：模型/服务单测 + API 集成测试 + 越权用例（未登录、角色、ID 枚举、重复提交、并发修改、输入边界、幂等）。
- 前端 Vitest：组件/工具单测。
- Playwright：核心 E2E（登录改密、无企业建线索、企业匹配、快捷跟进计数、判断/交接/反馈、越权被拒）。
- CI：`vue-tsc`/`eslint`/`vitest`/`vite build`（前端）；`ruff` + `pytest --cov-fail-under=70`（后端）；Playwright。

## 14. 部署架构（PRD §9）

Docker Compose 编排 `db`（PostgreSQL，持久卷 + 健康检查）、`backend`（FastAPI/Uvicorn）、`frontend`（构建后静态资源）、`nginx`（HTTPS 反代 + 日志轮转）。环境变量经 `.env` 注入；初始管理员由 `app/seed.py` 幂等种子（凭据环境变量注入，不进迁移、不硬编码）。备份与恢复、升级与迁移、回滚见 `docs/deployment.md`。

## 15. 兼容迁移策略（对齐 docs/v1.4-migration-plan.md）

迁移链 7 个 revision 线性单链，可 `upgrade`/`downgrade` 往返：

- `cdff02953343`：建 `users`/`user_sessions`/`audit_logs`。
- `e62b96822f83`：建 V1.3 业务表（`companies` 起，含状态机三维字段）。
- `7ad73d5f13fb`：`leads` 外部事件唯一索引。
- `3c5c7d4916c9`：`leads` 加 `notes`。
- `b1e974ca9835`：`companies` 加 `phone`/`website`。
- `a3f1e2d4c5b6`：V1.4 联系事件重构（`lead_activities` 废 `phone_count`、加 `result`）+ 建 `lead_parse_records`/`lead_event_revisions`/`app_settings`。
- `f1a2b3c4d5e6`：`leads` 加 `next_follow_up_at`。

- **保留不动**：`users`/`user_sessions`/`audit_logs` 及 V1.3 全部业务表，历史账号/字典不重建。
- **users.role 去 sales**：不改字段/表，仅 seed 与创建用户逻辑不再创建 sales 账号。
- **无破坏性变更**：不 drop、不 truncate、不清空数据；`lead_activities` 仅删 `phone_count`（历史数据为空，安全）并加 `result`。
