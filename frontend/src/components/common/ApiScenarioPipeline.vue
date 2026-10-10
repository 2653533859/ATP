<template>
  <div class="api-scenario-pipeline">
    <!-- 流水线顶栏 -->
    <div class="pipeline-header-toolbar">
      <div class="toolbar-info">
        <div class="pipeline-badge-title">
          <ClusterOutlined class="pipeline-title-icon" />
          <span class="pipeline-title-text">{{ t('api_scenario.pipeline_title') }}</span>
          <span class="pipeline-count-pill">{{ steps.length }}</span>
        </div>
        <div class="pipeline-subtitle">
          {{ t('api_scenario.pipeline_desc') }}
        </div>
      </div>

      <div v-if="steps.length" class="toolbar-actions">
        <a-button
          type="primary"
          ghost
          size="small"
          class="pipeline-action-btn"
          :disabled="!canModify"
          @click="emit('openLibraryPicker')"
        >
          <ApiOutlined /> {{ t('api_scenario.import_from_library') }}
        </a-button>
        <a-button
          size="small"
          class="pipeline-action-btn"
          :disabled="!canModify"
          @click="addBlankStep"
        >
          <PlusOutlined /> {{ t('api_scenario.add_blank_step') }}
        </a-button>
      </div>
    </div>

    <!-- 步骤为空时的指引 -->
    <div v-if="!steps.length" class="pipeline-empty-guide">
      <div class="guide-content">
        <ThunderboltOutlined class="guide-icon" />
        <h4>{{ t('api_scenario.empty_title') }}</h4>
        <p>{{ t('api_scenario.empty_hint') }}</p>
        <div class="guide-actions">
          <a-button type="primary" :disabled="!canModify" @click="emit('openLibraryPicker')">
            <ApiOutlined /> {{ t('api_scenario.import_from_library') }}
          </a-button>
          <a-button :disabled="!canModify" @click="addBlankStep">
            <PlusOutlined /> {{ t('api_scenario.add_blank_step') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- 步骤卡片流转视图 -->
    <div v-else class="pipeline-step-flow">
      <draggable
        :list="steps"
        item-key="_id"
        handle=".step-drag-handle"
        animation="200"
        @change="handleDragChange"
      >
        <template #item="{ element, index }">
          <div class="pipeline-node">
            <!-- 步骤与步骤之间的流动连接线 -->
            <div v-if="index > 0" class="pipeline-connector-line">
              <div class="connector-arrow">
                <span class="connector-dash" />
                <span class="connector-tip">↓ {{ t('api_scenario.context_flow') }}</span>
              </div>
            </div>

            <div class="pipeline-step-card" :class="{ 'is-expanded': expandedIndexes.has(index) }">
              <!-- 卡片标头 -->
              <div class="card-top-bar">
                <div class="bar-left">
                  <HolderOutlined class="step-drag-handle" :title="t('api_scenario.drag_to_reorder')" />
                  <span class="step-index-chip">Step {{ index + 1 }}</span>
                  <span class="method-tag" :class="`method-${element.method || 'GET'}`">
                    {{ element.method || 'GET' }}
                  </span>
                  <a-input
                    v-model:value="element.name"
                    class="step-name-input"
                    size="small"
                    :placeholder="t('api_scenario.step_name_placeholder', { index: index + 1 })"
                  />
                </div>

                <div class="bar-right">
                  <!-- 依赖前置步骤选择 -->
                  <div v-if="index > 0" class="step-dependency-select">
                    <span class="dep-label">{{ t('api_scenario.depends_on_label') }}:</span>
                    <a-select
                      v-model:value="element.depends_on"
                      mode="multiple"
                      size="small"
                      style="min-width: 140px; max-width: 220px"
                      allow-clear
                      :placeholder="t('api_scenario.no_dependency')"
                      :options="getDependencyOptions(index)"
                    />
                  </div>

                  <a-space size="small">
                    <a-button
                      type="text"
                      size="small"
                      :title="t('api_scenario.clone_step')"
                      @click="cloneStep(index)"
                    >
                      <CopyOutlined />
                    </a-button>
                    <a-button
                      type="text"
                      size="small"
                      :title="expandedIndexes.has(index) ? t('api_scenario.collapse') : t('api_scenario.expand')"
                      @click="toggleExpand(index)"
                    >
                      <DownOutlined :class="{ 'rotate-180': expandedIndexes.has(index) }" />
                    </a-button>
                    <a-popconfirm
                      :title="t('api_scenario.confirm_delete_step')"
                      :ok-text="t('common.delete')"
                      :cancel-text="t('common.cancel')"
                      @confirm="removeStep(index)"
                    >
                      <a-button type="text" danger size="small" :title="t('common.delete')">
                        <DeleteOutlined />
                      </a-button>
                    </a-popconfirm>
                  </a-space>
                </div>
              </div>

              <!-- 卡片摘要栏 (URL与变量流转标记) -->
              <div class="card-summary-bar">
                <div class="summary-url" :title="element.url">
                  <code>{{ element.url || t('api_workbench.target_missing') }}</code>
                </div>

                <div class="summary-indicators">
                  <!-- 提取变量指示 -->
                  <template v-if="getExtractions(element).length">
                    <span
                      v-for="v in getExtractions(element)"
                      :key="`ext_${v}`"
                      class="var-badge var-extract"
                      :title="t('api_scenario.extract_var_title', { name: v })"
                    >
                      📤 {{ v }}
                    </span>
                  </template>

                  <!-- 引用变量指示 -->
                  <template v-if="getReferences(element).length">
                    <span
                      v-for="v in getReferences(element)"
                      :key="`ref_${v}`"
                      class="var-badge var-ref"
                      :title="t('api_scenario.ref_var_title', { name: v })"
                    >
                      📥 &#123;&#123;{{ v }}&#125;&#125;
                    </span>
                  </template>

                  <!-- 断言计数 -->
                  <span class="assertion-count-chip">
                    ✓ {{ (element.assertions || []).length }} {{ t('api_scenario.assertions_unit') }}
                  </span>
                </div>
              </div>

              <!-- 展开配置面板 -->
              <div v-if="expandedIndexes.has(index)" class="card-expanded-body">
                <div class="expand-field-row">
                  <div class="expand-field-label">{{ t('case_form.sections.request_config') }} URL:</div>
                  <div class="expand-field-input">
                    <a-input v-model:value="element.url" size="small" placeholder="https://api.example.com/endpoint" />
                  </div>
                </div>

                <!-- 快捷参数与断言简要配置 -->
                <div class="expand-quick-config">
                  <div class="quick-config-col">
                    <span class="config-kicker">{{ t('api_scenario.step_extractions') }}:</span>
                    <div v-if="!element.extractions?.length" class="config-empty-tip">
                      {{ t('api_scenario.no_extractions_tip') }}
                    </div>
                    <div v-else class="config-tag-list">
                      <a-tag
                        v-for="(ext, eIdx) in element.extractions"
                        :key="eIdx"
                        color="green"
                        closable
                        @close="element.extractions.splice(eIdx, 1)"
                      >
                        {{ ext.variable }} = {{ ext.expression }}
                      </a-tag>
                    </div>
                  </div>

                  <div class="quick-config-col">
                    <span class="config-kicker">{{ t('api_scenario.step_assertions') }}:</span>
                    <div v-if="!element.assertions?.length" class="config-empty-tip">
                      {{ t('api_scenario.no_assertions_tip') }}
                    </div>
                    <div v-else class="config-tag-list">
                      <a-tag
                        v-for="(ast, aIdx) in element.assertions"
                        :key="aIdx"
                        color="blue"
                        closable
                        @close="element.assertions.splice(aIdx, 1)"
                      >
                        {{ ast.target }} {{ ast.operator }} {{ ast.expected }}
                      </a-tag>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </draggable>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  ClusterOutlined,
  ApiOutlined,
  PlusOutlined,
  HolderOutlined,
  DeleteOutlined,
  CopyOutlined,
  DownOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import draggable from 'vuedraggable'
import { useI18n } from 'vue-i18n'
import {
  type ApiScenarioStep,
  detectVariableReferences,
  detectVariableExtractions,
} from '@/types/apiScenario'

const props = defineProps<{
  steps: ApiScenarioStep[]
  projectId?: number | null
  canModify: boolean
}>()

const emit = defineEmits<{
  (e: 'update:steps', steps: ApiScenarioStep[]): void
  (e: 'openLibraryPicker'): void
}>()

const { t } = useI18n()

const expandedIndexes = ref(new Set<number>())

function toggleExpand(index: number) {
  if (expandedIndexes.value.has(index)) {
    expandedIndexes.value.delete(index)
  } else {
    expandedIndexes.value.add(index)
  }
}

function getDependencyOptions(currentIndex: number) {
  return props.steps.slice(0, currentIndex).map((step, idx) => ({
    label: `Step ${idx + 1}: ${step.name || `步骤 ${idx + 1}`}`,
    value: idx,
  }))
}

function addBlankStep() {
  const newIndex = props.steps.length
  const newStep: ApiScenarioStep = {
    name: t('api_scenario.blank_step_default_name', { index: newIndex + 1 }),
    method: 'GET',
    url: '',
    headers: {},
    params: {},
    cookies: {},
    body_type: 'none',
    body: '',
    assertions: [],
    extractions: [],
    depends_on: newIndex > 0 ? [newIndex - 1] : [],
  }
  const next = [...props.steps, newStep]
  emit('update:steps', next)
  expandedIndexes.value.add(newIndex)
}

function cloneStep(index: number) {
  const source = props.steps[index]
  const cloned: ApiScenarioStep = JSON.parse(JSON.stringify(source)) as ApiScenarioStep
  cloned.name = `${source.name} (副本)`
  const next = [...props.steps]
  next.splice(index + 1, 0, cloned)
  emit('update:steps', next)
}

function removeStep(index: number) {
  const next = [...props.steps]
  next.splice(index, 1)
  // 修正后续步骤的 depends_on 索引
  next.forEach((step) => {
    if (Array.isArray(step.depends_on)) {
      step.depends_on = step.depends_on
        .filter((d) => d !== index)
        .map((d) => (d > index ? d - 1 : d))
    }
  })
  emit('update:steps', next)
}

function handleDragChange() {
  emit('update:steps', [...props.steps])
}

function getExtractions(step: ApiScenarioStep): string[] {
  return detectVariableExtractions(step)
}

function getReferences(step: ApiScenarioStep): string[] {
  return detectVariableReferences(step)
}
</script>

<style scoped>
.api-scenario-pipeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 14px;
}

.pipeline-header-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
}

