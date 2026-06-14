<script setup>
import { computed } from 'vue'
import { useI18n } from '../i18n'
import videos from '../data/videos'
import CourseSections from '../components/CourseSections.vue'

const { t } = useI18n()

// Finer than the 5 broad categories — one playlist group per module so a
// section is never more than a handful of videos. Order follows the catalog.
const MODULE_ORDER = [
  'getting-started',
  'optical',
  'landsat',
  'sar',
  'mapbiomas',
  'dem',
  'sysi',
  'climaplots',
  'fieldguide',
]

const groups = computed(() =>
  MODULE_ORDER.map((mod) => ({
    key: mod,
    label: t(`tutorials.modules.${mod}`),
    videos: videos.filter((v) => v.wiki === mod),
  })).filter((g) => g.videos.length > 0)
)
</script>

<template>
  <section class="page-head">
    <div class="container">
      <p class="sec-label light">{{ t('tutorials.label') }}</p>
      <h1>{{ t('tutorials.title') }}</h1>
      <p class="head-lead">{{ t('tutorials.lead') }}</p>
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
