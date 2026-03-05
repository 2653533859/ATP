<template>
  <div class="step-editor">
    <div class="step-toolbar">
      <a-button type="dashed" @click="addStep">
        <PlusOutlined /> 添加步骤
      </a-button>
      <span style="color: #999; font-size: 12px; margin-left: 8px">
        拖拽左侧图标可调整步骤顺序
      </span>
    </div>

    <a-empty v-if="steps.length === 0" description="暂无步骤，请点击上方按钮添加" />

    <draggable
      v-else
      v-model="steps"
      item-key="_key"
      handle=".drag-handle"
      @end="emitUpdate"
    >
      <template #item="{ element: step, index }">
        <a-card size="small" class="step-card" :key="step._key">
          <template #title>
            <div class="step-header">
              <HolderOutlined class="drag-handle" />
              <span class="step-index">#{{ index + 1 }}</span>
              <a-input
                v-model:value="step.name"
                size="small"
                placeholder="步骤名称"
                style="width: 200px"
                @change="emitUpdate"
              />
              <a-select
                v-model:value="step.action"
                size="small"
                style="width: 160px"
                :options="actionOptions"
                @change="() => onActionChange(step)"
              />
              <a-button
                type="text"
                danger
                size="small"
                @click="removeStep(index)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
          </template>

          <!-- goto -->
          <template v-if="step.action === 'goto'">
            <a-form-item label="URL" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.url"
                placeholder="https://example.com  (支持 {{VAR}} 变量)"
                @change="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- click -->
          <template v-else-if="step.action === 'click'">
            <a-form-item label="选择器" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.selector"
                placeholder="CSS 选择器或 Playwright 定位器 (如 text=登录)"
                @change="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- fill -->
          <template v-else-if="step.action === 'fill'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="选择器" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.selector"
                    placeholder="CSS 选择器"
                    @change="emitUpdate"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="输入值" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.value"
                    placeholder="要输入的文本 (支持 {{VAR}})"
                    @change="emitUpdate"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- assert_text -->
          <template v-else-if="step.action === 'assert_text'">
            <a-form-item label="断言文本" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.text"
                placeholder="页面应包含的文本内容"
                @change="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- assert_visible -->
          <template v-else-if="step.action === 'assert_visible'">
            <a-form-item label="选择器" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.selector"
                placeholder="断言该元素可见"
                @change="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- wait -->
          <template v-else-if="step.action === 'wait'">
            <a-form-item label="等待时间" :label-col="{ span: 3 }">
              <a-input-number
                v-model:value="step.params.ms"
                :min="100"
                :max="30000"
                addon-after="ms"
                style="width: 200px"
                @change="emitUpdate"
              />
            </a-form-item>
          </template>

          <!-- screenshot -->
          <template v-else-if="step.action === 'screenshot'">
            <a-alert message="此步骤将截取当前页面截图" type="info" show-icon />
          </template>

          <!-- select -->
          <template v-else-if="step.action === 'select'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="选择器" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.selector"
                    placeholder="<select> 元素选择器"
                    @change="emitUpdate"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="选项值" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.value"
                    placeholder="option 的 value"
                    @change="emitUpdate"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- press -->
          <template v-else-if="step.action === 'press'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="按键" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.key"
                    placeholder="如 Enter、Tab、Escape"
                    @change="emitUpdate"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="目标元素" :label-col="{ span: 6 }">
                  <a-input
                    v-model:value="step.params.selector"
                    placeholder="可选，留空则对整个页面按键"
                    @change="emitUpdate"
                  />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- hover -->
          <template v-else-if="step.action === 'hover'">
            <a-form-item label="选择器" :label-col="{ span: 3 }">
              <a-input
                v-model:value="step.params.selector"
                placeholder="鼠标悬停的目标元素"
                @change="emitUpdate"
              />
            </a-form-item>
          </template>
        </a-card>
      </template>
    </draggable>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { PlusOutlined, DeleteOutlined, HolderOutlined } from '@ant-design/icons-vue'
import draggable from 'vuedraggable'

interface StepDef {
  action: string
  name: string
  params: Record<string, any>
  _key: number
}

const props = defineProps<{
  modelValue: Array<{ action: string; name: string; params: Record<string, any> }>
}>()
const emit = defineEmits<{
  'update:modelValue': [value: Array<{ action: string; name: string; params: Record<string, any> }>]
}>()

let keyCounter = 0

const actionOptions = [
  { label: '跳转 URL', value: 'goto' },
  { label: '点击元素', value: 'click' },
  { label: '输入文本', value: 'fill' },
  { label: '断言文本', value: 'assert_text' },
  { label: '断言可见', value: 'assert_visible' },
  { label: '等待', value: 'wait' },
  { label: '截图', value: 'screenshot' },
  { label: '下拉选择', value: 'select' },
  { label: '键盘按键', value: 'press' },
  { label: '鼠标悬停', value: 'hover' },
]

const defaultParams: Record<string, () => Record<string, any>> = {
  goto: () => ({ url: '' }),
  click: () => ({ selector: '' }),
  fill: () => ({ selector: '', value: '' }),
  assert_text: () => ({ text: '' }),
  assert_visible: () => ({ selector: '' }),
  wait: () => ({ ms: 1000 }),
  screenshot: () => ({}),
  select: () => ({ selector: '', value: '' }),
  press: () => ({ key: 'Enter', selector: '' }),
  hover: () => ({ selector: '' }),
}

function toInternal(items: Array<{ action: string; name: string; params: Record<string, any> }>): StepDef[] {
  return items.map((item) => ({
    ...item,
    params: { ...item.params },
    _key: keyCounter++,
  }))
}

function toExternal(items: StepDef[]): Array<{ action: string; name: string; params: Record<string, any> }> {
  return items.map(({ action, name, params }) => ({ action, name, params }))
}

const steps = ref<StepDef[]>([])

watch(
  () => props.modelValue,
  (val) => {
    steps.value = toInternal(val || [])
  },
  { immediate: true },
)

function emitUpdate() {
  emit('update:modelValue', toExternal(steps.value))
}

function addStep() {
  const action = 'goto'
  steps.value = [
    ...steps.value,
    {
      action,
      name: `步骤 ${steps.value.length + 1}`,
      params: defaultParams[action](),
      _key: keyCounter++,
    },
  ]
  emitUpdate()
}

function removeStep(index: number) {
  steps.value = steps.value.filter((_, i) => i !== index)
  emitUpdate()
}

function onActionChange(step: StepDef) {
  step.params = defaultParams[step.action]?.() ?? {}
  emitUpdate()
}
</script>

<style scoped>
.step-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.step-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}
.step-card {
  margin-bottom: 8px;
}
.step-card :deep(.ant-card-head) {
  min-height: 40px;
  padding: 0 12px;
}
.step-card :deep(.ant-card-head-title) {
  padding: 6px 0;
}
.step-card :deep(.ant-card-body) {
  padding: 8px 12px;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.drag-handle {
  cursor: grab;
  color: #999;
  font-size: 16px;
}
.drag-handle:active {
  cursor: grabbing;
}
.step-index {
  font-weight: 600;
  color: #666;
  min-width: 28px;
}
</style>
