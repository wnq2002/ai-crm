<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import {
  exportReports,
  getReportsActivities,
  getReportsHandoffs,
  getReportsOverview,
  getReportsSources,
  type ActivityStat,
  type HandoffStat,
  type ReportOverview,
  type SourceStat,
} from '@/api/reports'
import { downloadBlob } from '@/utils'
import { getErrorMessage } from '@/api/http'

const loading = ref(false)
const exporting = ref(false)
const dateRange = ref<[Date, Date]>(currentMonthRange())

const overview = ref<ReportOverview | null>(null)
const sources = ref<SourceStat[]>([])
const activities = ref<ActivityStat[]>([])
const handoffs = ref<HandoffStat[]>([])

function currentMonthRange(): [Date, Date] {
  const now = new Date()
  return [new Date(now.getFullYear(), now.getMonth(), 1), now]
}

function buildQuery() {
  const to = new Date(dateRange.value[1])
  to.setHours(23, 59, 59, 999)
  return {
    from: dateRange.value[0].toISOString(),
    to: to.toISOString(),
  }
}

function formatRate(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return '—'
  return `${(rate * 100).toFixed(1)}%`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [ov, src, act, hf] = await Promise.all([
      getReportsOverview(buildQuery()),
      getReportsSources(buildQuery()),
      getReportsActivities(buildQuery()),
      getReportsHandoffs(buildQuery()),
    ])
    overview.value = ov
    sources.value = src
    activities.value = act
    handoffs.value = hf
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

async function handleExport(): Promise<void> {
  exporting.value = true
  try {
    const blob = await exportReports(buildQuery())
    downloadBlob(blob, '数据分析报表.xlsx')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="toolbar">
        <el-space>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 280px"
          />
          <el-button @click="load">查询</el-button>
        </el-space>
        <el-button :icon="Download" :loading="exporting" @click="handleExport">导出报表</el-button>
      </div>

      <el-row v-loading="loading" :gutter="12">
        <el-col :span="4">
          <el-card shadow="never" class="metric-card">
            <div class="metric-value">{{ overview?.total_leads ?? 0 }}</div>
            <div class="metric-label">线索数</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="metric-card">
            <div class="metric-value">{{ overview?.distinct_companies ?? 0 }}</div>
            <div class="metric-label">去重企业数</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="metric-card">
            <div class="metric-value">{{ overview?.valid ?? 0 }} / {{ overview?.invalid ?? 0 }}</div>
            <div class="metric-label">有效 / 无效</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="metric-card">
            <div class="metric-value">{{ formatRate(overview?.effective_rate) }}</div>
            <div class="metric-label">有效率</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="metric-card">
            <div class="metric-value">{{ overview?.handed_off ?? 0 }}</div>
            <div class="metric-label">已交接</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="never" class="metric-card">
            <div class="metric-value">{{ overview?.pending ?? 0 }}</div>
            <div class="metric-label">待确认</div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="section">
        <template #header><span>结果分布</span></template>
        <el-space wrap>
          <el-tag type="success">已成交 {{ overview?.outcome_won ?? 0 }}</el-tag>
          <el-tag type="danger">未成交 {{ overview?.outcome_lost ?? 0 }}</el-tag>
          <el-tag type="primary">推进中 {{ overview?.outcome_in_progress ?? 0 }}</el-tag>
          <el-tag type="info">暂无反馈 {{ overview?.no_feedback ?? 0 }}</el-tag>
        </el-space>
      </el-card>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-card shadow="never" class="section">
            <template #header><span>来源分析</span></template>
            <el-table :data="sources" size="small">
              <el-table-column prop="category_name" label="来源" min-width="120" />
              <el-table-column prop="lead_count" label="线索数" width="80" />
              <el-table-column prop="valid_count" label="有效" width="80" />
              <el-table-column prop="handed_off_count" label="交接" width="80" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" class="section">
            <template #header><span>活动工作量</span></template>
            <el-table :data="activities" size="small">
              <el-table-column prop="display_name" label="操作者" min-width="120" />
              <el-table-column prop="phone_total" label="电话次数" width="90" />
              <el-table-column prop="total" label="总记录" width="90" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="section">
        <template #header><span>部门交接分布</span></template>
        <el-table :data="handoffs" size="small">
          <el-table-column prop="department" label="部门" min-width="160" />
          <el-table-column prop="count" label="交接次数" width="120" />
        </el-table>
      </el-card>
    </el-card>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.metric-card {
  text-align: center;
  margin-bottom: 12px;
}
.metric-value {
  font-size: 22px;
  font-weight: 600;
}
.metric-label {
  margin-top: 4px;
  color: #909399;
  font-size: 13px;
}
.section {
  margin-top: 12px;
}
</style>
