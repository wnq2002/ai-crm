<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { setHandoff } from '@/api/leads'
import { listDepartments, listDepartmentContacts } from '@/api/dictionaries'
import { getErrorMessage } from '@/api/http'
import type { Department, DepartmentContact, Lead } from '@/types'

const props = defineProps<{
  modelValue: boolean
  leadId: string
  currentDepartmentId?: string | null
  currentContactId?: string | null
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
const departments = ref<Department[]>([])
const departmentContacts = ref<DepartmentContact[]>([])
const form = reactive({ department_id: '', department_contact_id: '', note: '' })

const filteredContacts = computed(() =>
  departmentContacts.value.filter((c) => c.department_id === form.department_id),
)

function onDepartmentChange(): void {
  const def = departmentContacts.value.find(
    (c) => c.department_id === form.department_id && c.is_default,
  )
  form.department_contact_id = def?.id ?? ''
}

async function loadDictionaries(): Promise<void> {
  try {
    const [depts, contacts] = await Promise.all([listDepartments(), listDepartmentContacts()])
    departments.value = depts.filter((d) => d.active)
    departmentContacts.value = contacts.filter((c) => c.active)
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    form.note = ''
    await loadDictionaries()
    form.department_id = props.currentDepartmentId ?? ''
    form.department_contact_id = props.currentContactId ?? ''
    if (form.department_id && !form.department_contact_id) onDepartmentChange()
  },
)

async function handleSubmit(): Promise<void> {
  if (!form.department_id) {
    ElMessage.warning('请选择部门')
    return
  }
  submitting.value = true
  try {
    const lead = await setHandoff(props.leadId, {
      department_id: form.department_id,
      department_contact_id: form.department_contact_id || undefined,
      note: form.note || undefined,
    })
    ElMessage.success('已交接')
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
  <el-dialog v-model="visible" title="部门交接" width="480px" :close-on-click-modal="false">
    <el-form label-width="88px">
      <el-form-item label="部门">
        <el-select
          v-model="form.department_id"
          filterable
          placeholder="选择部门"
          style="width: 100%"
          @change="onDepartmentChange"
        >
          <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="对接人">
        <el-select
          v-model="form.department_contact_id"
          filterable
          clearable
          placeholder="默认对接人可改选"
          style="width: 100%"
          :disabled="!form.department_id"
        >
          <el-option v-for="c in filteredContacts" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="交接摘要">
        <el-input v-model="form.note" type="textarea" :rows="2" placeholder="选填" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确认交接</el-button>
    </template>
  </el-dialog>
</template>
