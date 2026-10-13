# S0 架构与契约切片 · 轻量复盘草稿

> 状态：草稿（待 #4 基础工程与登录鉴权交付后固化）
> 日期：2026-10-10
> 复盘对象：task #1（产出架构、契约、验收与实施计划文档）
> 复盘人：DistillAgent
> 关联：`docs/decisions.md`（ADR-001~014）、`docs/api-contract.md`、`docs/architecture.md`、`docs/acceptance.md`、`docs/implementation-plan.md`、`docs/qa-test-plan.md`

## 1. 背景

项目冷启动，仓库为空（仅 PRD 与解决方案 HTML）。task #1 的目标是在编码前先把「结构与契约」定下来：仓库骨架 + 8 份基线文档（AGENTS / README / PRD / architecture / api-contract / acceptance / decisions / deployment）+ 实施计划 + QA 测试计划。多 Agent 并行协作：architect（架构）、product（需求澄清）、api（契约）、qa（测试计划）、distill（复盘），team-lead 作为 FDE 拍板。

## 2. 做法

- **架构与契约前置**：先落盘全部文档与目录骨架，再进入可运行工程（#4）。避免一次性生成大量未连接的页面。
- **ADR 驱动决策**：14 条 ADR 固化技术选型（单体前后端分离、同步 SQLAlchemy、HttpOnly Cookie 会话、Argon2id、UUID 主键、软删除、可插拔 AI Provider、Axios、Alembic 唯一迁移入口、定时作业替代消息队列、不引入 Redis/向量库），以及契约澄清（ADR-012/013/014）。
- **DoD 与验收前置**：`AGENTS.md` §6 定义切片完成定义（迁移+API+前端+权限+测试+文档+可运行验证）；`acceptance.md` + `qa-test-plan.md` 以悲观立场逐条映射 PRD §16 验收项。
- **契约缺口收敛流程**：product 通读 PRD 提歧义 → api/architect 交叉校验 → team-lead 拍板，闭环写入 ADR。

## 3. 契约缺口如何被发现与收敛

- **发现机制**：product 通读 PRD 提出 12 个缺口/歧义点；architect/qa 从状态机、权限矩阵、幂等、时区等维度交叉检查。
- **缺口 1（ADR-012，状态机 vs API 清单不一致）**：PRD §7 要求销售「开始跟进」为显式动作、商机终态需「显式重开」，但 §12 API 清单只列了 `assign/close/reopen/convert` 与商机 `/transition`，缺两个端点。收敛：新增 `POST /leads/{id}/start-following` 与 `POST /opportunities/{id}/reopen`，与线索 `reopen` 对称。
- **缺口 2（ADR-013，业务歧义 8 条收敛）**：AI 话术草稿并入 `POST /ai/followup-suggestion`（不单列 contact-script）；任务取消走 `PATCH /tasks/{id}`；角色固定枚举 `market/sales/admin` 无 CRUD；AI 配置 env-only、§5「AI 配置」页降级为只读/连通性测试；联系方式可见性以 §2 角色矩阵为唯一权限源；客户负责人默认创建人且不随线索/商机负责人变更；导入结果返回 JSON、前端导出 CSV（服务端防公式注入）；AI 验收补「输出可编辑、记录生成时间与人工确认状态、不自动改写、不自动对外发送」。
- **缺口 3（ADR-014，横切约定）**：`request_id` 由服务端生成/回显 `X-Request-Id`，贯穿审计；复盘资产落盘 `ai-crm/docs/retrospectives/`，组织级 `ai-assets/` 暂缓。

## 4. 踩坑

1. **团队共享配置并发写坏**：多 Agent 同时写共享 `.opcteam/.opcteam.json`，产生 5 份时间递增的 backup（08:51→09:03），需恢复。教训：共享配置文件应由单一 owner 串行写，其余 agent 只读；或落盘前加锁。
2. **并发编辑共享文档导致读到中间态（误判为缺口）**：distill 复核 `api-contract.md` 时读到 api agent 编辑中途的旧态（§4 缺 start-following、§6 缺 reopen），误报「ADR-012 未回填」；team-lead 复读最新文件确认两端点均已落地（§4/§6 + §13 权限矩阵）。教训：① 多 Agent 并发编辑同一文档时，读者可能看到不一致的中间态，下结论前应二次确认最新文件；② ADR 决策回填契约文档存在窗口期，验收应以「编辑完成态」为准，而非中间快照。

## 5. 结论

- 架构前置 + ADR 驱动的做法有效：契约缺口在编码前被收敛，状态机、权限、幂等、时区等高风险点在文档层已有明确约束，为后续切片降低返工。
- 待固化（#4 交付后正式复盘落实）：
  1. 已确认 `api-contract.md` 含 ADR-012 两端点（`POST /leads/{id}/start-following`、`POST /opportunities/{id}/reopen`），无需再补。
  2. 建立「ADR 变更 → 契约/架构/验收文档同步」的检查清单，纳入切片 DoD。
  3. 共享配置/文档写冲突的规避约定（owner 单一化 / 编辑完成态确认）。
- 反哺统筹：S0→S1（#4 基础工程+登录）依赖链路正常，已 in_progress。建议后续切片交付说明附带「实际改动文件 + 测试命令与结果 + 踩坑 + 遗留」，供本复盘直接沉淀，减少二次询问。
