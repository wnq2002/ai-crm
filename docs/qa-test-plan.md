# AI CRM V1.4 测试计划与验收矩阵（QAAgent）

> 作者：QAAgent（质量 Gate）
> 基线：`docs/PRD.md`（V1.4）+ `docs/api-contract.md` + `docs/v1.4-migration-plan.md` §六 场景 1–6
> 立场：悲观验证——默认一切产出物不合格，穷尽边界/异常/反例证明其错误。
> 状态：V1.4 代码已落地（后端 7 迁移链 head=f1a2b3c4d5e6，前端 10 视图 / 8 组件）。本矩阵已对齐实现，待按 team-lead 指令跑 Gate。

---

## 0. Gate 规则（铁律）

| 项 | 门槛 | 命令（后端） | 命令（前端） |
|---|---|---|---|
| 覆盖率 | **≥ 70%**（必过） | `pytest --cov=app --cov-fail-under=70` | `vitest run --coverage --coverage.thresholds.lines=70` |
| Lint + format | 0 error（必过） | `ruff check app && ruff format --check app` | `eslint src` |
| 类型检查 | 0 error | mypy（可选，ADR-015 非硬门禁） | `vue-tsc --noEmit`（必过） |
| 后端测试 | 全绿（必过） | `pytest -q` | — |
| 前端测试 | 全绿（必过） | — | `vitest run` |
| 构建 | 通过（必过） | — | `vite build` |
| E2E | 核心链路绿 | `playwright test` | `playwright test` |

不通过 → 触发「发现→修复→验证」循环，直到通过或达最大重试（默认 3 次），并回报 team-lead。

**悲观立场检查清单（每条负面场景必测）：**
未登录访问、角色越权（admin-only 写操作）、ID 枚举（UUID 主键低风险，仍校验）、重复提交/网络重试（幂等）、并发修改（409 version）、输入边界（空/超长/非法类型/非法枚举/非法 todo 参数）、事务回滚、AI 停机兜底（503）、事件修正审计（reason/before-after/未来时间）、密钥不回传、空数据库空状态。

**工具链（ADR-015，唯一口径）：**
- 后端：`ruff`（lint + format，必过）+ `pytest --cov-fail-under=70`（必过）；`mypy` 可选（有配置则跑，非硬门禁）。
- 前端：`vue-tsc`（typecheck，必过）+ `eslint`（lint，必过）+ `vitest`（必过）+ `vite build`（必过）。
- E2E：`playwright`。
- 后端集成测试打**真 PostgreSQL**（compose `db` 服务 + 独立测试库），严禁 mock 数据库；`backend/tests/conftest.py` 负责测试库生命周期。
- 一键脚本：`bash /Users/wnq/Downloads/ai_crm_公司版/ai-crm/docs/qa-gate.sh [backend|frontend|e2e|all]`，命令详单见 §9。

---

## 1. 测试栈与约定

| 层 | 工具 | 范围 | 隔离 |
|---|---|---|---|
| 单元 | Pytest / Vitest | 纯函数、校验器、状态机、权限策略、序列化 | mock 外部 I/O |
| 集成 | Pytest + httpx ASGI | API 契约 + 真 PostgreSQL | 每个测试独立事务/回滚 |
| E2E | Playwright | 登录→智能新增→电话/微信→移交→反馈→统计 核心闭环 | 真实浏览器 + 种子数据 |
| 性能 | 自研脚本（locust 可选） | 列表分页、跟进聚合、AI 提取超时 | 独立基准 |

约定：
- 后端 fixture 用工厂（自写 factory），不用手写 SQL 造数。
- 集成测试必须打真 PostgreSQL，**禁止** mock 数据库。
- 所有断言以 HTTP 状态码 + JSON 错误体 `{code,message,request_id,details?}` 为准。
- 时间相关测试用可注入时钟（freezegun / fake timer），禁止依赖 `time.sleep`。
- AI 相关测试用 stub/fake Provider，不真实外呼网络。

---

## 2. 后端 API 契约测试矩阵（对齐 V1.4 实现）

