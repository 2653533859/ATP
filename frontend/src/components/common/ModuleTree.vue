<template>
  <div class="module-tree">
    <div class="tree-header">
      <span class="tree-title">模块目录</span>
      <a-tooltip title="新建根模块">
        <PlusOutlined class="tree-add-btn" @click="showAddModal(null)" />
      </a-tooltip>
    </div>

    <a-spin :spinning="loading" size="small">
      <a-tree
        v-if="treeData.length"
        v-model:selectedKeys="selectedKeys"
        :tree-data="treeData"
        :field-names="{ title: 'name', key: 'id', children: 'children' }"
        block-node
        @select="onSelect"
      >
        <template #title="node">
          <div class="tree-node">
            <span class="node-name">{{ node.name }}</span>
            <span class="node-actions" @click.stop>
              <a-tooltip title="新建子模块">
                <PlusOutlined @click="showAddModal(node)" />
              </a-tooltip>
              <a-tooltip title="删除模块">
                <a-popconfirm
                  title="删除后该模块下所有用例将被删除，确认？"
                  ok-text="删除"
                  ok-type="danger"
                  @confirm="handleDelete(node)"
                >
                  <DeleteOutlined style="color: #ff4d4f; margin-left: 8px" />
                </a-popconfirm>
              </a-tooltip>
            </span>
          </div>
        </template>
      </a-tree>
      <a-empty v-else description="暂无模块" :image="Empty.PRESENTED_IMAGE_SIMPLE" />
    </a-spin>

    <!-- 新建模块弹窗 -->
    <a-modal
      v-model:open="addVisible"
      :title="addParent ? `在「${addParent.name}」下新建子模块` : '新建根模块'"
      width="400px"
      @ok="handleAdd"
      :confirm-loading="adding"
    >
      <a-input
        v-model:value="newModuleName"
        placeholder="模块名称"
        @pressEnter="handleAdd"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Empty, message } from 'ant-design-vue'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { projectApi, moduleApi } from '@/api'

const props = defineProps<{ projectId: number }>()
const emit = defineEmits<{ select: [moduleId: number | null] }>()

const treeData = ref<any[]>([])
const loading = ref(false)
const selectedKeys = ref<number[]>([])

const addVisible = ref(false)
const addParent = ref<any>(null)
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

function onSelect(keys: number[]) {
  selectedKeys.value = keys
  emit('select', keys.length ? keys[0] : null)
}

function showAddModal(parent: any) {
  addParent.value = parent
  newModuleName.value = ''
  addVisible.value = true
}

async function handleAdd() {
  if (!newModuleName.value.trim()) {
    message.warning('请输入模块名称')
    return
  }
  adding.value = true
  try {
    await moduleApi.create({
      name: newModuleName.value.trim(),
      project_id: props.projectId,
      parent_id: addParent.value?.id ?? null,
    })
    message.success('创建成功')
    addVisible.value = false
    await loadModules()
  } finally {
    adding.value = false
  }
}

async function handleDelete(node: any) {
  await moduleApi.delete(node.id)
  message.success('已删除')
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
  padding: 0 4px 12px;
  font-weight: 600;
  color: #1f1f1f;
}
.tree-add-btn {
  cursor: pointer;
  color: #1677ff;
  font-size: 14px;
}
.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-actions {
  display: none;
  align-items: center;
  flex-shrink: 0;
  padding-left: 4px;
}
.tree-node:hover .node-actions {
  display: flex;
}
</style>
