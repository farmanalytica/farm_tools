<script setup>
import { useI18n } from '../i18n'

const { t } = useI18n()

const MODULES = [
  { key: 'optical', icon: '🌿', wiki: 'optical' },
  { key: 'landsat', icon: '🛰️', wiki: 'landsat' },
  { key: 'sar', icon: '📡', wiki: 'sar' },
  { key: 'dem', icon: '⛰️', wiki: 'dem' },
  { key: 'sysi', icon: '🟤', wiki: 'sysi' },
  { key: 'climaplots', icon: '🌦️', wiki: 'climaplots' },
  { key: 'fieldguide', icon: '📍', wiki: 'fieldguide' },
  { key: 'mapbiomas', icon: '🗺️', wiki: 'mapbiomas' },
]
</script>

<template>
  <section class="hero-section">
    <div class="container hero">
      <div>
        <div class="hero-tag">{{ t('hero.tag') }}</div>
        <h1>{{ t('hero.title') }}</h1>
        <p class="hero-desc">{{ t('hero.description') }}</p>
        <div class="cta-row">
          <router-link class="btn btn-white" to="/tutorials">{{ t('hero.ctaTutorials') }}</router-link>
          <router-link class="btn btn-ghost" to="/wiki/getting-started">{{ t('hero.ctaWiki') }}</router-link>
          <a
            class="btn btn-ghost"
            href="https://github.com/farmanalytica/farm_tools"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ t('hero.ctaGithub') }}
          </a>
        </div>
      </div>
      <aside class="hero-card" aria-hidden="true">
        <div class="hero-card-head">
          <strong>{{ t('hero.previewTitle') }}</strong>
          <p>{{ t('hero.previewSubtitle') }}</p>
        </div>
        <div class="hero-card-body">
          <strong>{{ t('hero.previewLabel') }}</strong>
          <div v-for="(item, i) in t('hero.previewItems')" :key="i" class="hero-item">{{ item }}</div>
        </div>
      </aside>
    </div>
  </section>

  <section>
    <div class="container">
      <p class="sec-label">{{ t('intro.label') }}</p>
      <h2>{{ t('intro.title') }}</h2>
      <p class="sec-lead">{{ t('intro.lead') }}</p>
      <div class="video-wrap">
        <iframe
          src="https://www.youtube.com/embed/ju4jlqBOt4k?start=2"
          title="FARM tools introduction"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen
          loading="lazy"
        ></iframe>
      </div>
    </div>
  </section>

  <section id="features" class="alt">
    <div class="container">
      <p class="sec-label">{{ t('modules.label') }}</p>
      <h2>{{ t('modules.title') }}</h2>
      <p class="sec-lead">{{ t('modules.lead') }}</p>
      <div class="grid3">
        <article v-for="m in MODULES" :key="m.key" class="card">
          <div class="card-icon">{{ m.icon }}</div>
          <h3>{{ t(`modules.items.${m.key}.title`) }}</h3>
          <p>{{ t(`modules.items.${m.key}.desc`) }}</p>
          <router-link class="card-link" :to="`/wiki/${m.wiki}`">→ {{ t('modules.wikiLink') }}</router-link>
        </article>
      </div>
    </div>
  </section>

  <section id="how-it-works">
    <div class="container">
      <p class="sec-label">{{ t('how.label') }}</p>
      <h2>{{ t('how.title') }}</h2>
      <p class="sec-lead">{{ t('how.lead') }}</p>
      <div class="steps-col">
        <div v-for="(step, i) in t('how.steps')" :key="i" class="step">
          <div class="step-num">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="step-body">
            <h3>{{ step.title }}</h3>
            <p>{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section id="setup" class="alt">
    <div class="container">
      <p class="sec-label">{{ t('setup.label') }}</p>
      <h2>{{ t('setup.title') }}</h2>
      <p class="sec-lead">{{ t('setup.lead') }}</p>
      <div class="steps-col">
        <div v-for="(step, i) in t('setup.steps')" :key="i" class="step">
          <div class="step-num">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="step-body">
            <h3>{{ step.title }}</h3>
            <p>{{ step.desc }}</p>
            <a
              v-if="step.href"
              class="step-link"
              :href="step.href"
              target="_blank"
              rel="noopener noreferrer"
            >
              → {{ step.link }}
            </a>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section id="resources">
    <div class="container">
      <p class="sec-label">{{ t('resources.label') }}</p>
      <h2>{{ t('resources.title') }}</h2>
      <p class="sec-lead">{{ t('resources.lead') }}</p>
      <div class="grid3">
        <article class="card">
          <div class="card-icon">💻</div>
          <h3>{{ t('resources.repo.title') }}</h3>
          <p>{{ t('resources.repo.desc') }}</p>
          <a
            class="card-link"
            href="https://github.com/farmanalytica/farm_tools"
            target="_blank"
            rel="noopener noreferrer"
          >
            → {{ t('resources.repo.link') }}
          </a>
        </article>
        <article class="card">
          <div class="card-icon">💬</div>
          <h3>{{ t('resources.issues.title') }}</h3>
          <p>{{ t('resources.issues.desc') }}</p>
          <a
            class="card-link"
            href="https://github.com/farmanalytica/farm_tools/issues"
            target="_blank"
            rel="noopener noreferrer"
          >
            → {{ t('resources.issues.link') }}
          </a>
        </article>
        <article class="card">
          <div class="card-icon">📜</div>
          <h3>{{ t('resources.license.title') }}</h3>
          <p>{{ t('resources.license.desc') }}</p>
          <a
            class="card-link"
            href="https://github.com/farmanalytica/farm_tools/blob/main/LICENSE"
            target="_blank"
            rel="noopener noreferrer"
          >
            → {{ t('resources.license.link') }}
          </a>
        </article>
      </div>
    </div>
  </section>

  <section class="alt">
    <div class="container">
      <p class="sec-label">{{ t('about.label') }}</p>
      <h2>{{ t('about.title') }}</h2>
      <div class="about-box">
        <p>
          {{ t('about.textPre') }}<a
            class="about-link"
            href="https://www.linkedin.com/in/caioarantes/"
            target="_blank"
            rel="noopener noreferrer"
          >Caio Arantes</a>{{ t('about.textMid') }}<a
            class="about-link"
            href="https://www.linkedin.com/in/lucas-rios-do-amaral-bb302449/"
            target="_blank"
            rel="noopener noreferrer"
          >Prof. Dr. Lucas dos Rios Amaral</a>{{ t('about.textPost') }}
        </p>
        <div class="partner-row">
          <img class="partner-logo" src="/farm_icon.png" alt="FARM Analytica logo" />
          <div class="partner-info">
            <span class="partner-tag">{{ t('about.sponsorLabel') }}</span>
            <strong class="partner-name">FARM Analytica</strong>
            <p>{{ t('about.sponsorDesc') }}</p>
            <div class="chips">
              <a
                class="chip chip-green"
                href="https://api.whatsapp.com/send/?phone=5519992741032&text=Ol%C3%A1!+Preciso+de+mais+informa%C3%A7%C3%B5es&type=phone_number&app_absent=0"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ t('about.whatsapp') }}
              </a>
              <a class="chip" href="mailto:contato@farmanalytica.com.br">contato@farmanalytica.com.br</a>
            </div>
            <a
              class="partner-cta"
              href="https://farmanalytica.com.br"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ t('about.sponsorCta') }}
            </a>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero-section {
  background: var(--primary);
  padding: 5.5rem 0 5rem;
}

