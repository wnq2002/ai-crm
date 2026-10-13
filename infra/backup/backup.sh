#!/usr/bin/env bash
# AI CRM V1.0 — PostgreSQL 备份脚本（pg_dump 自定义格式）
#
# 连接信息经标准 PG 环境变量注入：PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE。
# 用法：PGDATABASE=ai_crm ./infra/backup/backup.sh [输出目录]
# 输出：<输出目录>/<库名>-<时间戳>.dump（pg_dump 自定义格式，可被 pg_restore 还原）
#
# Docker Compose 环境等价命令（见 docs/deployment.md）：
#   docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > backup.dump
set -euo pipefail

DB="${PGDATABASE:-ai_crm}"
OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${OUT_DIR}/${DB}-${STAMP}.dump"

echo "[backup] 备份数据库 ${DB} -> ${OUT}"
pg_dump --format=custom --file="$OUT" "$DB"

SIZE="$(du -h "$OUT" | cut -f1)"
echo "[backup] 完成：${OUT}（${SIZE}）"
