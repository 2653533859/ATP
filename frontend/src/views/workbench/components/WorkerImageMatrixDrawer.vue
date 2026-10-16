<template>
  <a-drawer
    :open="open"
    :width="960"
    placement="right"
    destroy-on-close
    @close="handleClose"
  >
    <template #title>
      <div class="drawer-title-box">
        <span>容器执行环境镜像版本矩阵与标签路由解析</span>
        <a-tag color="blue">多语言 / 多 SDK 执行矩阵</a-tag>
      </div>
    </template>

    <div class="worker-image-matrix-drawer">
      <!-- 头部控制栏：镜像注册表单 -->
      <a-card size="small" class="register-card">
        <div class="register-header">
          <h4 class="title">执行环境镜像矩阵注册 (Image Matrix Registry)</h4>
          <p class="subtitle">
            支持 Python、Node.js、Android SDK、Headless 浏览器与高并发性能压测等企业级容器镜像版本注册；结合用例运行标签执行加权交集打分路由，并在标签不匹配时平滑兜底回退。
          </p>
        </div>

        <a-form layout="inline" class="register-form">
          <a-form-item label="镜像 ID" required>
            <a-input v-model:value="newImageId" placeholder="如 img_py312_core" size="small" style="width: 130px" />
          </a-form-item>

          <a-form-item label="镜像名称" required>
            <a-input v-model:value="newName" placeholder="如 Python 3.12 核心镜像" size="small" style="width: 150px" />
          </a-form-item>

          <a-form-item label="分类">
            <a-select v-model:value="newCategory" size="small" style="width: 110px">
              <a-select-option value="python">Python</a-select-option>
              <a-select-option value="nodejs">Node.js</a-select-option>
              <a-select-option value="android_sdk">Android</a-select-option>
              <a-select-option value="browser">Browser</a-select-option>
              <a-select-option value="performance">Perf</a-select-option>
              <a-select-option value="generic">通用</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="镜像 Registry 路径" required>
            <a-input v-model:value="newImageUrl" placeholder="registry.internal/atp/worker:tag" size="small" style="width: 180px" />
          </a-form-item>

          <a-form-item label="环境标签 (逗号隔开)">
            <a-input v-model:value="newTagsStr" placeholder="如 python:3.12, pytest" size="small" style="width: 150px" />
          </a-form-item>

          <a-form-item>
            <a-button type="primary" size="small" :loading="registering" @click="handleRegisterImage">
              注册镜像
            </a-button>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 交互式标签路由解析模拟器 (Tag Resolution Simulator) -->
      <a-card size="small" title="用例标签动态路由匹配调试器 (Tag Resolution Simulator)" class="resolver-card">
        <div class="resolver-box">
          <div class="resolver-input-bar">
            <span class="resolver-label">用例需求标签 (逗号隔开):</span>
            <a-input
              v-model:value="queryTagsStr"
              placeholder="如 python:3.12, playwright:chromium, x86_64"
              size="small"
              style="flex: 1"
            />
            <a-select v-model:value="queryCategory" size="small" style="width: 110px">
              <a-select-option value="">全部分类</a-select-option>
              <a-select-option value="python">Python</a-select-option>
              <a-select-option value="nodejs">Node.js</a-select-option>
              <a-select-option value="browser">Browser</a-select-option>
              <a-select-option value="android_sdk">Android</a-select-option>
              <a-select-option value="performance">Perf</a-select-option>
            </a-select>
            <a-button type="primary" size="small" :loading="resolving" @click="handleResolveImage">
              推演命中镜像
            </a-button>
          </div>

          <!-- 路由匹配结果展示 -->
          <div v-if="matchResult" class="match-result-section">
            <a-alert
              :type="matchResult.matched ? 'success' : 'warning'"
              show-icon
              class="match-alert"
              :message="matchResult.matched ? `[精准命中] ${matchResult.reason}` : `[平滑兜底] ${matchResult.reason}`"
              :description="`命中镜像: ${matchResult.selected_image.name} (${matchResult.selected_image.image_url}) | 得分: ${matchResult.match_score} | 兜底状态: ${matchResult.is_fallback ? 'YES' : 'NO'}`"
            />

            <div class="tags-diff-row">
              <div class="diff-block">
                <span class="diff-label text-green">成功命中标签 (Matched):</span>
                <a-space size="small" wrap>
                  <a-tag v-for="t in matchResult.matched_tags" :key="t" color="green">{{ t }}</a-tag>
                  <span v-if="!matchResult.matched_tags.length" class="empty-hint">无</span>
                </a-space>
              </div>

              <div class="diff-block">
                <span class="diff-label text-orange">未命中差异标签 (Unmatched):</span>
                <a-space size="small" wrap>
                  <a-tag v-for="t in matchResult.unmatched_tags" :key="t" color="orange">{{ t }}</a-tag>
                  <span v-if="!matchResult.unmatched_tags.length" class="empty-hint">无 (全量重合)</span>
                </a-space>
              </div>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 镜像版本矩阵列表表格 -->
      <a-card size="small" title="镜像矩阵版本库流水" class="matrix-table-card">
        <template #extra>
          <a-space size="small">
            <a-select v-model:value="filterCategory" size="small" style="width: 110px" @change="loadImages">
              <a-select-option value="">全部分类</a-select-option>
              <a-select-option value="python">Python</a-select-option>
              <a-select-option value="nodejs">Node.js</a-select-option>
              <a-select-option value="browser">Browser</a-select-option>
              <a-select-option value="android_sdk">Android</a-select-option>
              <a-select-option value="performance">Perf</a-select-option>
            </a-select>
            <a-button size="small" :loading="loading" @click="loadImages">
              刷新矩阵
            </a-button>
          </a-space>
        </template>

        <a-table
          :data-source="images"
          :columns="columns"
          row-key="image_id"
          size="small"
          :pagination="{ pageSize: 5 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <div class="img-name-cell">
                <div class="name-row">
                  <strong>{{ record.name }}</strong>
                  <a-tag v-if="record.is_default" color="purple" class="default-pill">默认兜底</a-tag>
                </div>
                <code class="url-text">{{ record.image_url }}</code>
              </div>
            </template>

            <template v-if="column.key === 'category'">
              <a-tag :color="getCategoryColor(record.category)">
                {{ record.category.toUpperCase() }}
              </a-tag>
            </template>

            <template v-if="column.key === 'tags'">
              <a-space size="small" wrap>
                <a-tag v-for="tag in record.tags" :key="tag" class="tag-pill">{{ tag }}</a-tag>
              </a-space>
            </template>

            <template v-if="column.key === 'min_resources'">
              <span class="resource-text">{{ record.min_cpu_cores }}C / {{ record.min_memory_mb }}MB</span>
            </template>

            <template v-if="column.key === 'actions'">
              <a-button
                size="small"
                type="link"
                danger
                @click="handleDeleteImage(record.image_id)"
              >
                删除
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  workerImageMatrixApi,
  type WorkerImageItem,
  type ImageCategory,
  type ImageRouteMatchResult,
} from '@/api/cloudNativeWorkers'

