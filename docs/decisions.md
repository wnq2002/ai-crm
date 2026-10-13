# AI CRM 架构决策记录（ADR）

> 版本：1.4 · 需求基线已切换为 `docs/PRD.md`（V1.4，替换 V1.3）。
> 本文记录所有开放决策的上下文、选项与结论；新增决策追加在末尾沿用编号。实现默认采用 PRD 默认值，不随意创造功能或改变流程。
> V1.0 时期的部分决策（涉及商机/任务/销售分配）已被 V1.3 取代，见文末「已废弃」清单。

## 持续有效的架构决策

### ADR-001 单体前后端分离而非微服务

- **状态**：已接受
- **结论**：前端 SPA + 单 FastAPI 服务 + 单 PostgreSQL，单一服务承载全部业务与权限。
- **影响**：垂直扩展优先；后续需更高吞吐再评估异步（ADR-002）。

### ADR-002 同步 SQLAlchemy 事务起步

- **状态**：已接受
- **结论**：FastAPI 同步 `def` + SQLAlchemy 2.x 同步 Session，事务边界在 service 层。
- **影响**：请求简单可控；暂不引入 asyncpg/异步引擎。

### ADR-003 会话用 HttpOnly Cookie 而非 localStorage JWT

- **状态**：已接受
- **结论**：服务端会话（Cookie 承载会话 ID），配合 CSRF；可即时撤销。
- **影响**：前端 axios 同源 Cookie；登出/禁用即时撤销。

### ADR-004 密码哈希用 Argon2id

- **状态**：已接受
- **结论**：`argon2-cffi` Argon2id + 登录限流。

### ADR-005 主键统一 UUID

- **状态**：已接受
- **结论**：全部业务表主键 `UUID`，字符串形式对外暴露，防 ID 枚举。

### ADR-006 归档/带审计撤销而非物理删除

- **状态**：已接受（V1.3 措辞更新）
- **结论**：V1.3 用 `leads.archived_at` 归档、`lead_activities.revoked_at` 撤销、`companies.merged_into_id` 合并，历史保留。
- **影响**：列表默认过滤已归档/已撤销；审计保留完整轨迹。

### ADR-007 AI 采用服务端可插拔 Provider（V1.3 降级为可选摘要/交接草稿）

- **状态**：已接受（V1.3 范围收紧）
- **结论**：`backend/app/ai/` 仅提供「客户摘要」与「交接摘要草稿」；未配置/超时返回 `AI_UNAVAILABLE`，不阻断主流程。
- **影响**：不得未经确认改写客户信息/状态或自动对外发送；正式接入前完成合规评估与脱敏。

### ADR-008 HTTP 客户端选 Axios

- **状态**：已接受
- **结论**：前端统一 Axios 封装，集中处理错误、请求 ID、401 拦截、CSRF 头。

### ADR-009 Alembic 为唯一结构变更入口

- **状态**：已接受
- **结论**：任何表/字段/索引/约束/枚举变更必须新增 Alembic revision 并同步文档。

### ADR-011 不引入 Redis / 向量库 / 知识图谱 / 复杂 Agent 框架

- **状态**：已接受
- **结论**：AI 直接 HTTP 调用 Provider，不建向量检索、不做知识图谱。

### ADR-014 request_id 来源与复盘资产落盘

- **状态**：已接受
- **结论**：`request_id` 服务端生成并贯穿审计；客户端 `X-Request-Id` 可回显。复盘落盘 `ai-crm/docs/retrospectives/`。

### ADR-015 工具链标准（lint/typecheck/测试门禁）

- **状态**：已接受
- **结论**：后端 `ruff` + `pytest --cov-fail-under=70`（mypy 可选）；前端 `vue-tsc`/`eslint`/`vitest`/`vite build`；E2E Playwright。

### ADR-016 CSRF 防护：双提交 Cookie 模式

- **状态**：已接受
- **结论**：登录下发非 HttpOnly `csrf_token` cookie；写操作回传 `X-CSRF-Token` 校验；全环境强制，不提供关闭开关。

### ADR-017 服务端会话落库 + 初始管理员种子 + 初始迁移范围

