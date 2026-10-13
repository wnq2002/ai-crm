<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import {
  commitImport,
  downloadImportTemplate,
  previewImport,
  type ImportCommitResult,
  type ImportPreviewResult,
} from '@/api/imports'
import { generateIdempotencyKey } from '@/utils/idempotency'
import { getErrorMessage } from '@/api/http'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'imported'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const file = ref<File | null>(null)
const preview = ref<ImportPreviewResult | null>(null)
const commitResult = ref<ImportCommitResult | null>(null)
const loading = ref(false)

function reset(): void {
  file.value = null
  preview.value = null
  commitResult.value = null
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleTemplateDownload(): Promise<void> {
  try {
    const blob = await downloadImportTemplate()
    triggerDownload(blob, '线索导入模板.xlsx')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

function onFileChange(uploadFile: UploadFile): void {
  file.value = uploadFile.raw ?? null
  preview.value = null
  commitResult.value = null
}

async function handlePreview(): Promise<void> {
  if (!file.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  loading.value = true
  try {
    preview.value = await previewImport(file.value)
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

async function handleCommit(): Promise<void> {
  if (!preview.value) return
  loading.value = true
  try {
    commitResult.value = await commitImport(preview.value.preview_token, generateIdempotencyKey())
    ElMessage.success('导入完成')
    emit('imported')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}

function handleDownloadErrors(): void {
  const errors = preview.value?.errors ?? []
  if (errors.length === 0) return
  const header = '行号,错误说明'
  const body = errors
    .map((e) => `${e.row_number},"${String(e.message).replace(/"/g, '""')}"`)
    .join('\n')
  const blob = new Blob([`\ufeff${header}\n${body}`], { type: 'text/csv;charset=utf-8' })
  triggerDownload(blob, '导入错误明细.csv')
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="Excel / CSV 导入线索"
    width="640px"
    :close-on-click-modal="false"
    @open="reset"
  >
    <el-space direction="vertical" fill style="width: 100%">
      <el-button link type="primary" @click="handleTemplateDownload">下载导入模板</el-button>

      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".xlsx,.csv"
        :on-change="onFileChange"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em>（.xlsx / .csv）</div>
      </el-upload>

      <el-button type="primary" :loading="loading" :disabled="!file" @click="handlePreview">
        预览校验
      </el-button>

      <template v-if="preview">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="总行数">{{ preview.total_rows }}</el-descriptions-item>
          <el-descriptions-item label="有效行">{{ preview.valid_rows }}</el-descriptions-item>
          <el-descriptions-item label="疑似重复">{{ preview.duplicates.length }}</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="preview.errors.length > 0"
          type="warning"
          :closable="false"
          show-icon
          :title="`${preview.errors.length} 行存在错误`"
        >
          <el-table :data="preview.errors" size="small" max-height="180">
            <el-table-column prop="row_number" label="行号" width="80" />
            <el-table-column prop="message" label="错误说明" show-overflow-tooltip />
          </el-table>
        </el-alert>

        <div>
          <el-button type="success" :loading="loading" @click="handleCommit">确认导入</el-button>
          <el-button v-if="preview.errors.length" link type="primary" @click="handleDownloadErrors">
            下载错误明细
          </el-button>
        </div>
      </template>

      <el-result
        v-if="commitResult"
        icon="success"
        title="导入完成"
        :sub-title="`成功 ${commitResult.success_rows} 行，失败 ${commitResult.failed_rows} 行，跳过 ${commitResult.skipped_rows} 行`"
      />
    </el-space>
  </el-dialog>
</template>
