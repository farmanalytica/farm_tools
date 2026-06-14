<script setup>
import { computed, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from '../i18n'
import { getArticles, getArticle } from '../wiki'
import videos from '../data/videos'
import VideoCard from '../components/VideoCard.vue'

const route = useRoute()
const router = useRouter()
const { locale, t } = useI18n()

const articles = computed(() => getArticles(locale.value))
const article = computed(() => getArticle(locale.value, route.params.slug))
const articleVideos = computed(() => videos.filter((v) => v.wiki === route.params.slug))

const currentIndex = computed(() => articles.value.findIndex((a) => a.slug === route.params.slug))
const prevArticle = computed(() => (currentIndex.value > 0 ? articles.value[currentIndex.value - 1] : null))
const nextArticle = computed(() =>
  currentIndex.value >= 0 && currentIndex.value < articles.value.length - 1
    ? articles.value[currentIndex.value + 1]
    : null
)

watchEffect(() => {
  if (!article.value) router.replace('/wiki/getting-started')
})
</script>

<template>
  <section class="page-head">
    <div class="container">
      <p class="sec-label light">{{ t('wiki.label') }}</p>
      <h1>{{ t('wiki.title') }}</h1>
      <p class="head-lead">{{ t('wiki.lead') }}</p>
    </div>
  </section>

  <section class="wiki-body">
    <div class="container wiki-layout">
      <nav class="wiki-nav" :aria-label="t('wiki.onThisPage')">
        <p class="wiki-nav-label">{{ t('wiki.onThisPage') }}</p>
        <router-link
          v-for="a in articles"
          :key="a.slug"
          :to="`/wiki/${a.slug}`"
          class="wiki-nav-item"
          :class="{ active: a.slug === route.params.slug }"
        >
          <span class="wiki-nav-icon">{{ a.icon }}</span>
          <span>{{ a.title }}</span>
        </router-link>
      </nav>

      <article v-if="article" class="wiki-article">
        <h2 class="wiki-title">{{ article.icon }} {{ article.title }}</h2>
        <p class="wiki-summary">{{ article.summary }}</p>

        <template v-for="(section, i) in article.sections" :key="i">
          <h3 v-if="section.h2">{{ section.h2 }}</h3>
          <p v-else-if="section.p">{{ section.p }}</p>
          <ul v-else-if="section.list">
            <li v-for="(item, j) in section.list" :key="j">{{ item }}</li>
          </ul>
          <ol v-else-if="section.steps">
            <li v-for="(item, j) in section.steps" :key="j">{{ item }}</li>
          </ol>
          <div v-else-if="section.note" class="wiki-note">{{ section.note }}</div>
          <div v-else-if="section.table" class="wiki-table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="(h, j) in section.table.headers" :key="j">{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, j) in section.table.rows" :key="j">
                  <td v-for="(cell, k) in row" :key="k">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <section v-if="articleVideos.length" class="wiki-videos">
          <h3>{{ t('wiki.videos') }}</h3>
          <div class="wiki-video-grid">
            <VideoCard v-for="video in articleVideos" :key="video.id" :video="video" hide-wiki-link />
          </div>
        </section>

        <div class="wiki-pager">
          <router-link v-if="prevArticle" class="pager-link" :to="`/wiki/${prevArticle.slug}`">
            ← {{ t('wiki.prev') }}: {{ prevArticle.title }}
          </router-link>
          <span v-else></span>
          <router-link v-if="nextArticle" class="pager-link next" :to="`/wiki/${nextArticle.slug}`">
            {{ t('wiki.next') }}: {{ nextArticle.title }} →
          </router-link>
        </div>

        <a
          class="wiki-issue"
          href="https://github.com/farmanalytica/farm_tools/issues"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ t('wiki.edit') }}
        </a>
      </article>
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

.wiki-body {
  padding: 3.5rem 0 5rem;
}

.wiki-layout {
  display: grid;
  grid-template-columns: 250px 1fr;
  gap: 2.5rem;
  align-items: start;
}

/* Sidebar */
.wiki-nav {
  position: sticky;
  top: 84px;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 1rem;
  box-shadow: var(--sh-sm);
}

.wiki-nav-label {
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin: 0 0.5rem 0.5rem;
}

.wiki-nav-item {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.45rem 0.6rem;
  border-radius: var(--r-sm);
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text-soft);
  transition: all 0.15s;
}

.wiki-nav-item:hover {
  background: var(--bg);
  color: var(--primary);
}

.wiki-nav-item.active {
  background: var(--accent-soft);
  color: var(--primary);
  font-weight: 600;
}

.wiki-nav-icon {
  font-size: 0.95rem;
}

/* Article */
.wiki-article {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 2.2rem 2.4rem;
  box-shadow: var(--sh-sm);
  min-width: 0;
}

.wiki-title {
  font-family: 'Fraunces', serif;
  font-size: clamp(1.5rem, 2.4vw, 1.9rem);
  font-weight: 700;
  color: var(--text);
  margin-bottom: 0.5rem;
}

.wiki-summary {
  color: var(--text-muted);
  font-size: 0.95rem;
  margin-bottom: 1.8rem;
  padding-bottom: 1.4rem;
  border-bottom: 1px solid var(--border);
}

