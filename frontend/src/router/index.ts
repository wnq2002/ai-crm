import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { Role } from '@/types'

declare module 'vue-router' {
  interface RouteMeta {
    /** 免登录即可访问 */
    public?: boolean
    /** 允许访问的角色（缺省表示任意已登录用户） */
    roles?: Role[]
    title?: string
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/change-password',
    name: 'change-password',
    component: () => import('@/views/ChangePasswordView.vue'),
    meta: { title: '修改密码' },
  },
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    redirect: '/leads',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '工作台' },
      },
      {
        path: 'leads',
        name: 'leads',
        component: () => import('@/views/LeadsView.vue'),
        meta: { title: '线索管理' },
      },
      {
        path: 'leads/:id',
        name: 'lead-detail',
        component: () => import('@/views/LeadDetailView.vue'),
        meta: { title: '线索详情' },
      },
      {
        path: 'customers',
        name: 'customers',
        component: () => import('@/views/CustomersView.vue'),
        meta: { title: '客户管理' },
      },
      {
        path: 'customers/:id',
        name: 'company-detail',
        component: () => import('@/views/CompanyDetailView.vue'),
        meta: { title: '企业详情' },
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('@/views/ReportsView.vue'),
        meta: { title: '数据分析' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '系统设置', roles: ['admin'] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!auth.initialized) {
    await auth.fetchMe()
  }

  document.title = to.meta.title ? `${to.meta.title} · AI CRM` : 'AI CRM'

  if (to.meta.public) {
    if (auth.isAuthenticated && to.name === 'login') {
      return { name: 'dashboard' }
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (auth.mustChangePassword && to.name !== 'change-password') {
    return { name: 'change-password' }
  }

  if (to.meta.roles && !auth.hasRole(...to.meta.roles)) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