> 枚举口径（共享事实基线）：`outcome ∈ unknown|in_progress|won|lost|deferred`；`activity.kind ∈ phone|wechat_request|wechat_approved|wechat_chat|note`；`activity.result ∈ connected|unconnected|rejected`（仅 phone）；`follow_up_status` 7 态含 `handed_off_pending`；`wechat_relationship` 派生 `none|pending|approved`。角色仅 `admin|market`（ADR-022 弃用 sales）。

### 2.1 Auth 与用户管理
| 用例 | 断言 |
|---|---|
| POST /auth/login 成功 | 设置 HttpOnly+SameSite 会话 Cookie + CSRF Cookie；不返回 password_hash |
| 登录失败 | 统一 401，不区分「用户不存在/密码错」 |
| 登录限流 | 连续失败触发 429（`login_rate_limiter` 滑动窗口） |
| POST /auth/logout | 会话撤销，旧 Cookie 再访问 → 401；缺 CSRF → 403 |
| GET /auth/me | 已认证且缺 csrf Cookie 时补发 |
| POST /auth/change-password | 校验旧密码；清除 `must_change_password`；撤销该用户其他会话 |
| **must_change_password 门禁** | ⚠️ **已知缺口**：仅前端路由守卫强制改密，服务端 `get_session_record` 未强制（未改密仍可直调受保护 API），矩阵记录为待补负面场景 |
| POST /admin/users | 仅 admin；初始 `must_change_password=true`；不泄露 password_hash |
| PATCH /admin/users/{id} | 仅 admin；重置密码/禁用/赋角色；禁用后活跃会话失效 |

### 2.2 Leads（列表/创建/详情/更新/归档/关联/导出/时间线）
| 用例 | 断言 |
|---|---|
| GET /leads 分页 | `page,page_size,total,items` 结构；page_size ≤100；非法 page → 422 |
| GET /leads 筛选 | q/occurred_from·to/source_category_id/need_type_id/qualification_status/handoff_status/outcome_status/department_id/archived 组合过滤 |
| **GET /leads?todo=<非法值>** | ⚠️ **已知缺陷**：`todo_condition` 对未知类别抛 `ValueError`（未映射为 APIError），现状返回 **500**，应为 422；矩阵记录该负面场景（合法值：overdue/first_follow/today/no_progress/stale/handed_off_pending） |
| POST /leads 最小内容 | 需「联系方式 / 外部事件 / 姓名+来源 / 需求+来源」之一，缺 → 422（`_validate_min_content`） |
| 输入边界 | company_name>200、contact_name>128、phone>64、notes>2000 → 422；intake_method 非法枚举 → 422 |
| 邮箱/电话规范化 | 存小写去空格/去格式符 |
| 幂等 | 同 idempotency_key → 返回已存在线索不重复建；同渠道 external_source_event_id 重复推送 → 复用 |
| 重复提示 | 手机/邮箱命中历史 → duplicate_hints（不泄露对方 PII）；企业匹配返回 candidates，不自动合并 |
| 随附解析记录 | 带 parse_record → 写 lead_parse_records（raw_text 必保留，lead_id 创建后回填） |
| PATCH /leads/{id} | 带旧 version 不一致 → 409（乐观锁）；PII 字段变化经 mask 写 lead_events |
| 归档 | POST archive/unarchive 仅 admin；归档后 get → 404 |
| 关联企业 | link-company/unlink-company 写审计；unlink 保留历史 |
| GET /leads/export | CSV；PII 脱敏（mask_phone/mask_email）；公式注入转义（safe_csv） |
| GET /leads/{id}/timeline | 统一时间线（创建/电话/微信申请/通过/沟通/备注/有效性/移交/反馈），按 happened_at 倒序 |

