# AI CRM V1.4 REST API 契约

> 版本：1.4 · 基路径：`/api/v1` · 关联：PRD V1.4 §8、`docs/architecture.md`、`docs/decisions.md`（ADR-018~031）
> 需求基线已切换为「市场部线索优先管理系统」，替换 V1.0 通用 CRM；商机/任务/销售分配等 V1.0 概念已废弃（ADR-018）。
> 说明：V1.3 PRD §8 以 `/api/...` 为路径简写，实际基路径统一为 `/api/v1`（ADR-025）。

## 1. 通用约定

- **错误**：统一 JSON `{"code": string, "message": string, "request_id": string, "details": object?}`。
- **request_id**：由服务端生成并贯穿审计日志；客户端携带 `X-Request-Id` 请求头时回显该值，否则服务端生成（ADR-014）。
- **分页**：请求 `page`(1-based)、`page_size`(默认 20，上限 100)；响应 `{"items": [], "page": int, "page_size": int, "total": int}`。
- **时间**：ISO 8601 UTC 存储（UI 按 Asia/Shanghai 展示）；区分「咨询发生时间 occurred_at / 系统创建时间 created_at / 交接时间 / 跟进时间 / 反馈时间」统计口径。
- **ID**：UUID 字符串。
- **幂等**：创建线索、跟进活动、导入提交接受 `Idempotency-Key` 请求头（或请求体 `idempotency_key`）；重复提交返回首次结果（ADR-019 层次①）。
- **并发**：更新用 `version` 字段做乐观锁，冲突返回 `409 Conflict`。
- **排序/筛选**：服务端实现；查询参数见各端点。
- **权限**：所有写操作与范围过滤在服务端逐条校验；market 与 admin 均可见全部线索（零隔离，market 不再限定本部门），仅写操作按角色区分（见 §12）。
- **CSRF**：`/auth/login` 下发 HttpOnly 会话 Cookie 与非 HttpOnly 的 `csrf_token` Cookie；`/auth/me` 在已认证但缺 csrf_token 时补发。所有写操作（POST/PATCH/DELETE）须在请求头 `X-CSRF-Token` 回传该值，服务端校验不一致返回 403 `FORBIDDEN`；读操作（GET）不要求。会话 Cookie 为 HttpOnly + `SameSite=Lax`（生产 `Secure=true`）第一道防线，CSRF token 为第二道。**CSRF 校验全环境强制（含 dev），不提供关闭开关**（ADR-016）。
- **PII 脱敏**：手机号/邮箱按授权读取；日志不记录明文手机号/邮箱/会话密钥；导出受权限控制并审计（PRD §7/§9）。

通用错误码：`UNAUTHORIZED`(401)、`FORBIDDEN`(403)、`NOT_FOUND`(404)、`CONFLICT`(409)、`VALIDATION_ERROR`(422)、`RATE_LIMITED`(429)、`INTERNAL`(500)；AI 未配置/不可用返回 503 `AI_UNAVAILABLE`。

## 2. 认证 `/auth`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 登录，返回用户信息并下发 HttpOnly 会话 Cookie 与非 HttpOnly 的 `csrf_token` Cookie |
| POST | `/auth/logout` | 登出，撤销会话 |
| GET | `/auth/me` | 当前用户与权限（已认证但缺 csrf_token 时补发） |
| POST | `/auth/change-password` | 修改密码（首次登录强制） |

**POST /auth/login** 请求：`{"username": str, "password": str}`；成功 200：`User`；失败 401。登录限流。密码 Argon2id 校验。

**POST /auth/change-password** 请求：`{"old_password": str, "new_password": str}`；`new_password` 最小 8 字符（Argon2id）；成功清除 `must_change_password`。

密码策略：最小 8 字符，Argon2id 哈希（ADR-004）。

## 3. 通用资源模型与枚举

