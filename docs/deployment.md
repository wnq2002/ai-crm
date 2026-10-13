# AI CRM V1.3 生产部署指南

> 版本：1.3 · 状态：部署骨架 + 备份恢复演练已完成（M8）。
> 关联：`docs/PRD-v1.3-source.md` §9/§10/§12、`docs/architecture.md`、`AGENTS.md` §3 安全铁律。

## 1. 服务器环境要求

- 操作系统：Linux（Ubuntu 22.04+ / Debian 12+ 均可），x86_64 或 arm64。
- 运行时：Docker Engine 24+、Docker Compose v2（`docker compose`）。
- 端口：对外仅开放 `80`、`443`；`5432`（PostgreSQL）仅绑定 `127.0.0.1` 用于本地调试，生产不暴露公网。
- 域名与 TLS 证书：正式域名、受信任 CA 证书（`fullchain.pem` + `privkey.pem`）。
- 磁盘：PostgreSQL 数据卷 + Nginx 日志卷，预留备份空间。

## 2. 环境变量与凭据注入

- 复制 `.env.example` 为 `.env`，填入真实值；`.env` 已在 `.gitignore` 排除，绝不提交。
- 所有凭据（数据库密码、`SECRET_KEY`、AI API Key、TLS 私钥）只进 `.env` / 服务器本地文件，通过环境变量注入，不硬编码、不入文档。
- 关键变量：

| 变量 | 说明 |
|---|---|
| `POSTGRES_USER/PASSWORD/DB` | 数据库账号/密码/库名 |
| `DATABASE_URL` | SQLAlchemy 连接串；本地开发为 `localhost`，容器内由 compose 覆盖为 `db` |
| `SECRET_KEY` | 会话签名密钥，生产用随机 64 字节 |
| `COOKIE_SECURE` | 生产 `true`（HTTPS 下 Secure Cookie） |
| `CORS_ORIGINS` | 允许的来源，生产收敛为正式域名 |
| `ADMIN_INITIAL_PASSWORD` | 初始管理员种子密码，仅空库首次 `app.seed` 使用；未设置则跳过创建 admin |
| `AI_PROVIDER_*` | AI 可选，未配置则 AI 能力返回不可用，不影响 CRM 业务 |

## 3. compose.yaml 服务与持久化卷

| 服务 | 镜像/构建 | 职责 | 持久化 |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 唯一数据源，健康检查 `pg_isready` | 卷 `pgdata` |
| `backend` | `build: ./backend` | FastAPI/Uvicorn，启动先 `alembic upgrade head` | 无（无状态） |
| `frontend` | `build: ./frontend` | 一次性构建静态资源到 `frontend/dist` | 宿主机 `./frontend/dist` |
| `nginx` | `nginx:1.27-alpine` | HTTPS 反代 + 静态托管 | 卷 `nginx_logs` |

- 镜像版本固定（`postgres:16-alpine`、`nginx:1.27-alpine`、`python:3.12`、`node:20`），禁止 `latest`。
- 后端不对外暴露端口，仅 nginx 反代访问；数据库仅容器网络内可达。

## 4. Nginx HTTPS 与边界

配置见 `infra/nginx/app.conf`：

- HTTP(80) 一律 301 跳转 HTTPS(443)，保留 `/.well-known/acme-challenge/` 供证书签发/续期。
- TLS 1.2/1.3；证书/私钥挂载自 `infra/certs/`（`fullchain.pem` + `privkey.pem`）。
- `/` 托管 SPA（history 路由回退 `index.html`）；`/assets/` 长缓存。
- `/api/` 反代到 `backend:8000`，透传 `X-Request-Id`（ADR-014 request_id 贯穿）。
- `client_max_body_size 12m`：Excel/CSV 导入 ≤10MB 预留 multipart 余量。
- 健康检查：`/healthz`（Nginx 存活，直接 200 不泄露配置）、`/readyz`（全栈就绪，反代后端 `/healthz`）。
- 安全头：`X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`。
- **访问日志 PII 脱敏**：`log_format` 只记 `$request_method $uri`（去 query），不记录 query string，避免线索搜索的手机号/邮箱进入日志（PRD V1.3 §9）。
- CORS：后端按 `CORS_ORIGINS` 白名单限制，生产收敛为正式域名。

## 5. 一条命令初始化部署 + 冒烟测试

```bash
cp .env.example .env                  # 1. 填入真实凭据（含 ADMIN_INITIAL_PASSWORD）
./infra/certs/generate-selfsigned.sh  # 2. 本地/冒烟用自签名证书（生产换 CA 证书）
docker compose up -d --build          # 3. 一键启动：迁移 + 构建 + 反代
docker compose ps                     # 4. 确认四服务 healthy
curl -fsS http://localhost/healthz    # 5. Nginx 存活探针 → ok
curl -fsS http://localhost/readyz     # 6. 全栈就绪探针（Nginx → 后端）→ ok
curl -fsS https://localhost/healthz -k # 7. HTTPS 存活探针
```

