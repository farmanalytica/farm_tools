import { createRouter, createWebHashHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import TutorialsPage from '../pages/TutorialsPage.vue'
import WikiPage from '../pages/WikiPage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: HomePage },
    { path: '/tutorials', name: 'tutorials', component: TutorialsPage },
    { path: '/wiki', redirect: '/wiki/getting-started' },
    { path: '/wiki/:slug', name: 'wiki', component: WikiPage },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
})

export default router
