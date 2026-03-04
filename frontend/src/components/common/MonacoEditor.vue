<template>
  <div ref="el" :style="{ height, width: '100%', border: '1px solid #d9d9d9', borderRadius: '4px', overflow: 'hidden' }" />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import loader from '@monaco-editor/loader'

const props = withDefaults(defineProps<{
  modelValue?: string
  language?: string
  height?: string
  readOnly?: boolean
}>(), {
  modelValue: '',
  language: 'python',
  height: '400px',
  readOnly: false,
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const el = ref<HTMLElement>()
let editor: any = null

onMounted(async () => {
  const monaco = await loader.init()
  editor = monaco.editor.create(el.value!, {
    value: props.modelValue,
    language: props.language,
    theme: 'vs',
    readOnly: props.readOnly,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    fontSize: 13,
    tabSize: 4,
    automaticLayout: true,
    lineNumbers: 'on',
    renderLineHighlight: 'line',
  })
  editor.onDidChangeModelContent(() => {
    emit('update:modelValue', editor.getValue())
  })
})

watch(() => props.modelValue, (v) => {
  if (editor && editor.getValue() !== v) {
    editor.setValue(v ?? '')
  }
})

onBeforeUnmount(() => {
  editor?.dispose()
})
</script>
