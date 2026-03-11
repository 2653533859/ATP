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
                @input="emitUpdate"
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

          <!-- click -->
          <template v-if="step.action === 'click'">
            <a-row :gutter="12">
              <a-col :span="8">
                <a-form-item label="文本" :label-col="{ span: 8 }">
                  <a-input v-model:value="step.params.text" placeholder="按钮文本" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="资源ID" :label-col="{ span: 8 }">
                  <a-input v-model:value="step.params.resourceId" placeholder="com.app:id/btn" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="X" :label-col="{ span: 8 }">
                  <a-input-number v-model:value="step.params.x" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="Y" :label-col="{ span: 8 }">
                  <a-input-number v-model:value="step.params.y" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- long_click -->
          <template v-else-if="step.action === 'long_click'">
            <a-row :gutter="12">
              <a-col :span="6">
                <a-form-item label="X" :label-col="{ span: 6 }">
                  <a-input-number v-model:value="step.params.x" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="Y" :label-col="{ span: 6 }">
                  <a-input-number v-model:value="step.params.y" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="6">
                <a-form-item label="时长(ms)" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.duration" :min="300" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- swipe -->
          <template v-else-if="step.action === 'swipe'">
            <a-row :gutter="12">
              <a-col :span="8">
                <a-form-item label="方向" :label-col="{ span: 8 }">
                  <a-select v-model:value="step.params.direction" allow-clear placeholder="或用坐标" @change="emitUpdate">
                    <a-select-option value="up">上滑</a-select-option>
                    <a-select-option value="down">下滑</a-select-option>
                    <a-select-option value="left">左滑</a-select-option>
                    <a-select-option value="right">右滑</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="起X" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.x1" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="起Y" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.y1" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="终X" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.x2" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="终Y" :label-col="{ span: 10 }">
                  <a-input-number v-model:value="step.params.y2" style="width:100%" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- input -->
          <template v-else-if="step.action === 'input'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="输入内容" :label-col="{ span: 6 }">
                  <a-input v-model:value="step.params.text" placeholder="要输入的文本" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="资源ID" :label-col="{ span: 8 }">
                  <a-input v-model:value="step.params.resourceId" placeholder="目标输入框（可选）" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="4">
                <a-form-item label="清空" :label-col="{ span: 10 }">
                  <a-switch v-model:checked="step.params.clear" size="small" @change="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- press_key -->
          <template v-else-if="step.action === 'press_key'">
            <a-form-item label="按键" :label-col="{ span: 3 }">
              <a-select v-model:value="step.params.key" style="width: 200px" @change="emitUpdate">
                <a-select-option value="HOME">HOME</a-select-option>
                <a-select-option value="BACK">BACK</a-select-option>
                <a-select-option value="ENTER">ENTER</a-select-option>
                <a-select-option value="MENU">MENU</a-select-option>
                <a-select-option value="RECENT">RECENT</a-select-option>
                <a-select-option value="DELETE">DELETE</a-select-option>
                <a-select-option value="POWER">POWER</a-select-option>
                <a-select-option value="VOLUME_UP">音量+</a-select-option>
                <a-select-option value="VOLUME_DOWN">音量-</a-select-option>
              </a-select>
            </a-form-item>
          </template>

          <!-- start_app -->
          <template v-else-if="step.action === 'start_app'">
            <a-row :gutter="12">
              <a-col :span="12">
                <a-form-item label="包名" :label-col="{ span: 6 }">
                  <a-input v-model:value="step.params.package" placeholder="com.example.app" @input="emitUpdate" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="Activity" :label-col="{ span: 6 }">
                  <a-input v-model:value="step.params.activity" placeholder="可选，如 .MainActivity" @input="emitUpdate" />
                </a-form-item>
              </a-col>
            </a-row>
          </template>

          <!-- stop_app -->
          <template v-else-if="step.action === 'stop_app'">
            <a-form-item label="包名" :label-col="{ span: 3 }">
              <a-input v-model:value="step.params.package" placeholder="com.example.app" @input="emitUpdate" />
            </a-form-item>
          </template>

          <!-- assert_text -->
          <template v-else-if="step.action === 'assert_text'">
            <a-form-item label="预期文本" :label-col="{ span: 3 }">
              <a-input v-model:value="step.params.text" placeholder="页面中应包含的文本" @input="emitUpdate" />
            </a-form-item>
          </template>

          <!-- assert_element -->
          <template v-else-if="step.action === 'assert_element'">
            <a-form-item label="资源ID" :label-col="{ span: 3 }">
              <a-input v-model:value="step.params.resourceId" placeholder="com.app:id/element" @input="emitUpdate" />
            </a-form-item>
          </template>

          <!-- wait -->
          <template v-else-if="step.action === 'wait'">
            <a-form-item label="等待时间(ms)" :label-col="{ span: 4 }">
              <a-input-number v-model:value="step.params.ms" :min="100" :step="500" style="width: 200px" @change="emitUpdate" />
            </a-form-item>
          </template>

          <!-- screenshot: 无额外参数 -->
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
  { label: '点击', value: 'click' },
  { label: '长按', value: 'long_click' },
  { label: '滑动', value: 'swipe' },
  { label: '输入文本', value: 'input' },
  { label: '按键', value: 'press_key' },
  { label: '启动应用', value: 'start_app' },
  { label: '停止应用', value: 'stop_app' },
  { label: '断言文本', value: 'assert_text' },
  { label: '断言元素', value: 'assert_element' },
  { label: '等待', value: 'wait' },
  { label: '截图', value: 'screenshot' },
]

