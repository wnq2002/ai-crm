<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  createLead,
  parseLead,
  updateLead,
  type LeadCreateResult,
  type LeadParseResult,
} from '@/api/leads'
import { listNeedTypes, listSourceCategories } from '@/api/dictionaries'
import { generateIdempotencyKey } from '@/utils/idempotency'
import { getErrorMessage } from '@/api/http'
import type { Lead, NeedType, SourceCategory } from '@/types'

const props = defineProps<{
  modelValue: boolean
  lead?: Lead | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'saved', result: LeadCreateResult | Lead): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const sourceCategories = ref<SourceCategory[]>([])
const needTypes = ref<NeedType[]>([])

// 粘贴识别（前端 M2）：把官网表单/钉钉消息原文交给 /leads/parse 提取字段后回填。
const parseText = ref('')
const parsing = ref(false)
const parseResult = ref<LeadParseResult | null>(null)
const parsedRawText = ref('')

const FIELD_LABELS: Record<string, string> = {
  company_name: '企业名称',
  contact_name: '联系人',
  phone: '手机号',
  email: '邮箱',
  inquiry_text: '需求描述',
  need_type: '需求类型',
  source_channel: '来源渠道',
}

const recognizedFields = computed(() => {
  const r = parseResult.value
  if (!r) return []
  return Object.keys(FIELD_LABELS).map((key) => {
    const field = r[key as keyof LeadParseResult] as { value: string | null; confidence: string | null }
    return { key, label: FIELD_LABELS[key], value: field.value, confidence: field.confidence }
  })
})

const form = reactive({
  occurred_at: new Date() as Date | null,
  contact_name_raw: '',
  phone_raw: '',
  email_raw: '',
  wechat_raw: '',
  company_name_raw: '',
  need_type_id: '',
  inquiry_text: '',
  source_category_id: '',
  notes: '',
})

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const isEdit = computed(() => !!props.lead)

const rules: FormRules = {
  occurred_at: [{ required: true, message: '请选择获取时间', trigger: 'change' }],
}

function resetForm(): void {
  form.occurred_at = new Date()
  form.contact_name_raw = ''
  form.phone_raw = ''
  form.email_raw = ''
  form.wechat_raw = ''
  form.company_name_raw = ''
  form.need_type_id = ''
  form.inquiry_text = ''
  form.source_category_id = ''
  form.notes = ''
  parseText.value = ''
  parseResult.value = null
  parsedRawText.value = ''
}

function confidenceTagType(confidence: string | null): 'success' | 'warning' | 'info' {
  if (confidence === 'high') return 'success'
  if (confidence === 'low') return 'warning'
  return 'info'
}

async function handleParse(): Promise<void> {
  if (!parseText.value.trim()) {
    ElMessage.warning('请先粘贴需要识别的原文')
    return
  }
  parsing.value = true
  try {
    parseResult.value = await parseLead(parseText.value.trim())
    ElMessage.success('识别完成，请核对后填入')
  } catch (err) {
    parseResult.value = null
    ElMessage.error(getErrorMessage(err))
  } finally {
    parsing.value = false
  }
}

function matchNeedTypeId(name: string): string | null {
  const n = name.trim().toLowerCase()
  return needTypes.value.find((t) => t.name.trim().toLowerCase() === n)?.id ?? null
}

function matchSourceCategoryId(name: string): string | null {
  const n = name.trim().toLowerCase()
  return (
    sourceCategories.value.find(
      (c) => c.name.trim().toLowerCase() === n || c.code.toLowerCase() === n,
    )?.id ?? null
  )
}

// 只填入当前为空的字段，避免覆盖用户已手动输入的内容。
function applyParsed(): void {
  const p = parseResult.value
  if (!p) return
  if (p.company_name.value && !form.company_name_raw) form.company_name_raw = p.company_name.value
  if (p.contact_name.value && !form.contact_name_raw) form.contact_name_raw = p.contact_name.value
  if (p.phone.value && !form.phone_raw) form.phone_raw = p.phone.value
  if (p.email.value && !form.email_raw) form.email_raw = p.email.value
  if (p.inquiry_text.value && !form.inquiry_text) form.inquiry_text = p.inquiry_text.value
  if (p.need_type.value && !form.need_type_id) {
    const id = matchNeedTypeId(p.need_type.value)
    if (id) form.need_type_id = id
    else ElMessage.warning(`需求类型「${p.need_type.value}」不在字典中，未自动填入`)
  }
  if (p.source_channel.value && !form.source_category_id) {
    const id = matchSourceCategoryId(p.source_channel.value)
    if (id) form.source_category_id = id
    else ElMessage.warning(`来源「${p.source_channel.value}」不在字典中，未自动填入`)
  }
  parsedRawText.value = parseText.value.trim()
  ElMessage.success('已填入空字段，请核对')
}

// 校验底线：至少具备联系方式 / 可识别姓名+来源 / 需求描述+来源 / 外部事件引用之一（api-contract §4）。
function hasIdentifiableContent(): boolean {
  const hasContact = !!(form.phone_raw || form.email_raw || form.wechat_raw)
  const hasNameAndSource = !!(form.contact_name_raw && form.source_category_id)
  const hasInquiryAndSource = !!(form.inquiry_text && form.source_category_id)
  return hasContact || hasNameAndSource || hasInquiryAndSource
}

