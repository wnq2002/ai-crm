# AI CRM V1.4 验收标准

> 版本：1.4 · 关联：`docs/PRD.md`（V1.4 唯一需求源）、`docs/v1.4-migration-plan.md` §六（场景 1-6）。
> 说明：逐条标注 PASS / FAIL / 未验证，附证据。不得宣称未测试项已可上线。

## 0. 总体结论

- 实现状态：V1.4 模块 M1-M6（数据模型/迁移、智能新增、联系事件、部门移交与反馈、数据分析、系统设置）已落地，对应后端测试用例已编写；**M7 测试与验收尚未复跑**，本表 PASS/FAIL 以「服务端代码核验 + 测试用例存在性」为依据，最终以 qa（品控域）复跑结果为准。
- 迁移：7 个 revision 线性单链 `cdff02953343 → e62b96822f83 → 7ad73d5f13fb → 3c5c7d4916c9 → b1e974ca9835 → a3f1e2d4c5b6 → f1a2b3c4d5e6`；V1.4 变更集中在 `a3f1e2d4c5b6`（联系事件重构 + 三新表）与 `f1a2b3c4d5e6`（`leads.next_follow_up_at`），共 20 表。
- 权限裁决（ADR-031）：market 零隔离（看全部线索/报表）；跟进活动撤销与修正 = 创建者本人或 admin；seed 来源分类保持「官网/其他」。

## 1. 功能验收（V1.4 §六 场景 1-6，真 PostgreSQL）

> 标注依据：实现经服务端代码核验；测试用例已覆盖（下表标注用例名）。**PASS/FAIL 以 M7 复跑结果为准，本轮未执行 pytest。**

| # | 场景 | 关键断言 | 证据（pytest 用例 / 核验） |
|---|---|---|---|
| 1 | 智能新增（M2） | 粘贴原文 → AI 提取字段（置信度 high/medium/low）→ 创建线索，刷新可见原文与最终字段 | `test_parse_lead`、`test_parse_lead_ai_unavailable`、`test_parse_need_type_dict_filter`、`test_create_lead_with_parse_record` |
| 2 | 历史电话补录（M3） | 每通电话独立事件；两通电话=累计 2 次；补录实际时间、拒绝未来时间；记录沟通后更新 `next_follow_up_at` | `test_create_phone_activity`、`test_phone_count_aggregation`、`test_activity_happened_at_future_rejected`、`test_timeline_includes_activities`、`test_create_activity_updates_next_follow_up_at` |
| 3 | 微信好友状态（M3） | 申请/通过/沟通三条独立事件；关系由最新有效事件派生=已通过；未通过不可沟通 | `test_wechat_relationship_derivation`、`test_create_wechat_activity_no_result`、`test_wechat_chat_requires_approved`、`test_wechat_approved_creates_new_event_not_modify_history` |
| 4 | 部门移交与反馈（M4） | 有效线索移交 → 推进中 → 已成交（含暂缓），时间线可追溯 | `test_handoff_success`、`test_outcome_success`、`test_outcome_deferred`、`test_timeline_includes_decision_events` |
| 5 | 数据统计（M5） | 「线索数量」与「事件数量」口径分离；趋势/渠道×部门/明细/导出对齐筛选 | `test_dashboard_summary`、`test_reports_overview`、`test_reports_sources`、`test_dashboard_trend`、`test_leads_export_csv` |
| 6 | 系统设置（M6） | 管理员新增来源/需求/部门/AI 配置（密钥不可见），新建表单可选；market 只读不可写 | `test_admin_can_write_dictionaries`、`test_market_cannot_write_dictionaries`、`test_admin_write_ai_config_success_and_key_masked`、`test_ai_config_key_preserved_when_not_resend`、`test_delete_unreferenced_dictionary`、`test_reassign_contact_leads` |

## 2. 工程验收

| # | 验收项 | 证据（核验点） |
|---|---|---|
| E1 | 后端 lint + pytest + 覆盖率 ≥70% | `ruff check app tests`、`ruff format --check`、`pytest --cov=app --cov-fail-under=70`；用例覆盖 M2-M6（见 §1） |
| E2 | 前端 typecheck/lint/test/build | `vue-tsc`、`eslint .`、`vitest run`、`vite build` |
| E3 | Alembic 全链往返 + 空库一键初始化 | 7 revision 线性单链 `upgrade→downgrade→upgrade`（20 表）；`python -m app.seed` 生成 admin + 字典（部门/官网/其他/需求类型） |
| E4 | 越权：未登录/角色/ID 枚举/重复提交/并发/输入边界 | 未登录 401；market 不可合并企业/撤销他人 activity/写系统设置 403（`test_merge_companies_admin_only`、`test_revoke_activity_creator_or_admin`、`test_market_cannot_write_dictionaries`）；幂等（lead/activity/import）；version 409；边界 422 |
| E5 | HTTPS/持久化/健康检查/日志轮转/备份恢复 | nginx TLS + healthz/readyz + logrotate；compose pgdata 卷；pg_dump/pg_restore 演练 |
| E6 | Playwright 核心 E2E | 浏览器级 E2E 待接线；以真实 HTTP 冒烟替代验证（见 §4） |
| E7 | 日志不记录明文 PII / 密钥 | `lead_service.update_lead` 经 `_PII_MASKERS` 脱敏写入 lead_events；AI 密钥仅写不读回、响应 mask、审计脱敏（`test_ai_config_audit_log_masks_key`） |

## 3. 未完成 / 已知限制

1. **M7 测试与验收未复跑**：后端测试已编写（覆盖 §1 场景），但本轮未执行 pytest/coverage/迁移往返，最终 PASS/FAIL 待 qa 复跑确认。
2. **浏览器级 Playwright E2E 未接线**：项目未接入 @playwright/test 用例，浏览器 UI 自动化待后续补（以真实 HTTP 冒烟替代）。

## 4. 交付证据记录

| 项 | 运行命令 | 结果 |
|---|---|---|
| 后端 | `pytest --cov=app --cov-fail-under=70`（真 PG16） | 待 M7 复跑 |
| 后端 lint | `ruff check app tests` + `ruff format --check app` | 待 M7 复跑 |
| 前端 | `npm run typecheck/lint/test/build` | 待 M7 复跑 |
| 迁移 | `alembic upgrade head → downgrade base → upgrade head` | 7 revision / 20 表，待复跑 |
| 备份恢复 | `pg_dump -Fc → drop → pg_restore` | 待复跑 |
| 全链路冒烟 | uvicorn + curl（登录→建线索→智能识别→电话/微信→判断→移交→反馈→报表） | 待复跑 |

> 复跑人：qa（品控域）。本轮为文档对齐：实现与测试用例经代码核验，具体 PASS/FAIL 以 M7 复跑结果为准。