冒烟判定：`db/backend/frontend/nginx` 全部 healthy；`/healthz`、`/readyz` 返回 200；`/api/v1/auth/me` 未登录返回 401（服务端权限生效）。

**初始化内容**：`alembic upgrade head` 建表 → 应用 lifespan 触发 `app.seed`（创建初始管理员 + 业务字典：部门/对接人/来源分类/需求类型）。种子仅在「空库且 `ADMIN_INITIAL_PASSWORD` 已设置、无 admin」时创建管理员；市场部账号由管理员登录后经 `/admin/users` 创建（无公开注册）。数据库为空时展示空状态，初始化仅有管理员账号，无虚构客户/线索/商机。

> 重新部署（代码变更后）：`frontend` 为一次性构建服务（`restart: "no"`），需 `docker compose up -d --build --force-recreate` 强制重建，或先 `docker compose rm -f frontend` 再 `up -d --build`。

## 6. 数据库备份与恢复

脚本：`infra/backup/backup.sh`（`pg_dump -Fc`）、`infra/backup/restore.sh`（`dropdb`→`createdb`→`pg_restore`）。

### 6.1 备份

```bash
# 宿主机（连接经 PG* 环境变量注入）
PGHOST=127.0.0.1 PGUSER=postgres PGDATABASE=ai_crm ./infra/backup/backup.sh /var/backups/ai-crm

# Docker Compose
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > backup.dump
```

建议 cron 每日一次，`pg_dump -Fc` 自定义格式，按日保留 14 份，异地同步备份目标。

### 6.2 恢复

```bash
# 宿主机
PGHOST=127.0.0.1 PGUSER=postgres PGDATABASE=ai_crm ./infra/backup/restore.sh backup.dump

# Docker Compose
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < backup.dump
```

### 6.3 恢复演练记录（2026-10-10 实测，真实 PostgreSQL）

- 环境：本机 PostgreSQL 16.15（127.0.0.1:5432），演练库 `ai_crm_drill`。
- 初始化：`alembic upgrade head`（5 个 migration：`cdff02953343`→`e62b96822f83`→`7ad73d5f13fb`→`3c5c7d4916c9`→`b1e974ca9835`）+ `python -m app.seed`。
- 种子态：`users=1`(admin)、`departments=3`、`department_contacts=3`、`lead_source_categories=8`、`lead_need_types=2`；`leads/companies/activities/handoffs/outcome_events=0`（无 Mock 业务数据）。
- 备份：`pg_dump -Fc` → `ai_crm_drill-20261010-115044.dump`（44K）。
- 清库：`dropdb --if-exists` + `createdb`（空库）。
- 恢复：`pg_restore --clean --if-exists --no-owner --exit-on-error`。
- 校验：恢复后各表行数与备份前完全一致，`users` 中 `admin` 账号存在。**结果 PASS。**

## 7. Alembic 迁移的升级与回滚

- 升级：容器启动自动执行 `alembic upgrade head`（全新库一条命令初始化建表）。
- 回滚：`docker compose exec backend alembic downgrade -1`（逐版本）或 `alembic downgrade <rev>`。
- 结构变更必须新增迁移（ADR-009）；CI 执行 up/down roundtrip 校验可回滚。
- 数据初始化：`python -m app.seed`（幂等，可重复执行；只补缺，不覆盖既有 admin 与字典）。

## 8. 日志轮转与审计保留

- 容器 stdout/stderr：compose 已配 `json-file` 驱动 `max-size=10m`、`max-file=3`。
- Nginx 访问/错误日志：写入卷 `nginx_logs`，宿主 logrotate 用 `infra/nginx/logrotate.conf`（daily、rotate 14、compress）；访问日志已去 query（见 §4 PII 脱敏）。
- 审计日志（`audit_logs` 表）与日志不记录密码、完整邮箱/手机号、API Key（脱敏）。

## 9. 上线前需业务方明确配置（默认值不阻塞开发）

- 部门与默认对接人：seed 预置 `GDC/同事A、Token 供应链/同事B、润效营/同事C`，为可编辑配置，上线前由管理员确认名单。
- 线索来源分类/详情、需求类型：seed 预置，可维护启停，不将需求类型自动绑定到部门。
- 市场部账号与角色：由管理员创建（无公开注册），上线时按实际人员建号。
- 产品知识库与 AI 服务：可后补，不阻碍基础 CRM 发布。
- 公司环境：正式域名、TLS 证书、服务器、备份目标、实际用户规模须在部署前落实。

> 上线前业务合规确认：对联系人信息遵循最小必要、授权访问、保留期限与删除更正规则。