function toCreatePayload() {
  return {
    occurred_at: form.occurred_at ? form.occurred_at.toISOString() : undefined,
    contact_name_raw: form.contact_name_raw || undefined,
    phone_raw: form.phone_raw || undefined,
    email_raw: form.email_raw || undefined,
    wechat_raw: form.wechat_raw || undefined,
    company_name_raw: form.company_name_raw || undefined,
    need_type_id: form.need_type_id || undefined,
    inquiry_text: form.inquiry_text || undefined,
    source_category_id: form.source_category_id || undefined,
    notes: form.notes || undefined,
    intake_method: 'manual',
    idempotency_key: generateIdempotencyKey(),
    parse_record: parsedRawText.value
      ? {
          raw_text: parsedRawText.value,
          parsed_json: parseResult.value
            ? (parseResult.value as unknown as Record<string, unknown>)
            : undefined,
        }
      : undefined,
  }
}

function fillFromLead(lead: Lead): void {
  form.occurred_at = lead.occurred_at ? new Date(lead.occurred_at) : new Date()
  form.contact_name_raw = lead.contact_name_raw ?? ''
  form.phone_raw = lead.phone_raw ?? ''
  form.email_raw = lead.email_raw ?? ''
  form.wechat_raw = lead.wechat_raw ?? ''
  form.company_name_raw = lead.company_name_raw ?? ''
  form.need_type_id = lead.need_type_id ?? ''
  form.inquiry_text = lead.inquiry_text ?? ''
  form.source_category_id = lead.source_category_id ?? ''
  form.notes = lead.notes ?? ''
}

async function loadDictionaries(): Promise<void> {
  const [categories, types] = await Promise.all([
    listSourceCategories(),
    listNeedTypes(),
  ])
  sourceCategories.value = categories.filter((c) => c.active)
  needTypes.value = types.filter((t) => t.active)
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  if (!hasIdentifiableContent()) {
    ElMessage.warning('请至少填写联系方式、姓名+来源、需求描述+来源或外部事件 ID')
    return
  }

  submitting.value = true
  try {
    if (isEdit.value && props.lead) {
      const updated = await updateLead(props.lead.id, {
        version: props.lead.version,
        occurred_at: form.occurred_at ? form.occurred_at.toISOString() : undefined,
        contact_name_raw: form.contact_name_raw || undefined,
        phone_raw: form.phone_raw || undefined,
        email_raw: form.email_raw || undefined,
        wechat_raw: form.wechat_raw || undefined,
        company_name_raw: form.company_name_raw || undefined,
        need_type_id: form.need_type_id || undefined,
        inquiry_text: form.inquiry_text || undefined,
        source_category_id: form.source_category_id || undefined,
        notes: form.notes || undefined,
      })
      emit('saved', updated)
      ElMessage.success('线索已更新')
    } else {
      const result = await createLead(toCreatePayload())
      emit('saved', result)
      ElMessage.success('线索已保存')
    }
    visible.value = false
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    resetForm()
    if (props.lead) fillFromLead(props.lead)
  },
)
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑线索' : '新建线索'"
    width="640px"
    :close-on-click-modal="false"
    @open="loadDictionaries"
  >
    <div v-if="!isEdit" class="parse-section">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="粘贴识别（可选）：把官网表单 / 钉钉群消息原文粘进来，自动提取字段填入下方表单"
      />
      <el-input
        v-model="parseText"
        type="textarea"
        :rows="4"
        class="parse-input"
        placeholder="在此粘贴原文，例如：客户赵六，电话 13800001234，想要 AI Agent，来自官网表单"
      />
      <div class="parse-actions">
        <el-button type="primary" :loading="parsing" @click="handleParse">识别</el-button>
        <el-button v-if="parseResult" type="success" plain @click="applyParsed">填入空字段</el-button>
      </div>
      <template v-if="parseResult">
        <el-descriptions :column="2" border size="small" class="parse-result">
          <el-descriptions-item v-for="f in recognizedFields" :key="f.key" :label="f.label">
            <template v-if="f.value">
              {{ f.value }}
              <el-tag :type="confidenceTagType(f.confidence)" size="small" effect="plain">
                {{ f.confidence ?? '—' }}
              </el-tag>
            </template>
            <span v-else class="parse-empty">未识别</span>
          </el-descriptions-item>
        </el-descriptions>
        <el-alert
          v-if="parseResult.hints.length"
          type="warning"
          :closable="false"
          show-icon
          :title="parseResult.hints.join('；')"
        />
      </template>
      <el-divider />
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="获取时间" prop="occurred_at">
        <el-date-picker
          v-model="form.occurred_at"
          type="datetime"
          placeholder="选择获取时间"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="form.contact_name_raw" placeholder="选填" />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="form.phone_raw" placeholder="选填" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email_raw" placeholder="选填" />
      </el-form-item>
      <el-form-item label="微信号">
        <el-input v-model="form.wechat_raw" placeholder="选填" />
      </el-form-item>
      <el-form-item label="企业名称">
        <el-input v-model="form.company_name_raw" placeholder="未填写（选填，可无企业录入）" />
      </el-form-item>
      <el-form-item label="需求类型">
        <el-select v-model="form.need_type_id" clearable placeholder="选填" style="width: 100%">
          <el-option v-for="t in needTypes" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="需求描述">
        <el-input v-model="form.inquiry_text" type="textarea" :rows="3" placeholder="选填" />
      </el-form-item>
      <el-form-item label="来源类型">
        <el-select v-model="form.source_category_id" clearable placeholder="默认未知，可后补" style="width: 100%">
          <el-option v-for="c in sourceCategories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="选填，补充说明" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.parse-section {
  margin-bottom: 8px;
}
.parse-input {
  margin-top: 12px;
}
.parse-actions {
  margin-top: 12px;
}
.parse-result {
  margin-top: 12px;
}
.parse-empty {
  color: var(--el-text-color-secondary);
}
</style>
