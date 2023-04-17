import { createRouter, createWebHistory } from 'vue-router'
import auth from '@/utils/auth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/pages/Home.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: {
      hideSidebar: true,
      allowGuest: true,
    },
  },
]

let router = createRouter({
  history: createWebHistory('/mrp'),
  routes,
})

router.beforeEach(async (to, from, next) => {
  if (!auth.isLoggedIn && to.name !== 'Login' && to.meta.allowGuest) {
    // if page is allowed for guest, and is not login page, allow
    return next()
  }

  if (!auth.isLoggedIn) {
    // if in dev mode, open login page
    if (import.meta.env.DEV) {
      return to.fullPath === '/login' ? next() : next('/login')
    }
    // redirect to frappe login page, for oauth and signup
    window.location.href = '/login'
    return next(false)
  }

  const isAuthorized = await auth.isAuthorized()
  if (!isAuthorized && to.name !== 'No Permission') {
    return next('/no-permission')
  }
  if (isAuthorized && to.name === 'No Permission') {
    return next()
  }
  if (to.meta.isAllowed && !to.meta.isAllowed()) {
    return next('/no-permission')
  }

  if (to.path === '/login') {
    next('/')
  } else {
    next()
  }
})

const _fetch = window.fetch
window.fetch = async function () {
  const res = await _fetch(...arguments)
  if (
    res.status === 403 &&
    (!document.cookie || document.cookie.includes('user_id=Guest'))
  ) {
    auth.reset()
    router.push('/login')
  }
  return res
}

export default router
