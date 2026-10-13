<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createActivity } from '@/api/activities'
import { generateIdempotencyKey } from '@/utils/idempotency'
import { getErrorMessage } from '@/api/http'

const props = defineProps<{
  modelValue: boolean
  leadId: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const submitting = ref(false)
const form = reactive({ content: '' })

async function handleSubmit(): Promise<void> {
  submitting.value = true
  try {
    await createActivity(props.leadId, {
      kind: 'note',
      content: form.content || undefined,
      idempotency_key: generateIdempotencyKey(),
    })
    ElMessage.success('备注已保存')
    form.content = ''
    visible.value = false
    emit('saved')
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="备注" width="480px" :close-on-click-modal="false">
    <el-input
      v-model="form.content"
      type="textarea"
      :rows="4"
      maxlength="2000"
      show-word-limit
      placeholder="可选填，最多 2000 字"
    />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>
