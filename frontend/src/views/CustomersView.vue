<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  createCompany,
  listCompanies,
  mergeCompanies,
  mergePreview,
  type CompanyListQuery,
} from '@/api/companies'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils'
import { getErrorMessage } from '@/api/http'
import type { CompanyListItem, CompanyMergePreview } from '@/types'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const companies = ref<CompanyListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const q = ref('')

const mergeVisible = ref(false)
const mergeOptions = ref<CompanyListItem[]>([])
const mergeSource = ref('')
const mergeTarget = ref('')
const mergeReason = ref('')
const merging = ref(false)
const previewing = ref(false)
const preview = ref<CompanyMergePreview | null>(null)

const isAdmin = computed(() => auth.role === 'admin')

const companyDialog = reactive({
  visible: false,
  canonical_name: '',
  aliases: '',
  industry: '',
  phone: '',
  website: '',
})
const savingCompany = ref(false)

function openCreateCompany(): void {
  companyDialog.canonical_name = ''
  companyDialog.aliases = ''
  companyDialog.industry = ''
  companyDialog.phone = ''
  companyDialog.website = ''
  companyDialog.visible = true
}

function splitAliases(raw: string): string[] {
  return raw
    .split(/[,，、\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

async function submitCompany(): Promise<void> {
  if (!companyDialog.canonical_name.trim()) {
    ElMessage.warning('请输入企业名称')
    return
  }
  savingCompany.value = true
  try {
    await createCompany({
      canonical_name: companyDialog.canonical_name.trim(),
      aliases: splitAliases(companyDialog.aliases),
      industry: companyDialog.industry.trim() || undefined,
      phone: companyDialog.phone.trim() || undefined,
      website: companyDialog.website.trim() || undefined,
    })
    ElMessage.success('已新建企业')
    companyDialog.visible = false
    loadCompanies()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    savingCompany.value = false
  }
}

async function loadCompanies(): Promise<void> {
  loading.value = true
  try {
    const params: CompanyListQuery = {
      q: q.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    }
    const data = await listCompanies(params)
    companies.value = data.items
    total.value = data.total
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  loadCompanies()
}

function openDetail(id: string): void {
  router.push({ name: 'company-detail', params: { id } })
}

async function openMerge(): Promise<void> {
  mergeVisible.value = true
  preview.value = null
  try {
    const data = await listCompanies({ page: 1, page_size: 100 })
    mergeOptions.value = data.items
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

function resetPreview(): void {
  preview.value = null
}

async function handlePreview(): Promise<void> {
  if (!mergeSource.value || !mergeTarget.value) {
    ElMessage.warning('请选择源企业与目标企业')
    return
  }
  if (mergeSource.value === mergeTarget.value) {
    ElMessage.warning('源企业与目标企业不能相同')
    return
  }
  previewing.value = true
  try {
    preview.value = await mergePreview({
      source_company_id: mergeSource.value,
      target_company_id: mergeTarget.value,
    })
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    previewing.value = false
  }
}

async function handleMerge(): Promise<void> {
  if (!mergeSource.value || !mergeTarget.value) {
    ElMessage.warning('请选择源企业与目标企业')
    return
  }
  if (mergeSource.value === mergeTarget.value) {
    ElMessage.warning('源企业与目标企业不能相同')
    return
  }
  try {
    await ElMessageBox.confirm(
      '合并后源企业的线索与联系人将归并到目标企业，且不可撤销。确定合并？',
      '提示',
      { type: 'warning', confirmButtonText: '合并', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  merging.value = true
  try {
    await mergeCompanies({
      source_company_id: mergeSource.value,
      target_company_id: mergeTarget.value,
      reason: mergeReason.value || undefined,
    })
    ElMessage.success('合并完成')
    mergeVisible.value = false
    loadCompanies()
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    merging.value = false
  }
}

onMounted(loadCompanies)
</script>

<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="toolbar">
        <el-space>
          <el-input
            v-model="q"
            placeholder="搜索企业名称"
            clearable
            :prefix-icon="Search"
            style="width: 260px"
            @keyup.enter="handleSearch"
          />
          <el-button @click="handleSearch">查询</el-button>
        </el-space>
        <el-space>
          <el-button type="primary" :icon="Plus" @click="openCreateCompany">新建企业</el-button>
          <el-button v-if="isAdmin" plain type="warning" @click="openMerge">合并企业</el-button>
        </el-space>
      </div>

      <el-table v-loading="loading" :data="companies" row-key="id">
        <el-table-column label="企业名称" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.canonical_name }}</template>
        </el-table-column>
        <el-table-column label="行业" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.industry || '—' }}</template>
        </el-table-column>
        <el-table-column label="联系电话" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column label="官网" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.website || '—' }}</template>
        </el-table-column>
        <el-table-column label="关联线索数" width="110">
          <template #default="{ row }">{{ row.lead_count }}</template>
        </el-table-column>
        <el-table-column label="最近咨询时间" width="160">
          <template #default="{ row }">{{ formatDateTime(row.recent_inquiry_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.id)">查看</el-button>
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
        @current-change="loadCompanies"
        @size-change="handleSearch"
      />
    </el-card>

    <el-dialog v-model="mergeVisible" title="合并企业" width="520px" :close-on-click-modal="false">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="合并后源企业的线索与联系人将归并到目标企业，源企业标记为已合并（保留快照与审计）"
      />
      <el-form label-width="88px" class="merge-form">
        <el-form-item label="源企业">
          <el-select v-model="mergeSource" filterable placeholder="选择被合并的企业" style="width: 100%" @change="resetPreview">
            <el-option
              v-for="c in mergeOptions.filter((x) => x.id !== mergeTarget)"
              :key="c.id"
              :label="c.canonical_name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标企业">
          <el-select v-model="mergeTarget" filterable placeholder="选择保留的企业" style="width: 100%" @change="resetPreview">
            <el-option
              v-for="c in mergeOptions.filter((x) => x.id !== mergeSource)"
              :key="c.id"
              :label="c.canonical_name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="合并原因">
          <el-input v-model="mergeReason" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <el-alert
        v-if="preview"
        type="warning"
        :closable="false"
        show-icon
        :title="`将重指 ${preview.lead_relink_count} 条线索、归并 ${preview.contact_merge_count} 个联系人到目标企业，别名去向：${preview.alias_destination}`"
      />
      <template #footer>
        <el-button @click="mergeVisible = false">取消</el-button>
        <el-button :loading="previewing" @click="handlePreview">预览影响</el-button>
        <el-button type="warning" :loading="merging" :disabled="!preview" @click="handleMerge">确认合并</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="companyDialog.visible" title="新建企业" width="520px" :close-on-click-modal="false">
      <el-form label-width="88px">
        <el-form-item label="企业名称" required>
          <el-input v-model="companyDialog.canonical_name" placeholder="标准企业名称" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="companyDialog.aliases" placeholder="多个别名用逗号/空格分隔" />
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="companyDialog.industry" placeholder="选填" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="companyDialog.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="官网">
          <el-input v-model="companyDialog.website" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="companyDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="savingCompany" @click="submitCompany">保存</el-button>
      </template>
    </el-dialog>
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
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.merge-form {
  margin-top: 16px;
}
</style>
