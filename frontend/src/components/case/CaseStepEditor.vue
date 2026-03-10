<template>
  <div class="case-step-editor">
    <div class="toolbar">
      <a-button type="dashed" @click="addStep">新增步骤</a-button>
      <span class="hint">按业务步骤维护动作、数据和预期结果。</span>
    </div>

    <a-empty v-if="rows.length === 0" description="暂无标准步骤" />

    <a-card v-for="(step, index) in rows" :key="step.step_no ?? index" size="small" class="step-card">
      <template #title>
        <div class="step-title">
          <span>步骤 {{ index + 1 }}</span>
          <a-space>
            <a-button size="small" :disabled="index === 0" @click="moveStep(index, -1)">上移</a-button>
            <a-button size="small" :disabled="index === rows.length - 1" @click="moveStep(index, 1)">下移</a-button>
            <a-button size="small" danger @click="removeStep(index)">删除</a-button>
          </a-space>
        </div>
      </template>

      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="14">
            <a-form-item label="动作">
              <a-input v-model:value="step.action" placeholder="例如：打开登录页 / 发送登录请求" />
            </a-form-item>
          </a-col>
          <a-col :span="10">
            <a-form-item label="关键步骤">
              <a-switch v-model:checked="step.is_key_step" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="测试数据">
          <a-textarea v-model:value="step.test_data" :rows="2" placeholder="输入参数、前置数据或关键请求体" />
        </a-form-item>

        <a-form-item label="预期结果">
          <a-textarea v-model:value="step.expected_result" :rows="2" placeholder="例如：返回 200，页面展示欢迎信息" />
        </a-form-item>

        <a-form-item label="备注">
          <a-textarea v-model:value="step.remarks" :rows="2" placeholder="可选" />
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { CaseStepItem } from '@/api'

const props = defineProps<{
  modelValue: CaseStepItem[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: CaseStepItem[]]
}>()

const rows = ref<CaseStepItem[]>([])
const syncingFromProps = ref(false)

function normalize(items: CaseStepItem[]): CaseStepItem[] {
  return items.map((item, index) => ({
    ...item,
    step_no: index + 1,
    action: item.action ?? '',
    test_data: item.test_data ?? '',
    expected_result: item.expected_result ?? '',
    remarks: item.remarks ?? '',
    is_key_step: Boolean(item.is_key_step),
  }))
}

function syncFromProps() {
  syncingFromProps.value = true
  rows.value = normalize(props.modelValue ?? [])
  void nextTick(() => {
    syncingFromProps.value = false
  })
}

function emitUpdate() {
  emit('update:modelValue', normalize(rows.value))
}

function addStep() {
  rows.value = [
    ...rows.value,
    {
      step_no: rows.value.length + 1,
      action: '',
      test_data: '',
      expected_result: '',
      remarks: '',
      is_key_step: rows.value.length === 0,
    },
  ]
  emitUpdate()
}

function removeStep(index: number) {
  rows.value = rows.value.filter((_, currentIndex) => currentIndex !== index)
  emitUpdate()
}

function moveStep(index: number, offset: number) {
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= rows.value.length) {
    return
  }
  const next = [...rows.value]
  const [item] = next.splice(index, 1)
  next.splice(targetIndex, 0, item)
  rows.value = next
  emitUpdate()
}

watch(
  () => props.modelValue,
  () => {
    syncFromProps()
  },
  { immediate: true, deep: true },
)

watch(
  rows,
  () => {
    if (syncingFromProps.value) {
      return
    }
    emitUpdate()
  },
  { deep: true },
)
</script>

<style scoped>
.case-step-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hint {
  color: #888;
  font-size: 12px;
}

.step-card {
  border-radius: 10px;
}

.step-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