### 2.3 智能新增（M2：/leads/parse + /leads/duplicate-check）
| 用例 | 断言 |
|---|---|
| POST /leads/parse 未配置 AI | ⚠️ **503 `AI_UNAVAILABLE`**，且不阻塞手动创建（parse 独立于 create） |
| parse 置信度分级 | 每字段 confidence ∈ high/medium/low；value 为 null 时 confidence 为 null |
| parse 需求类型字典校验 | need_type 仅在 `lead_need_types` 精确匹配才返回，否则置 null + hints 提示 |
| parse 输入边界 | raw_text 空 → 422；>20000 → 422 |
| parse 不落库 | parse 仅返回提取结果，**不写 lead_parse_records、不建客户/线索**（ADR-029） |
| duplicate-check | 返回 contact_duplicate/contact_hint/company_candidates/external_event_conflict 四类 |
| 缺 CSRF | parse/duplicate-check 缺 CSRF → 403 |

### 2.4 联系事件（M3：activities 创建/修正/撤销）
| 用例 | 断言 |
|---|---|
| kind 枚举 | 非法 kind → 422；result 非法枚举 → 422 |
| phone result 必填 | kind=phone 时 result 必须 connected/unconnected/rejected，否则 422 |
| 微信/备注禁 result | 非 phone 写 result → 422 |
| 微信沟通前置 | kind=wechat_chat 仅当 wechat_relationship=approved，否则 422 |
| **电话累计（V1.4 变更）** | 废 phone_count 列；phone_total = 有效(未撤销) phone 事件数（每通电话独立）；result=connected 事件数 = 接通次数 |
| 微信三态 | wechat_request/wechat_approved/wechat_chat 各自独立事件；wechat_count = 有效微信事件数（不含 note） |
| wechat_relationship 派生 | 无微信事件→none；最新为 request→pending；最新为 approved/chat→approved（ADR-028，不落列） |
| happened_at | 未来时间 → 422；不填取 now |
| next_follow_up_at | 非 note 事件写入 leads.next_follow_up_at |
| 幂等 | 同 (created_by, idempotency_key) → 返回已存在事件不重复计（UniqueConstraint） |
| PATCH /activities/{id} 修正 | reason 必填(缺→422)；写 lead_event_revisions 保留 before/after；created_at 不可改 |
| 修正未来时间 | happened_at 晚于当前 → 422 |
| 修正越权 | 非创建者且非 admin → 403；已撤销记录 → 409 |
| 修正内容 | 至少一项变更，否则 422；非 phone 事件设 result → 422 |
| POST /activities/{id}/revoke | 创建者或 admin；写 reason+审计；累计实时排除撤销 |

