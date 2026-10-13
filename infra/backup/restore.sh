#!/usr/bin/env bash
# AI CRM V1.0 — PostgreSQL 恢复脚本（pg_restore）
#
# 用法：PGDATABASE=ai_crm ./infra/backup/restore.sh <dump文件>
# 流程：DROP 目标库 → 重建空库 → pg_restore（清库→恢复演练）。
# 连接信息经 PGHOST / PGPORT / PGUSER / PGPASSWORD 注入。
#
# Docker Compose 环境等价命令（见 docs/deployment.md）：
#   docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < backup.dump
set -euo pipefail

DB="${PGDATABASE:-ai_crm}"
DUMP="${1:?用法: restore.sh <dump文件>}"
HOST="${PGHOST:-127.0.0.1}"
PORT="${PGPORT:-5432}"
USER="${PGUSER:-postgres}"

if [ ! -f "$DUMP" ]; then
  echo "[restore] 错误：找不到备份文件 ${DUMP}" >&2
  exit 1
fi

echo "[restore] 清库：DROP 并重建 ${DB}"
dropdb -h "$HOST" -p "$PORT" -U "$USER" --if-exists "$DB"
createdb -h "$HOST" -p "$PORT" -U "$USER" "$DB"

echo "[restore] 恢复 ${DUMP} -> ${DB}"
pg_restore \
  -h "$HOST" -p "$PORT" -U "$USER" \
  --dbname="$DB" \
  --clean --if-exists --no-owner --exit-on-error \
  "$DUMP"

echo "[restore] 完成"