const defaultParams: Record<string, () => Record<string, any>> = {
  click: () => ({ text: '', resourceId: '', x: undefined, y: undefined }),
  long_click: () => ({ x: undefined, y: undefined, duration: 1000 }),
  swipe: () => ({ direction: 'up', x1: undefined, y1: undefined, x2: undefined, y2: undefined }),
  input: () => ({ text: '', resourceId: '', clear: false }),
  press_key: () => ({ key: 'BACK' }),
  start_app: () => ({ package: '', activity: '' }),
  stop_app: () => ({ package: '' }),
  assert_text: () => ({ text: '' }),
  assert_element: () => ({ resourceId: '' }),
  wait: () => ({ ms: 1000 }),
  screenshot: () => ({}),
}

function toInternal(items: Array<{ action: string; name: string; params: Record<string, any> }>): StepDef[] {
  const keyPool = new Map<string, number[]>()

  for (const step of steps.value) {
    const signature = JSON.stringify(toExternal([step])[0])
    const keys = keyPool.get(signature) ?? []
    keys.push(step._key)
    keyPool.set(signature, keys)
  }

  return items.map((item) => {
    const params = { ...item.params }
    const signature = JSON.stringify({ action: item.action, name: item.name, params })
    const reusableKey = keyPool.get(signature)?.shift()

    return {
      ...item,
      params,
      _key: reusableKey ?? keyCounter++,
    }
  })
}

function toExternal(items: StepDef[]): Array<{ action: string; name: string; params: Record<string, any> }> {
  return items.map(({ action, name, params }) => ({ action, name, params }))
}

const steps = ref<StepDef[]>([])

function isSameSteps(items: Array<{ action: string; name: string; params: Record<string, any> }>) {
  return JSON.stringify(items) === JSON.stringify(toExternal(steps.value))
}

watch(
  () => props.modelValue,
  (val) => {
    const nextSteps = val || []
    if (isSameSteps(nextSteps)) {
      return
    }
    steps.value = toInternal(nextSteps)
  },
  { immediate: true },
)

function emitUpdate() {
  emit('update:modelValue', toExternal(steps.value))
}

function addStep() {
  const action = 'click'
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
