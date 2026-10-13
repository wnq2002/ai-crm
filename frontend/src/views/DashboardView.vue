<script setup lang="ts">
import { computed, onMounted, ref, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import { CircleCheck, Clock, Connection, Phone, Timer, Warning } from '@element-plus/icons-vue'
import {
  getDashboardSummary,
  getDashboardTrend,
  type DashboardSummary,
  type RecentEvent,
  type TodoItem,
  type TrendBucket,
} from '@/api/reports'
import { getErrorMessage } from '@/api/http'
import { formatDateTime } from '@/utils'
import { QUALIFICATION_LABELS } from '@/utils/labels'
import BaseChart from '@/components/BaseChart.vue'
import ActivityDialog from '@/components/ActivityDialog.vue'

const router = useRouter()

const loading = ref(false)
const summary = ref<DashboardSummary | null>(null)
const trend = ref<TrendBucket[]>([])

const TODO_LABELS: Record<string, string> = {
  overdue: '已逾期',
  first_follow: '待首次跟进',
  today: '今日待跟进',
  no_progress: '多次跟进无进展',
  stale: '长期未更新',
  handed_off_pending: '交接待反馈',
}

// 今日工作概览：已逾期 / 今日待跟进 更醒目（尺寸与层级）
const todoCards = computed<
  { key: string; label: string; count: number; color: string; icon: Component; big: boolean }[]
>(() => {
  const t = summary.value?.todos
  return [
    { key: 'overdue', label: '跟进已逾期', count: t?.overdue ?? 0, color: '#dc2626', icon: Warning, big: true },
    { key: 'today', label: '今日待跟进', count: t?.today ?? 0, color: '#b7791f', icon: Clock, big: true },
    { key: 'first_follow', label: '待首次跟进', count: t?.first_follow ?? 0, color: '#2878d4', icon: Phone, big: false },
    { key: 'no_progress', label: '多次跟进无进展', count: t?.no_progress ?? 0, color: '#64748b', icon: CircleCheck, big: false },
    { key: 'stale', label: '长期未更新', count: t?.stale ?? 0, color: '#64748b', icon: Timer, big: false },
    { key: 'handed_off_pending', label: '交接待反馈', count: t?.handed_off_pending ?? 0, color: '#2878d4', icon: Connection, big: false },
  ]
})

const todoList = computed(() => summary.value?.todo_list ?? [])
const recentLeads = computed(() => summary.value?.recent_leads ?? [])
const recentEvents = computed<RecentEvent[]>(() => summary.value?.recent_events ?? [])

const EVENT_TYPE_LABELS: Record<string, string> = {
  'lead.created': '创建线索',
  'lead.updated': '更新线索',
  'lead.archived': '归档线索',
  'lead.company_link': '关联企业',
  'lead.company_unlink': '解除企业关联',
  'lead.qualification': '需求判断',
  'lead.handoff': '部门交接',
  'lead.outcome': '进展反馈',
  phone: '电话联系',
  wechat_request: '微信申请',
  wechat_approved: '微信通过',
  wechat_chat: '微信沟通',
  note: '备注',
  handoff: '部门交接',
  outcome: '进展反馈',
}

function recentEventLabel(type: string): string {
  return EVENT_TYPE_LABELS[type] ?? type
}

function recentEventColor(type: string): string {
  if (type.includes('won') || type === 'lead.created') return '#15803d'
  if (type.includes('lost') || type.includes('archived')) return '#dc2626'
  if (type.includes('handoff')) return '#b7791f'
  if (type.includes('phone')) return '#2878d4'
  if (type.includes('wechat')) return '#2878d4'
  if (type.includes('qualification')) return '#64748b'
  return '#94a3b8'
}

const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 36, right: 12, top: 16, bottom: 28 },
  xAxis: {
    type: 'category',
    data: trend.value.map((b) => b.date),
    axisLabel: { fontSize: 11 },
  },
  yAxis: { type: 'value', minInterval: 1 },
  series: [
    {
      name: '新增线索',
      type: 'line',
      smooth: true,
      data: trend.value.map((b) => b.leads),
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(40, 120, 212, 0.22)' },
            { offset: 1, color: 'rgba(40, 120, 212, 0)' },
          ],
        },
      },
      itemStyle: { color: '#2878d4' },
    },
  ],
}))

function gotoLeads(query: Record<string, string>): void {
  router.push({ name: 'leads', query })
}

function openTodoCard(card: { key: string }): void {
  gotoLeads({ todo: card.key })
}

function openDetail(id: string): void {
  router.push({ name: 'lead-detail', params: { id } })
}

const activityVisible = ref(false)
const activityLeadId = ref('')
const activityKind = ref<'phone' | 'wechat'>('phone')

function openActivity(id: string, kind: 'phone' | 'wechat'): void {
  activityLeadId.value = id
  activityKind.value = kind
  activityVisible.value = true
}

function onSaved(): void {
  load()
}

function todoTagType(todo: string): 'danger' | 'warning' | 'primary' | 'info' {
  if (todo === 'overdue') return 'danger'
  if (todo === 'today') return 'warning'
  if (todo === 'first_follow') return 'primary'
  return 'info'
}

