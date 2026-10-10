<template>
  <div class="request-editor" :inert="disabled">
    <section v-for="(request, index) in requests" :key="index">
      <h4>{{ t('hermes.actions.request_number', { index: index + 1 }) }}</h4>
      <div class="request-line">
        <a-select :value="String(request.method || 'GET')" :options="methods" :aria-label="t('hermes.actions.method')" @change="value => edit(index, 'method', value)" />
        <a-input :value="String(request.url || '')" :aria-label="t('hermes.actions.url')" @update:value="value => edit(index, 'url', value)" />
      </div>
      <div v-for="(assertion, number) in assertions(request)" :key="number" class="assertion-line">
        <a-select :value="String(assertion.target || '')" :options="targets" :aria-label="t('case_form.assertion.target_placeholder')" @change="value => editAssertion(index, number, 'target', value)" />
        <a-select :value="String(assertion.operator || '')" :options="operators" :aria-label="t('case_form.assertion.operator_placeholder')" @change="value => editAssertion(index, number, 'operator', value)" />
        <a-input :value="String(assertion.expression || '')" :aria-label="t('case_form.assertion.expression_placeholder')" :placeholder="t('case_form.assertion.expression_placeholder')" @update:value="value => editAssertion(index, number, 'expression', value)" />
        <a-input :value="displayExpected(assertion.expected)" :disabled="assertion.operator === 'exists'" :aria-label="t('case_form.assertion.expected_placeholder')" :placeholder="t('case_form.assertion.expected_placeholder')" @update:value="value => editAssertion(index, number, 'expected', value)" />
        <a-button danger @click="removeAssertion(index, number)">{{ t('hermes.actions.remove') }}</a-button>
      </div>
      <a-button type="dashed" @click="addAssertion(index)">{{ t('hermes.actions.add_assertion') }}</a-button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
const props = defineProps<{ modelValue: Record<string, unknown>; disabled: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, unknown>] }>()
const { t } = useI18n()
type Item = Record<string, unknown>
const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].map(value => ({ value, label: value }))
const targets = computed(() => ['status_code', 'body', 'header', 'duration', 'json_schema'].map(value => ({ value, label: t(`case_form.assertion.targets.${value}`) })))
const operators = computed(() => ['eq', 'contains', 'gt', 'lt', 'exists', 'valid', 'invalid'].map(value => ({ value, label: t(`case_form.assertion.operators.${value}`) })))
const requests = computed(() => Array.isArray(props.modelValue.steps) ? props.modelValue.steps as Item[] : [props.modelValue])
function assertions(request: Item): Item[] { return Array.isArray(request.assertions) ? request.assertions as Item[] : [] }
function displayExpected(value: unknown): string {
  return value && typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')
}
function change(index: number, update: (request: Item) => void) {
  if (props.disabled) return
  const config = JSON.parse(JSON.stringify(props.modelValue)) as Item
  const request = Array.isArray(config.steps) ? config.steps[index] as Item : config
  update(request)
  emit('update:modelValue', config)
}
function edit(index: number, field: string, value: unknown) { change(index, request => { request[field] = value }) }
function editAssertion(index: number, number: number, field: string, value: unknown) {
  change(index, request => {
    const assertion = assertions(request)[number]
    if (!assertion) return
    // 保留数字/布尔预期的类型，避免编辑后状态码和 JSON 值变成字符串。
    if (field === 'expected' && typeof assertion.expected === 'number') {
      const number = Number(value)
      assertion[field] = String(value).trim() && Number.isFinite(number) ? number : String(value)
    }
    else if (field === 'expected' && assertion.expected && typeof assertion.expected === 'object') {
      try { assertion[field] = JSON.parse(String(value)) } catch { assertion[field] = String(value) }
    }
    else if (field === 'expected' && typeof assertion.expected === 'boolean' && ['true', 'false'].includes(String(value))) assertion[field] = value === 'true'
    else assertion[field] = value
  })
}
function addAssertion(index: number) { change(index, request => { request.assertions = [...assertions(request), { target: 'status_code', operator: 'eq', expected: 200 }] }) }
function removeAssertion(index: number, number: number) { change(index, request => { request.assertions = assertions(request).filter((_, item) => item !== number) }) }
</script>

<style scoped>
.request-editor section { margin: 16px 0; }
.request-line { display: grid; grid-template-columns: 110px 1fr; gap: 8px; margin-bottom: 12px; }
.assertion-line { display: grid; grid-template-columns: 120px 100px 1fr 1fr auto; gap: 8px; margin-bottom: 8px; }
@media (max-width: 650px) { .assertion-line { grid-template-columns: 1fr 1fr; } }
</style>