const props = withDefaults(
  defineProps<{
    open: boolean
  }>(),
  {
    open: false,
  }
)

const emit = defineEmits<{
  (e: 'update:open', val: boolean): void
}>()

const loading = ref(false)
const registering = ref(false)
const resolving = ref(false)

const filterCategory = ref('')
const newImageId = ref('')
const newName = ref('')
const newImageUrl = ref('')
const newCategory = ref<ImageCategory>('python')
const newTagsStr = ref('')

const queryTagsStr = ref('python:3.12, playwright')
const queryCategory = ref('')
const matchResult = ref<ImageRouteMatchResult | null>(null)

const images = ref<WorkerImageItem[]>([])

const columns = [
  { title: '镜像名称 / Registry URL', key: 'name', width: 260 },
  { title: '分类', key: 'category', width: 90 },
  { title: '环境标签矩阵 (Tags)', key: 'tags' },
  { title: '门槛配置', key: 'min_resources', width: 110 },
  { title: '操作', key: 'actions', width: 70 },
]

function getCategoryColor(cat: ImageCategory): string {
  switch (cat) {
    case 'python':
      return 'blue'
    case 'nodejs':
      return 'green'
    case 'browser':
      return 'cyan'
    case 'android_sdk':
      return 'purple'
    case 'performance':
      return 'red'
    default:
      return 'default'
  }
}