.toolbar-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pipeline-badge-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--c-text, #1e293b);
}

.pipeline-title-icon {
  font-size: 16px;
  color: var(--c-primary, #1677ff);
}

.pipeline-count-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 20px;
  padding: 0 6px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 10px;
  background: var(--c-primary-soft, #e6f4ff);
  color: var(--c-primary, #1677ff);
}

.pipeline-subtitle {
  font-size: 12px;
  color: var(--c-text-tertiary, #94a3b8);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pipeline-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.pipeline-empty-guide {
  padding: 32px 20px;
  text-align: center;
  border: 2px dashed var(--c-border, #e2e8f0);
  border-radius: 10px;
  background: var(--c-bg-elevated, #fff);
}

.guide-icon {
  font-size: 36px;
  color: #fa8c16;
  margin-bottom: 12px;
}

.guide-content h4 {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
  margin-bottom: 6px;
}

.guide-content p {
  font-size: 13px;
  color: var(--c-text-secondary, #64748b);
  max-width: 520px;
  margin: 0 auto 18px;
}

.guide-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.pipeline-step-flow {
  display: flex;
  flex-direction: column;
}

.pipeline-node {
  position: relative;
}

.pipeline-connector-line {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 28px;
}

.connector-arrow {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  font-weight: 600;
}

.pipeline-step-card {
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  background: var(--c-bg-elevated, #fff);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
  transition: all 0.2s ease;
  overflow: hidden;
}

.pipeline-step-card:hover {
  border-color: var(--c-primary-soft, #91caff);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.pipeline-step-card.is-expanded {
  border-color: var(--c-primary, #1677ff);
}

.card-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--c-bg-subtle, #f8fafc);
  border-bottom: 1px solid var(--c-border, #e2e8f0);
}

.bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.step-drag-handle {
  cursor: grab;
  color: var(--c-text-tertiary, #94a3b8);
  font-size: 14px;
  padding: 2px;
}

.step-drag-handle:hover {
  color: var(--c-primary, #1677ff);
}

.step-index-chip {
  font-size: 11px;
  font-weight: 700;
  color: #fa8c16;
  background: #fff7e6;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid #ffd591;
  white-space: nowrap;
}

.step-name-input {
  max-width: 260px;
  font-weight: 600;
}

.bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-dependency-select {
  display: flex;
  align-items: center;
  gap: 6px;
}

.dep-label {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  white-space: nowrap;
}

.method-tag {
  display: inline-block;
  padding: 2px 6px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 4px;
  text-align: center;
  min-width: 44px;
}

.method-GET { background: #e6f4ff; color: #0958d9; border: 1px solid #91caff; }
.method-POST { background: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }
.method-PUT { background: #fff7e6; color: #d46b08; border: 1px solid #ffd591; }
.method-DELETE { background: #fff1f0; color: #cf1322; border: 1px solid #ffa39e; }
.method-PATCH { background: #f9f0ff; color: #722ed1; border: 1px solid #d3adf7; }
.method-GRAPHQL { background: #fff0f6; color: #c41d7f; border: 1px solid #ffadd2; }
.method-WS { background: #e6fffb; color: #08979c; border: 1px solid #87e8de; }

.card-summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  background: var(--c-bg-elevated, #fff);
  font-size: 12px;
  flex-wrap: wrap;
}

.summary-url {
  flex: 1;
  min-width: 180px;
}

.summary-url code {
  color: var(--c-text, #1e293b);
  background: var(--c-bg-subtle, #f1f5f9);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: monospace;
}

.summary-indicators {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.var-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
}

.var-extract {
  background: #f6ffed;
  color: #389e0d;
  border: 1px solid #b7eb8f;
}

.var-ref {
  background: #e6f4ff;
  color: #0958d9;
  border: 1px solid #91caff;
}

.assertion-count-chip {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.card-expanded-body {
  padding: 12px 14px;
  background: var(--c-bg-subtle, #f8fafc);
  border-top: 1px solid var(--c-border, #e2e8f0);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.expand-field-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.expand-field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--c-text, #1e293b);
  width: 140px;
  flex-shrink: 0;
}

.expand-field-input {
  flex: 1;
}

.expand-quick-config {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.quick-config-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-kicker {
  font-size: 11px;
  font-weight: 700;
  color: var(--c-text-secondary, #64748b);
}

.config-empty-tip {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  font-style: italic;
}

.config-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.rotate-180 {
  transform: rotate(180deg);
  transition: transform 0.2s ease;
}
</style>
