<script setup>
import { ref } from 'vue'
import { useI18n, SUPPORTED_LOCALES } from '../i18n'

const { locale, setLocale, t } = useI18n()
const menuOpen = ref(false)

const LANG_LABELS = { 'en-US': 'EN', 'pt-BR': 'PT' }

function closeMenu() {
  menuOpen.value = false
}
</script>

<template>
  <header>
    <div class="container nav">
      <router-link class="brand" to="/" @click="closeMenu" aria-label="FARM tools">
        <img class="brand-logo" src="/logo.svg" alt="FARM tools" />
      </router-link>
      <div class="nav-right">
        <button
          class="menu-toggle"
          :aria-expanded="menuOpen ? 'true' : 'false'"
          @click="menuOpen = !menuOpen"
        >
          {{ menuOpen ? '✕' : '☰' }}
        </button>
        <nav class="nav-links" :class="{ open: menuOpen }" aria-label="Main navigation">
          <router-link to="/" @click="closeMenu">{{ t('nav.home') }}</router-link>
          <router-link to="/tutorials" @click="closeMenu">{{ t('nav.tutorials') }}</router-link>
          <router-link to="/wiki/getting-started" :class="{ 'router-link-active': $route.name === 'wiki' }" @click="closeMenu">
            {{ t('nav.wiki') }}
          </router-link>
          <a
            href="https://github.com/farmanalytica/farm_tools"
            target="_blank"
            rel="noopener noreferrer"
            @click="closeMenu"
          >
            {{ t('nav.github') }}
          </a>
        </nav>
        <div class="lang-toggle" role="group" :aria-label="t('langToggle.label')">
          <button
            v-for="code in SUPPORTED_LOCALES"
            :key="code"
            type="button"
            :class="{ active: locale === code }"
            @click="setLocale(code)"
          >
            {{ LANG_LABELS[code] }}
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border);
}

.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 0;
  gap: 1.5rem;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Fraunces', serif;
  font-size: 1.18rem;
  font-weight: 700;
  color: var(--primary);
}

.brand-logo {
  height: 30px;
  width: auto;
  object-fit: contain;
  display: block;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 1.1rem;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.nav-links a {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-soft);
  transition: color 0.15s;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  color: var(--primary);
}

.lang-toggle {
  display: inline-flex;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--r-full);
  padding: 0.18rem;
  gap: 0.12rem;
}

.lang-toggle button {
  border: none;
  background: transparent;
  color: var(--text-soft);
  font-weight: 600;
  font-size: 0.72rem;
  padding: 0.26rem 0.58rem;
  border-radius: var(--r-full);
  cursor: pointer;
  transition: all 0.15s;
  font-family: 'Inter', sans-serif;
}

.lang-toggle button.active {
  background: var(--primary);
  color: var(--white);
}

.lang-toggle button:not(.active):hover {
  background: var(--border);
}

.menu-toggle {
  display: none;
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 0.36rem 0.52rem;
  cursor: pointer;
  color: var(--text);
  font-size: 1.1rem;
  line-height: 1;
}

@media (max-width: 900px) {
  .menu-toggle {
    display: flex;
  }

  .nav-links {
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.97);
    border-bottom: 1px solid var(--border);
    flex-direction: column;
    padding: 1rem 1.4rem;
    gap: 0.5rem;
    z-index: 40;
  }

  .nav-links.open {
    display: flex;
  }

  .nav-right {
    gap: 0.7rem;
  }
}
</style>
