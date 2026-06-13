<script setup>
import { useI18n } from '../i18n'

const { t } = useI18n()
</script>

<template>
  <footer>
    <div class="container footer-in">
      <img class="f-logo" src="/icon.png" alt="FARM tools" />
      <img class="f-logo" src="/farm_icon.png" alt="FARM Analytica" />
      <span>{{ t('footer.text') }}</span>
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

.f-logo {
  width: 27px;
  height: 27px;
  border-radius: 7px;
  object-fit: contain;
  opacity: 0.85;
}
</style>
