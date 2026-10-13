<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'
import { getErrorMessage } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

// 密码最小长度 8 与 api-contract §2 对齐；最终以服务端 Pydantic 校验为准。
const MIN_PASSWORD_LENGTH = 8

const rules: FormRules<typeof form> = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: MIN_PASSWORD_LENGTH, message: `新密码至少 ${MIN_PASSWORD_LENGTH} 位`, trigger: 'blur' },
  ],
  confirm_password: [{ required: true, message: '请再次输入新密码', trigger: 'blur' }],
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  if (form.new_password !== form.confirm_password) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    await auth.changePassword({
      old_password: form.old_password,
      new_password: form.new_password,
    })
    ElMessage.success('密码已修改')
    router.push({ name: 'dashboard' })
  } catch (err) {
    ElMessage.error(getErrorMessage(err))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="change-password">
    <el-card class="change-password__card" shadow="always">
      <div class="change-password__brand">
        <h1>修改密码</h1>
        <p>首次登录须修改初始密码后方可继续使用系统</p>
      </div>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleSubmit"
      >
        <el-form-item label="原密码" prop="old_password">
          <el-input
            v-model="form.old_password"
            type="password"
            :prefix-icon="Lock"
            placeholder="请输入原密码"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            :prefix-icon="Lock"
            placeholder="请输入新密码"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            :prefix-icon="Lock"
            placeholder="请再次输入新密码"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="change-password__submit" :loading="loading" @click="handleSubmit">
            确认修改
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.change-password {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--app-page-bg);
}
.change-password__card {
  width: 420px;
}
.change-password__brand {
  text-align: center;
  margin-bottom: 24px;
}
.change-password__brand h1 {
  margin: 0 0 8px;
  font-size: 22px;
}
.change-password__brand p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
.change-password__submit {
  width: 100%;
}
</style>
