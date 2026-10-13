<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createActivity } from '@/api/activities'
import { generateIdempotencyKey } from '@/utils/idempotency'
import { getErrorMessage } from '@/api/http'
import type { ActivityKind, ActivityResult, LeadActivity, WechatRelationship } from '@/types'

const props = defineProps<{
  modelValue: boolean
  leadId: string
  kind: 'phone' | 'wechat'
  wechatRelationship?: WechatRelationship
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved', activity: LeadActivity): void
}>()

const submitting = ref(false)
const form = reactive({
  result: 'connected' as ActivityResult,
  wechatKind: 'wechat_request' as Extract<
    ActivityKind,
    'wechat_request' | 'wechat_approved' | 'wechat_chat'
  >,
  content: '',
  happened_at: null as Date | null,
  next_follow_up_at: null as Date | null,
})

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const title = computed(() => '记录跟进')

// 微信沟通（wechat_chat）仅在关系已通过后可选（服务端强校验）。
const wechatOptions = computed(() => [
  { value: 'wechat_request', label: '发送好友申请' },
  { value: 'wechat_approved', label: '好友申请通过' },
  {
    value: 'wechat_chat',
    label: '微信沟通',
    disabled: props.wechatRelationship !== 'approved',
  },
])

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    form.result = 'connected'
    form.wechatKind = 'wechat_request'
    form.content = ''
    form.happened_at = null
    form.next_follow_up_at = null
  },
)

async function handleSubmit(): Promise<void> {
  submitting.value = true
  try {
    const next = form.next_follow_up_at ? form.next_follow_up_at.toISOString() : undefined
    const payload =
      props.kind === 'phone'
        ? {
            kind: 'phone' as const,
            result: form.result,
            content: form.content || undefined,
            happened_at: form.happened_at ? form.happened_at.toISOString() : undefined,
            next_follow_up_at: next,
            idempotency_key: generateIdempotencyKey(),
          }
        : {
            kind: form.wechatKind,
            content: form.content || undefined,
            happened_at: form.happened_at ? form.happened_at.toISOString() : undefined,
            next_follow_up_at: next,
            idempotency_key: generateIdempotencyKey(),
          }
    const activity = await createActivity(props.leadId, payload)
    ElMessage.success('已记录')
    emit('saved', activity)
    visible.value = false
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" :title="title" width="480px" :close-on-click-modal="false">
    <el-form label-width="96px">
      <el-form-item v-if="kind === 'phone'" label="联系结果">
        <el-select v-model="form.result" style="width: 100%">
          <el-option label="已接通" value="connected" />
          <el-option label="未接通" value="unconnected" />
          <el-option label="拒接" value="rejected" />
        </el-select>
      </el-form-item>
      <el-form-item v-else label="沟通类型">
        <el-select v-model="form.wechatKind" style="width: 100%">
          <el-option
            v-for="opt in wechatOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
            :disabled="opt.disabled"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="发生时间">
        <el-date-picker
          v-model="form.happened_at"
          type="datetime"
          placeholder="默认当前时间（可补录过去时间）"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="下次跟进">
        <el-date-picker
          v-model="form.next_follow_up_at"
          type="datetime"
          placeholder="选填，设置下次计划跟进时间"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="内容">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
          placeholder="选填，重要沟通内容"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>
