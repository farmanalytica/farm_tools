<script setup>
import ModuleSection from './ModuleSection.vue'

// One stacked section per module: a big featured player plus the module's other
// videos listed small on the side. `groups` is an ordered list of
// { key, label, videos }.
defineProps({
  groups: { type: Array, required: true },
})
</script>

<template>
  <section
    v-for="(group, i) in groups"
    :key="group.key"
    class="module-section"
    :class="{ alt: i % 2 === 1 }"
  >
    <div class="container">
      <div class="module-head">
        <h2>{{ group.label }}</h2>
        <span class="module-count">{{ group.videos.length }}</span>
      </div>
      <ModuleSection :group="group" />
    </div>
  </section>
</template>

<style scoped>
.module-section {
  padding: 3.5rem 0;
}

.module-section.alt {
  background: var(--white);
}

/* Wider so the player + side list breathe. */
.module-section .container {
  width: min(1260px, 95vw);
}

.module-head {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-bottom: 1.6rem;
}

.module-head h2 {
  margin-bottom: 0;
}

.module-count {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--r-full);
  padding: 0.12rem 0.7rem;
}

@media (max-width: 768px) {
  .module-section {
    padding: 2.5rem 0;
  }
}

@media (max-width: 480px) {
  .module-section {
    padding: 1.8rem 0;
  }
}
</style>