```
User           { id, username, display_name, role: admin|market, is_active, must_change_password }
Company        { id, canonical_name, normalized_name, aliases?, industry?, phone?, website?, created_at, merged_into_id? }
Contact        { id, company_id?, name?, phone?, email?, wechat_id?, created_at }
SourceCategory { id, code, name, active }
SourceDetail   { id, category_id, name, active }
NeedType       { id, name, active }
Department     { id, name, active }
DepartmentContact { id, department_id, name, active, is_default }
Lead           { id, company_id?, contact_id?, company_name_raw, contact_name_raw,
                 phone_raw?, email_raw?, wechat_raw?, need_type_id?, inquiry_text?,
                 occurred_at, source_category_id, source_detail_id?, source_detail_text?, notes?,
                 intake_method: manual|import|api, external_source_event_id?, source_payload_json?,
                 qualification_status: pending|valid|invalid,
                 handoff_status: not_handed_off|handed_off,
                 outcome_status: unknown|in_progress|won|lost|deferred,
                 department_id?, department_contact_id?,
                 created_by, created_at, updated_at, archived_at?, version,
                 next_follow_up_at?, follow_up_count, follow_up_status,
                 phone_total_count, wechat_count, recent_followup_at? }
LeadActivity   { id, lead_id, kind: phone|wechat_request|wechat_approved|wechat_chat|note,
                 result?: connected|unconnected|rejected, content?, happened_at,
                 created_at, created_by, revoked_at?, revoked_by?, revoke_reason? }
LeadParseRecord { id, lead_id?, raw_text, parsed_json?, created_by, created_at }
LeadEventRevision { id, activity_id, before_json?, after_json?, reason, revised_by, created_at }
AppSetting     { id, key, value, updated_by?, updated_at? }
Handoff        { id, lead_id, from_department_id?, to_department_id, to_contact_id?, note?,
                 happened_at, created_by, reason? }
OutcomeEvent   { id, lead_id, from_outcome, to_outcome, note?, feedback_at, created_by, created_at }
```

> `Lead` 响应额外含聚合派生字段（不落库，由有效 `lead_activities` 实时聚合）：`phone_total_count`（电话累计次数，有效 phone 事件数）、`wechat_count`（微信记录数）、`recent_followup_at`（最近跟进时间，无跟进为 null）、`wechat_relationship`（微信关系 `none|pending|approved`，由最新一条有效微信事件派生，见 §6）。

> 响应暴露口径：`LeadActivity.revoked_by`（撤销人）与 `Lead.source_payload_json`（外部原始载荷）为模型落库列，但**不在 API 响应暴露**——`ActivityOut` 仅回 `revoked_at`/`revoke_reason`，`LeadOut` 不回 `source_payload_json`。

> PII 口径：`LeadListItem`（列表态）不含明文 `phone_raw`/`email_raw`/`wechat_raw`，改由 `contact_summary`（脱敏摘要，mask_phone/mask_email，如 `138****8000`/`a***@x.com`）提供联系方式摘要；`LeadDetail`（详情态）含完整明文联系方式（market/admin 授权访问，用于跟进）。
>
> `LeadListItem` 字段：`id, occurred_at, company_name_raw, contact_name_raw, contact_summary, need_type_id, inquiry_text, qualification_status, handoff_status, outcome_status, department_id, department_contact_id, source_category_id, source_detail_id, source_detail_text, recent_followup_at, next_follow_up_at, follow_up_count, follow_up_status, created_at, updated_at`（`recent_followup_at`/`follow_up_count` 由有效跟进事件聚合派生，`follow_up_status` 由服务端分类器派生，`next_follow_up_at` 为线索落库字段，见 §6）。

