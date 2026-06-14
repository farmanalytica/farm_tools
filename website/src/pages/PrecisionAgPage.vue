<script setup>
import { computed } from 'vue'
import { useI18n } from '../i18n'
import lessons from '../data/precision'
import VideoCard from '../components/VideoCard.vue'

const { t } = useI18n()

const CATEGORY_ORDER = ['concepts', 'data', 'analysis', 'output']

const grouped = computed(() =>
  CATEGORY_ORDER.map((category) => ({
    category,
    lessons: lessons.filter((l) => l.category === category),
  })).filter((g) => g.lessons.length > 0)
)
</script>

<template>
  <section class="page-head">
    <div class="container">
      <p class="sec-label light">{{ t('precision.label') }}</p>
      <h1>{{ t('precision.title') }}</h1>
      <p class="head-lead">{{ t('precision.lead') }}</p>
    </div>
  </section>

  <section v-for="(group, i) in grouped" :key="group.category" :class="{ alt: i % 2 === 1 }">
    <div class="container">
      <h2>{{ t(`precision.categories.${group.category}`) }}</h2>
      <div class="grid3 video-grid">
        <VideoCard v-for="lesson in group.lessons" :key="lesson.id" :video="lesson" />
      </div>
    </div>
  </section>
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

section:not(.page-head) {
  padding: 3.5rem 0;
}

.video-grid {
  margin-top: 1.6rem;
}

@media (max-width: 768px) {
  .page-head {
    padding: 3rem 0 2.5rem;
  }

  .head-lead {
    font-size: 0.98rem;
  }

  section:not(.page-head) {
    padding: 2.5rem 0;
  }
}

@media (max-width: 480px) {
  .page-head {
    padding: 2rem 0 1.5rem;
  }

  .head-lead {
    font-size: 0.93rem;
  }

  section:not(.page-head) {
    padding: 1.8rem 0;
  }

  .video-grid {
    margin-top: 1.2rem;
  }
}
</style>