.wiki-article h3 {
  font-family: 'Fraunces', serif;
  font-size: 1.18rem;
  font-weight: 700;
  color: var(--text);
  margin: 2rem 0 0.7rem;
}

.wiki-article p {
  color: var(--text-soft);
  font-size: 0.94rem;
  line-height: 1.75;
  margin-bottom: 1rem;
}

.wiki-article ul,
.wiki-article ol {
  margin: 0 0 1.2rem 1.3rem;
  display: grid;
  gap: 0.45rem;
}

.wiki-article li {
  color: var(--text-soft);
  font-size: 0.94rem;
  line-height: 1.65;
}

.wiki-note {
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
  border-radius: var(--r-sm);
  padding: 0.9rem 1.1rem;
  font-size: 0.89rem;
  color: #0a2e1f;
  line-height: 1.65;
  margin: 0 0 1.2rem;
}

.wiki-table-wrap {
  overflow-x: auto;
  margin: 0 0 1.4rem;
}

.wiki-table-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.wiki-table-wrap th,
.wiki-table-wrap td {
  text-align: left;
  padding: 0.6rem 0.8rem;
  border: 1px solid var(--border);
  color: var(--text-soft);
  line-height: 1.55;
  vertical-align: top;
}

.wiki-table-wrap th {
  background: var(--bg);
  color: var(--text);
  font-weight: 600;
}

/* Videos */
.wiki-videos {
  margin-top: 2.4rem;
  padding-top: 1.6rem;
  border-top: 1px solid var(--border);
}

.wiki-videos h3 {
  margin-top: 0;
}

.wiki-video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.4rem;
  margin-top: 1rem;
}

/* Pager */
.wiki-pager {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 2.4rem;
  padding-top: 1.4rem;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}

.pager-link {
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--accent);
}

.pager-link:hover {
  text-decoration: underline;
}

.pager-link.next {
  margin-left: auto;
  text-align: right;
}

.wiki-issue {
  display: inline-block;
  margin-top: 1.6rem;
  font-size: 0.82rem;
  color: var(--text-muted);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.wiki-issue:hover {
  color: var(--accent);
}

@media (max-width: 900px) {
  .wiki-layout {
    grid-template-columns: 1fr;
  }

  .wiki-nav {
    position: static;
  }

  .wiki-article {
    padding: 1.6rem 1.4rem;
  }
}

@media (max-width: 768px) {
  .page-head {
    padding: 3rem 0 2.5rem;
  }

  .head-lead {
    font-size: 0.98rem;
  }

  .wiki-body {
    padding: 2.5rem 0 3rem;
  }

  .wiki-layout {
    gap: 1.5rem;
  }

  .wiki-nav {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .wiki-nav-label {
    width: 100%;
    margin: 0 0 0.5rem;
  }

  .wiki-nav-item {
    font-size: 0.8rem;
    padding: 0.35rem 0.5rem;
  }

  .wiki-article {
    padding: 1.5rem 1.2rem;
  }

  .wiki-title {
    font-size: clamp(1.3rem, 2.4vw, 1.7rem);
  }

  .wiki-article h3 {
    font-size: 1.05rem;
    margin: 1.6rem 0 0.6rem;
  }

  .wiki-article p {
    font-size: 0.9rem;
  }

  .wiki-article ul,
  .wiki-article ol {
    margin: 0 0 1rem 1.1rem;
  }

  .wiki-article li {
    font-size: 0.9rem;
  }

  .pager-link.next {
    margin-left: 0;
  }
}

@media (max-width: 480px) {
  .page-head {
    padding: 2rem 0 1.5rem;
  }

  .head-lead {
    font-size: 0.93rem;
  }

  .wiki-body {
    padding: 2rem 0 2.5rem;
  }

  .wiki-layout {
    gap: 1rem;
  }

  .wiki-nav {
    flex-direction: column;
    gap: 0.3rem;
  }

  .wiki-nav-label {
    width: auto;
    margin-bottom: 0.3rem;
    font-size: 0.65rem;
  }

  .wiki-nav-item {
    font-size: 0.78rem;
    padding: 0.4rem 0.5rem;
  }

  .wiki-article {
    padding: 1.2rem 1rem;
  }

  .wiki-title {
    font-size: clamp(1.1rem, 2.4vw, 1.5rem);
  }

  .wiki-article h3 {
    font-size: 0.95rem;
    margin: 1.4rem 0 0.5rem;
  }

  .wiki-article p {
    font-size: 0.85rem;
  }

  .wiki-article ul,
  .wiki-article ol {
    margin: 0 0 0.8rem 1rem;
  }

  .wiki-article li {
    font-size: 0.85rem;
  }

  .wiki-summary {
    font-size: 0.9rem;
    margin-bottom: 1.4rem;
  }

  .wiki-note {
    padding: 0.8rem 1rem;
    font-size: 0.82rem;
  }

  .wiki-table-wrap table {
    font-size: 0.8rem;
  }

  .wiki-table-wrap th,
  .wiki-table-wrap td {
    padding: 0.4rem 0.6rem;
  }

  .wiki-pager {
    gap: 0.5rem;
    margin-top: 1.8rem;
    padding-top: 1.2rem;
  }

  .pager-link {
    font-size: 0.78rem;
  }

  .wiki-issue {
    font-size: 0.75rem;
  }
}
</style>
