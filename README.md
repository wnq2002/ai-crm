# AI CRM V1.3

面向市场部的「线索优先管理系统」（广州云物智能科技有限公司）。以市场部接收咨询为主线，覆盖线索创建（企业名称可空）、Excel/CSV 导入、企业自动关联与去重、快捷跟进（电话/微信 +1）、需求初筛、部门交接与进展反馈、数据分析与汇报，并提供可选 AI 增强（客户摘要/交接草稿）。

> 交付目标：可上线使用的真实业务系统，非静态原型或演示数据系统。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Vue Router + Pinia + Axios |
| 后端 | Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic |
| 数据库 | PostgreSQL 16+ |
| 测试 | Pytest + Vitest + Playwright |
| 部署 | Nginx + Docker Compose |

## 目录结构

```
ai-crm/
├── AGENTS.md           # 开发契约（必读）
├── README.md
├── docs/               # PRD / architecture / api-contract / acceptance / decisions / deployment
├── frontend/           # Vue 3 SPA
│   └── src/{api,components,layouts,router,stores,views,types,utils}/
├── backend/            # FastAPI 服务
│   ├── app/{api,core,models,schemas,services,repositories,auth,ai}/
│   ├── migrations/     # Alembic 迁移
│   └── tests/
├── infra/nginx/        # 反向代理配置
├── compose.yaml
└── .env.example
```

## 文档索引

- 需求基线：`docs/PRD-v1.3-source.md`（迁移方案 `docs/v1.3-migration-plan.md`）
- 系统架构与数据模型：`docs/architecture.md`
- REST API 契约：`docs/api-contract.md`
- 验收标准：`docs/acceptance.md`
- 架构决策记录（ADR）：`docs/decisions.md`
- 生产部署：`docs/deployment.md`
- 操作手册：`docs/operations.md`

## 本地开发

> 命令以最终基础工程落地为准，此处为约定入口。所有敏感值由本地 `.env` 提供（复制 `.env.example` 生成，勿提交）。

```bash
# 1. 环境变量
cp .env.example .env   # 填写占位值

# 2. 启动依赖（PostgreSQL）
docker compose up -d db

# 3. 后端（FastAPI）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
export ADMIN_INITIAL_PASSWORD='ChangeMe123!'   # 仅空库首次 seed 创建 admin
python -m app.seed                              # 初始化 admin + 业务字典（幂等）
uvicorn app.main:app --reload --port 8000

# 4. 前端（Vite）
cd frontend
npm install
npm run dev

# 5. 测试（后端需先装 dev 依赖）
cd backend && pip install -r requirements-dev.txt && pytest
cd frontend && npm run typecheck && npm run lint && npm run test
```

## 快速部署

```bash
cp .env.example .env                  # 填入真实凭据（凭据只进 .env，不提交）
./infra/certs/generate-selfsigned.sh  # 本地/冒烟用自签名证书（生产换 CA 证书）
docker compose up -d --build          # 一键启动：迁移 + 构建 + 反代
docker compose ps                     # 确认四服务 healthy

# 冒烟：存活 / 就绪 / 权限探针
curl -fsS http://localhost/healthz     # → ok（Nginx 存活）
curl -fsS http://localhost/readyz      # → ok（全栈就绪，Nginx→后端）
curl -fsS https://localhost/healthz -k # → ok（HTTPS）
```

详见 `docs/deployment.md`。
