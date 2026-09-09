import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/login',
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/Login.vue'),
    },
    {
      path: '/agents',
      name: 'Agents',
      component: () => import('../views/AgentList.vue'),
    },
    {
      path: '/llm-configs',
      name: 'LlmConfigs',
      component: () => import('../views/LlmConfig.vue'),
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../views/Settings.vue'),
    },
    {
      path: '/admin',
      component: () => import('../views/admin/AdminLayout.vue'),
      children: [
        { path: '', redirect: '/admin/overview' },
        { path: 'overview', name: 'AdminOverview', component: () => import('../views/admin/AdminOverview.vue') },
        { path: 'users', name: 'AdminUsers', component: () => import('../views/admin/AdminUsers.vue') },
        { path: 'tasks', name: 'AdminTasks', component: () => import('../views/admin/AdminTasks.vue') },
        { path: 'usage', name: 'AdminUsage', component: () => import('../views/admin/AdminUsage.vue') },
        { path: 'logs', name: 'AdminLogs', component: () => import('../views/admin/AdminLogs.vue') },
        { path: 'diagnose', name: 'AdminDiagnose', component: () => import('../views/admin/AdminDiagnose.vue') },
      ],
    },
    {
      path: '/skills',
      name: 'Skills',
      component: () => import('../views/SkillList.vue'),
    },
    {
      path: '/tasks',
      name: 'Tasks',
      component: () => import('../views/TaskCenter.vue'),
    },
    {
      path: '/web-monitor',
      name: 'WebMonitor',
      component: () => import('../views/WebMonitor.vue'),
    },
    {
      path: '/widgets',
      name: 'WidgetStudio',
      component: () => import('../views/WidgetStudio.vue'),
    },
    {
      path: '/knowledge-spaces',
      name: 'KnowledgeSpaceCenter',
      component: () => import('../views/knowledge/SpaceCenter.vue'),
    },
    {
      path: '/knowledge-spaces/:id',
      name: 'KnowledgeSpaceDetail',
      component: () => import('../views/knowledge/SpaceDetail.vue'),
      props: true,
    },
    {
      path: '/knowledge-spaces/:id/debug',
      name: 'KnowledgeSpaceDebug',
      component: () => import('../views/knowledge/RagDebugConsole.vue'),
      props: true,
    },
    {
      path: '/chat/:agentId',
      name: 'Chat',
      component: () => import('../views/Chat.vue'),
      props: true,
    },
    {
      path: '/agents/:agentId/debug',
      name: 'AgentDebug',
      component: () => import('../views/AgentDebug.vue'),
      props: true,
    },
    {
      path: '/memory/:agentId',
      name: 'Memory',
      component: () => import('../views/Memory.vue'),
      props: true,
    },
    {
        path: '/knowledge/:agentId',
        name: 'Knowledge',
        component: () => import('../views/Knowledge.vue'),
        props: true,
    },
  ],
})

// 路由守卫：未登录跳转登录页
router.beforeEach((to, _from) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    return '/login'
  }
  const user = JSON.parse(localStorage.getItem('user') || 'null')
  if (token && to.path === '/login') {
    return user?.is_admin ? '/admin' : '/agents'
  }
  if (to.path.startsWith('/admin')) {
    if (!user?.is_admin) return '/agents'
  }
  if (user?.is_admin && !to.path.startsWith('/admin')) {
    return '/admin'
  }
  return true
})

export default router
