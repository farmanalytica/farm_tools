<script setup>
import { useI18n } from '../i18n'

const { t } = useI18n()
</script>

<template>
  <footer>
    <div class="container footer-in">
      <img class="f-logo" src="/farm_analytica_horizontal_white.svg" alt="FARM Analytica" />
      <span>{{ t('footer.textBefore') }}<a class="f-link" href="https://farmanalytica.com.br" target="_blank" rel="noopener">{{ t('footer.linkText') }}</a>{{ t('footer.textAfter') }}</span>
    </div>
  </footer>
</template>

<style scoped>
footer {
  background: var(--primary);
  padding: 2.2rem 0;
}

.footer-in {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.8rem;
  flex-wrap: wrap;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.87rem;
}

.f-link {
  color: inherit;
  text-decoration: underline;
}

.f-link:hover {
  color: #fff;
}

.f-logo {
  height: 30px;
  width: auto;
  object-fit: contain;
  opacity: 0.85;
}
</style>