状态枚举：
- `qualification_status`：`pending` 待确认（默认）/ `valid` 有效 / `invalid` 无效
- `handoff_status`：`not_handed_off`（默认）/ `handed_off`
- `outcome_status`：`unknown` 暂无反馈（默认）/ `in_progress` 推进中 / `won` 已成交 / `lost` 未成交 / `deferred` 暂缓
- `intake_method`：`manual` / `import` / `api`
- 活动 `kind`：`phone` / `wechat_request`（发送好友申请）/ `wechat_approved`（申请通过）/ `wechat_chat`（微信沟通）/ `note`
- 电话 `result`：`connected` 已接通 / `unconnected` 未接通 / `rejected` 拒接（仅电话写入，微信/备注为 null）
- 跟进待办 `follow_up_status`：`overdue` 已逾期 / `first_follow` 待首次跟进 / `today` 今日待跟进 / `no_progress` 多次跟进无进展 / `stale` 长期未更新 / `handed_off_pending` 已交接待反馈 / `normal` 正常（无待办）

## 4. 线索 `/leads`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/leads` | 列表（筛选/分页/排序） |
| POST | `/leads` | 新建（企业名称可空；幂等；非阻塞企业匹配提示） |
| POST | `/leads/parse` | AI 提取线索字段（不落库、不建客户，附置信度） |
| POST | `/leads/duplicate-check` | 创建前重复检查（联系人/企业/渠道） |
| GET | `/leads/{id}` | 详情 |
| PATCH | `/leads/{id}` | 更新（version 乐观锁 + 审计） |
| GET | `/leads/{id}/timeline` | 统一时间线（创建/电话/微信/判断/移交/反馈，倒序） |
| POST | `/leads/{id}/archive` | 归档（软删除 + 审计） |
| POST | `/leads/{id}/unarchive` | 恢复归档（仅 admin + 审计） |

**GET /leads** 查询：`q`(企业/联系人/手机/邮箱/需求关键词)、`qualification_status`、`handoff_status`、`outcome_status`、`source_category_id`、`source_detail_id`、`need_type_id`、`department_id`、`todo`(overdue|first_follow|today|no_progress|stale|handed_off_pending，按跟进待办分类过滤；`normal` 不用于过滤)、`archived`(查已归档)、`occurred_from`/`occurred_to`、`page`、`page_size`、`sort`(默认 `-occurred_at`)。响应 `Page[LeadListItem]`（列表态脱敏，见 §3 PII 口径；含 `follow_up_status`/`follow_up_count`/`next_follow_up_at`）。

**GET /leads/{id}** 响应 `LeadDetail`（含完整明文联系方式，market/admin 授权访问用于跟进）。

**POST /leads** 请求：
```json
{ "occurred_at": "ISO 8601 (默认当前时间)", "contact_name_raw": "str?",
  "phone_raw": "str?", "email_raw": "str?", "wechat_raw": "str?",
  "company_name_raw": "str?", "need_type_id": "uuid?", "inquiry_text": "str?",
  "source_category_id": "uuid? (默认 未知分类)", "source_detail_id": "uuid?", "source_detail_text": "str?",
  "intake_method": "manual|import|api (默认 manual)", "external_source_event_id": "str?", "notes": "str?",
  "parse_record": {"raw_text": "str", "parsed_json": "object?"}? }
```
校验底线：至少具备「联系方式、可识别姓名+来源、需求描述+来源、或可信外部事件引用」之一，否则 `VALIDATION_ERROR`。企业名称选填（`company_id` 可空）。响应 `Lead` + `company_candidates: [Company]` + `duplicate_hints: [str]`（非阻塞提示：疑似同一联系人等，ADR-020）。外部渠道幂等由 `external_source_event_id`（渠道内唯一）或 `Idempotency-Key` 保证（ADR-019）——同一渠道重复推送 `external_source_event_id` 时幂等复用已存在线索（不重复创建）。

`parse_record`（AI 解析记录）随创建落库 `lead_parse_records`：`raw_text` 原文必保留、`parsed_json` 可选，`lead_id` 创建后回填。

**POST /leads/parse** 请求：`{"raw_text": "str"}`（AI 只提取，不落库、不创建客户/线索）。响应：

