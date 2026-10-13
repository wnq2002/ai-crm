# AGENTS.md — AI CRM V1.3 开发契约（市场部线索优先管理系统）

本文档是仓库内所有编码 Agent（含 Codex / Claude Code / 人工开发者）必须遵守的硬性约束。任何实现若违反本文，视为不合格，不得合并。

## 1. 单一需求源

- 唯一需求基线是 `docs/PRD.md`（即 `AI_CRM_V1.3_线索优先_产品需求与交付规范.md` 的落盘副本，替换 V1.0）。
- 所有功能范围、字段、状态机、权限、验收标准一律以 PRD 为准。遇到歧义，优先采用 PRD 默认值，并把决策记入 `docs/decisions.md`，不得自行发挥。
- 禁止凭记忆或推测添加 PRD 未要求的功能、字段、页面或模块。

## 2. 硬性红线

1. **禁止 Mock 伪装正式功能**：不得用前端静态数据、内存假数据、随机种子数据冒充已实现的真实功能。数据库为空时必须展示空状态；初始化只允许存在管理员账号，不得虚构客户、线索等业务数据。
2. **禁止无要求增加模块**：不得引入 PRD 明确不做的范围（V1.3 §1「明确不做」：销售商机/报价/合同/收款、初筛负责人流程、主动爬取/自动外呼/群发、多租户 SaaS、Redis、向量库、知识图谱、复杂 Agent 框架等）。
3. **端到端连通**：每个功能必须连通「前端 UI → API → 数据库 → 权限校验 → 测试」全链路，缺一不可。
4. **迁移强制**：任何数据结构变更（加字段/表/索引/约束/枚举）必须写 Alembic migration，并同步更新 `docs/architecture.md` 数据模型章节与 `docs/api-contract.md`。严禁仅在代码里建表或在启动时随意重建数据库。
5. **权限服务端强制**：访问范围必须在服务端逐条校验，禁止仅靠前端隐藏按钮。普通市场人员不得通过猜对象 ID 读取他人数据。

## 3. 安全铁律

- 凭据（数据库密码、AI API Key、TLS 私钥等）只允许以占位符形式出现在本地 `.env` / `.env.example`，通过环境变量注入。
- **绝不**把任何密钥硬编码进代码、提交进文档、写进提示词或 Git 历史。`.env` 加入 `.gitignore`。
- 密码使用 Argon2id 或等效可信算法；登录会话放 HttpOnly + SameSite Cookie，生产 `Secure=true`；不把长期身份令牌放 localStorage。
- 输入必须 Pydantic 校验、SQL 参数化、输出转义；Excel 限大小（10 MB）与行数（5000 行/次），阻断公式注入与危险附件；CSV 导出防公式注入。
- 审计日志不记录密码、完整邮箱/手机号、API Key（脱敏）。

## 4. 技术栈（已确定，不得擅自更换）

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Vue Router + Pinia + Axios |
| 后端 | Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic |
| 数据库 | PostgreSQL 16+ |
| 测试 | Pytest + Vitest + Playwright |
| 部署 | Nginx + Docker Compose |
| AI | 服务端可插拔 Provider（可选：客户摘要/交接草稿，停机不影响主流程） |

依赖锁定在受支持稳定版本并记录版本，禁止部署时拉取 `latest`。

## 5. 目录约定

```
ai-crm/
├── AGENTS.md                 # 本文件
├── README.md                 # 项目说明与本地开发命令
├── docs/                     # PRD.md / architecture.md / api-contract.md / acceptance.md / decisions.md / deployment.md
├── frontend/src/{api,components,layouts,router,stores,views,types,utils}/
├── backend/app/{api,core,models,schemas,services,repositories,auth,ai}/
├── backend/migrations/       # Alembic 迁移（强制）
├── infra/nginx/
├── compose.yaml
└── .env.example
```

后端分层：`api/`（路由与依赖注入）→ `services/`（业务逻辑与事务）→ `repositories/`（数据访问）→ `models/`（SQLAlchemy ORM）；`schemas/`（Pydantic 请求/响应）；`core/`（配置、安全、数据库会话、日志）；`auth/`（鉴权与 RBAC）；`ai/`（Provider 适配层）。

## 6. 每个切片的完成定义（DoD）

一个功能切片只有同时满足以下条件才算完成，才可标记对应 task 为 completed：

1. 有对应的 Alembic migration 且可正向/回滚。
2. 有服务端 API 与 Pydantic 校验、分页/排序、权限校验、审计（如属关键动作）。
3. 有前端页面/组件接入真实 API（无 Mock）。
4. 有自动化测试：后端 Pytest（含权限越权用例）+ 前端 Vitest 单元 + 核心路径 Playwright E2E。
5. 有相关文档更新（architecture / api-contract / acceptance）。
6. 本地或 CI 可运行验证（附实际命令与结果）。

## 7. 协作与提交

- 按 `docs/architecture.md` 的切片顺序与接口契约实现；跨切片依赖先读契约再编码。
- 提交信息说明「为什么」而非流水账；禁止提交 `.env`、密钥、本地产物、`node_modules`、`__pycache__`。
- 不得宣称未测试的部分已可上线；交付必须附「实际运行命令 + 已通过测试 + 仍未完成项」。
