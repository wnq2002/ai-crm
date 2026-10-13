<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  createDepartment,
  createDepartmentContact,
  createNeedType,
  createSourceCategory,
  deleteDepartment,
  deleteDepartmentContact,
  deleteNeedType,
  deleteSourceCategory,
  listDepartmentContacts,
  listDepartments,
  listNeedTypes,
  listSourceCategories,
  reassignContactLeads,
  updateDepartment,
  updateDepartmentContact,
  updateNeedType,
  updateSourceCategory,
} from '@/api/dictionaries'
import { createUser, listUsers, updateUser, type UserUpdatePayload } from '@/api/admin'
import { getAIConfig, saveAIConfig, type AIConfig } from '@/api/settings'
import { getErrorMessage } from '@/api/http'
import { formatDateTime } from '@/utils'
import type {
  Department,
  DepartmentContact,
  NeedType,
  Role,
  SourceCategory,
  User,
} from '@/types'

const activeTab = ref('departments')
const showInactive = ref(false)

const departments = ref<Department[]>([])
const contacts = ref<DepartmentContact[]>([])
const categories = ref<SourceCategory[]>([])
const needTypes = ref<NeedType[]>([])
const users = ref<User[]>([])

const shownDepartments = computed(() =>
  departments.value.filter((d) => showInactive.value || d.active),
)
const shownContacts = computed(() =>
  contacts.value.filter((c) => showInactive.value || c.active),
)
const shownCategories = computed(() =>
  categories.value.filter((c) => showInactive.value || c.active),
)
const shownNeedTypes = computed(() =>
  needTypes.value.filter((t) => showInactive.value || t.active),
)
const activeDepartments = computed(() => departments.value.filter((d) => d.active))

const aiConfig = ref<AIConfig | null>(null)
const aiLoading = ref(false)
const aiSaving = ref(false)
const aiForm = reactive({
  provider: '',
  endpoint: '',
  model: '',
  timeout_seconds: 30,
  api_key: '',
})
const clearKey = ref(false)

const deptMap = ref(new Map<string, string>())

function rebuildMaps(): void {
  deptMap.value = new Map(departments.value.map((d) => [d.id, d.name]))
}