```json
{ "company_name": {"value": "str?", "confidence": "high|medium|low?"},
  "contact_name": {"value": "str?", "confidence": "..."},
  "phone": {"value": "str?", "confidence": "..."},
  "email": {"value": "str?", "confidence": "..."},
  "inquiry_text": {"value": "str?", "confidence": "..."},
  "need_type": {"value": "str?", "confidence": "..."},
  "source_channel": {"value": "str?", "confidence": "..."},
  "hints": ["str"] }
```

约束：AI 不得编造信息，未提供的信息 `value`/`confidence` 均为 `null`；`need_type` 仅在系统字典 `lead_need_types` 存在匹配项时才返回，否则 `value` 置空并在 `hints` 提示；格式错误/字段歧义写入 `hints`。未配置/超时返回 503 `AI_UNAVAILABLE`。

**POST /leads/duplicate-check** 请求：`{"phone_raw"?, "email_raw"?, "company_name_raw"?, "external_source_event_id"?, "source_category_id"?}`。响应：

```json
{ "contact_duplicate": "bool", "contact_hint": "str?",
  "company_candidates": "[Company]", "external_event_conflict": "bool" }
```

覆盖四类情形：手机号/邮箱规范化后命中 → `contact_duplicate`（提示疑似同一联系人）；企业名匹配 → `company_candidates`（提示已有企业）；同一渠道 `external_source_event_id` 已存在 → `external_event_conflict`（创建时阻止并幂等复用）。

**PATCH /leads/{id}** 请求：`{"version": int, ...可编辑原始字段}`；版本不匹配返回 409；变更写 `lead_events` 审计。

**GET /leads/{id}/timeline** 统一聚合线索创建、电话、微信申请、微信通过、微信沟通、备注、有效性变化、部门移交、部门反馈，按实际发生时间倒序。每项含 `id`、`type`（清晰类型字段，前端据此画图标）、`result`（操作结果）、`content`（内容）、`happened_at`（实际发生时间）、`recorded_at`（系统记录时间）、`created_by`、`created_by_name`。

`type` 取值：`lead_created`（线索创建）、`phone`（电话联系）、`wechat_request`（微信申请）、`wechat_approved`（微信通过）、`wechat_chat`（微信沟通）、`note`（备注）、`qualification`（线索有效性变化，`result`=qualification_status）、`handoff`（部门移交，`content`=目标部门名）、`outcome`（部门反馈变化，`result`=outcome_status）。

## 5. 企业匹配与客户 `/companies`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/leads/{id}/company-candidates` | 可能关联企业候选（name/phone/email 规范化匹配） |
| POST | `/leads/{id}/link-company` | 关联线索到企业 |
| DELETE | `/leads/{id}/company-link` | 解除关联（审计） |
| GET | `/companies` | 企业列表（检索 + 去重提示） |
| POST | `/companies` | 新建 |
| GET | `/companies/{id}` | 详情（含联系人、关联线索） |
| PATCH | `/companies/{id}` | 更新 |
| GET | `/companies/{id}/leads` | 该企业关联的全部线索 |
| GET | `/companies/{id}/contacts` | 该企业全部联系人 |
| POST | `/companies/{id}/contacts` | 新增联系人（关联该企业） |
| PATCH | `/contacts/{id}` | 更新联系人 |
| POST | `/companies/merge-preview` | 合并影响预览（仅 admin） |
| POST | `/companies/merge` | 确认执行合并（仅 admin，审计） |

**POST /leads/{id}/link-company** 请求：`{"company_id": "uuid", "contact_id": "uuid?"}`；写 `lead_events` 审计。企业归属变化不覆盖 `company_name_raw` 与来源快照。

**GET /companies** 响应 `Page[CompanyListItem]`；`CompanyListItem = { id, canonical_name, industry?, phone?, website?, lead_count, recent_inquiry_at? }`（`lead_count`/`recent_inquiry_at` 为聚合派生字段）。

