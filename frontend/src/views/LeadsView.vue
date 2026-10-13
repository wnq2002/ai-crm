<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Plus, Upload } from '@element-plus/icons-vue'
import {
  archiveLead,
  listLeads,
  setQualification,
  unarchiveLead,
  type LeadCreateResult,
  type LeadListQuery,
} from '@/api/leads'
import { exportLeads } from '@/api/imports'
import {
  listDepartments,
  listDepartmentContacts,
  listNeedTypes,
  listSourceCategories,
  listSourceDetails,
} from '@/api/dictionaries'
import { revokeActivity } from '@/api/activities'
import LeadFormDialog from '@/components/LeadFormDialog.vue'
import NoteDialog from '@/components/NoteDialog.vue'
import ImportDialog from '@/components/ImportDialog.vue'
import ActivityDialog from '@/components/ActivityDialog.vue'
import HandoffDialog from '@/components/HandoffDialog.vue'
import { downloadBlob, formatDateTime } from '@/utils'
import { ACTIVITY_KIND_LABELS } from '@/utils/labels'
import { getErrorMessage } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import type {
  Company,
  Department,
  DepartmentContact,
  Lead,
  LeadActivity,
  LeadListItem,
  NeedType,
  SourceCategory,
  SourceDetail,
} from '@/types'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const isAdmin = computed(() => auth.role === 'admin')

const loading = ref(false)
const leads = ref<LeadListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const showArchived = ref(false)

const sourceCategories = ref<SourceCategory[]>([])
const sourceDetails = ref<SourceDetail[]>([])
const needTypes = ref<NeedType[]>([])
const departments = ref<Department[]>([])
const departmentContacts = ref<DepartmentContact[]>([])

const categoryMap = ref(new Map<string, string>())
const detailMap = ref(new Map<string, string>())
const needTypeMap = ref(new Map<string, string>())
const departmentMap = ref(new Map<string, string>())
const contactMap = ref(new Map<string, string>())

const filters = reactive({
  q: '',
  qualification_status: '',
  handoff_status: '',
  outcome_status: '',
  todo: '',
  source_category_id: '',
  need_type_id: '',
  department_id: '',
  date_range: null as [Date, Date] | null,
})

const createVisible = ref(false)
const importVisible = ref(false)
const candidates = ref<Company[]>([])
const candidateLead = ref<Lead | null>(null)
const noteVisible = ref(false)
const noteLeadId = ref('')
const lastActivity = ref<{ id: string; label: string } | null>(null)

const activityVisible = ref(false)
const activityLeadId = ref('')
const activityKind = ref<'phone' | 'wechat'>('phone')

const handoffVisible = ref(false)
const handoffLeadId = ref('')
const handoffCurrentDept = ref<string | null>(null)
const handoffCurrentContact = ref<string | null>(null)

function buildQuery(): LeadListQuery {
  const query: LeadListQuery = {
    q: filters.q || undefined,
    qualification_status: filters.qualification_status || undefined,
    handoff_status: filters.handoff_status || undefined,
    outcome_status: filters.outcome_status || undefined,
    source_category_id: filters.source_category_id || undefined,
    need_type_id: filters.need_type_id || undefined,
    department_id: filters.department_id || undefined,
    archived: showArchived.value || undefined,
    todo: filters.todo || undefined,
    page: page.value,
    page_size: pageSize.value,
    sort: '-occurred_at',
  }
  if (filters.date_range) {
    query.occurred_from = filters.date_range[0].toISOString()
    const to = new Date(filters.date_range[1])
    to.setHours(23, 59, 59, 999)
    query.occurred_to = to.toISOString()
  }
  return query
}