### 2.5 判断 / 移交 / 反馈（M4，含 deferred）
| 用例 | 断言 |
|---|---|
| qualification | 仅 pending/valid/invalid；判 invalid 缺 reason → 422；已交接线索非 admin 不可改判断 → 403 |
| handoff | 仅有效线索可交接(否则 422)；部门/对接人不存在 → 404；未配对接人 → 422；写 lead_handoffs + 审计 |
| outcome 枚举 | unknown/in_progress/won/lost/**deferred**（V1.4 新增）；非法 → 422 |
| outcome 前置 | 非 unknown 结果仅已交接线索可登记，否则 422 |
| won/lost 需依据 | 缺 note → 422；deferred 不强制 note |
| 统计口径 | deferred 单独计入 outcome 分布，不等于 lost/no_feedback |
| 时间线 | 移交/反馈事件接入统一时间线，可追溯 |
| 幂等/并发 | 重复 outcome 写多条 event（保留历史）；version 冲突 → 409 |

### 2.6 客户与联系人
| 用例 | 断言 |
|---|---|
| 企业匹配 | 疑似同名返回 candidates，人工确认，不自动合并 |
| 合并 | merge/merge-preview 仅 admin；market → 403 |
| 联系人 | 新增/编辑 is_primary；写操作仅需登录 + CSRF（无 owner 隔离，见 §3）；缺 CSRF → 403 |
| 企业详情 | 含 contacts + leads 聚合；无企业 → 404 |

### 2.7 系统设置（M6：字典 + AI 配置）
| 用例 | 断言 |
|---|---|
| 字典读 | departments/department-contacts/source-categories/source-details/need-types GET 对任意登录用户开放 |
| 字典写 | POST/PATCH/DELETE 仅 admin + CSRF；market → 403 |
| 删除保护 | 被引用部门/对接人/来源/需求类型删除 → 409（提示停用/改派） |
| 改派 | department-contacts reassign 仅同部门；写 LeadHandoff+LeadEvent+审计 |
| GET /settings/ai | 任意登录用户可读；**密钥不回传**（仅 api_key_configured + 脱敏占位 `***configured***`） |
| PUT/POST /settings/ai | 仅 admin + CSRF；api_key 语义：None 保留、空串清除、非空覆盖 |
| AI 配置审计 | settings.ai_update 写审计，before/after 密钥脱敏（_mask） |
| 越权/CSRF | market 写 /settings/ai → 403；缺 CSRF → 403 |

### 2.8 导入（Imports）
| 用例 | 断言 |
|---|---|
| preview 边界 | >大小上限 / >行数上限 → 422；非 xlsx/csv → 422 |
| preview | 返回 preview_token + 逐行错误（行号+说明）+ duplicates 计数 |
| commit 幂等 | 同 idempotency_key → 返回既有批次，不重复写入 |
| commit 防重放 | preview_token 无效/已消费 → 404 |
| 逐行结果 | success/failed 计数；failed 行不吞错误；get_result 逐行可查 |
| 公式注入 | 导出侧 safe_csv 转义 `= + - @`；导入以字符串读入不执行 |

### 2.9 报表与工作台（M5：11 指标）
| 用例 | 断言 |
|---|---|
| GET /reports/overview 11 指标 | total_leads/distinct_companies/valid/invalid/pending/effective_rate/handed_off/outcome_won/outcome_lost/outcome_in_progress/no_feedback 逐项正确 |
| **线索数与事件数分离** | 线索按 occurred_at、事件按 happened_at 分别口径（ADR-030），不混用 |
| 趋势时序 | GET /dashboard/trend 按日分桶（leads/valid/handed_off），空桶补零 |
| 渠道分析 | GET /reports/sources 按来源分类计 lead/valid/handed_off |
| 部门分析 | GET /reports/handoffs 按目标部门计数 |
| **渠道×部门交叉** | ⚠️ **缺口**：sources(按渠道) 与 handoffs(按部门) 分立，无真正交叉下钻端点，记录为待补 |
| 下钻 | 经 GET /leads 组合筛选（source_category_id/department_id/qualification_status/outcome_status）实现 |
| 导出对齐筛选 | ⚠️ **缺口**：/reports/export 仅接受 from/to，未对齐全量筛选（渠道/部门/状态），记录为待补 |
| 员工跟进 | GET /reports/activities 按人计 total/phone_total |
| 报表越权 | market 可读全部报表（零隔离，见 §3）；导出写审计 |

---

## 3. 权限/越权矩阵（V1.4：admin/market，无 sales）

V1.4 仅 `admin` 与 `market` 两角色（ADR-022，V1.3 弃用 sales），线索**无归属人/owner 字段**，故不存在「sales A 读 sales B 线索」的横向隔离；market 对线索/客户域均为**零隔离（可读全部）**。安全红线收敛为「admin-only 写操作」与「服务端逐条强制」：

| 资源/操作 | market | admin |
|---|---|---|
| 线索读/建/改/判断/移交/反馈/跟进/时间线 | 全部 | 全部 |
| 线索归档/取消归档 | — | 仅 admin |
| 企业合并 | — | 仅 admin |
| 系统设置字典写/删除/改派 | — | 仅 admin |
| AI 配置写 | — | 仅 admin |
| 用户管理 /admin/users | — | 仅 admin |

通用越权/安全断言（服务端逐条验证，禁止仅前端隐藏按钮）：
- 未登录访问任意 `/api/v1/*` → 401（Cookie 缺失/失效/过期/禁用）
- market 调 admin-only 端点（归档/合并/字典写/AI 配置写/用户管理）→ 403
- 所有写操作缺 CSRF（`X-CSRF-Token` 头 != csrf Cookie）→ 403
- ID 枚举：主键 UUID（ADR-005）不可枚举，越权/不存在资源统一 404 不泄露存在性
- 直接 curl 绕过前端调 API → 仍被服务端拦截（角色 + CSRF）

---

## 4. 前端测试（Vitest）

对齐 V1.4 实际组件/视图（10 视图 / 8 组件 / 6 utils）：

- 组件：`LeadFormDialog`（智能新增粘贴识别 + 置信度展示 + 重复提示）、`ActivityDialog`（电话 result 三态、微信三态隐藏 result）、`ReviseActivityDialog`（reason 必填 + before/after）、`HandoffDialog`/`OutcomeDialog`（deferred 选项）、`ImportDialog`（逐行错误展示）、时间线逆序与图标类型区分。
- Pinia store：`auth` 登录态、角色权限、`must_change_password`、身份过期拦截（401 → 跳登录）。
- API 封装层：统一错误处理、request_id 透传、幂等键注入、CSRF 头注入。
- 路由守卫：未登录跳转、`must_change_password` 强制改密、settings 仅 admin（`meta.roles`）。
- 工具：电话/邮箱/微信号规范化、时间 UTC 显示按上海时区、CSV 下载、幂等键生成、PII 脱敏。

现状缺口：前端仅 3 个 spec（auth/pii/utils），V1.4 新增组件（ReviseActivityDialog、LeadFormDialog 解析区、ActivityDialog 微信三态）**无组件测试**，记录为待补。

---

## 5. E2E（Playwright，核心闭环 + V1.4 场景 1–6）

1. 管理员登录 → 创建市场/管理员账号 → 首次改密（前端强制）。
2. 智能新增（场景 1）：粘贴原文 → 提取字段（置信度）→ 创建 → 刷新可见原文与最终字段（AI 停机时提示 503 且可手动创建）。
3. 历史电话补录（场景 2）：两通电话 → 累计 2 次，时间线准确。
4. 微信好友状态（场景 3）：发送申请/通过/沟通三条独立事件 → 关系=已通过。
5. 部门移交（场景 4）：移交 → 推进中 → 已成交，时间线可追溯。
6. 数据统计（场景 5）：1 线索 / 2 电话 / 1 申请 / 1 通过 / 1 移交，口径分离（线索 vs 事件）。
7. 系统设置（场景 6）：新增来源渠道 → 新建表单可选。
8. 事件修正：修正发生时间/结果，reason 必填，时间线反映修正。
9. 越权 E2E：market 登录无法看到/触发 admin-only 写操作；直接 API 调用仍被拦。
10. 空数据库 → 空状态展示，无虚构客户，仅 admin 种子。

---

## 6. 性能基线（生产加固）

- 线索列表 10 万行分页查询 < 300ms（有索引）；todo 分类聚合避免 N+1。
- 跟进累计次数/最近跟进时间批量聚合 < 200ms（`followup_aggregates` 单查询 group_by）。
- 统一时间线聚合 < 300ms（创建/活动/移交/反馈批量拼接，避免逐表 N+1）。
- AI 提取超时受 `timeout_seconds` 约束（1–300s），超时抛 503 不拖垮请求线程。
- 越权/审计扫描：UUID 主键不可枚举 + 登录限流（429）防止批量爆破。

---

## 7. 验收矩阵（V1.4 §九 场景 1–6 → 测试映射）

### 功能验收（V1.4 场景）
| # | 场景 | 对应测试 |
|---|---|---|
| 1 | 智能新增：粘贴→提取→创建，刷新可见原文与最终字段 | §2.3、§5.2 |
| 2 | 历史电话补录：两通电话=累计 2 次，时间线准确 | §2.4、§5.3 |
| 3 | 微信好友状态：三条独立事件，关系=已通过 | §2.4、§5.4 |
| 4 | 部门移交：移交→推进中→已成交，时间线可追溯 | §2.5、§5.5 |
| 5 | 数据统计：口径分离（线索 vs 事件） | §2.9、§5.6 |
| 6 | 系统设置：新增来源→新建表单可选 | §2.7、§5.7 |

### AI 验收（ADR-029 §8 补充）
| # | 验收项 | 对应测试 |
|---|---|---|
| A1 | AI 提取为可编辑草稿，含置信度与 hints | §2.3 |
| A2 | AI 不自动落库/建客户/改写线索（仅提取） | §2.3（parse 不写库断言） |
| A3 | AI 密钥不出后端（GET 脱敏、审计脱敏） | §2.7 |

### 工程与上线验收
| # | 验收点 | 对应 Gate |
|---|---|---|
| 7 | 非 Mock；空库空状态；仅 admin 种子无虚构客户 | §5.10、集成 fixture |
| 8 | 全部 Alembic 迁移（7 revision，head=f1a2b3c4d5e6）可往返；空库一键初始化 | 迁移测试（集成） |
| 9 | 前端 typecheck/lint/build；后端 lint/Pytest；核心 E2E | §0 Gate |
| 10 | 越权（未登录/角色/CSRF）+ 幂等 + 并发 409 + 输入边界 + 非法 todo | §3、§2 |
| 11 | HTTPS/环境变量/持久化/健康检查/日志轮转/备份恢复 | 生产加固切片 |
| 12 | 已知缺陷闭环：todo 非法值 500→422；must_change_password 服务端强制；渠道×部门交叉与导出对齐筛选 | §2 标注项 |

---

## 8. 切片 Gate 顺序（对齐 V1.4 模块 M1–M7）

按 team-lead 指令，每个模块完成后对下述做 Gate：
1. **M1 数据模型与迁移**：迁移往返 + §0 全部门槛 + 迁移测试。
2. **M2 智能新增**：§2.3 parse/duplicate-check、AI 503 兜底、parse_record 落库。
3. **M3 联系事件（重点）**：§2.4 全部（三态微信/result/修正审计/幂等/撤销）。
4. **M4 部门移交与反馈**：§2.5 deferred、handoff/outcome 时间线。
5. **M5 数据分析**：§2.9 11 指标、口径分离、趋势、导出。
6. **M6 系统设置**：§2.7 字典 + AI 配置密钥不回传。
7. **M7 测试与验收**：§6 性能、§7 工程验收、越权/并发/幂等全量回归。

---

## 9. Gate 命令速查

一键脚本：`bash /Users/wnq/Downloads/ai_crm_公司版/ai-crm/docs/qa-gate.sh [backend|frontend|e2e|all]`。

### 后端（真 PostgreSQL，禁止 mock 库）
```bash
cd /Users/wnq/Downloads/ai_crm_公司版/ai-crm/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
docker compose -f ../compose.yaml up -d db          # 真 PostgreSQL
export DATABASE_URL="postgresql+psycopg://ai_crm:CHANGE_ME@127.0.0.1:5432/ai_crm_test"  # 独立测试库
alembic upgrade head                                  # 空库一条命令初始化（head=f1a2b3c4d5e6）
ruff check app && ruff format --check app              # lint + format（必过）
# mypy 可选（ADR-015，有配置则跑，非硬门禁）
pytest -q --cov=app --cov-report=term-missing --cov-fail-under=70   # 测试 + 覆盖率 ≥70%（必过）
```

### 前端
```bash
cd /Users/wnq/Downloads/ai_crm_公司版/ai-crm/frontend
npm ci
npm run typecheck      # vue-tsc --noEmit（必过）
npm run lint           # eslint src（必过）
npm run test -- --coverage   # vitest run + 覆盖率阈值 ≥70%（必过）
npm run build          # vite build（必过）
```

### E2E
```bash
cd /Users/wnq/Downloads/ai_crm_公司版/ai-crm/frontend
npx playwright test
```

---

## 10. 当前状态

- V1.4 代码已落地：后端 7 迁移链（head=f1a2b3c4d5e6），前端 10 视图 / 8 组件。
- 后端测试文件已有 `test_activities`/`test_decision`/`test_settings`/`test_followup`/`test_imports`/`test_models`/`test_seed`/`test_leads`/`test_reports` 等，覆盖 V1.4 主要域。
- 待补（矩阵已标注）：todo 非法值 500→422 缺陷；must_change_password 服务端强制门禁；前端 V1.4 组件测试（ReviseActivityDialog/解析区/微信三态）；浏览器级 Playwright E2E 未接线（现以 HTTP 冒烟替代）；渠道×部门交叉与导出对齐筛选。
- 待 team-lead 指令跑 Gate（§9 命令）。