**GET /companies/{id}** 响应 `CompanyDetail = { id, canonical_name, normalized_name, aliases, industry?, phone?, website?, merged_into_id?, contacts: [Contact], leads: [Lead] }`。联系电话/官网读企业 `phone`/`website` 字段（不做主联系人推导、不加 is_primary）。

**POST /companies/merge-preview** 请求：`{"source_company_id": "uuid", "target_company_id": "uuid"}`；返回影响预览：`{lead_relink_count: int, contact_merge_count: int, alias_destination: string}`（将重指线索数、将归并联系人数、别名去向 = 目标企业 canonical_name）。与 `POST /companies/merge`（确认执行）分离，仅 admin。

**POST /companies/merge** 请求：`{"source_company_id": "uuid", "target_company_id": "uuid", "reason": "str?"}`；仅 admin；保留线索快照与审计（ADR-024）。模糊匹配不得直接合并（ADR-019/020）。

## 6. 跟进活动 `/activities`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/leads/{id}/activities` | 该线索全部未撤销活动（撤销事件不回传） |
| POST | `/leads/{id}/activities` | 新增（幂等；列表快捷 +1 走同一接口） |
| PATCH | `/activities/{id}` | 修正事件（发生时间/结果/内容，写 `lead_event_revisions` 留痕） |
| POST | `/activities/{id}/revoke` | 撤销（创建者本人或 admin，原因必填 + 审计，软删除） |

**POST /leads/{id}/activities** 请求：
```json
{ "kind": "phone|wechat_request|wechat_approved|wechat_chat|note",
  "result": "connected|unconnected|rejected (仅电话)", "content": "str? (<=2000)",
  "happened_at": "ISO 8601 (默认服务端当前时间，可补录)",
  "next_follow_up_at": "ISO 8601?", "idempotency_key": "str" }
```
约束：
- `phone` 的 `result` ∈ {connected,unconnected,rejected}，一通电话一条事件；`wechat_*`/`note` 不写联系结果（result 省略或 null）。
- `happened_at` 默认当前时间，允许补录过去时间，**严格禁止未来时间**（不得晚于服务器当前时间，无容忍窗口）。
- 微信三态：`wechat_request`（发送好友申请，关系→待通过）、`wechat_approved`（申请通过，生成新的通过事件，关系→已通过，**不修改历史申请记录**）、`wechat_chat`（微信沟通，**仅当当前微信关系为已通过**才允许）。
- 微信关系 `wechat_relationship`（none/pending/approved）由最新一条有效微信事件实时派生，不落冗余列（ADR-028）。
- 电话累计次数 = 有效 phone 事件数实时聚合，不信任前端（ADR-019 层次①防重复计数）。
- 记录非 `note` 沟通事件后，服务端将线索 `next_follow_up_at` 更新为请求传入的 `next_follow_up_at`（传值则设为该值、未传则清空），作为线索下次计划跟进时间（落库 `leads.next_follow_up_at`）；`note` 不改变该字段。

**PATCH /activities/{id}** 请求：`{"reason": "str(必填)", "happened_at"?, "result"?, "content"?}`；仅 admin 或该事件创建者可修正；修正发生时间/结果/内容并写 `lead_event_revisions`（`before_json`/`after_json`/`reason`/`revised_by`）；系统 `created_at` 不可改；至少提供一项修正；`result` 仅电话可设；修正后 `happened_at` 仍禁止未来时间。

