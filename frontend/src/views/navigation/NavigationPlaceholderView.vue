<template>
  <section class="placeholder-page">
    <div class="placeholder-rail" aria-hidden="true"></div>
    <div class="placeholder-content">
      <p class="placeholder-eyebrow">{{ t('navigation.placeholder.eyebrow') }}</p>
      <div class="placeholder-heading">
        <div>
          <h1>{{ t(titleKey) }}</h1>
          <p>{{ t(descriptionKey) }}</p>
        </div>
        <a-tag color="processing">{{ t('navigation.placeholder.planned') }}</a-tag>
      </div>

      <a-alert
        :message="t('navigation.placeholder.status_title')"
        :description="t('navigation.placeholder.status_description')"
        type="info"
        show-icon
      />

      <div class="placeholder-section-heading">
        <div>
          <h2>{{ t('navigation.placeholder.existing_title') }}</h2>
          <p>{{ t('navigation.placeholder.existing_description') }}</p>
        </div>
      </div>
      <div v-if="existingLinks.length" class="placeholder-links">
        <a-button
          v-for="link in existingLinks"
          :key="link.path"
          type="default"
          class="placeholder-link"
          @click="router.push(link.path)"
        >
          {{ t(link.labelKey) }}
          <span aria-hidden="true">→</span>
        </a-button>
      </div>
      <a-empty v-else :description="t('common.no_data')" />

      <p class="placeholder-footer">{{ t('navigation.placeholder.footer') }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

type NavigationLink = {
  path: string
  labelKey: string
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const titleKey = computed(() => String(route.meta.menuTitleKey ?? 'layout.sider_title_full'))
const descriptionKey = computed(() => String(route.meta.descriptionKey ?? 'navigation.placeholder.status_description'))
const existingLinks = computed<NavigationLink[]>(() => {
  const links = route.meta.existingLinks
  return Array.isArray(links) ? links as NavigationLink[] : []
})
</script>

<style scoped>
.placeholder-page {
  position: relative;
  min-height: calc(100vh - 148px);
  overflow: hidden;
  border-radius: var(--radius-lg);
  background: var(--c-bg-elevated);
}

.placeholder-rail {
  position: absolute;
  inset: 0 0 auto;
  height: 156px;
  background:
    radial-gradient(circle at 80% 0%, color-mix(in srgb, var(--c-primary) 18%, transparent), transparent 42%),
    linear-gradient(120deg, color-mix(in srgb, var(--c-primary) 12%, var(--c-bg-elevated)), var(--c-bg-elevated) 68%);
}

.placeholder-content {
  position: relative;
  max-width: 880px;
  margin: 0 auto;
  padding: 52px 44px;
}

.placeholder-eyebrow {
  margin: 0 0 16px;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.placeholder-heading,
.placeholder-section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

h1,
h2 {
  margin: 0;
  color: var(--c-text);
}

h1 {
  font-size: clamp(24px, 3vw, 36px);
  letter-spacing: -0.03em;
}

h2 {
  font-size: 18px;
}

.placeholder-heading p,
.placeholder-section-heading p {
  max-width: 680px;
  margin: 10px 0 0;
  color: var(--c-text-secondary);
  line-height: 1.7;
}

.placeholder-content :deep(.ant-alert) {
  margin: 32px 0 40px;
  border-radius: var(--radius-md);
}

.placeholder-links {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
  margin-top: 20px;
}

.placeholder-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: auto;
  min-height: 48px;
  padding: 12px 16px;
  color: var(--c-text);
  text-align: left;
  border-color: var(--c-border);
  border-radius: var(--radius-md);
}

.placeholder-link:hover {
  color: var(--c-primary);
  border-color: var(--c-primary);
}

.placeholder-footer {
  margin: 44px 0 0;
  color: var(--c-text-tertiary);
  font-size: 13px;
}

@media (max-width: 640px) {
  .placeholder-content {
    padding: 36px 20px;
  }

  .placeholder-heading,
  .placeholder-section-heading {
    display: block;
  }

  .placeholder-heading :deep(.ant-tag) {
    display: inline-block;
    margin-top: 16px;
  }
}
</style>
