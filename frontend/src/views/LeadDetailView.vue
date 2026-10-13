<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { ArrowLeft, Edit, Delete } from '@element-plus/icons-vue'
import {
  archiveLead,
  getCompanyCandidates,
  getLead,
  getLeadTimeline,
  linkCompany,
  setQualification,
  unlinkCompany,
  type TimelineEvent,
} from '@/api/leads'
import { createCompany, getCompany } from '@/api/companies'
import { listDepartments, listDepartmentContacts } from '@/api/dictionaries'
import { listActivities, revokeActivity } from '@/api/activities'
import LeadFormDialog from '@/components/LeadFormDialog.vue'
import NoteDialog from '@/components/NoteDialog.vue'
import ActivityDialog from '@/components/ActivityDialog.vue'
import HandoffDialog from '@/components/HandoffDialog.vue'
import OutcomeDialog from '@/components/OutcomeDialog.vue'
import ReviseActivityDialog from '@/components/ReviseActivityDialog.vue'
import { formatDateTime } from '@/utils'
import {
  ACTIVITY_KIND_LABELS,
  ACTIVITY_RESULT_LABELS,
  INTAKE_LABELS,
  OUTCOME_LABELS,
  QUALIFICATION_LABELS,
  WECHAT_RELATIONSHIP_LABELS,
} from '@/utils/labels'
import { getErrorMessage } from '@/api/http'
import type {
  ActivityResult,
  Company,
  CompanyDetail,
  Department,
  DepartmentContact,
  Lead,
  LeadActivity,
  OutcomeStatus,
  QualificationStatus,
} from '@/types'

const route = useRoute()
const router = useRouter()
const leadId = route.params.id as string

const lead = ref<Lead | null>(null)
const linkedCompany = ref<CompanyDetail | null>(null)
const candidates = ref<Company[]>([])
const timeline = ref<TimelineEvent[]>([])
const loading = ref(false)
const editVisible = ref(false)
const auth = useAuthStore()
const isAdmin = computed(() => auth.role === 'admin')
const activities = ref<LeadActivity[]>([])
const noteVisible = ref(false)
const departments = ref<Department[]>([])
const departmentContacts = ref<DepartmentContact[]>([])
const qualifyLoading = ref(false)
const activityVisible = ref(false)
const activityKind = ref<'phone' | 'wechat'>('phone')
const handoffVisible = ref(false)
const outcomeVisible = ref(false)
const currentDepartmentLabel = computed(() => {
  const l = lead.value
  if (!l?.department_id) return '未交接'
  const dept = departments.value.find((d) => d.id === l.department_id)
  const contact = departmentContacts.value.find((c) => c.id === l.department_contact_id)
  const deptName = dept?.name ?? l.department_id
  return contact ? `${deptName} / ${contact.name}` : deptName
})