## 7. 判断 / 交接 / 反馈

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/leads/{id}/qualification` | 初筛结论（valid 可交接；invalid 必填原因） |
| POST | `/leads/{id}/handoff` | 部门交接（仅 valid；默认对接人可改选） |
| POST | `/leads/{id}/outcome` | 部门进展反馈（依据简述 + 反馈时间） |

**POST /leads/{id}/qualification** 请求：`{"qualification_status": "valid|invalid", "reason": "str?"}`；`invalid` 必填 `reason`；写 `lead_events` 审计。电话次数不得自动改为有效。

**POST /leads/{id}/handoff** 请求：`{"department_id": "uuid", "department_contact_id": "uuid?", "note": "str?", "reason": "str?"}`；仅 `qualification_status=valid` 可交接；记录交接日期/操作人，改派保留历史（`lead_handoffs`）。

**POST /leads/{id}/outcome** 请求：`{"outcome_status": "unknown|in_progress|won|lost|deferred", "note": "str?", "feedback_at": "ISO 8601?"}`；`deferred` 为暂缓；`won`/`lost` 最终结果需依据简述；未收到反馈保持 `unknown`，不得推断为 `lost`；每次变化写独立的 `lead_outcome_events` 留痕（不覆盖历史），并进入统一时间线。

## 8. 导入导出 `/imports` 与 `/leads/export`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/imports/template` | 下载导入模板（.xlsx/.csv） |
| POST | `/imports/preview` | 上传并预览（返回 preview token + 逐行错误/疑似重复） |
| POST | `/imports/commit` | 提交入库（重新校验 + 批次幂等） |
| GET | `/imports/{id}` | 导入结果（成功/失败/跳过行 + 错误明细） |
| GET | `/leads/export` | 导出当前筛选数据（受控 + 防公式注入 + 审计） |

**POST /imports/preview**：`multipart/form-data`（.xlsx/.csv，大小/行数上限可配置）；响应 `{preview_token, total_rows, valid_rows, duplicates: int, errors: [{row_number, message}]}`（`duplicates` 为疑似重复行计数，非数组）。

**POST /imports/commit**：`{"preview_token": "str", "idempotency_key": "str"}`；提交前重新校验；返回 `{batch_id, success_rows, failed_rows, skipped_rows}`（`batch_id` 即导入批次 ID；幂等重试返回首次结果）。重试不得重复导入已提交行。

**GET /imports/{id}** 响应：`{batch_id, filename, status, total_rows, success_rows, failed_rows, rows: [{row_number, status, message?, lead_id?}]}`。

**GET /leads/export**：按当前筛选导出 CSV/Excel；手机号/邮箱导出权限受控并审计；转义 Excel 公式注入前缀；带数据口径说明。

