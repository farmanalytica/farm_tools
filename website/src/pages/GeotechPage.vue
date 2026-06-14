<script setup>
import { computed } from 'vue'
import { useI18n } from '../i18n'
import lessons from '../data/lessons'
import CourseSections from '../components/CourseSections.vue'

const { t } = useI18n()

const CATEGORY_ORDER = ['foundations', 'data', 'analysis', 'output']

const groups = computed(() =>
  CATEGORY_ORDER.map((category) => ({
    key: category,
    label: t(`geotech.categories.${category}`),
    videos: lessons.filter((l) => l.category === category),
  })).filter((g) => g.videos.length > 0)
)
</script>

<template>
  <section class="page-head">
    <div class="container">
      <p class="sec-label light">{{ t('geotech.label') }}</p>
      <h1>{{ t('geotech.title') }}</h1>
      <p class="head-lead">{{ t('geotech.lead') }}</p>
    </div>
  </section>

  <CourseSections :groups="groups" />
</template>

<style scoped>
.page-head {
  background: var(--primary);
  padding: 4.5rem 0 4rem;
}

.page-head h1 {
  max-width: none;
}

.sec-label.light {
  color: #8fd4bb;
}

.head-lead {
  color: rgba(255, 255, 255, 0.72);
  font-size: 1.04rem;
  max-width: 60ch;
  line-height: 1.75;
}

@media (max-width: 768px) {
  .page-head {
    padding: 3rem 0 2.5rem;
  }

  .head-lead {
    font-size: 0.98rem;
  }
}

@media (max-width: 480px) {
  .page-head {
    padding: 2rem 0 1.5rem;
  }

  .head-lead {
    font-size: 0.93rem;
  }
}
</style>
