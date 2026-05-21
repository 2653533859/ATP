<template>
  <a-card :title="title">
    <div ref="container" :style="{ minHeight: minHeight + 'px' }">
      <slot v-if="visible" />
      <div v-else style="display: flex; align-items: center; justify-content: center; height: 320px">
        <a-spin />
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    title: string
    minHeight?: number
  }>(),
  { minHeight: 360 },
)

const emit = defineEmits<{ visible: [] }>()

const visible = ref(false)
const container = ref<HTMLElement>()
let observer: IntersectionObserver | null = null

void props // ensure compiler treats props as read; minHeight is consumed in template

onMounted(() => {
  if (!container.value) return
  if (typeof IntersectionObserver === 'undefined') {
    visible.value = true
    emit('visible')
    return
  }
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && !visible.value) {
        visible.value = true
        emit('visible')
        observer?.disconnect()
        observer = null
      }
    },
    { threshold: 0.1 },
  )
  observer.observe(container.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})
</script>