## 9. 工作台与报表

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/dashboard/summary` | 工作台指标（新增线索/去重企业/待确认/有效/已交接/暂无反馈/电话次数/微信量/已知成交） |
| GET | `/dashboard/trend` | 趋势（按天分桶：线索/有效/交接，Asia/Shanghai，补空日期） |
| GET | `/reports/overview` | 线索与企业概览（线索数/去重企业数/有效率） |
| GET | `/reports/sources` | 来源分析（按分类与详情：数量/有效数/交接数） |
| GET | `/reports/activities` | 活动工作量（按操作者统计电话/微信事件） |
| GET | `/reports/handoffs` | 部门交接分布与反馈（交接次数/当前分布/暂无反馈/推进中/赢单/输单） |
| GET | `/reports/export` | 报表导出 |

查询通用：`from`/`to`（日期区间，默认本月）；报表为聚合结果，无分页。统计口径：线索/概览/来源按 `occurred_at`，活动/交接按 `happened_at`；导出时间展示为 Asia/Shanghai。

**GET /dashboard/summary** 响应：`{total_leads, distinct_companies, pending, valid, handed_off, no_feedback, won, phone_total, wechat_count, pending_to_confirm, valid_not_handed_off, handed_off_no_feedback, todos, todo_list, recent_leads, recent_events}`；其中 `todos` = 各待办分类计数 `{overdue, first_follow, today, no_progress, stale, handed_off_pending}`，`todo_list` = 优先级排序的待办线索清单（≤20 条，含 `lead_id`/`company_name_raw`/`contact_name_raw`/`qualification_status`/`outcome_status`/`follow_up_count`/`last_followup_at`/`next_follow_up_at`/`todo`），`recent_leads` = 最近新增线索（≤5 条），`recent_events` = 最近动态（≤20 条）。

**`recent_events`** 每项：`{event_type, occurred_at, actor_name}`。`event_type` 取值（dotted，与 §4 时间线 `type` 的 snake_case 区分，各自按实现标注）：`lead.created`、`lead.updated`、`lead.archived`、`lead.unarchived`、`lead.company_link`、`lead.company_unlink`、`lead.qualification`、`lead.handoff`、`lead.outcome`；活动事件为 `phone`、`wechat_request`、`wechat_approved`、`wechat_chat`、`note`。

**GET /dashboard/trend** 响应：`{buckets: [{date, leads, valid, handed_off}]}`；`date` 为 `YYYY-MM-DD`，`from`/`to` 省略时默认本月；按 `occurred_at`（线索/有效）与 `happened_at`（交接）归到 Asia/Shanghai 日期，缺日补 0。

**GET /reports/overview** 响应：`{total_leads, distinct_companies, valid, invalid, pending, effective_rate, handed_off, outcome_won, outcome_lost, outcome_in_progress, no_feedback}`；`effective_rate` = valid/(valid+invalid)，分母 0 为 `null`；outcome 为标量计数（非数组）。

**GET /reports/sources** 响应：`[{category_id, category_name, lead_count, valid_count, handed_off_count}]`（按来源分类聚合的列表）。

**GET /reports/activities** 响应：`[{user_id, display_name, total, phone_total}]`（total=全部活动次数，phone_total=电话拨打累计）。

**GET /reports/handoffs** 响应：`[{department, count}]`（部门交接次数分布）。

**GET /reports/export**、**GET /leads/export**：CSV 导出；手机/邮箱脱敏、时间转 Asia/Shanghai、防公式注入（`=`/`+`/`-`/`@`/制表符前缀加单引号转义）。

## 10. 管理 `/admin` 与设置 `/settings`（写操作仅 admin）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/users` | 用户列表 |
| POST | `/admin/users` | 创建用户（role 仅 admin/market，设初始密码 must_change_password=true） |
| PATCH | `/admin/users/{id}` | 更新（禁用/重置密码/赋角色） |
| GET/POST | `/settings/departments` | 部门列表/新建 |
| GET/PATCH | `/settings/departments/{id}` | 部门详情/更新（启停） |
| GET/POST | `/settings/department-contacts` | 部门对接人列表/新建 |
| GET/PATCH | `/settings/department-contacts/{id}` | 对接人详情/更新（含默认关系） |
| GET/POST | `/settings/source-categories` | 来源分类列表/新建 |
| GET/PATCH | `/settings/source-categories/{id}` | 来源分类详情/更新（启停） |
| GET/POST | `/settings/source-details` | 来源详情列表/新建（受控输入，避免字典爆炸） |
| GET/PATCH | `/settings/source-details/{id}` | 来源详情详情/更新 |
| GET/POST | `/settings/need-types` | 需求类型列表/新建 |
| GET/PATCH | `/settings/need-types/{id}` | 需求类型详情/更新 |
| GET | `/settings/ai` | AI 配置读取（admin/market，密钥脱敏） |
| PUT/POST | `/settings/ai` | AI 配置保存（仅 admin + CSRF） |
| DELETE | `/settings/departments/{id}`、`/settings/department-contacts/{id}`、`/settings/source-categories/{id}`、`/settings/source-details/{id}`、`/settings/need-types/{id}` | 物理删除（仅未被引用时；被引用返回 409，改用停用） |
| POST | `/settings/department-contacts/{id}/reassign` | 批量改派：把该对接人名下存量线索转给同部门另一对接人（保留历史），返回 `{moved_leads}` |

字典启停不得破坏历史数据（外键保留）；删除有引用保护（被线索/历史引用则 409，改用停用或批量改派）。`PATCH /admin/users/{id}` 禁用后撤销会话、停止新登录、审计权限变更。market 可读 `/settings/*` 字典（供下拉），但不可写。部门/对接人/来源/需求类型均为初始化可编辑配置，不得写死（PRD §5.8）。来源分类当前精简为「官网 / 其他」两项。