async function loadLead(): Promise<void> {
  loading.value = true
  try {
    lead.value = await getLead(leadId)
    if (lead.value.company_id) {
      linkedCompany.value = await getCompany(lead.value.company_id).catch(() => null)
    }
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

async function loadCandidates(): Promise<void> {
  try {
    candidates.value = await getCompanyCandidates(leadId)
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function loadTimeline(): Promise<void> {
  try {
    timeline.value = await getLeadTimeline(leadId)
  } catch {
    timeline.value = []
  }
}

async function handleLink(companyId: string): Promise<void> {
  try {
    await linkCompany(leadId, companyId)
    ElMessage.success('已关联企业')
    await Promise.all([loadLead(), loadCandidates()])
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function handleUnlink(): Promise<void> {
  try {
    await unlinkCompany(leadId)
    ElMessage.success('已解除关联')
    await Promise.all([loadLead(), loadCandidates()])
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

async function handleArchive(): Promise<void> {
  try {
    await ElMessageBox.confirm('归档后线索将不再出现在列表中，确定归档？', '提示', {
      confirmButtonText: '归档',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await archiveLead(leadId)
    ElMessage.success('已归档')
    router.push({ name: 'leads' })
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

function openCompany(id: string): void {
  router.push({ name: 'company-detail', params: { id } })
}

function timelineTime(event: TimelineEvent): string {
  const raw = event.happened_at ?? event.recorded_at
  return raw ? formatDateTime(String(raw)) : '—'
}

const TIMELINE_TYPE_LABELS: Record<string, string> = {
  lead_created: '创建线索',
  phone: '电话联系',
  wechat_request: '微信申请',
  wechat_approved: '微信通过',
  wechat_chat: '微信沟通',
  note: '备注',
  qualification: '需求判断',
  handoff: '部门交接',
  outcome: '进展反馈',
}

function timelineText(event: TimelineEvent): string {
  const base = TIMELINE_TYPE_LABELS[event.type] ?? event.type
  if (event.type === 'phone' && event.result) {
    return `${base} · ${ACTIVITY_RESULT_LABELS[event.result as ActivityResult] ?? event.result}`
  }
  if (event.type === 'qualification' && event.result) {
    return `${base} · ${QUALIFICATION_LABELS[event.result as QualificationStatus] ?? event.result}`
  }
  if (event.type === 'outcome' && event.result) {
    return `${base} · ${OUTCOME_LABELS[event.result as OutcomeStatus] ?? event.result}`
  }
  return event.content ? `${base} · ${event.content}` : base
}

function activityKindLabel(kind: string): string {
  return ACTIVITY_KIND_LABELS[kind as keyof typeof ACTIVITY_KIND_LABELS] ?? kind
}

async function loadActivities(): Promise<void> {
  try {
    activities.value = await listActivities(leadId)
  } catch {
    activities.value = []
  }
}

function openActivity(kind: 'phone' | 'wechat'): void {
  activityKind.value = kind
  activityVisible.value = true
}

async function onActivitySaved(): Promise<void> {
  await Promise.all([loadActivities(), loadLead(), loadTimeline()])
}

async function onDecisionSaved(): Promise<void> {
  await Promise.all([loadLead(), loadTimeline()])
}

function openNote(): void {
  noteVisible.value = true
}

function onNoteSaved(): void {
  loadActivities()
}

async function handleRevoke(activity: LeadActivity): Promise<void> {
  let reason: string
  try {
    const { value } = await ElMessageBox.prompt('请输入撤销原因', '撤销记录', {
      confirmButtonText: '撤销',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '撤销原因不能为空',
    })
    reason = value
  } catch {
    return
  }
  try {
    await revokeActivity(activity.id, reason)
    ElMessage.success('已撤销')
    await Promise.all([loadActivities(), loadLead()])
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

const reviseVisible = ref(false)
const revisingActivity = ref<LeadActivity | null>(null)

function openRevise(activity: LeadActivity): void {
  revisingActivity.value = activity
  reviseVisible.value = true
}

const creatingCompany = ref(false)

async function handleCreateAndLink(): Promise<void> {
  const name = lead.value?.company_name_raw?.trim()
  if (!name) return
  creatingCompany.value = true
  try {
    const company = await createCompany({ canonical_name: name })
    await linkCompany(leadId, company.id)
    ElMessage.success('已新建企业并关联')
    await Promise.all([loadLead(), loadCandidates()])
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    creatingCompany.value = false
  }
}

async function loadDictionaries(): Promise<void> {
  try {
    const [depts, contacts] = await Promise.all([listDepartments(), listDepartmentContacts()])
    // 展示当前/历史部门·对接人用全量（停用后仍要能显示名字）；交接下拉在 HandoffDialog 里另行过滤 active
    departments.value = depts
    departmentContacts.value = contacts
  } catch {
    /* ignore */
  }
}

async function handleQualify(status: 'valid' | 'invalid'): Promise<void> {
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
  qualifyLoading.value = true
  try {
    await setQualification(leadId, { qualification_status: status, reason })
    ElMessage.success(status === 'valid' ? '已标记有效' : '已标记无效')
    await Promise.all([loadLead(), loadTimeline()])
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    qualifyLoading.value = false
  }
}

onMounted(() => {
  loadLead()
  loadCandidates()
  loadTimeline()
  loadActivities()
  loadDictionaries()
})
</script>

<template>
  <div class="page-container">
    <div class="detail-header">
      <el-button :icon="ArrowLeft" link @click="router.push({ name: 'leads' })">返回线索列表</el-button>
      <el-space>
        <el-button :icon="Edit" @click="editVisible = true">编辑</el-button>
        <el-button v-if="isAdmin" :icon="Delete" type="danger" plain @click="handleArchive">归档</el-button>
      </el-space>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-card">
      <template #header>
        <span>{{ lead?.contact_name_raw || lead?.company_name_raw || '线索详情' }}</span>
      </template>

      <template v-if="lead">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="获取时间">{{ formatDateTime(lead.occurred_at) }}</el-descriptions-item>
          <el-descriptions-item label="录入方式">{{ INTAKE_LABELS[lead.intake_method] }}</el-descriptions-item>
          <el-descriptions-item label="企业名称(原文)">
            {{ lead.company_name_raw || '未填写' }}
          </el-descriptions-item>
          <el-descriptions-item label="联系人">{{ lead.contact_name_raw || '—' }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ lead.phone_raw || '—' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ lead.email_raw || '—' }}</el-descriptions-item>
          <el-descriptions-item label="微信号">{{ lead.wechat_raw || '—' }}</el-descriptions-item>
          <el-descriptions-item label="需求描述">{{ lead.inquiry_text || '—' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ lead.notes || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header>
        <span>初筛结论</span>
      </template>
      <div class="status-row">
        <el-tag size="small">{{ lead ? QUALIFICATION_LABELS[lead.qualification_status] : '—' }}</el-tag>
        <el-space>
          <el-button
            size="small"
            type="primary"
            :loading="qualifyLoading"
            :disabled="!!lead && lead.handoff_status === 'handed_off' && !isAdmin"
            @click="handleQualify('valid')"
          >
            标记有效
          </el-button>
          <el-button
            size="small"
            plain
            type="danger"
            :loading="qualifyLoading"
            :disabled="!!lead && lead.handoff_status === 'handed_off' && !isAdmin"
            @click="handleQualify('invalid')"
          >
            标记无效
          </el-button>
        </el-space>
      </div>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header>
        <span>部门交接</span>
      </template>
      <div class="status-row">
        <span>{{ currentDepartmentLabel }}</span>
        <el-button size="small" type="primary" :disabled="lead?.qualification_status !== 'valid'" @click="handoffVisible = true">
          交接
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header>
        <span>反馈</span>
      </template>
      <div class="status-row">
        <el-tag size="small">{{ lead ? OUTCOME_LABELS[lead.outcome_status] : '—' }}</el-tag>
        <el-button size="small" type="primary" :disabled="lead?.handoff_status !== 'handed_off'" @click="outcomeVisible = true">
          登记反馈
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header>
        <span>企业关联</span>
      </template>

      <div v-if="linkedCompany" class="linked-company">
        <span>已关联：{{ linkedCompany.canonical_name }}</span>
        <el-space>
          <el-button link type="primary" @click="openCompany(linkedCompany.id)">查看企业详情</el-button>
          <el-button link type="danger" @click="handleUnlink">解除关联</el-button>
        </el-space>
      </div>
      <div v-else-if="!candidates.length" class="no-company">
        <el-empty description="暂无关联企业，可忽略或稍后在候选企业中关联" />
        <div v-if="lead?.company_name_raw" class="no-company-action">
          <el-button
            type="primary"
            plain
            :loading="creatingCompany"
            @click="handleCreateAndLink"
          >
            新建企业「{{ lead.company_name_raw }}」并关联
          </el-button>
        </div>
      </div>

      <template v-if="candidates.length">
        <el-alert type="info" :closable="false" show-icon title="可能关联的企业（规范化匹配，需人工确认）" />
        <el-table :data="candidates" size="small" class="candidate-table">
          <el-table-column prop="canonical_name" label="企业名称" />
          <el-table-column prop="industry" label="行业">
            <template #default="{ row }">{{ row.industry || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                :disabled="!!lead?.company_id"
                @click="handleLink(row.id)"
              >
                关联
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header>
        <span>市场沟通</span>
      </template>
      <div class="comm-toolbar">
        <el-space>
          <span>电话累计：{{ lead?.phone_total_count ?? 0 }}</span>
          <span>微信记录：{{ lead?.wechat_count ?? 0 }}</span>
          <span>微信关系：{{ lead ? WECHAT_RELATIONSHIP_LABELS[lead.wechat_relationship] : '—' }}</span>
        </el-space>
        <el-space>
          <el-button size="small" type="primary" @click="openActivity('phone')">登记电话</el-button>
          <el-button size="small" @click="openActivity('wechat')">微信沟通</el-button>
          <el-button size="small" @click="openNote">备注</el-button>
        </el-space>
      </div>
      <el-table :data="activities" size="small" class="comm-table">
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ activityKindLabel(row.kind) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            {{ row.result ? ACTIVITY_RESULT_LABELS[row.result as ActivityResult] : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="内容" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.content || '—' }}</template>
        </el-table-column>
        <el-table-column label="发生时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.happened_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.revoked_at" type="info" size="small">已撤销</el-tag>
            <el-tag v-else type="success" size="small">有效</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <template v-if="!row.revoked_at && (isAdmin || row.created_by === auth.user?.id)">
              <el-button link type="primary" @click="openRevise(row)">修正</el-button>
              <el-button link type="danger" @click="handleRevoke(row)">撤销</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header>
        <span>时间线</span>
      </template>
      <el-timeline v-if="timeline.length">
        <el-timeline-item
          v-for="event in timeline"
          :key="event.id"
          :timestamp="timelineTime(event)"
        >
          {{ timelineText(event) }}
          <span v-if="event.created_by_name" class="timeline-actor">（{{ event.created_by_name }}）</span>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无事件" />
    </el-card>

    <LeadFormDialog v-if="lead" v-model="editVisible" :lead="lead" @saved="loadLead" />
    <NoteDialog v-model="noteVisible" :lead-id="leadId" @saved="onNoteSaved" />
    <ActivityDialog
      v-model="activityVisible"
      :lead-id="leadId"
      :kind="activityKind"
      :wechat-relationship="lead?.wechat_relationship"
      @saved="onActivitySaved"
    />
    <HandoffDialog
      v-model="handoffVisible"
      :lead-id="leadId"
      :current-department-id="lead?.department_id ?? null"
      :current-contact-id="lead?.department_contact_id ?? null"
      @saved="onDecisionSaved"
    />
    <OutcomeDialog v-model="outcomeVisible" :lead-id="leadId" @saved="onDecisionSaved" />
    <ReviseActivityDialog v-model="reviseVisible" :activity="revisingActivity" @saved="onActivitySaved" />
  </div>
</template>

<style scoped>
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.detail-card {
  margin-bottom: 16px;
}
.linked-company {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.comm-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}
.comm-table {
  margin-top: 4px;
}
.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.candidate-table {
  margin-top: 12px;
}
.no-company-action {
  text-align: center;
  margin-top: -12px;
  padding-bottom: 16px;
}
.timeline-actor {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