- **状态**：已接受（V1.3 沿用，role 仅 admin/market）
- **结论**：会话落 `user_sessions`（DB 存 SHA-256 摘要）；初始管理员 `app/seed.py` 幂等种子；初始迁移建 `users`/`user_sessions`/`audit_logs`。
- **影响**：seed 与创建用户逻辑不再创建 sales 账号（V1.3）。

## V1.3 新增决策

### ADR-018 V1.3 基线切换：线索优先，删除商机/任务/销售分配

- **状态**：已接受
- **背景**：`AI_CRM_V1.3_线索优先_产品需求与交付规范.md` 替换 V1.0 为唯一需求源。
- **结论**：删除 `opportunities`/`tasks`/`followups`/`lead_assignments` 等 V1.0 概念与契约；引入 Company/Activity/Handoff/Outcome；线索状态机重构为三维正交（ADR-021）。
- **影响**：见 `docs/v1.3-migration-plan.md`；ADR-010/012/013 废弃（见文末）。

### ADR-019 去重分三个层次

- **状态**：已接受
- **结论**：①技术幂等（渠道事件 ID/导入唯一键/幂等键）阻止重复写入；②疑似重复录入仅提示、不擅自删除；③同企业多次不同需求允许保留多条线索。
- **影响**：手机/邮箱仅辅助匹配证据，不能单独证明两企业相同；企业名做规范化候选匹配，人工确认合并。

### ADR-020 企业名称选填 + 非阻塞企业匹配

- **状态**：已接受
- **结论**：`company_id` 可空；先成功保存线索，再返回「可能关联企业」非阻塞提示；无企业信息也可录入（页面显示「企业待补全」）。
- **影响**：企业归属变化不能覆盖 `company_name_raw` 与来源快照。

### ADR-021 线索状态机三维正交

- **状态**：已接受
- **结论**：`qualification_status`(pending/valid/invalid) × `handoff_status`(not_handed_off/handed_off) × `outcome_status`(unknown/in_progress/won/lost)，取代 V1.0 线性状态。
- **影响**：仅 `valid` 可交接；未交接不得填正式部门结果；撤销有效/改派需审计并保持字段一致。

### ADR-022 角色缩减为 market/admin

- **状态**：已接受
- **结论**：弃用 `sales`；`users.role` 为 String，不删字段/表，仅不再创建 sales 账号；不设「初筛负责人」字段。

### ADR-023 录入方式与来源渠道分离

- **状态**：已接受
- **结论**：`intake_method`(manual/import/api) 与 `source_category`/`source_detail` 严格区分；手动录入官网来源时来源仍为「官网」、录入方式为「手动」。

### ADR-024 企业合并限管理员

- **状态**：已接受
- **结论**：合并仅 admin，需预览影响、保留原始线索快照与审计；模糊匹配不直接合并。

### ADR-025 保留 `/api/v1` 前缀

- **状态**：已接受
- **背景**：V1.3 PRD §8 以 `/api/...` 为路径简写；已建后端（`/auth/*`、`/admin/users`）部署于 `/api/v1` 且联调 PASS。
- **结论**：延续 `/api/v1` 前缀，避免破坏已建认证与前端 axios 基址；若需严格 `/api` 仅需改 `api_v1_prefix` 配置。

### ADR-026 兼容迁移（纯新增，无破坏性变更）

- **状态**：已接受
- **结论**：保留 `users`/`user_sessions`/`audit_logs`（revision `cdff02953343`）；新增 revision `e62b96822f83` 建全部 V1.3 业务表；不 drop/truncate/清空数据；未来若现历史数据先出搬迁迁移。

## V1.4 新增决策

### ADR-027 联系事件沿用 `lead_activities`（重构语义）

- **状态**：已接受
- **背景**：V1.3 的 `lead_events` 是通用审计事件（before/after JSON），V1.4 需求里的「联系事件」（电话/微信三态）语义不同。若为 V1.4 新建独立表并重命名，将引发外键与代码大面积改动。
- **结论**：联系事件沿用 `lead_activities` 表名，仅重构其字段语义（废 `phone_count` 累计、加 `result`、微信三态子类型）；`lead_events` 保持「审计事件」职责不变，避免双表重命名。
- **影响**：电话总次数/微信互动数由 `lead_activities` 有效事件实时聚合，不信任前端累计值。

### ADR-028 微信关系状态由事件实时派生