字典写端点（POST/PATCH）仅 admin + CSRF，支持 `active` 启停（来源分类/详情、需求类型、部门、对接人）与 `is_default`（部门默认对接人）。

**GET/PUT/POST /settings/ai**：AI Provider 配置（ADR-029，存 `app_settings`，键 `ai_provider`）。`GET` 对 admin/market 开放，返回 `{provider, endpoint, model, timeout_seconds, api_key_configured, api_key, updated_at}`——密钥仅写入不读回：`api_key_configured` 为是否已配置的布尔值，`api_key` 为脱敏占位（`***configured***` 或 `null`），绝不返回真实密钥。`PUT`/`POST` 仅 admin + CSRF，请求 `{provider, endpoint, model, api_key?, timeout_seconds?}`；`api_key` 语义：`null` 保留现有密钥、非空字符串覆盖、空字符串清除。

分组口径：`/admin/*` 仅承载用户账号（`/admin/users`）；`/settings/*` 承载全部业务字典（部门、部门对接人、来源分类、来源详情、需求类型）；两组写操作均仅 admin。market 只读 GET 全部 `/settings/*` 字典（供列表筛选与展示），不可写；用户账号（`/admin/users`）对 market 完全不可见。

## 11. AI 增强（并入 `/leads/parse` 与 `/settings/ai`）

V1.3 的 `/ai/lead-summary`、`/ai/handoff-draft` 已移除；V1.4 的 AI 能力由 `POST /leads/parse`（字段提取，§4）与 `/settings/ai`（Provider 配置，§10）承载。AI 仅提取信息，不创建/修改客户数据（ADR-029）；未配置/超时返回 503 `AI_UNAVAILABLE`，不影响任何主流程。

## 12. 权限矩阵速查（服务端强制）

| 端点 | market | admin |
|---|---|---|
| `GET/POST /leads`、`GET/PATCH /leads/{id}`、`timeline` | 是（全部线索） | 全部 |
| `POST /leads/{id}/archive` | 否 | 是 |
| 企业匹配 `company-candidates`/`link-company`/`company-link` | 是 | 全部 |
| `GET/POST /companies`、`GET/PATCH /companies/{id}`、`GET /companies/{id}/leads` | 是（维护基础资料） | 全部 |
| `GET/POST /companies/{id}/contacts`、`PATCH /contacts/{id}` | 是（维护基础资料） | 全部 |
| `POST /companies/merge-preview`、`POST /companies/merge` | 否 | 是 |
| `GET/POST /leads/{id}/activities` | 是（全部线索） | 全部 |
| `POST /activities/{id}/revoke` | 是（仅自己创建的） | 是（任意） |
| `POST /leads/{id}/qualification\|handoff\|outcome` | 是（全部线索） | 全部 |
| `/imports/*`、`GET /leads/export` | 是（受控导出） | 全部 |
| `GET /dashboard/*`、`GET /reports/*` | 是（全量口径） | 全部 |
| `GET /settings/departments`、`GET /settings/department-contacts`、`GET /settings/source-categories`、`GET /settings/source-details`、`GET /settings/need-types`、`GET /settings/ai` | 是（只读字典/配置） | 全部 |
| `GET/POST/PATCH /admin/users`、`/settings/*` 写 | 否 | 是 |

## 13. 运维端点（非业务 API，独立于 `/api/v1`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 存活探针（liveness）：不鉴权、不查库，仅返回 `{"status":"ok"}`，不泄露配置/客户信息 |

> `/readyz` 为 Nginx 层的全栈就绪别名，反向代理到后端 `/healthz`，非独立后端路由（见 `infra/nginx/app.conf`、`docs/deployment.md`）。backend 仅实现 `/healthz`，无需实现 `/readyz`。
