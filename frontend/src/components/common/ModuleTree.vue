<template>
  <div class="module-tree">
    <div class="tree-header">
      <span class="tree-title">{{ title }}</span>
      <div class="tree-header-actions">
        <a-button
          v-if="showReset"
          type="link"
          size="small"
          class="tree-reset-btn"
          :disabled="resetDisabled"
          @click="emit('reset')"
        >
          {{ t('common.view_all') }}
        </a-button>
          <a-tooltip v-if="editable" :title="t('case.module_tree.new_root')">
          <PlusOutlined class="tree-add-btn" @click="showAddModal(null)" />
        </a-tooltip>
      </div>
    </div>

    <a-spin :spinning="loading" size="small">
      <a-tree
        v-if="treeData.length"
        v-model:selectedKeys="selectedKeys"
        :tree-data="treeNodes"
        :field-names="{ title: 'name', key: 'id', children: 'children' }"
        block-node
        @select="onSelect"
      >
        <template #title="node">
          <div class="tree-node">
            <span class="node-icon">
              <FolderOpenOutlined v-if="selectedKeys.includes(node.id)" />
              <FolderOutlined v-else />
            </span>
            <span class="node-name" :title="node.name">{{ node.name }}</span>
            <span v-if="editable" class="node-actions" @click.stop>
              <a-tooltip :title="t('case.module_tree.new_child')">
                <PlusOutlined class="action-btn-mini" @click="showAddModal(node)" />
              </a-tooltip>
              <a-tooltip :title="t('case.module_tree.delete_module')">
                <a-popconfirm
                  :title="t('case.module_tree.delete_confirm')"
                  :ok-text="t('common.delete')"
                  ok-type="danger"
                  @confirm="handleDelete(node)"
                >
                  <DeleteOutlined class="action-btn-mini delete-btn" />
                </a-popconfirm>
              </a-tooltip>
            </span>
          </div>
        </template>
      </a-tree>
      <a-empty v-else :description="t('case.module_tree.empty')" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
    </a-spin>

    <a-modal
      v-model:open="addVisible"
      :title="addParent ? t('case.module_tree.new_child_under', { name: addParent.name }) : t('case.module_tree.new_root')"
      width="400px"
      @ok="handleAdd"
      :confirm-loading="adding"
    >
      <a-input
        v-model:value="newModuleName"
        :placeholder="t('case.module_tree.module_name')"
        @pressEnter="handleAdd"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Empty, message, type TreeProps } from 'ant-design-vue'
import { PlusOutlined, DeleteOutlined, FolderOutlined, FolderOpenOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { projectApi, moduleApi, type ModuleTreeItem } from '@/api'

const props = withDefaults(defineProps<{
  projectId: number
  title?: string
  showReset?: boolean
  resetDisabled?: boolean
  editable?: boolean
}>(), {
  title: undefined,
  showReset: false,
  resetDisabled: true,
  editable: true,
})
const emit = defineEmits<{ select: [moduleId: number | null]; reset: [] }>()
const { t } = useI18n()
const title = computed(() => props.title ?? t('case.module_tree.title'))

const treeData = ref<ModuleTreeItem[]>([])
// a-tree 经 field-names 映射消费 ModuleTreeItem（name/id/children），结构对 DataNode 是设计内偏差
const treeNodes = computed(() => treeData.value as unknown as TreeProps['treeData'])
const loading = ref(false)
const selectedKeys = ref<number[]>([])

const addVisible = ref(false)
const addParent = ref<ModuleTreeItem | null>(null)
const newModuleName = ref('')
const adding = ref(false)

async function loadModules() {
  loading.value = true
  try {
    treeData.value = await projectApi.getModules(props.projectId)
  } finally {
    loading.value = false
  }
}

// a-tree 的 Key 是 string | number；本树 key 取自 module id，恒为 number
function onSelect(keys: (string | number)[]) {
  selectedKeys.value = keys.map(Number)
  emit('select', keys.length ? Number(keys[0]) : null)
}

function showAddModal(parent: ModuleTreeItem | null) {
  addParent.value = parent
  newModuleName.value = ''
  addVisible.value = true
}

async function handleAdd() {
  if (!props.editable) return
  if (!newModuleName.value.trim()) {
    message.warning(t('case.module_tree.msg.name_required'))
    return
  }
  adding.value = true
  try {
    await moduleApi.create({
      name: newModuleName.value.trim(),
      project_id: props.projectId,
      parent_id: addParent.value?.id ?? null,
    })
    message.success(t('case.module_tree.msg.create_success'))
    addVisible.value = false
    await loadModules()
  } finally {
    adding.value = false
  }
}

async function handleDelete(node: ModuleTreeItem) {
  if (!props.editable) return
  await moduleApi.delete(node.id)
  message.success(t('case.module_tree.msg.delete_success'))
  if (selectedKeys.value.includes(node.id)) {
    selectedKeys.value = []
    emit('select', null)
  }
  await loadModules()
}

watch(() => props.projectId, loadModules, { immediate: true })

defineExpose({ reload: loadModules })
</script>

<style scoped>
.module-tree {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 0 4px 10px;
  font-weight: 700;
  font-size: 13px;
  color: var(--c-text);
  border-bottom: 1px solid var(--c-border-subtle);
  margin-bottom: 8px;
}
.tree-title {
  color: var(--c-text);
  font-weight: 700;
  font-size: 13px;
}
.tree-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tree-reset-btn {
  padding-inline: 0;
  font-size: 12px;
  color: var(--c-primary);
}
.tree-add-btn {
  cursor: pointer;
  color: var(--c-primary);
  font-size: 13px;
  padding: 3px 5px;
  border-radius: var(--radius-xs);
  transition: all 0.16s ease;
}
.tree-add-btn:hover {
  background: var(--c-primary-soft);
}
.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.node-icon {
  color: var(--c-primary);
  font-size: 13px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}
.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  color: var(--c-text);
}
.node-actions {
  display: none;
  align-items: center;
  flex-shrink: 0;
  gap: 4px;
  padding-left: 4px;
}
.tree-node:hover .node-actions {
  display: flex;
}
.action-btn-mini {
  color: var(--c-text-secondary);
  font-size: 12px;
  padding: 2px 4px;
  border-radius: var(--radius-xs);
  transition: all 0.16s ease;
}
.action-btn-mini:hover {
  color: var(--c-primary);
  background: var(--c-primary-soft);
}
.action-btn-mini.delete-btn {
  color: var(--c-error);
}
.action-btn-mini.delete-btn:hover {
  background: var(--c-error-soft);
}
</style>
