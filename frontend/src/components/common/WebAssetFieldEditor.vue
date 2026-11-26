<template>
  <div class="web-asset-field-editor">
    <div class="editor-toolbar">
      <div class="mode-pills" role="tablist">
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'visual' }"
          :aria-selected="mode === 'visual'"
          @click="switchMode('visual')"
        >
          {{ t('web_asset_editor.mode_visual') }}
        </button>
        <button
          type="button"
          role="tab"
          class="mode-pill"
          :class="{ 'is-active': mode === 'raw' }"
          :aria-selected="mode === 'raw'"
          @click="switchMode('raw')"
        >
          {{ t('web_asset_editor.mode_raw') }}
        </button>
      </div>
    </div>

    <div v-if="mode === 'visual'" class="visual-body">
      <template v-if="kind === 'locator'">
        <div class="field-row">
          <a-select
            v-model:value="locatorRow.strategy"
            size="small"
            class="strategy-select"
            :disabled="disabled"
            @change="emitLocator"
          >
            <a-select-option v-for="s in LOCATOR_STRATEGIES" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
          <a-input
            v-model:value="locatorRow.value"
            size="small"
            class="flex-main mono"
            :placeholder="t('web_asset_editor.value')"
            :disabled="disabled"
            @change="emitLocator"
          />
        </div>
        <div class="field-row">
          <a-input
            v-model:value="locatorRow.name"
            size="small"
            class="flex-main"
            :placeholder="t('web_asset_editor.role_name')"
            :disabled="disabled"
            @change="emitLocator"
          />
          <a-checkbox v-model:checked="locatorRow.exact" :disabled="disabled" @change="emitLocator">
            {{ t('web_asset_editor.exact') }}
          </a-checkbox>
        </div>
      </template>

      <template v-else-if="kind === 'fallbacks'">
        <div v-for="(row, idx) in fallbackRows" :key="idx" class="field-row">
          <a-select
            v-model:value="row.strategy"
            size="small"
            class="strategy-select"
            :disabled="disabled"
            @change="emitFallbacks"
          >
            <a-select-option v-for="s in LOCATOR_STRATEGIES" :key="s" :value="s">{{ s }}</a-select-option>
          </a-select>
          <a-input
            v-model:value="row.value"
            size="small"
            class="flex-main mono"
            :placeholder="t('web_asset_editor.value')"
            :disabled="disabled"
            @change="emitFallbacks"
          />
          <a-input
            v-model:value="row.name"
            size="small"
            style="width: 120px"
            :placeholder="t('web_asset_editor.role_name')"
            :disabled="disabled"
            @change="emitFallbacks"
          />
          <MinusCircleOutlined v-if="!disabled" class="remove-icon" @click="removeFallback(idx)" />
        </div>
        <a-button v-if="!disabled" type="dashed" size="small" block @click="addFallback">
          <PlusOutlined /> {{ t('web_asset_editor.add_fallback') }}
        </a-button>
      </template>

      <template v-else-if="kind === 'element_refs'">
        <div v-for="(row, idx) in elementRefRows" :key="idx" class="field-row">
          <a-select
            :value="row.asset_id ?? undefined"
            size="small"
            show-search
            allow-clear
            option-filter-prop="label"
            :options="elementSelectOptions"
            :placeholder="t('web_asset_editor.select_element')"
            class="flex-main"
            :disabled="disabled"
            @update:value="(val: unknown) => { row.asset_id = typeof val === 'number' ? val : null; onSelectElementRef(row) }"
          />
          <a-input
            v-model:value="row.alias"
            size="small"
            style="width: 140px"
            :placeholder="t('web_asset_editor.alias')"
            :disabled="disabled"
            @change="emitElementRefs"
          />
          <MinusCircleOutlined v-if="!disabled" class="remove-icon" @click="removeElementRef(idx)" />
        </div>
        <a-button v-if="!disabled" type="dashed" size="small" block @click="addElementRef">
          <PlusOutlined /> {{ t('web_asset_editor.add_ref') }}
        </a-button>
      </template>

      <template v-else-if="kind === 'actions'">
        <div v-for="(row, idx) in actionRows" :key="idx" class="field-row">
          <a-input
            v-model:value="row.name"
            size="small"
            style="width: 115px"
            :placeholder="t('web_asset_editor.action_name')"
            :disabled="disabled"
            @change="emitActions"
          />
          <a-select
            v-model:value="row.step"
            size="small"
            style="width: 115px"
            :disabled="disabled"
            @change="emitActions"
          >
            <a-select-option v-for="step in PAGE_ACTION_STEPS" :key="step" :value="step">{{ step }}</a-select-option>
          </a-select>
          <a-auto-complete
            v-model:value="row.alias"
            size="small"
            :options="aliasOptions"
            :placeholder="t('web_asset_editor.action_target')"
            class="flex-main"
            :disabled="disabled"
            @change="emitActions"
          />
          <a-input
            v-model:value="row.value"
            size="small"
            style="width: 120px"
            :placeholder="t('web_asset_editor.action_value')"
            :disabled="disabled"
            @change="emitActions"
          />
          <MinusCircleOutlined v-if="!disabled" class="remove-icon" @click="removeAction(idx)" />
        </div>
        <a-button v-if="!disabled" type="dashed" size="small" block @click="addAction">
          <PlusOutlined /> {{ t('web_asset_editor.add_action') }}
        </a-button>
      </template>

      <template v-else-if="kind === 'ignore_regions'">
        <div v-for="(row, idx) in ignoreRegionRows" :key="idx" class="field-row">
          <a-select
            v-model:value="row.mode"
            size="small"
            style="width: 125px"
            :disabled="disabled"
            @change="emitIgnoreRegions"
          >
            <a-select-option value="selector">{{ t('web_asset_editor.ignore_type_selector') }}</a-select-option>
            <a-select-option value="box">{{ t('web_asset_editor.ignore_type_box') }}</a-select-option>
          </a-select>
          <a-input
            v-if="row.mode === 'selector'"
            v-model:value="row.selector"
            size="small"
            class="flex-main mono"
            :placeholder="t('web_asset_editor.selector_placeholder')"
            :disabled="disabled"
            @change="emitIgnoreRegions"
          />
          <div v-else class="box-coords">
            <a-input-number v-model:value="row.x" size="small" :min="0" addon-before="X" :disabled="disabled" @change="emitIgnoreRegions" />
            <a-input-number v-model:value="row.y" size="small" :min="0" addon-before="Y" :disabled="disabled" @change="emitIgnoreRegions" />
            <a-input-number v-model:value="row.width" size="small" :min="0" addon-before="W" :disabled="disabled" @change="emitIgnoreRegions" />
            <a-input-number v-model:value="row.height" size="small" :min="0" addon-before="H" :disabled="disabled" @change="emitIgnoreRegions" />
          </div>
          <MinusCircleOutlined v-if="!disabled" class="remove-icon" @click="removeIgnoreRegion(idx)" />
        </div>
        <a-button v-if="!disabled" type="dashed" size="small" block @click="addIgnoreRegion">
          <PlusOutlined /> {{ t('web_asset_editor.add_ignore') }}
        </a-button>
      </template>
    </div>

    <div v-else>
      <a-textarea
        v-model:value="rawText"
        :rows="rows"
        :placeholder="placeholder"
        :disabled="disabled"
        class="mono-textarea"
        @change="handleRawChange"
      />
      <div v-if="rawInvalid" class="json-error">{{ t('web_asset_editor.invalid_json_hint') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import {
  LOCATOR_STRATEGIES,
  PAGE_ACTION_STEPS,
  parseElementRefsText,
  parseFallbackLocatorsText,
  parseIgnoreRegionsText,
  parseLocatorText,
  parsePageActionsText,
  serializeElementRefs,
  serializeFallbackLocators,
  serializeIgnoreRegions,
  serializeLocator,
  serializePageActions,
  type WebElementRefRow,
  type WebIgnoreRegionRow,
  type WebLocatorRow,
  type WebPageActionRow,
} from '@/utils/webAssetEditors'

export type WebAssetFieldKind = 'locator' | 'fallbacks' | 'element_refs' | 'actions' | 'ignore_regions'

const props = withDefaults(
  defineProps<{
    kind: WebAssetFieldKind
    value?: string
    elements?: Array<{ id: number; name: string }>
    elementRefsText?: string
    rows?: number
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    value: '',
    elements: () => [],
    elementRefsText: '',
    rows: 4,
    placeholder: '',
    disabled: false,
  },
)

const emit = defineEmits<{ 'update:value': [v: string] }>()
const { t } = useI18n()

const mode = ref<'visual' | 'raw'>('visual')
const rawText = ref(props.value ?? '')
const rawInvalid = ref(false)

const locatorRow = reactive<WebLocatorRow>({ strategy: 'css', value: '', name: '', exact: false })
const fallbackRows = ref<WebLocatorRow[]>([])
const elementRefRows = ref<WebElementRefRow[]>([])
const actionRows = ref<WebPageActionRow[]>([])
const ignoreRegionRows = ref<WebIgnoreRegionRow[]>([])

const elementSelectOptions = computed(() =>
  props.elements.map((item) => ({
    label: `${item.name} (#${item.id})`,
    value: item.id,
  })),
)

const aliasOptions = computed(() => {
  const parsed = parseElementRefsText(props.elementRefsText || '[]')
  if (!parsed.valid) return []
  return parsed.rows
    .map((item) => item.alias.trim())
    .filter(Boolean)
    .map((alias) => ({ value: alias }))
})

function syncFromRaw(text: string): boolean {
  if (props.kind === 'locator') {
    const res = parseLocatorText(text)
    if (!res.valid) return false
    locatorRow.strategy = res.row.strategy
    locatorRow.value = res.row.value
    locatorRow.name = res.row.name
    locatorRow.exact = res.row.exact
    locatorRow.extra = res.row.extra
    return true
  }
  if (props.kind === 'fallbacks') {
    const res = parseFallbackLocatorsText(text)
    if (!res.valid) return false
    fallbackRows.value = res.rows
    return true
  }
  if (props.kind === 'element_refs') {
    const res = parseElementRefsText(text)
    if (!res.valid) return false
    elementRefRows.value = res.rows
    return true
  }
  if (props.kind === 'actions') {
    const res = parsePageActionsText(text)
    if (!res.valid) return false
    actionRows.value = res.rows
    return true
  }
  const res = parseIgnoreRegionsText(text)
  if (!res.valid) return false
  ignoreRegionRows.value = res.rows
  return true
}

watch(
  () => props.value,
  (nextValue, prevValue) => {
    const normalized = nextValue ?? ''
    if (prevValue !== undefined && normalized === rawText.value) {
      return
    }
    rawText.value = normalized
    const ok = syncFromRaw(normalized)
    rawInvalid.value = !ok
    mode.value = ok ? 'visual' : 'raw'
  },
  { immediate: true },
)

function emitRaw(next: string) {
  rawText.value = next
  rawInvalid.value = false
  emit('update:value', next)
}

function handleRawChange() {
  rawInvalid.value = !syncFromRaw(rawText.value)
  emit('update:value', rawText.value)
}

function switchMode(nextMode: 'visual' | 'raw') {
  if (nextMode === mode.value) return
  if (nextMode === 'visual') {
    const ok = syncFromRaw(rawText.value)
    if (!ok) {
      message.warning(t('web_asset_editor.invalid_json_hint'))
      return
    }
  }
  mode.value = nextMode
}

function emitLocator() {
  emitRaw(serializeLocator(locatorRow))
}

function emitFallbacks() {
  emitRaw(serializeFallbackLocators(fallbackRows.value))
}

function addFallback() {
  fallbackRows.value.push({ strategy: 'css', value: '', name: '', exact: false })
}

function removeFallback(idx: number) {
  fallbackRows.value.splice(idx, 1)
  emitFallbacks()
}

function emitElementRefs() {
  emitRaw(serializeElementRefs(elementRefRows.value))
}

function onSelectElementRef(row: WebElementRefRow) {
  if (row.asset_id != null && !row.alias.trim()) {
    const found = props.elements.find((item) => item.id === row.asset_id)
    if (found) row.alias = found.name
  }
  emitElementRefs()
}

function addElementRef() {
  elementRefRows.value.push({ asset_id: null, alias: '' })
}

function removeElementRef(idx: number) {
  elementRefRows.value.splice(idx, 1)
  emitElementRefs()
}

function emitActions() {
  emitRaw(serializePageActions(actionRows.value))
}

function addAction() {
  actionRows.value.push({ name: '', step: 'click', alias: '', value: '' })
}

function removeAction(idx: number) {
  actionRows.value.splice(idx, 1)
  emitActions()
}

function emitIgnoreRegions() {
  emitRaw(serializeIgnoreRegions(ignoreRegionRows.value))
}

function addIgnoreRegion() {
  ignoreRegionRows.value.push({ mode: 'selector', selector: '', x: 0, y: 0, width: 100, height: 40 })
  emitIgnoreRegions()
}

function removeIgnoreRegion(idx: number) {
  ignoreRegionRows.value.splice(idx, 1)
  emitIgnoreRegions()
}
</script>

<style scoped>
.web-asset-field-editor {
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-bg-body);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mode-pills {
  display: inline-flex;
  padding: 2px;
  border-radius: var(--radius-sm);
  background: var(--c-bg-subtle);
  border: 1px solid var(--c-border-subtle);
  gap: 2px;
}

.mode-pill {
  border: 0;
  background: transparent;
  padding: 2px 10px;
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: 500;
  color: var(--c-text-secondary);
  cursor: pointer;
  font-family: inherit;
}

.mode-pill.is-active {
  background: var(--c-bg-elevated);
  color: var(--c-primary);
  font-weight: 600;
  box-shadow: var(--shadow-xs);
}

.visual-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.strategy-select {
  width: 112px;
  flex-shrink: 0;
}

.flex-main {
  flex: 1;
  min-width: 120px;
}

.box-coords {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(70px, 1fr));
  gap: 6px;
}

.remove-icon {
  color: var(--c-text-tertiary);
  cursor: pointer;
  font-size: 14px;
}

.remove-icon:hover {
  color: var(--c-error);
}

.mono,
.mono-textarea {
  font-family: monospace;
  font-size: 12px;
}

.json-error {
  margin-top: 4px;
  font-size: 12px;
  color: var(--c-error);
}
</style>
