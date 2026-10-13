#!/usr/bin/env bash
#
# AI CRM V1.0 — QA Gate 脚本（质量门禁）
# 用于 #4「基础工程与登录鉴权」及后续切片收尾。
#
# 用法：
#   bash docs/qa-gate.sh backend    # 后端：真 PostgreSQL 集成 + pytest 覆盖率 + ruff（lint+format）
#   bash docs/qa-gate.sh frontend   # 前端：typecheck(vue-tsc) + lint(eslint) + vitest + build(vite build)
#   bash docs/qa-gate.sh e2e        # Playwright 核心 E2E
#   bash docs/qa-gate.sh all        # 全部（默认）
#
# 前置约定（按 ADR-015 唯一口径；缺失即 Gate 失败）：
#   - backend/requirements-dev.txt 含 pytest, pytest-cov, ruff, httpx, psycopg；mypy 可选
#   - backend/pyproject.toml（或 pytest.ini/setup.cfg）配好 pytest 与覆盖率路径
#   - frontend/package.json 提供 typecheck(vue-tsc) / lint(eslint) / test(vitest) / build(vite build) 脚本
#   - 集成测试打真 PostgreSQL（compose db 服务），严禁 mock 数据库
#   - backend/tests/conftest.py 负责测试库生命周期（建库 / 迁移 / 每测试事务回滚）
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
COVERAGE_THRESHOLD="${COVERAGE_THRESHOLD:-70}"

log()  { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
fail() { printf '\033[1;31m[GATE FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

gate_backend() {
  log "后端 Gate"
  [ -f "$BACKEND/pyproject.toml" ] || [ -f "$BACKEND/pytest.ini" ] || [ -f "$BACKEND/setup.cfg" ] \
    || fail "缺少 pytest 配置（pyproject.toml / pytest.ini / setup.cfg）"
  [ -f "$BACKEND/requirements.txt" ] || fail "缺少 backend/requirements.txt"

  cd "$BACKEND"

  if [ ! -d ".venv" ]; then
    python3 -m venv .venv || fail "无法创建虚拟环境（需 Python 3.12）"
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r requirements.txt
  [ -f requirements-dev.txt ] && pip install -q -r requirements-dev.txt

  log "启动真 PostgreSQL（compose db）"
  (cd "$ROOT" && docker compose up -d db)

  # 测试库独立于开发库，避免污染；密码/账号取自 .env 或环境覆盖
  export DATABASE_URL="${TEST_DATABASE_URL:-postgresql+psycopg://ai_crm:ai_crm@127.0.0.1:5432/ai_crm_test}"

  log "Alembic 迁移（空库可一条命令初始化）"
  alembic upgrade head

  log "Lint + format（ruff，必过）"
  ruff check app tests
  ruff format --check app

  # mypy 可选（ADR-015）：有配置则跑，不作为硬门禁
  if command -v mypy >/dev/null 2>&1 && \
     { [ -f mypy.ini ] || [ -f .mypy.ini ] || [ -f setup.cfg ] || \
       { [ -f pyproject.toml ] && grep -q 'tool.mypy' pyproject.toml; }; }; then
    log "类型检查（mypy，可选，不阻断）"
    mypy app || log "[soft] mypy 告警（ADR-015 非硬门禁，不阻断）"
  else
    log "跳过 mypy（未配置，ADR-015 可选门禁）"
  fi

  log "Pytest + 覆盖率 ≥ ${COVERAGE_THRESHOLD}%（必过）"
  pytest -q --cov=app --cov-report=term-missing --cov-fail-under="$COVERAGE_THRESHOLD"
}

gate_frontend() {
  log "前端 Gate"
  [ -f "$FRONTEND/package.json" ] || fail "缺少 frontend/package.json"
  cd "$FRONTEND"
  npm ci || npm install

  log "typecheck（vue-tsc，必过）"
  npm run typecheck

  log "lint（eslint，必过）"
  npm run lint

  log "vitest 单测 + 覆盖率阈值 ≥ ${COVERAGE_THRESHOLD}%（必过）"
  npm run test -- --coverage --coverage.thresholds.lines="$COVERAGE_THRESHOLD"

  log "build（vite build，必过）"
  npm run build
}

gate_e2e() {
  log "E2E Gate（Playwright）"
  [ -d "$FRONTEND" ] || fail "缺少 frontend/"
  cd "$FRONTEND"
  npx playwright test
}

case "${1:-all}" in
  backend)  gate_backend ;;
  frontend) gate_frontend ;;
  e2e)      gate_e2e ;;
  all)      gate_backend; gate_frontend; gate_e2e ;;
  *)        echo "用法: bash docs/qa-gate.sh [backend|frontend|e2e|all]" >&2; exit 2 ;;
esac

log "GATE PASS"
