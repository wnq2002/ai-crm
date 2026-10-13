<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Component } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types'
import {
  ArrowDown,
  DataAnalysis,
  OfficeBuilding,
  Odometer,
  Setting,
  SwitchButton,
  Tickets,
  UserFilled,
} from '@element-plus/icons-vue'

interface MenuItem {
  index: string
  title: string
  icon: Component
  roles?: Role[]
}

const allMenuItems: MenuItem[] = [
  { index: '/dashboard', title: '工作台', icon: Odometer },
  { index: '/leads', title: '线索管理', icon: Tickets },
  { index: '/customers', title: '客户管理', icon: OfficeBuilding },
  { index: '/reports', title: '数据分析', icon: DataAnalysis },
  { index: '/settings', title: '系统设置', icon: Setting, roles: ['admin'] },
]

const roleLabel: Record<Role, string> = {
  admin: '管理员',
  market: '市场部',
}

const router = useRouter()
const auth = useAuthStore()

const menuItems = computed(() =>
  allMenuItems.filter(
    (item) => !item.roles || (auth.role !== null && item.roles.includes(auth.role)),
  ),
)

const activeMenu = computed(() => router.currentRoute.value.path)
const pageTitle = computed(() => String(router.currentRoute.value.meta.title ?? ''))
const displayName = computed(() => auth.user?.display_name ?? auth.user?.username ?? '')
const roleText = computed(() => (auth.role ? roleLabel[auth.role] : ''))

async function handleLogout(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  await auth.logout()
  ElMessage.success('已退出登录')
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside class="layout__aside">
      <div class="layout__logo">AI CRM</div>
      <el-menu
        :default-active="activeMenu"
        router
        class="layout__menu"
        text-color="var(--app-sidebar-text)"
        active-text-color="var(--primary)"
        background-color="transparent"
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="layout__body">
      <el-header class="layout__header">
        <span class="layout__page-title">{{ pageTitle }}</span>
        <el-dropdown trigger="click">
          <span class="layout__user">
            <el-icon><UserFilled /></el-icon>
            <span>{{ displayName }}</span>
            <el-tag size="small" type="info" effect="plain">{{ roleText }}</el-tag>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item :icon="SwitchButton" @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="layout__main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100%;
}
.layout__aside {
  width: var(--app-sidebar-width);
  background: var(--app-sidebar-bg);
  border-right: 1px solid var(--border-color);
  --el-menu-hover-bg-color: var(--bg-hover);
}
.layout__logo {
  height: var(--app-header-height);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 1px;
}
.layout__menu {
  border-right: none;
}
.layout__menu .el-menu-item.is-active {
  background: var(--bg-selected);
  color: var(--primary);
}
.layout__body {
  min-width: 0;
}
.layout__header {
  height: var(--app-header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #ffffff;
  border-bottom: 1px solid var(--border-color);
}
.layout__page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}
.layout__user {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text-primary);
  outline: none;
}
.layout__main {
  background: var(--app-page-bg);
  overflow: auto;
}
</style>
