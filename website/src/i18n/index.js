import { ref, computed } from 'vue'
import enUS from './en-US'
import ptBR from './pt-BR'

export const SUPPORTED_LOCALES = ['en-US', 'pt-BR']
const STORAGE_KEY = 'farmToolsWebsiteLang'

const messages = { 'en-US': enUS, 'pt-BR': ptBR }

function detectLocale() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (SUPPORTED_LOCALES.includes(saved)) return saved
  const browser = (navigator.language || 'en').toLowerCase()
  return browser.startsWith('pt') ? 'pt-BR' : 'en-US'
}

export const locale = ref(detectLocale())

export function setLocale(value) {
  if (!SUPPORTED_LOCALES.includes(value)) return
  locale.value = value
  localStorage.setItem(STORAGE_KEY, value)
  document.documentElement.lang = value
}

/** Resolve a dot-separated key in the active locale, falling back to en-US. */
export function t(key) {
  const resolve = (msgs) => key.split('.').reduce((node, part) => (node == null ? node : node[part]), msgs)
  const value = resolve(messages[locale.value])
  if (value !== undefined) return value
  const fallback = resolve(messages['en-US'])
  return fallback !== undefined ? fallback : key
}

export const i18n = {
  install(app) {
    document.documentElement.lang = locale.value
    app.config.globalProperties.$t = t
    app.provide('i18n', { locale, setLocale, t })
  },
}

export function useI18n() {
  return { locale, setLocale, t, currentLocale: computed(() => locale.value) }
}
