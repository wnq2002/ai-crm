<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getCompany } from '@/api/companies'
import { formatDateTime } from '@/utils'
import { QUALIFICATION_LABELS } from '@/utils/labels'
import { getErrorMessage } from '@/api/http'
import type { CompanyDetail, QualificationStatus } from '@/types'

const route = useRoute()
const router = useRouter()
const companyId = route.params.id as string

const company = ref<CompanyDetail | null>(null)
const loading = ref(false)

async function loadCompany(): Promise<void> {
  loading.value = true
  try {
    company.value = await getCompany(companyId)
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

function openLead(id: string): void {
  router.push({ name: 'lead-detail', params: { id } })
}

function qualificationLabel(status: string): string {
  return QUALIFICATION_LABELS[status as QualificationStatus] ?? status
}

onMounted(loadCompany)
</script>

<template>
  <div class="page-container">
    <div class="detail-header">
      <el-button :icon="ArrowLeft" link @click="router.push({ name: 'customers' })">返回企业列表</el-button>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-card">
      <template #header>
        <span>{{ company?.canonical_name ?? '企业详情' }}</span>
      </template>

      <template v-if="company">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标准名称">{{ company.canonical_name }}</el-descriptions-item>
          <el-descriptions-item label="别名">
            {{ company.aliases?.length ? company.aliases.join('、') : '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="行业">{{ company.industry || '—' }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ company.phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="官网">{{ company.website || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header><span>联系人（{{ company?.contacts?.length ?? 0 }}）</span></template>
      <el-table :data="company?.contacts ?? []" size="small">
        <el-table-column label="姓名" min-width="100">
          <template #default="{ row }">{{ row.name || '—' }}</template>
        </el-table-column>
        <el-table-column label="手机号" min-width="130">
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column label="邮箱" min-width="160">
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column label="微信号" min-width="120">
          <template #default="{ row }">{{ row.wechat_id || '—' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <template #header><span>关联线索（{{ company?.leads?.length ?? 0 }}）</span></template>
      <el-table :data="company?.leads ?? []" size="small" row-key="id">
        <el-table-column label="获取时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.occurred_at) }}</template>
        </el-table-column>
        <el-table-column label="联系人" min-width="100">
          <template #default="{ row }">{{ row.contact_name_raw || '—' }}</template>
        </el-table-column>
        <el-table-column label="需求描述" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.inquiry_text || '—' }}</template>
        </el-table-column>
        <el-table-column label="判断" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ qualificationLabel(row.qualification_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openLead(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.detail-header {
  margin-bottom: 12px;
}
.detail-card {
  margin-bottom: 16px;
}
</style>