async function loadDictionaries(): Promise<void> {
  try {
    const [categories, details, types] = await Promise.all([
      listSourceCategories(),
      listSourceDetails(),
      listNeedTypes(),
    ])
    sourceCategories.value = categories.filter((c) => c.active)
    sourceDetails.value = details
    needTypes.value = types.filter((t) => t.active)
    // 展示映射用全量，保证停用分类的历史线索仍能显示名称（如「未知」）
    categoryMap.value = new Map(categories.map((c) => [c.id, c.name]))
    detailMap.value = new Map(details.map((d) => [d.id, d.name]))
    needTypeMap.value = new Map(types.map((t) => [t.id, t.name]))
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }

  try {
    const [depts, contacts] = await Promise.all([listDepartments(), listDepartmentContacts()])
    departments.value = depts
    departmentContacts.value = contacts
    departmentMap.value = new Map(depts.map((d) => [d.id, d.name]))
    contactMap.value = new Map(contacts.map((c) => [c.id, c.name]))
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function loadLeads(): Promise<void> {
  loading.value = true
  try {
    const data = await listLeads(buildQuery())
    leads.value = data.items
    total.value = data.total
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  loadLeads()
}

function handleReset(): void {
  filters.q = ''
  filters.qualification_status = ''
  filters.handoff_status = ''
  filters.outcome_status = ''
  filters.todo = ''
  filters.source_category_id = ''
  filters.need_type_id = ''
  filters.department_id = ''
  filters.date_range = null
  handleSearch()
}

// 支持从工作台看板下钻：读取 URL query 初始化筛选
function applyQueryToFilters(): void {
  const q = route.query
  filters.q = (q.q as string) ?? ''
  filters.qualification_status = (q.qualification_status as string) ?? ''
  filters.handoff_status = (q.handoff_status as string) ?? ''
  filters.outcome_status = (q.outcome_status as string) ?? ''
  filters.todo = (q.todo as string) ?? ''
  filters.source_category_id = (q.source_category_id as string) ?? ''
  filters.need_type_id = (q.need_type_id as string) ?? ''
  filters.department_id = (q.department_id as string) ?? ''
  if (q.occurred_from && q.occurred_to) {
    filters.date_range = [
      new Date(q.occurred_from as string),
      new Date(q.occurred_to as string),
    ]
  } else {
    filters.date_range = null
  }
}

async function handleExport(): Promise<void> {
  try {
    const blob = await exportLeads(buildQuery() as unknown as Record<string, unknown>)
    downloadBlob(blob, '线索导出.csv')
    ElMessage.success('导出成功')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

function onSaved(result: LeadCreateResult | Lead): void {
  loadLeads()
  if ('company_candidates' in result) {
    candidates.value = result.company_candidates
    candidateLead.value = result.lead
  }
}

function openDetail(id: string): void {
  router.push({ name: 'lead-detail', params: { id } })
}

function sourceLabel(lead: LeadListItem): string {
  const parts: string[] = []
  if (lead.source_category_id) {
    parts.push(categoryMap.value.get(lead.source_category_id) ?? lead.source_category_id)
  }
  if (lead.source_detail_id) {
    parts.push(detailMap.value.get(lead.source_detail_id) ?? lead.source_detail_id)
  } else if (lead.source_detail_text) {
    parts.push(lead.source_detail_text)
  }
  return parts.length ? parts.join(' · ') : '—'
}

const FOLLOWUP_STATUS_LABELS: Record<string, string> = {
  first_follow: '待首次跟进',
  today: '今日待跟进',
  overdue: '已逾期',
  no_progress: '多次跟进无进展',
  stale: '长期未更新',
  handed_off_pending: '交接待反馈',
  normal: '正常',
}

const TODO_OPTIONS = [
  { value: 'overdue', label: '已逾期' },
  { value: 'first_follow', label: '待首次跟进' },
  { value: 'today', label: '今日待跟进' },
  { value: 'no_progress', label: '多次跟进无进展' },
  { value: 'stale', label: '长期未更新' },
  { value: 'handed_off_pending', label: '交接待反馈' },
]

function followupTagType(s: string): 'danger' | 'warning' | 'primary' | 'info' | 'success' {
  if (s === 'overdue') return 'danger'
  if (s === 'today') return 'warning'
  if (s === 'first_follow') return 'primary'
  if (s === 'no_progress' || s === 'stale' || s === 'handed_off_pending') return 'info'
  return 'success'
}

function handleFollowCommand(lead: LeadListItem, k: string): void {
  if (k === 'note') openNote(lead)
  else openActivity(lead, k as 'phone' | 'wechat')
}

function handleMoreCommand(lead: LeadListItem, k: string): void {
  if (k === 'valid') quickQualify(lead, 'valid')
  else if (k === 'invalid') quickQualify(lead, 'invalid')
  else if (k === 'handoff') openHandoff(lead)
  else if (k === 'delete') removeLead(lead)
}

function dismissCandidates(): void {
  candidates.value = []
  candidateLead.value = null
}

function openActivity(lead: LeadListItem, kind: 'phone' | 'wechat'): void {
  activityLeadId.value = lead.id
  activityKind.value = kind
  activityVisible.value = true
}

function onActivitySaved(activity: LeadActivity): void {
  lastActivity.value = { id: activity.id, label: ACTIVITY_KIND_LABELS[activity.kind] }
  loadLeads()
}

function openHandoff(lead: LeadListItem): void {
  handoffLeadId.value = lead.id
  handoffCurrentDept.value = lead.department_id ?? null
  handoffCurrentContact.value = lead.department_contact_id ?? null
  handoffVisible.value = true
}

function openNote(lead: LeadListItem): void {
  noteLeadId.value = lead.id
  noteVisible.value = true
}

async function quickQualify(lead: LeadListItem, status: 'valid' | 'invalid'): Promise<void> {
  let reason: string | undefined
  if (status === 'invalid') {
    try {
      const { value } = await ElMessageBox.prompt('请输入无效原因', '标记无效', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPattern: /\S+/,
        inputErrorMessage: '无效原因不能为空',
      })
      reason = value
    } catch {
      return
    }
  }
  try {
    await setQualification(lead.id, { qualification_status: status, reason })
    ElMessage.success(status === 'valid' ? '已标记有效' : '已标记无效')
    loadLeads()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function removeLead(lead: LeadListItem): Promise<void> {
  try {
    await ElMessageBox.confirm('删除后线索将被归档、不再出现在列表中，确定删除？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await archiveLead(lead.id)
    ElMessage.success('已删除（归档）')
    loadLeads()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function restoreLead(lead: LeadListItem): Promise<void> {
  try {
    await unarchiveLead(lead.id)
    ElMessage.success('已恢复')
    loadLeads()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

function onNoteSaved(): void {
  loadLeads()
}

async function undoLast(): Promise<void> {
  if (!lastActivity.value) return
  const { id, label } = lastActivity.value
  try {
    await revokeActivity(id, '误操作撤销')
    ElMessage.success(`已撤销${label}`)
    lastActivity.value = null
    loadLeads()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

function dismissUndo(): void {
  lastActivity.value = null
}

onMounted(() => {
  loadDictionaries()
  applyQueryToFilters()
  loadLeads()
})
</script>

<template>
  <div class="page-container">
    <el-alert v-if="candidates.length" type="info" show-icon :closable="true" @close="dismissCandidates">
      <template #title>
        线索已保存，发现 {{ candidates.length }} 个可能关联的企业
        <el-button link type="primary" @click="candidateLead && openDetail(candidateLead.id)">
          查看并关联
        </el-button>
      </template>
    </el-alert>

    <el-alert v-if="lastActivity" type="success" show-icon :closable="true" @close="dismissUndo">
      <template #title>
        已记录{{ lastActivity.label }}
        <el-button link type="danger" @click="undoLast">撤销</el-button>
      </template>
    </el-alert>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="filters.q"
          placeholder="搜索企业/联系人/手机/邮箱/需求"
          clearable
          class="toolbar__search"
          @keyup.enter="handleSearch"
        />
        <el-button @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <div class="toolbar__spacer" />
        <el-button type="primary" :icon="Plus" @click="createVisible = true">新建线索</el-button>
        <el-button :icon="Upload" @click="importVisible = true">导入</el-button>
        <el-button :icon="Download" @click="handleExport">导出</el-button>
      </div>

      <div class="filter-bar">
        <el-select v-model="filters.qualification_status" placeholder="线索判断" clearable style="width: 120px">
          <el-option label="待确认" value="pending" />
          <el-option label="有效" value="valid" />
          <el-option label="无效" value="invalid" />
        </el-select>
        <el-select v-model="filters.handoff_status" placeholder="交接状态" clearable style="width: 120px">
          <el-option label="待交接" value="not_handed_off" />
          <el-option label="已交接" value="handed_off" />
        </el-select>
        <el-select v-model="filters.outcome_status" placeholder="业务结果" clearable style="width: 120px">
          <el-option label="暂无反馈" value="unknown" />
          <el-option label="推进中" value="in_progress" />
          <el-option label="已成交" value="won" />
          <el-option label="未成交" value="lost" />
          <el-option label="暂缓" value="deferred" />
        </el-select>
        <el-select v-model="filters.todo" placeholder="待办" clearable style="width: 150px">
          <el-option v-for="t in TODO_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-select v-model="filters.source_category_id" placeholder="来源" clearable style="width: 120px">
          <el-option v-for="c in sourceCategories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-select v-model="filters.need_type_id" placeholder="需求" clearable style="width: 120px">
          <el-option v-for="t in needTypes" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select v-model="filters.department_id" placeholder="部门" clearable style="width: 120px">
          <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
        <el-date-picker
          v-model="filters.date_range"
          type="daterange"
          start-placeholder="获取时间起"
          end-placeholder="获取时间止"
          style="width: 240px"
        />
        <el-switch v-model="showArchived" active-text="查看已归档" @change="handleSearch" />
      </div>

      <el-table v-loading="loading" :data="leads" row-key="id">
        <el-table-column label="获取时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.occurred_at) }}</template>
        </el-table-column>
        <el-table-column label="来源" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ sourceLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="企业名称" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.company_name_raw || '未填写' }}</template>
        </el-table-column>
        <el-table-column label="联系人" min-width="100" show-overflow-tooltip>
          <template #default="{ row }">{{ row.contact_name_raw || '—' }}</template>
        </el-table-column>
        <el-table-column label="联系方式" min-width="130">
          <template #default="{ row }">
            {{ row.contact_summary || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="需求摘要" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.inquiry_text || '—' }}</template>
        </el-table-column>
        <el-table-column label="跟进状态" width="120">
          <template #default="{ row }">
            <el-tag :type="followupTagType(row.follow_up_status)" size="small" effect="light">
              {{ FOLLOWUP_STATUS_LABELS[row.follow_up_status] ?? row.follow_up_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近跟进" width="150">
          <template #default="{ row }">{{ formatDateTime(row.recent_followup_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <template v-if="showArchived">
              <el-button v-if="isAdmin" link type="primary" @click="restoreLead(row)">恢复</el-button>
              <el-button text type="info" @click="openDetail(row.id)">查看</el-button>
            </template>
            <template v-else>
              <el-dropdown @command="(k: string) => handleFollowCommand(row, k)">
                <el-button size="small" text type="primary">记录跟进</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="phone">电话</el-dropdown-item>
                    <el-dropdown-item command="wechat">微信</el-dropdown-item>
                    <el-dropdown-item command="note">备注</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button size="small" text type="info" @click="openDetail(row.id)">查看</el-button>
              <el-dropdown @command="(k: string) => handleMoreCommand(row, k)">
                <el-button size="small" text type="info">更多</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      command="valid"
                      :disabled="row.qualification_status === 'valid' || (row.handoff_status === 'handed_off' && !isAdmin)"
                    >
                      标记有效
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="invalid"
                      :disabled="row.qualification_status === 'invalid' || (row.handoff_status === 'handed_off' && !isAdmin)"
                    >
                      标记无效
                    </el-dropdown-item>
                    <el-dropdown-item command="handoff" :disabled="row.qualification_status !== 'valid'">
                      交接
                    </el-dropdown-item>
                    <el-dropdown-item v-if="isAdmin" command="delete">删除（归档）</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="loadLeads"
        @size-change="handleSearch"
      />
    </el-card>

    <LeadFormDialog v-model="createVisible" @saved="onSaved" />
    <ImportDialog v-model="importVisible" @imported="loadLeads" />
    <NoteDialog v-model="noteVisible" :lead-id="noteLeadId" @saved="onNoteSaved" />
    <ActivityDialog
      v-model="activityVisible"
      :lead-id="activityLeadId"
      :kind="activityKind"
      @saved="onActivitySaved"
    />
    <HandoffDialog
      v-model="handoffVisible"
      :lead-id="handoffLeadId"
      :current-department-id="handoffCurrentDept"
      :current-contact-id="handoffCurrentContact"
      @saved="loadLeads"
    />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.toolbar__search {
  width: 300px;
  max-width: 40%;
}
.toolbar__spacer {
  flex: 1;
}
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  margin-bottom: 12px;
  background: #f7fbff;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