// ── 载入 ─────────────────────────────────────────────
async function loadAll(): Promise<void> {
  try {
    const [depts, cts, cats, nts, us] = await Promise.all([
      listDepartments(),
      listDepartmentContacts(),
      listSourceCategories(),
      listNeedTypes(),
      listUsers(),
    ])
    departments.value = depts
    contacts.value = cts
    categories.value = cats
    needTypes.value = nts
    users.value = us.items
    rebuildMaps()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function reload<K extends keyof typeof loaders>(what: K): Promise<void> {
  await loaders[what]()
  rebuildMaps()
}

const loaders = {
  departments: async () => {
    departments.value = await listDepartments()
  },
  contacts: async () => {
    contacts.value = await listDepartmentContacts()
  },
  categories: async () => {
    categories.value = await listSourceCategories()
  },
  needTypes: async () => {
    needTypes.value = await listNeedTypes()
  },
  users: async () => {
    users.value = (await listUsers()).items
  },
}

async function loadAIConfig(): Promise<void> {
  aiLoading.value = true
  try {
    const cfg = await getAIConfig()
    aiConfig.value = cfg
    aiForm.provider = cfg.provider ?? ''
    aiForm.endpoint = cfg.endpoint ?? ''
    aiForm.model = cfg.model ?? ''
    aiForm.timeout_seconds = cfg.timeout_seconds ?? 30
    aiForm.api_key = ''
    clearKey.value = false
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    aiLoading.value = false
  }
}

async function submitAIConfig(): Promise<void> {
  if (!aiForm.provider.trim() || !aiForm.endpoint.trim() || !aiForm.model.trim()) {
    ElMessage.warning('请填写服务商、接口地址与模型')
    return
  }
  aiSaving.value = true
  try {
    const payload: {
      provider: string
      endpoint: string
      model: string
      api_key?: string
      timeout_seconds: number
    } = {
      provider: aiForm.provider.trim(),
      endpoint: aiForm.endpoint.trim(),
      model: aiForm.model.trim(),
      timeout_seconds: aiForm.timeout_seconds,
    }
    if (clearKey.value) {
      payload.api_key = ''
    } else if (aiForm.api_key.trim()) {
      payload.api_key = aiForm.api_key.trim()
    }
    aiConfig.value = await saveAIConfig(payload)
    aiForm.api_key = ''
    clearKey.value = false
    ElMessage.success('已保存 AI 配置')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    aiSaving.value = false
  }
}

function deptName(id: string): string {
  return deptMap.value.get(id) ?? id
}

// ── 部门 ─────────────────────────────────────────────
const deptDialog = reactive({ visible: false, name: '' })

function openCreateDepartment(): void {
  deptDialog.name = ''
  deptDialog.visible = true
}

async function submitDepartment(): Promise<void> {
  if (!deptDialog.name.trim()) {
    ElMessage.warning('请输入部门名称')
    return
  }
  try {
    await createDepartment({ name: deptDialog.name.trim() })
    ElMessage.success('已新增部门')
    deptDialog.visible = false
    await reload('departments')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function renameDepartment(d: Department): Promise<void> {
  let value: string
  try {
    ;({ value } = await ElMessageBox.prompt('新名称', '修改部门', {
      inputValue: d.name,
      inputPattern: /\S+/,
      inputErrorMessage: '不能为空',
    }))
  } catch {
    return
  }
  try {
    await updateDepartment(d.id, { name: value.trim() })
    ElMessage.success('已更新')
    await reload('departments')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function toggleDepartment(d: Department, value: boolean): Promise<void> {
  try {
    await updateDepartment(d.id, { active: value })
    ElMessage.success('已更新')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
    await reload('departments')
  }
}

// ── 部门对接人 ───────────────────────────────────────
const contactDialog = reactive({
  visible: false,
  department_id: '',
  name: '',
  is_default: false,
})

function openCreateContact(): void {
  contactDialog.department_id = activeDepartments.value[0]?.id ?? ''
  contactDialog.name = ''
  contactDialog.is_default = false
  contactDialog.visible = true
}

async function submitContact(): Promise<void> {
  if (!contactDialog.department_id || !contactDialog.name.trim()) {
    ElMessage.warning('请选择部门并填写姓名')
    return
  }
  try {
    await createDepartmentContact({
      department_id: contactDialog.department_id,
      name: contactDialog.name.trim(),
      is_default: contactDialog.is_default,
    })
    ElMessage.success('已新增对接人')
    contactDialog.visible = false
    await reload('contacts')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function renameContact(c: DepartmentContact): Promise<void> {
  let value: string
  try {
    ;({ value } = await ElMessageBox.prompt('新姓名', '修改对接人', {
      inputValue: c.name,
      inputPattern: /\S+/,
      inputErrorMessage: '不能为空',
    }))
  } catch {
    return
  }
  try {
    await updateDepartmentContact(c.id, { name: value.trim() })
    ElMessage.success('已更新')
    await reload('contacts')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function toggleContact(c: DepartmentContact, value: boolean): Promise<void> {
  try {
    await updateDepartmentContact(c.id, { active: value })
    ElMessage.success('已更新')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
    await reload('contacts')
  }
}

async function toggleContactDefault(c: DepartmentContact, value: boolean): Promise<void> {
  try {
    await updateDepartmentContact(c.id, { is_default: value })
    ElMessage.success('已更新')
    await reload('contacts')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

// ── 来源分类 ─────────────────────────────────────────
const categoryDialog = reactive({ visible: false, code: '', name: '' })

function openCreateCategory(): void {
  categoryDialog.code = ''
  categoryDialog.name = ''
  categoryDialog.visible = true
}

async function submitCategory(): Promise<void> {
  if (!categoryDialog.code.trim() || !categoryDialog.name.trim()) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  try {
    await createSourceCategory({
      code: categoryDialog.code.trim(),
      name: categoryDialog.name.trim(),
    })
    ElMessage.success('已新增来源分类')
    categoryDialog.visible = false
    await reload('categories')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function toggleCategory(c: SourceCategory, value: boolean): Promise<void> {
  try {
    await updateSourceCategory(c.id, { active: value })
    ElMessage.success('已更新')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
    await reload('categories')
  }
}

// ── 需求类型 ─────────────────────────────────────────
const needTypeDialog = reactive({ visible: false, name: '' })

function openCreateNeedType(): void {
  needTypeDialog.name = ''
  needTypeDialog.visible = true
}

async function submitNeedType(): Promise<void> {
  if (!needTypeDialog.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  try {
    await createNeedType({ name: needTypeDialog.name.trim() })
    ElMessage.success('已新增需求类型')
    needTypeDialog.visible = false
    await reload('needTypes')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function toggleNeedType(t: NeedType, value: boolean): Promise<void> {
  try {
    await updateNeedType(t.id, { active: value })
    ElMessage.success('已更新')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
    await reload('needTypes')
  }
}

async function renameCategory(c: SourceCategory): Promise<void> {
  let value: string
  try {
    ;({ value } = await ElMessageBox.prompt('新名称', '修改来源分类', {
      inputValue: c.name,
      inputPattern: /\S+/,
      inputErrorMessage: '不能为空',
    }))
  } catch {
    return
  }
  try {
    await updateSourceCategory(c.id, { name: value.trim() })
    ElMessage.success('已更新')
    await reload('categories')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function renameNeedType(t: NeedType): Promise<void> {
  let value: string
  try {
    ;({ value } = await ElMessageBox.prompt('新名称', '修改需求类型', {
      inputValue: t.name,
      inputPattern: /\S+/,
      inputErrorMessage: '不能为空',
    }))
  } catch {
    return
  }
  try {
    await updateNeedType(t.id, { name: value.trim() })
    ElMessage.success('已更新')
    await reload('needTypes')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

// ── 账号 ─────────────────────────────────────────────
const userDialog = reactive({
  visible: false,
  username: '',
  display_name: '',
  role: 'market' as Role,
  password: '',
})

function openCreateUser(): void {
  userDialog.username = ''
  userDialog.display_name = ''
  userDialog.role = 'market'
  userDialog.password = ''
  userDialog.visible = true
}

async function submitUser(): Promise<void> {
  if (!userDialog.username.trim() || !userDialog.display_name.trim() || userDialog.password.length < 8) {
    ElMessage.warning('用户名/显示名必填，初始密码至少 8 位')
    return
  }
  try {
    await createUser({
      username: userDialog.username.trim(),
      display_name: userDialog.display_name.trim(),
      role: userDialog.role,
      password: userDialog.password,
    })
    ElMessage.success('已创建账号')
    userDialog.visible = false
    await reload('users')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function toggleUser(u: User, value: boolean): Promise<void> {
  try {
    await updateUser(u.id, { is_active: value })
    ElMessage.success('已更新')
    await reload('users')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function changeUserRole(u: User): Promise<void> {
  const next: Role = u.role === 'admin' ? 'market' : 'admin'
  try {
    await updateUser(u.id, { role: next })
    ElMessage.success('已更新角色')
    await reload('users')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function resetUserPassword(u: User): Promise<void> {
  let value: string
  try {
    ;({ value } = await ElMessageBox.prompt(`为 ${u.username} 设置新密码（至少 8 位）`, '重置密码', {
      inputPattern: /^\S{8,128}$/,
      inputErrorMessage: '密码需 8-128 位且不含空格',
    }))
  } catch {
    return
  }
  try {
    const payload: UserUpdatePayload = { new_password: value }
    await updateUser(u.id, payload)
    ElMessage.success('已重置密码')
    await reload('users')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function confirmDelete(fn: () => Promise<void>, label: string): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除「${label}」？此操作不可恢复。`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await fn()
    ElMessage.success('已删除')
    await loadAll()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

function removeDepartment(d: Department): void {
  confirmDelete(() => deleteDepartment(d.id), d.name)
}
function removeContact(c: DepartmentContact): void {
  confirmDelete(() => deleteDepartmentContact(c.id), c.name)
}
function removeCategory(c: SourceCategory): void {
  confirmDelete(() => deleteSourceCategory(c.id), c.name)
}
function removeNeedType(t: NeedType): void {
  confirmDelete(() => deleteNeedType(t.id), t.name)
}

const reassignVisible = ref(false)
const reassigning = ref(false)
const reassignSource = ref<DepartmentContact | null>(null)
const reassignTargetId = ref('')

const reassignCandidates = computed(() =>
  contacts.value.filter(
    (c) =>
      c.id !== reassignSource.value?.id &&
      c.department_id === reassignSource.value?.department_id &&
      c.active,
  ),
)

function openReassign(c: DepartmentContact): void {
  reassignSource.value = c
  reassignTargetId.value = ''
  reassignVisible.value = true
}

async function submitReassign(): Promise<void> {
  if (!reassignSource.value || !reassignTargetId.value) {
    ElMessage.warning('请选择目标对接人')
    return
  }
  reassigning.value = true
  try {
    const res = await reassignContactLeads(reassignSource.value.id, reassignTargetId.value)
    ElMessage.success(`已转接 ${res.moved_leads} 条线索`)
    reassignVisible.value = false
    await loadAll()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    reassigning.value = false
  }
}

function roleLabel(role: Role): string {
  return role === 'admin' ? '管理员' : '市场部'
}

onMounted(() => {
  loadAll()
  loadAIConfig()
})
</script>

<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="settings-toolbar">
        <el-switch v-model="showInactive" active-text="显示已停用" />
      </div>
      <el-tabs v-model="activeTab">
        <!-- 部门 -->
        <el-tab-pane label="部门" name="departments">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="openCreateDepartment">新增部门</el-button>
          </div>
          <el-table :data="shownDepartments" size="small">
            <el-table-column prop="name" label="名称" min-width="160" />
            <el-table-column label="启用" width="100">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.active"
                  @change="(v: string | number | boolean) => toggleDepartment(row, Boolean(v))"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="renameDepartment(row)">编辑</el-button>
                <el-button link type="danger" @click="removeDepartment(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 部门对接人 -->
        <el-tab-pane label="部门对接人" name="contacts">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="openCreateContact">新增对接人</el-button>
          </div>
          <el-table :data="shownContacts" size="small">
            <el-table-column label="部门" min-width="140">
              <template #default="{ row }">{{ deptName(row.department_id) }}</template>
            </el-table-column>
            <el-table-column prop="name" label="姓名" min-width="120" />
            <el-table-column label="默认" width="90">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_default"
                  @change="(v: string | number | boolean) => toggleContactDefault(row, Boolean(v))"
                />
              </template>
            </el-table-column>
            <el-table-column label="启用" width="90">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.active"
                  @change="(v: string | number | boolean) => toggleContact(row, Boolean(v))"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="210">
              <template #default="{ row }">
                <el-button link type="primary" @click="renameContact(row)">编辑</el-button>
                <el-button link type="warning" @click="openReassign(row)">批量改派</el-button>
                <el-button link type="danger" @click="removeContact(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 来源分类 -->
        <el-tab-pane label="来源分类" name="categories">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="openCreateCategory">新增来源分类</el-button>
          </div>
          <el-table :data="shownCategories" size="small">
            <el-table-column prop="code" label="编码" width="160" />
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column label="启用" width="100">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.active"
                  @change="(v: string | number | boolean) => toggleCategory(row, Boolean(v))"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="renameCategory(row)">编辑</el-button>
                <el-button link type="danger" @click="removeCategory(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 需求类型 -->
        <el-tab-pane label="需求类型" name="needTypes">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="openCreateNeedType">新增需求类型</el-button>
          </div>
          <el-table :data="shownNeedTypes" size="small">
            <el-table-column prop="name" label="名称" min-width="160" />
            <el-table-column label="启用" width="100">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.active"
                  @change="(v: string | number | boolean) => toggleNeedType(row, Boolean(v))"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="renameNeedType(row)">编辑</el-button>
                <el-button link type="danger" @click="removeNeedType(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 账号 -->
        <el-tab-pane label="账号" name="users">
          <div class="tab-toolbar">
            <el-button type="primary" :icon="Plus" @click="openCreateUser">新增账号</el-button>
          </div>
          <el-table :data="users" size="small">
            <el-table-column prop="username" label="用户名" min-width="120" />
            <el-table-column prop="display_name" label="显示名" min-width="120" />
            <el-table-column label="角色" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.role === 'admin' ? 'danger' : 'info'">
                  {{ roleLabel(row.role) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="90">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_active"
                  @change="(v: string | number | boolean) => toggleUser(row, Boolean(v))"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button link type="primary" @click="changeUserRole(row)">切换角色</el-button>
                <el-button link type="warning" @click="resetUserPassword(row)">重置密码</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- AI 配置 -->
        <el-tab-pane label="AI 配置" name="ai">
          <div v-loading="aiLoading">
            <el-alert
              type="info"
              :closable="false"
              show-icon
              title="用于 AI 智能识别线索。密钥仅写入不回读，保存后仅显示是否已配置。"
              class="ai-alert"
            />
            <el-form label-width="120px" class="ai-form">
              <el-form-item label="服务商">
                <el-input v-model="aiForm.provider" placeholder="如 openai / azure" />
              </el-form-item>
              <el-form-item label="接口地址">
                <el-input v-model="aiForm.endpoint" placeholder="https://…" />
              </el-form-item>
              <el-form-item label="模型">
                <el-input v-model="aiForm.model" placeholder="如 gpt-4o" />
              </el-form-item>
              <el-form-item label="超时（秒）">
                <el-input-number v-model="aiForm.timeout_seconds" :min="1" :max="300" />
              </el-form-item>
              <el-form-item label="API 密钥">
                <div class="key-row">
                  <el-tag
                    size="small"
                    :type="aiConfig?.api_key_configured ? 'success' : 'info'"
                    class="key-status"
                  >
                    {{ aiConfig?.api_key_configured ? '已配置' : '未配置' }}
                  </el-tag>
                  <el-input
                    v-model="aiForm.api_key"
                    type="password"
                    show-password
                    :disabled="clearKey"
                    :placeholder="aiConfig?.api_key_configured ? '留空保持不变' : '输入新密钥'"
                    class="key-input"
                  />
                </div>
              </el-form-item>
              <el-form-item v-if="aiConfig?.api_key_configured" label="清除密钥">
                <el-checkbox v-model="clearKey">保存时清除现有密钥</el-checkbox>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="aiSaving" @click="submitAIConfig">保存</el-button>
                <span v-if="aiConfig?.updated_at" class="ai-updated">
                  上次更新：{{ formatDateTime(aiConfig.updated_at) }}
                </span>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="deptDialog.visible" title="新增部门" width="420px">
      <el-input v-model="deptDialog.name" placeholder="部门名称" />
      <template #footer>
        <el-button @click="deptDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitDepartment">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="contactDialog.visible" title="新增部门对接人" width="460px">
      <el-form label-width="88px">
        <el-form-item label="部门">
          <el-select v-model="contactDialog.department_id" style="width: 100%">
            <el-option v-for="d in activeDepartments" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="contactDialog.name" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="contactDialog.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="contactDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitContact">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="categoryDialog.visible" title="新增来源分类" width="420px">
      <el-form label-width="72px">
        <el-form-item label="编码">
          <el-input v-model="categoryDialog.code" placeholder="英文编码，如 speech" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="categoryDialog.name" placeholder="展示名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitCategory">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="needTypeDialog.visible" title="新增需求类型" width="420px">
      <el-input v-model="needTypeDialog.name" placeholder="需求类型名称" />
      <template #footer>
        <el-button @click="needTypeDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitNeedType">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="userDialog.visible" title="新增账号" width="460px">
      <el-form label-width="88px">
        <el-form-item label="用户名">
          <el-input v-model="userDialog.username" placeholder="字母/数字/_.-" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="userDialog.display_name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userDialog.role" style="width: 100%">
            <el-option label="市场部" value="market" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input v-model="userDialog.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitUser">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reassignVisible" title="批量改派" width="460px" :close-on-click-modal="false">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        :title="`将「${reassignSource?.name ?? ''}」名下的存量线索全部转给同部门另一位对接人（保留交接历史）`"
      />
      <el-form label-width="88px" class="reassign-form">
        <el-form-item label="目标对接人">
          <el-select v-model="reassignTargetId" filterable placeholder="选择同部门对接人" style="width: 100%">
            <el-option v-for="c in reassignCandidates" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" :loading="reassigning" @click="submitReassign">确认改派</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tab-toolbar {
  margin-bottom: 12px;
}
.settings-toolbar {
  margin-bottom: 12px;
}
.reassign-form {
  margin-top: 12px;
}
.ai-alert {
  margin-bottom: 16px;
}
.ai-form {
  max-width: 560px;
}
.key-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.key-status {
  flex-shrink: 0;
}
.key-input {
  flex: 1;
}
.ai-updated {
  margin-left: 16px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
