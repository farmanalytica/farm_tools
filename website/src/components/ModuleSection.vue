<script setup>
import { computed, ref } from 'vue'
import { useI18n } from '../i18n'

// One module: a big featured player on the left and the module's other videos
// listed small on the right. Selection is local to this section.
const props = defineProps({
  group: { type: Object, required: true },
})

const { locale, t } = useI18n()

const localized = (field) => field[locale.value] || field['en-US'] || ''

const selectedId = ref(props.group.videos[0]?.id ?? null)
const playing = ref(false)

const selected = computed(
  () => props.group.videos.find((v) => v.id === selectedId.value) || props.group.videos[0]
)

const bigThumb = (video) =>
  video.youtubeId ? `https://i.ytimg.com/vi/${video.youtubeId}/hqdefault.jpg` : null
const smallThumb = (video) =>
  video.youtubeId ? `https://i.ytimg.com/vi/${video.youtubeId}/mqdefault.jpg` : null

const embedUrl = computed(() => {
  const v = selected.value
  if (!v || !v.youtubeId) return null
  const params = new URLSearchParams({
    rel: '0',
    modestbranding: '1',
    autoplay: '1',
  })
  if (v.start) params.set('start', String(v.start))
  return `https://www.youtube.com/embed/${v.youtubeId}?${params.toString()}`
})

const duration = (video) => {
  const m = localized(video.desc).match(/~\s*(\d+)\s*min/i)
  return m ? `${m[1]} min` : null
}

function pick(video) {
  selectedId.value = video.id
  playing.value = !!video.youtubeId
}

function playBig() {
  if (selected.value?.youtubeId) playing.value = true
}
</script>

<template>
  <div class="module">
    <!-- Featured player -->
    <div class="feature">
      <div class="player">
        <iframe
          v-if="playing && embedUrl"
          :key="selectedId"
          :src="embedUrl"
          :title="localized(selected.title)"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen
        ></iframe>

        <button
          v-else-if="selected && selected.youtubeId"
          type="button"
          class="facade"
          :style="{ backgroundImage: `url(${bigThumb(selected)})` }"
          :aria-label="localized(selected.title)"
          @click="playBig"
        >
          <span class="play-badge" aria-hidden="true">▶</span>
        </button>

        <div v-else class="facade soon">
          <span class="play-badge" aria-hidden="true">▶</span>
          <span>{{ t('tutorials.comingSoon') }}</span>
        </div>
      </div>

      <div class="feature-meta" v-if="selected">
        <h3>{{ localized(selected.title) }}</h3>
        <p class="feature-desc">{{ localized(selected.desc) }}</p>
        <div class="feature-foot">
          <span v-if="duration(selected)" class="dur">{{ duration(selected) }}</span>
          <router-link
            v-if="selected.wiki"
            class="card-link"
            :to="`/wiki/${selected.wiki}`"
          >
            → {{ t('tutorials.watchWiki') }}
          </router-link>
        </div>
      </div>
    </div>

    <!-- Side list -->
    <aside class="side">
      <p class="side-head">{{ group.videos.length }} {{ t('tutorials.playlist') }}</p>
      <ul>
        <li v-for="(video, idx) in group.videos" :key="video.id">
          <button
            type="button"
            class="row"
            :class="{ active: video.id === selectedId, soon: !video.youtubeId }"
            @click="pick(video)"
          >
            <span class="row-index" aria-hidden="true">
              <span v-if="video.id === selectedId" class="bars"><i></i><i></i><i></i></span>
              <span v-else>{{ idx + 1 }}</span>
            </span>
            <span class="thumb">
              <img v-if="smallThumb(video)" :src="smallThumb(video)" alt="" loading="lazy" />
              <span v-else class="thumb-soon" aria-hidden="true">▶</span>
              <span v-if="duration(video)" class="thumb-dur">{{ duration(video) }}</span>
            </span>
            <span class="row-body">
              <span class="row-title">{{ localized(video.title) }}</span>
              <span v-if="video.id === selectedId" class="now-playing">
                <span class="dot" aria-hidden="true"></span>{{ t('tutorials.nowPlaying') }}
              </span>
              <span v-else-if="!video.youtubeId" class="soon-tag">{{ t('tutorials.comingSoon') }}</span>
              <span v-else class="row-snippet">{{ localized(video.desc) }}</span>
            </span>
          </button>
        </li>
      </ul>
    </aside>
  </div>
