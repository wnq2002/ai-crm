<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { reviseActivity, type ActivityRevisePayload } from '@/api/activities'
import { getErrorMessage } from '@/api/http'
import type { ActivityResult, LeadActivity } from '@/types'

const props = defineProps<{
  modelValue: boolean
  activity: LeadActivity | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}>()

const submitting = ref(false)
const form = reactive({
  happened_at: null as Date | null,
  result: 'connected' as ActivityResult,
  content: '',
  reason: '',
})

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const isPhone = computed(() => props.activity?.kind === 'phone')

watch(
  () => props.modelValue,
  (open) => {
    if (!open || !props.activity) return
    form.happened_at = props.activity.happened_at
      ? new Date(props.activity.happened_at)
      : null
    form.result = (props.activity.result as ActivityResult) ?? 'connected'
    form.content = props.activity.content ?? ''
    form.reason = ''
  },
)

async function handleSubmit(): Promise<void> {
  const activity = props.activity
  if (!activity) return
  if (!form.reason.trim()) {
    ElMessage.warning('请填写修正原因')
    return
  }

  const payload: ActivityRevisePayload = { reason: form.reason.trim() }
  const happenedAtChanged =
    !!form.happened_at &&
    form.happened_at.getTime() !== new Date(activity.happened_at).getTime()
  if (happenedAtChanged) {
    payload.happened_at = form.happened_at!.toISOString()
  }
  if (isPhone.value && form.result !== (activity.result ?? null)) {
    payload.result = form.result
  }
  if (form.content !== (activity.content ?? '')) {
    payload.content = form.content
  }

  if (!('happened_at' in payload) && !('result' in payload) && !('content' in payload)) {
    ElMessage.warning('请至少修改一项内容')
    return
  }

  submitting.value = true
  try {
    await reviseActivity(activity.id, payload)
    ElMessage.success('已修正')
    emit('saved')
    visible.value = false
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="修正事件" width="480px" :close-on-click-modal="false">
    <el-form label-width="96px">
      <el-form-item label="发生时间">
        <el-date-picker
          v-model="form.happened_at"
          type="datetime"
          placeholder="发生时间"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item v-if="isPhone" label="联系结果">
        <el-select v-model="form.result" style="width: 100%">
          <el-option label="已接通" value="connected" />
          <el-option label="未接通" value="unconnected" />
          <el-option label="拒接" value="rejected" />
        </el-select>
      </el-form-item>
      <el-form-item label="内容">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
          placeholder="沟通内容"
        />
      </el-form-item>
      <el-form-item label="修正原因" required>
        <el-input
          v-model="form.reason"
          type="textarea"
          :rows="2"
          maxlength="255"
          placeholder="必填，说明本次修正的原因"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>
