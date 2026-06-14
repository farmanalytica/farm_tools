<script setup>
import { computed } from 'vue'
import { useI18n } from '../i18n'

const props = defineProps({
  video: { type: Object, required: true },
  hideWikiLink: { type: Boolean, default: false },
})

const { locale, t } = useI18n()

const title = computed(() => props.video.title[locale.value] || props.video.title['en-US'])
const desc = computed(() => props.video.desc[locale.value] || props.video.desc['en-US'])
const embedUrl = computed(() => {
  if (!props.video.youtubeId) return null
  const start = props.video.start ? `?start=${props.video.start}` : ''
  return `https://www.youtube.com/embed/${props.video.youtubeId}${start}`
})
</script>

<template>
  <article class="card video-card">
    <div class="video-wrap">
      <iframe
        v-if="embedUrl"
        :src="embedUrl"
        :title="title"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen
        loading="lazy"
      ></iframe>
      <div v-else class="video-placeholder">
        <span class="play-badge" aria-hidden="true">▶</span>
        <span>{{ t('tutorials.comingSoon') }}</span>
      </div>
    </div>
    <h3>{{ title }}</h3>
    <p>{{ desc }}</p>
    <router-link v-if="video.wiki && !hideWikiLink" class="card-link" :to="`/wiki/${video.wiki}`">
      → {{ t('tutorials.watchWiki') }}
    </router-link>
  </article>
</template>

<style scoped>
.video-card {
  display: flex;
  flex-direction: column;
}

.video-wrap {
  position: relative;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
  border-radius: var(--r-sm);
  margin-bottom: 1rem;
  background: linear-gradient(135deg, #c8e8db, #aad4c4);
}

.video-wrap iframe {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 0;
}

.video-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  color: var(--primary);
  font-size: 0.86rem;
  font-weight: 600;
}

.play-badge {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  padding-left: 4px;
  box-shadow: var(--sh-sm);
}
</style>