</template>

<style scoped>
.module {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 2rem;
  align-items: start;
}

/* ── Featured player ─────────────────────────────────── */
.player {
  position: relative;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
  border-radius: var(--r);
  background: #0a0f0d;
  box-shadow: var(--sh-lg);
}

.player iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
}

.facade {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: none;
  cursor: pointer;
  background-size: cover;
  background-position: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.7rem;
  transition: filter 0.18s;
}

.facade:hover {
  filter: brightness(1.05);
}

.facade.soon {
  cursor: default;
  background: linear-gradient(135deg, #16302a, #0f3d2e);
  color: rgba(255, 255, 255, 0.82);
  font-size: 0.92rem;
  font-weight: 600;
}

.play-badge {
  width: 62px;
  height: 62px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.92);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.35rem;
  padding-left: 5px;
  box-shadow: var(--sh-md);
  transition: transform 0.18s;
}

.facade:hover .play-badge {
  transform: scale(1.08);
}

.feature-meta {
  margin-top: 1.3rem;
}

.feature-meta h3 {
  font-family: 'Fraunces', serif;
  font-size: 1.3rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.55rem;
  line-height: 1.3;
}

.feature-desc {
  color: var(--text-soft);
  font-size: 0.98rem;
  line-height: 1.72;
  max-width: 68ch;
}

.feature-foot {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.9rem;
}

.feature-foot .card-link {
  margin: 0;
}

.dur {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-muted);
}

/* ── Side list ───────────────────────────────────────── */
.side {
  max-height: 62vh;
  overflow-y: auto;
  scrollbar-width: thin;
}

.side-head {
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 0.2rem 0.5rem 0.6rem;
}

.side ul {
  list-style: none;
}

.row {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--r-sm);
  font-family: inherit;
  transition: background 0.15s;
}

.row-index {
  flex-shrink: 0;
  width: 16px;
  padding-top: 0.35rem;
  text-align: center;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
}

.bars {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  height: 12px;
}

.bars i {
  width: 2px;
  background: var(--accent);
  animation: eq 0.9s ease-in-out infinite;
}

.bars i:nth-child(1) {
  height: 40%;
  animation-delay: -0.2s;
}

.bars i:nth-child(2) {
  height: 100%;
  animation-delay: -0.5s;
}

.bars i:nth-child(3) {
  height: 65%;
}

@keyframes eq {
  0%,
  100% {
    transform: scaleY(0.4);
  }
  50% {
    transform: scaleY(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .bars i {
    animation: none;
  }
}

.row:hover {
  background: var(--bg);
}

.row.active {
  background: var(--accent-soft);
}

.thumb {
  position: relative;
  flex-shrink: 0;
  width: 104px;
  height: 59px;
  border-radius: 6px;
  overflow: hidden;
  background: linear-gradient(135deg, #16302a, #0f3d2e);
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-soon {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.85rem;
}

.thumb-dur {
  position: absolute;
  right: 4px;
  bottom: 4px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  font-size: 0.68rem;
  font-weight: 600;
  line-height: 1;
  padding: 0.14rem 0.32rem;
  border-radius: 3px;
}

.row.active .thumb {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.row-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
  padding-top: 0.05rem;
}

.row-title {
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text);
  line-height: 1.34;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.row.active .row-title {
  font-weight: 600;
  color: #0a2e1f;
}

.row-snippet {
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.now-playing {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.74rem;
  font-weight: 700;
  color: var(--accent);
}

.now-playing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .now-playing .dot {
    animation: none;
  }
}

.soon-tag {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg);
  border-radius: var(--r-full);
  padding: 0.08rem 0.5rem;
}

.row.soon .row-title {
  color: var(--text-soft);
}

/* ── Responsive ──────────────────────────────────────── */
@media (max-width: 960px) {
  .module {
    grid-template-columns: 1fr;
    gap: 1.4rem;
  }

  .side {
    max-height: none;
  }

  .side ul {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 0.3rem;
  }
}

@media (max-width: 480px) {
  .feature-meta h3 {
    font-size: 1.12rem;
  }

  .feature-desc {
    font-size: 0.92rem;
  }
}
</style>
