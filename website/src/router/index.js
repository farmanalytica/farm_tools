import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import TutorialsPage from '../pages/TutorialsPage.vue'
import GeotechPage from '../pages/GeotechPage.vue'
import PrecisionAgPage from '../pages/PrecisionAgPage.vue'
import WikiPage from '../pages/WikiPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomePage },
    { path: '/tutorials', name: 'tutorials', component: TutorialsPage },
    { path: '/geotech', name: 'geotech', component: GeotechPage },
    { path: '/precisao', name: 'precision', component: PrecisionAgPage },
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
