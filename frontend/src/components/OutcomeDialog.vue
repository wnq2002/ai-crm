<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { setOutcome, type OutcomePayload } from '@/api/leads'
import { getErrorMessage } from '@/api/http'
import type { Lead } from '@/types'

const props = defineProps<{
  modelValue: boolean
  leadId: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved', lead: Lead): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const submitting = ref(false)
const form = reactive({
  outcome_status: 'in_progress' as OutcomePayload['outcome_status'],
  note: '',
  feedback_at: new Date() as Date | null,
})

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    form.outcome_status = 'in_progress'
    form.note = ''
    form.feedback_at = new Date()
  },
)

async function handleSubmit(): Promise<void> {
  const isFinal = form.outcome_status === 'won' || form.outcome_status === 'lost'
  if (isFinal && !form.note.trim()) {
    ElMessage.warning('成交/未成交需填写依据简述')
    return
  }
  submitting.value = true
  try {
    const lead = await setOutcome(props.leadId, {
      outcome_status: form.outcome_status,
      note: form.note || undefined,
      feedback_at: form.feedback_at ? form.feedback_at.toISOString() : undefined,
    })
    ElMessage.success('已登记反馈')
    emit('saved', lead)
    visible.value = false
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="登记反馈" width="480px" :close-on-click-modal="false">
    <el-form label-width="88px">
      <el-form-item label="进展">
        <el-select v-model="form.outcome_status" style="width: 100%">
          <el-option label="部门推进中" value="in_progress" />
          <el-option label="已成交" value="won" />
          <el-option label="未成交" value="lost" />
          <el-option label="暂缓" value="deferred" />
        </el-select>
      </el-form-item>
      <el-form-item label="依据简述">
        <el-input
          v-model="form.note"
          type="textarea"
          :rows="3"
          :placeholder="form.outcome_status === 'won' || form.outcome_status === 'lost' ? '成交/未成交必填' : '选填'"
        />
      </el-form-item>
      <el-form-item label="反馈时间">
        <el-date-picker
          v-model="form.feedback_at"
          type="datetime"
          placeholder="反馈时间"
          style="width: 100%"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>