function leadName(item: TodoItem): string {
  return item.company_name_raw || item.contact_name_raw || '未命名线索'
}

function qualificationLabel(status: string): string {
  return QUALIFICATION_LABELS[status as keyof typeof QUALIFICATION_LABELS] ?? status
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [sum, tr] = await Promise.all([getDashboardSummary({}), getDashboardTrend({})])
    summary.value = sum
    trend.value = tr?.buckets ?? []
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="page-container">
    <!-- 今日工作概览 -->
    <div class="todo-cards">
      <el-card
        v-for="card in todoCards"
        :key="card.key"
        shadow="never"
        class="todo-card clickable"
        :class="{ 'todo-card--big': card.big }"
        @click="openTodoCard(card)"
      >
        <div class="todo-card__inner">
          <div class="todo-card__icon" :style="{ background: card.color + '1a', color: card.color }">
            <el-icon :size="card.big ? 26 : 22"><component :is="card.icon" /></el-icon>
          </div>
          <div class="todo-card__body">
            <div class="todo-card__count" :style="{ color: card.color }">{{ card.count }}</div>
            <div class="todo-card__label">{{ card.label }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 优先处理列表 -->
    <el-card shadow="never" class="section">
      <template #header><span>优先处理</span></template>
      <el-table v-if="todoList.length" :data="todoList" size="small" row-key="lead_id">
        <el-table-column label="优先级" width="110">
          <template #default="{ row }">
            <el-tag :type="todoTagType(row.todo)" size="small" effect="light">
              {{ TODO_LABELS[row.todo] ?? row.todo }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="企业 / 联系人" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ leadName(row) }}</template>
        </el-table-column>
        <el-table-column label="当前状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" type="info" effect="plain">{{ qualificationLabel(row.qualification_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="跟进次数" width="90" align="center">
          <template #default="{ row }">{{ row.follow_up_count }}</template>
        </el-table-column>
        <el-table-column label="最近跟进" width="150">
          <template #default="{ row }">{{ row.last_followup_at ? formatDateTime(row.last_followup_at) : '—' }}</template>
        </el-table-column>
        <el-table-column label="下次跟进" width="150">
          <template #default="{ row }">{{ row.next_follow_up_at ? formatDateTime(row.next_follow_up_at) : '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-dropdown @command="(k: string) => openActivity(row.lead_id, k as 'phone' | 'wechat')">
              <el-button size="small" text type="primary">记录跟进</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="phone">电话</el-dropdown-item>
                  <el-dropdown-item command="wechat">微信</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button size="small" text type="info" @click="openDetail(row.lead_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无待处理事项" />
    </el-card>

    <el-card shadow="never" class="section">
      <template #header><span>最近动态</span></template>
      <el-timeline v-if="recentEvents.length" class="recent-timeline">
        <el-timeline-item
          v-for="(event, index) in recentEvents"
          :key="index"
          :timestamp="formatDateTime(event.occurred_at)"
          :color="recentEventColor(event.event_type)"
        >
          {{ recentEventLabel(event.event_type) }}
          <span v-if="event.actor_name" class="event-actor">（{{ event.actor_name }}）</span>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无动态" />
    </el-card>

    <el-row :gutter="12">
      <el-col :span="14">
        <el-card shadow="never" class="section">
          <template #header><span>最近新增线索</span></template>
          <el-table v-if="recentLeads.length" :data="recentLeads" size="small" row-key="id">
            <el-table-column label="企业 / 联系人" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ row.company_name_raw || row.contact_name_raw || '未命名线索' }}</template>
            </el-table-column>
            <el-table-column label="获取时间" width="150">
              <template #default="{ row }">{{ formatDateTime(row.occurred_at) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" type="info" effect="plain">{{ qualificationLabel(row.qualification_status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button size="small" text type="info" @click="openDetail(row.id)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无新增线索" />
          <div v-if="recentLeads.length" class="recent-more">
            <el-button link type="primary" @click="gotoLeads({})">查看全部线索 →</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" class="section">
          <template #header><span>近30天线索趋势</span></template>
          <BaseChart v-if="trend.some((b) => b.leads > 0)" :option="trendOption" height="280px" />
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <ActivityDialog
      v-model="activityVisible"
      :lead-id="activityLeadId"
      :kind="activityKind"
      @saved="onSaved"
    />
  </div>
</template>

<style scoped>
.todo-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.todo-card {
  cursor: pointer;
}
.todo-card--big .todo-card__count {
  font-size: 30px;
}
.todo-card__inner {
  display: flex;
  align-items: center;
  gap: 12px;
}
.todo-card__icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.todo-card--big .todo-card__icon {
  width: 54px;
  height: 54px;
}
.todo-card__count {
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
}
.todo-card__label {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}
.clickable {
  cursor: pointer;
}
.section {
  margin-bottom: 12px;
}
.recent-more {
  margin-top: 8px;
  text-align: right;
}
.recent-timeline {
  padding-left: 4px;
}
.event-actor {
  color: #94a3b8;
  font-size: 12px;
}
</style>