function handleClose() {
  emit('update:open', false)
}

async function loadImages() {
  loading.value = true
  try {
    const res = await workerImageMatrixApi.listImages(filterCategory.value || undefined)
    images.value = res.images
  } catch (err: any) {
    message.error(err.message || '获取镜像列表失败')
  } finally {
    loading.value = false
  }
}

async function handleRegisterImage() {
  if (!newImageId.value || !newName.value || !newImageUrl.value) {
    message.warning('请填写完整的镜像 ID、名称与路径')
    return
  }
  registering.value = true
  try {
    const tagList = newTagsStr.value
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    await workerImageMatrixApi.registerImage({
      image_id: newImageId.value,
      name: newName.value,
      image_url: newImageUrl.value,
      category: newCategory.value,
      tags: tagList,
    })
    message.success(`镜像 [${newName.value}] 注册成功！`)
    newImageId.value = ''
    newName.value = ''
    newImageUrl.value = ''
    newTagsStr.value = ''
    await loadImages()
  } catch (err: any) {
    message.error(err.message || '注册镜像失败')
  } finally {
    registering.value = false
  }
}

async function handleDeleteImage(imageId: string) {
  try {
    await workerImageMatrixApi.deleteImage(imageId)
    message.success('镜像已成功删除')
    await loadImages()
  } catch (err: any) {
    message.error(err.message || '删除镜像失败')
  }
}

async function handleResolveImage() {
  resolving.value = true
  try {
    const tagList = queryTagsStr.value
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)

    const res = await workerImageMatrixApi.resolveImage({
      required_tags: tagList,
      category: queryCategory.value || undefined,
    })
    matchResult.value = res
    if (res.matched) {
      message.success(`成功路由命中最佳镜像: ${res.selected_image.name}`)
    } else {
      message.warning('未找到完全满足标签的镜像，已安全平滑兜底回退！')
    }
  } catch (err: any) {
    message.error(err.message || '标签路由解析失败')
  } finally {
    resolving.value = false
  }
}

onMounted(() => {
  loadImages()
})
</script>

<style scoped>
.worker-image-matrix-drawer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drawer-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.register-card,
.resolver-card,
.matrix-table-card {
  border-radius: 8px;
}

.register-header {
  margin-bottom: 8px;
}

.title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text, #0f172a);
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.register-form {
  margin-top: 6px;
}

.resolver-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.resolver-input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.resolver-label {
  font-size: 12px;
  color: #334155;
  font-weight: 600;
}

.match-result-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.match-alert {
  border-radius: 6px;
}

.tags-diff-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  background: var(--c-bg-subtle, #f8fafc);
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--c-border, #e2e8f0);
}

.diff-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.diff-label {
  font-size: 11px;
  font-weight: 600;
}

.text-green {
  color: #16a34a;
}

.text-orange {
  color: #ea580c;
}

.empty-hint {
  font-size: 11px;
  color: #94a3b8;
  font-style: italic;
}

.img-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.default-pill {
  font-size: 10px;
  padding: 0 4px;
}

.url-text {
  font-size: 10px;
  color: #64748b;
  font-family: monospace;
}

.tag-pill {
  font-size: 11px;
  font-family: monospace;
}

.resource-text {
  font-size: 11px;
  color: #475569;
}
</style>