@media (max-width: 768px) {
  .hero-section {
    padding: 3.5rem 0 3rem;
  }
}

@media (max-width: 480px) {
  .hero-section {
    padding: 2rem 0 2.5rem;
  }
}

.hero {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 3.5rem;
  align-items: center;
}

.hero-tag {
  display: inline-flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: rgba(255, 255, 255, 0.88);
  padding: 0.33rem 0.85rem;
  border-radius: var(--r-full);
  font-size: 0.79rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  margin-bottom: 1.3rem;
}

.hero-desc {
  color: rgba(255, 255, 255, 0.72);
  font-size: 1.04rem;
  max-width: 46ch;
  margin-bottom: 2.2rem;
  line-height: 1.75;
}

.cta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

@media (max-width: 480px) {
  .cta-row {
    flex-direction: column;
    gap: 0.6rem;
  }

  .cta-row .btn {
    width: 100%;
    justify-content: center;
  }
}

.hero-card {
  background: var(--white);
  border-radius: 20px;
  padding: 1.4rem;
  box-shadow: var(--sh-lg);
}

.hero-card-head {
  background: linear-gradient(135deg, #c8e8db, #aad4c4);
  border-radius: 12px;
  padding: 1.4rem 1.6rem;
  text-align: center;
  margin-bottom: 1.2rem;
}

.hero-card-head strong {
  display: block;
  font-family: 'Fraunces', serif;
  font-size: 1.12rem;
  color: var(--primary);
  margin-bottom: 0.25rem;
}

.hero-card-head p {
  color: var(--accent);
  font-size: 0.87rem;
  margin: 0;
}

.hero-card-body strong {
  display: block;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin-bottom: 0.7rem;
}

.hero-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  font-size: 0.9rem;
  color: var(--text-soft);
  padding: 0.3rem 0;
}

.hero-item::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}

.video-wrap {
  position: relative;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
  border-radius: var(--r);
  box-shadow: var(--sh-md);
  max-width: 800px;
}

.video-wrap iframe {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 0;
}

.about-box {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 2rem;
  box-shadow: var(--sh-sm);
}

@media (max-width: 768px) {
  .about-box {
    padding: 1.5rem;
  }
}

@media (max-width: 480px) {
  .about-box {
    padding: 1rem;
  }
}

.about-box > p:first-of-type {
  color: var(--text-soft);
  line-height: 1.7;
  margin-bottom: 1.5rem;
}

.about-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.partner-row {
  display: flex;
  align-items: flex-start;
  gap: 1.1rem;
  padding: 1.2rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-bottom: 1.2rem;
}

@media (max-width: 768px) {
  .partner-row {
    flex-direction: column;
    align-items: center;
    padding: 1rem;
  }

  .partner-logo {
    width: 64px;
    height: 64px;
  }

  .partner-info {
    align-items: center;
    text-align: center;
  }
}

@media (max-width: 480px) {
  .partner-row {
    padding: 1rem;
  }

  .partner-logo {
    width: 56px;
    height: 56px;
  }

  .partner-tag {
    font-size: 0.68rem;
  }

  .partner-name {
    font-size: 0.95rem;
  }

  .partner-info p {
    font-size: 0.82rem;
  }

  .partner-cta {
    font-size: 0.8rem;
  }
}

.partner-logo {
  width: 68px;
  height: 68px;
  border-radius: 12px;
  object-fit: contain;
  background: var(--white);
  padding: 0.4rem;
  box-shadow: var(--sh-sm);
  flex-shrink: 0;
}

.partner-info {
  display: grid;
  gap: 0.28rem;
}

.partner-tag {
  font-size: 0.74rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--accent);
  font-weight: 700;
}

.partner-name {
  font-family: 'Fraunces', serif;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
}

.partner-info p {
  color: var(--text-soft);
  font-size: 0.88rem;
  line-height: 1.5;
}

.partner-cta {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 3px;
  margin-top: 0.1rem;
  display: inline-block;
}

@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .hero-card {
    display: none;
  }
}
</style>