- **状态**：已接受
- **背景**：微信好友关系（待通过/已通过）若落冗余列，易与事件历史不一致。
- **结论**：`wechat_relationship`（none/pending/approved）由最新一条有效微信事件实时派生（最新为 `wechat_request`→pending，`wechat_approved`/`wechat_chat`→approved），不落列。
- **影响**：`LeadDetail` 暴露派生字段；`wechat_chat` 仅在关系为已通过时允许记录。

### ADR-029 AI 配置存服务端 `app_settings`（密钥仅写不读回）

- **状态**：已接受
- **背景**：V1.4 系统设置新增「AI 配置」，管理员配置 AI Provider（provider/endpoint/model/超时/密钥）；市场人员可读配置但绝不可见密钥。AI 智能识别（M2）由 `backend/app/ai/` Provider 适配层消费该配置。
- **结论**：
  - 存储位置：`app_settings` 表（已由迁移 `a3f1e2d4c5b6` 建表），`key = "ai_provider"`，`value`（JSONB）结构：

    ```json
    {
      "provider": "openai",
      "endpoint": "https://api.openai.com/v1",
      "model": "gpt-4o",
      "api_key": "sk-xxx",
      "timeout_seconds": 30
    }
    ```

  - 端点：`GET /api/v1/settings/ai`（admin/market 可读）、`PUT`/`POST /api/v1/settings/ai`（仅 admin，需 CSRF）。
  - 密钥处理：读取响应 `api_key` 字段返回脱敏占位 `"***configured***"`（未配置则 `null`），并额外返回 `api_key_configured: bool`；真实密钥永不回传、不写日志、不落审计。
  - 写入 `api_key` 语义：`null` → 保留现有密钥（编辑其它字段无需重传）；非空字符串 → 覆盖；空字符串 → 清除。
  - 审计：写操作记录 `audit_logs`，`action="settings.ai_update"`、`resource_type="app_setting"`、`resource_id="ai_provider"`，before/after 均脱敏（api_key 仅记 `"***configured***"` 或 `null`）。
  - 后端读约定：`backend/app/ai/` Provider 适配层统一读 `app_settings` 的 `ai_provider` 键（或经 `app.services.app_setting_service.get_ai_config`），不得自行另建存储。
- **影响**：AI 未配置/密钥缺失时返回 `AI_UNAVAILABLE`，不阻断主流程（沿用 ADR-007/ADR-011）。

### ADR-030 数据统计「线索数量」与「事件数量」口径分离

- **状态**：已接受
- **背景**：V1.4 数据分析需区分「线索」与「跟进事件」两类统计，混用时间口径会得出错误指标。
- **结论**：线索数量按 `leads.occurred_at`、事件数量按 `lead_activities.happened_at`、移交按 `lead_handoffs.happened_at`、反馈按 `lead_outcome_events.feedback_at` 分别口径；全部来自真实业务数据，不落冗余累计列。
- **影响**：核心指标、趋势时序、渠道×部门分析、明细与导出均遵循该口径；电话/微信计数由有效事件实时聚合。

### ADR-031 V1.4 三项范围/权限裁决

- **状态**：已接受
- **背景**：V1.4 交付过程中对三项存在分歧的点做出最终裁决，作为实现与验收的统一口径。
- **结论**：
  1. **market 零隔离**：market 查看范围覆盖全部线索与全部报表数据，不按部门/归属人过滤。
  2. **撤销/修正权限 = 创建者本人或 admin**：跟进活动的撤销与修正仅限创建者本人或 admin，其余角色 403。
  3. **seed 来源分类保持现状**：种子来源分类维持「官网/其他」两分类，后台可配置新增，不在 seed 写死「演讲/展会」等。
- **影响**：与 `docs/api-contract.md` §12 若存在 market 范围矛盾，统一为「market 看全部」；跟进活动权限以本裁决为准。

## 已废弃（V1.0 历史，仅存档）

- **ADR-010（后台定时作业/逾期任务）**：V1.3 删除任务概念，无逾期检查，废弃。
- **ADR-012（start-following + 商机重开）**：V1.0 专属动作，随商机/销售管线删除而废弃。
- **ADR-013（销售管线需求澄清）**：V1.0 专属澄清，被 V1.3 基线取代。
