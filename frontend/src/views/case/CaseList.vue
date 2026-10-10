<template>
  <div class="page-shell case-page">
    <header class="case-toolbar page-header">
      <div class="toolbar-left">
        <FileTextOutlined class="toolbar-icon" />
        <h2 class="toolbar-title page-title">{{ t('case.title') }}</h2>
      </div>
      <div class="toolbar-right">
        <a-select
          v-model:value="(selectedProjectId as number | undefined)"
          size="small"
          :placeholder="t('case.select_project')"
          style="width: 200px"
          :options="projectOptions"
          allow-clear
          @change="handleProjectChange"
        />
        <a-button size="small" @click="router.push({ name: 'projects' })">{{ t('case.project_management') }}</a-button>
        <a-button size="small" :disabled="!selectedProjectId" @click="refreshCurrentProject">{{ t('common.refresh') }}</a-button>
      </div>
    </header>

    <a-alert
      v-if="pendingAiGeneration"
      type="info"
      show-icon
      closable
      class="ai-route-notice"
      :message="t('case.ai.title')"
      :description="t('case.ai.select_module_alert')"
      @close="clearPendingAiGeneration"
    />

    <template v-if="selectedProjectId">
      <div class="case-bento-grid">
        <div class="case-bento-tile">
          <div class="tile-header">
            <span class="tile-label">{{ t('case.stats.visible_cases') }}</span>
            <span class="tag-pill tag-blue">当前视图</span>
          </div>
          <div class="tile-value">{{ filteredCases.length }}</div>
          <div class="tile-footer">
            <span>{{ currentProjectName }} · 共 <b>{{ cases.length }}</b> 条</span>
          </div>
        </div>

        <div class="case-bento-tile">
          <div class="tile-header">
            <span class="tile-label">{{ t('case.stats.module_count') }}</span>
            <span class="tag-pill tag-gray">业务划分</span>
          </div>
          <div class="tile-value">{{ moduleCount }}</div>
          <div class="tile-footer">
            <span>已选: <b>{{ selectedModuleId ? (moduleNameMap[selectedModuleId] || '指定模块') : '全部模块' }}</b></span>
          </div>
        </div>

        <div class="case-bento-tile">
          <div class="tile-header">
            <span class="tile-label">{{ t('case.stats.pending_reviews') }}</span>
            <span class="tag-pill" :class="pendingReviewCount > 0 ? 'tag-yellow' : 'tag-gray'">
              {{ pendingReviewCount > 0 ? '待处理' : '已清空' }}
            </span>
          </div>
          <div class="tile-value" :class="{ 'value-warn': pendingReviewCount > 0 }">
            {{ pendingReviewCount }}
          </div>
          <div class="tile-footer">
            <span>团队用例评审</span>
          </div>
        </div>

        <div class="case-bento-tile">
          <div class="tile-header">
            <span class="tile-label">{{ t('case.stats.flaky_cases') }}</span>
            <span class="tag-pill" :class="flakyCaseCount > 0 ? 'tag-red' : 'tag-green'">
              {{ flakyCaseCount > 0 ? '需干预' : '稳定性良好' }}
            </span>
          </div>
          <div class="tile-value" :class="{ 'value-danger': flakyCaseCount > 0 }">
            {{ flakyCaseCount }}
          </div>
          <div class="tile-footer">
            <span>抖动异常监测</span>
          </div>
        </div>
      </div>

      <div class="workspace">
        <div class="side-panel">
          <ModuleTree
            :key="selectedProjectId"
            :project-id="selectedProjectId"
            show-reset
            :reset-disabled="!selectedModuleId"
            @select="onModuleSelect"
            @reset="clearModuleFilter"
          />
        </div>

        <div class="main-panel">
          <a-card class="toolbar-card" :bordered="false">
            <div class="toolbar">
              <div class="toolbar-main">
                <div class="filter-primary-row">
                  <a-input-search
                    v-model:value="keyword"
                    :placeholder="t('case.search_placeholder')"
                    style="width: 260px"
                    allow-clear
                    @search="handleSearch"
                  />
                  <a-select
                    v-model:value="filterPriority"
                    :placeholder="t('case.filters.priority')"
                    allow-clear
                    style="width: 110px"
                    :options="priorityOptions"
                    @change="loadCases"
                  />
                  <a-select
                    v-model:value="filterLevel"
                    :placeholder="t('case.filters.level')"
                    allow-clear
                    style="width: 120px"
                  >
                    <a-select-option value="smoke">{{ t('case.levels.smoke') }}</a-select-option>
                    <a-select-option value="core">{{ t('case.levels.core') }}</a-select-option>
                    <a-select-option value="regression">{{ t('case.levels.regression') }}</a-select-option>
                    <a-select-option value="extended">{{ t('case.levels.extended') }}</a-select-option>
                  </a-select>
                  <a-button
                    size="middle"
                    :type="showAdvancedFilters ? 'primary' : 'default'"
                    ghost
                    class="adv-filter-btn"
                    @click="showAdvancedFilters = !showAdvancedFilters"
                  >
                    <FilterOutlined /> 高级筛选 <DownOutlined :class="{ 'rotate-180': showAdvancedFilters }" />
                  </a-button>
                  <a-button @click="handleResetFilters">{{ t('common.reset') }}</a-button>
                </div>

                <div v-if="showAdvancedFilters" class="filter-advanced-row">
                  <a-select
                    v-model:value="filterStatus"
                    :placeholder="t('case.filters.status')"
                    allow-clear
                    style="width: 120px"
                    :options="statusOptions"
                    @change="loadCases"
                  />
                  <a-select
                    v-model:value="filterReviewStatus"
                    :placeholder="t('case.filters.review_status')"
                    allow-clear
                    style="width: 130px"
                    :options="reviewStatusOptions"
                    @change="loadCases"
                  />
                  <a-select
                    v-model:value="filterAutomationStatus"
                    :placeholder="t('case.filters.automation_status')"
                    allow-clear
                    style="width: 130px"
                    :options="automationStatusOptions"
                    @change="loadCases"
                  />
                </div>
              <div v-if="activeFilterTags.length" class="active-filter-row">
                <span class="active-filter-label">{{ t('case.active_filters') }}</span>
                <a-tag
                  v-for="tag in activeFilterTags"
                  :key="tag.key"
                  closable
                  @close.prevent="clearFilter(tag.key)"
                >
                  {{ tag.label }}
                </a-tag>
                <a-button size="small" type="link" @click="handleResetFilters">{{ t('case.clear_filters') }}</a-button>
              </div>
              </div>

              <div class="toolbar-actions">
                <a-space wrap>
                <a-tag color="blue">
                  {{ t('case.current_module', { name: selectedModuleId ? activeModuleName : t('common.all') }) }}
                </a-tag>
                <a-dropdown :disabled="!canModifyCases">
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="api" @click="openCreate('api')">{{ t('case.types.api') }}</a-menu-item>
                      <a-menu-item key="graphql" @click="openCreate('graphql')">{{ t('case.types.graphql') }}</a-menu-item>
                      <a-menu-item key="websocket" @click="openCreate('websocket')">{{ t('case.types.websocket') }}</a-menu-item>
                      <a-menu-item key="grpc" @click="openCreate('grpc')">{{ t('case.types.grpc') }}</a-menu-item>
                      <a-menu-item key="web" @click="openCreate('web')">{{ t('case.types.web') }}</a-menu-item>
                      <a-menu-item key="android" @click="openCreate('android')">{{ t('case.types.android') }}</a-menu-item>
                      <a-menu-item key="ios" @click="openCreate('ios')">{{ t('case.types.ios') }}</a-menu-item>
                    </a-menu>
                  </template>
                  <a-button type="primary" :disabled="!canModifyCases">
                    <PlusOutlined /> {{ t('case.new_case') }} <DownOutlined />
                  </a-button>
                </a-dropdown>
                <a-tooltip :title="caseCreateDisabledTip">
                  <a-button :disabled="!canModifyCases" @click="openAiGenerate">
                    <ThunderboltOutlined /> {{ t('case.ai_generate') }}
                  </a-button>
                </a-tooltip>
              </a-space>
              </div>
            </div>
          </a-card>

          <a-card class="table-card" :bordered="false">
            <div class="case-category-tabs-bar">
              <div class="category-tabs-pill">
                <button
                  type="button"
                  class="category-pill-btn"
                  :class="{ 'is-active': activeCategoryTab === 'all' }"
                  @click="handleCategoryTabChange('all')"
                >
                  <AppstoreOutlined class="pill-icon" />
                  <span>全部用例</span>
                  <span class="pill-count">{{ categoryCounts.all }}</span>
                </button>
                <button
                  type="button"
                  class="category-pill-btn pill-api"
                  :class="{ 'is-active': activeCategoryTab === 'api' }"
                  @click="handleCategoryTabChange('api')"
                >
                  <ApiOutlined class="pill-icon" />
                  <span>接口测试</span>
                  <span class="pill-count">{{ categoryCounts.api }}</span>
                </button>
                <button
                  type="button"
                  class="category-pill-btn pill-web"
                  :class="{ 'is-active': activeCategoryTab === 'web' }"
                  @click="handleCategoryTabChange('web')"
                >
                  <GlobalOutlined class="pill-icon" />
                  <span>Web UI</span>
                  <span class="pill-count">{{ categoryCounts.web }}</span>
                </button>
                <button
                  type="button"
                  class="category-pill-btn pill-mobile"
                  :class="{ 'is-active': activeCategoryTab === 'mobile' }"
                  @click="handleCategoryTabChange('mobile')"
                >
                  <MobileOutlined class="pill-icon" />
                  <span>APP 移动端</span>
                  <span class="pill-count">{{ categoryCounts.mobile }}</span>
                </button>
              </div>

              <!-- 仅在接口测试分类下，展示单接口 vs 场景链路的分流筛选 -->
              <div v-if="activeCategoryTab === 'api'" class="api-sub-category-pills">
                <button
                  type="button"
                  class="sub-pill-btn"
                  :class="{ 'is-active': apiSubFilter === 'all' }"
                  @click="apiSubFilter = 'all'"
                >
                  全部接口 ({{ apiCategoryCount }})
                </button>
                <button
                  type="button"
                  class="sub-pill-btn btn-scenario"
                  :class="{ 'is-active': apiSubFilter === 'scenario' }"
                  @click="apiSubFilter = 'scenario'"
                >
                  <ClusterOutlined /> 场景链路 ({{ apiScenarioCount }})
                </button>
                <button
                  type="button"
                  class="sub-pill-btn btn-single"
                  :class="{ 'is-active': apiSubFilter === 'single' }"
                  @click="apiSubFilter = 'single'"
                >
                  <ThunderboltOutlined /> 单接口 ({{ apiSingleCount }})
                </button>
              </div>
              <div class="category-bar-right">
                <a-button
                  v-if="activeCategoryTab === 'api'"
                  size="small"
                  type="link"
                  class="goto-workbench-link"
                  @click="router.push('/api-workbench')"
                >
                  <ArrowRightOutlined /> 接口资产库/工作台
                </a-button>
                <a-button size="small" type="text" :disabled="!canModifyCases" class="sub-tool-btn" @click="handleDownloadImportTemplate">
                  <DownloadOutlined /> {{ t('case.import_template') }}
                </a-button>
                <a-upload
                  :show-upload-list="false"
                  :before-upload="handleBatchImportBeforeUpload"
                  accept=".zip"
                  :disabled="!canModifyCases"
                >
                  <a-button size="small" type="text" :loading="importPreviewLoading" :disabled="!canModifyCases" class="sub-tool-btn">
                    <UploadOutlined /> {{ t('case.import_zip') }}
                  </a-button>
                </a-upload>
              </div>
            </div>

            <BatchOperationBar :selected-count="selectedRowKeys.length" @cancel="selectedRowKeys = []">
              <a-button size="small" @click="handleBatchExport">{{ t('case.export_csv') }}</a-button>
              <a-button size="small" @click="handleBatchExportZip">{{ t('case.export_zip') }}</a-button>
              <a-button size="small" :disabled="!canModifyCases" @click="openBatchMove">
                {{ t('case.batch_move') }}
              </a-button>
              <a-popconfirm
                :title="t('case.confirm_batch_delete', { count: selectedRowKeys.length })"
                :ok-text="t('common.delete')"
                :cancel-text="t('common.cancel')"
                @confirm="handleBatchDelete"
              >
                <a-button size="small" danger :disabled="!canModifyCases">{{ t('case.batch_delete') }}</a-button>
              </a-popconfirm>
            </BatchOperationBar>
            <a-table
              :columns="columns"
              :data-source="filteredCases"
              :loading="loading"
              row-key="id"
              size="middle"
              :pagination="{ pageSize: 20, showSizeChanger: true }"
              :scroll="cases.length ? { x: 1050 } : undefined"
              :row-selection="{ selectedRowKeys, columnWidth: 36, onChange: (keys: (string | number)[]) => (selectedRowKeys = keys as number[]) }"
            >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <div class="case-name-cell">
                  <div class="case-title-row">
                    <span class="case-type-badge" :class="`badge-${record.case_type}`">
                      <ApiOutlined v-if="isApiType(record.case_type)" />
                      <GlobalOutlined v-else-if="record.case_type === 'web'" />
                      <AndroidOutlined v-else-if="record.case_type === 'android'" />
                      <AppleOutlined v-else-if="record.case_type === 'ios'" />
                      <span>{{ caseTypeShortLabel(record.case_type) }}</span>
                    </span>
                    <span
                      class="case-link-title"
                      role="button"
                      tabindex="0"
                      :title="record.name"
                      @click="openDetail(record.id)"
                    >
                      {{ record.name }}
                    </span>
                  </div>
                  <div class="case-meta-row">
                    <code class="case-code-badge">{{ record.case_code }}</code>
                    <template v-if="isApiType(record.case_type)">
                      <span
                        v-if="record.case_mode === 'scenario' || record.is_scenario"
                        class="scenario-pipeline-tag"
                        :title="'多接口串联执行链路，共 ' + (record.step_count || 2) + ' 个步骤'"
                      >
                        <ClusterOutlined /> 场景链路 · {{ record.step_count || 2 }} 步
                      </span>
                      <span
                        v-else
                        class="single-api-tag"
                      >
                        单接口
                      </span>
                    </template>
                    <span v-if="getApiMethod(record)" class="method-tag" :class="`method-${getApiMethod(record)}`">
                      {{ getApiMethod(record) }}
                    </span>
                    <span v-if="getApiPath(record)" class="path-text" :title="getApiPath(record)">
                      {{ getApiPath(record) }}
                    </span>
                    <span v-if="record.automation_status === 'auto'" class="automation-chip">
                      <ThunderboltOutlined /> 自动化
                    </span>
                    <span v-if="record.ai_generated" class="ai-chip">
                      ✨ AI
                    </span>
                    <span v-if="cleanSummary(record)" class="summary-text" :title="cleanSummary(record)">
                      {{ cleanSummary(record) }}
                    </span>
                    <template v-if="record.tags && record.tags.length">
                      <span v-for="tag in record.tags.slice(0, 2)" :key="tag" class="tag-chip" @click.stop="quickFilterKeyword(tag)">
                        #{{ tag }}
                      </span>
                    </template>
                  </div>
                </div>
              </template>
              <template v-else-if="column.key === 'module'">
                <span>{{ moduleNameMap[record.module_id] ?? t('case.module_fallback', { id: record.module_id }) }}</span>
              </template>
              <template v-else-if="column.key === 'level_priority'">
                <div class="level-priority-cell">
                  <a-tag :color="priorityColor(record.priority)" class="priority-tag" @click.stop="quickFilterPriority(record.priority)">{{ record.priority }}</a-tag>
                  <span class="level-sub-text" @click.stop="quickFilterLevel(record.case_level)">{{ caseLevelLabel(record.case_level) }}</span>
                </div>
              </template>
              <template v-else-if="column.key === 'latest_run'">
                <div class="run-status-cell">
                  <template v-if="getLatestRun(record.id)">
                    <div class="run-badge-line">
                      <span
                        class="run-tag"
                        :class="`tag-${getLatestRun(record.id)?.status}`"
                      >
                        <CheckCircleOutlined v-if="getLatestRun(record.id)?.status === 'passed'" />
                        <CloseCircleOutlined v-else-if="getLatestRun(record.id)?.status === 'failed' || getLatestRun(record.id)?.status === 'error'" />
                        <SyncOutlined v-else-if="getLatestRun(record.id)?.status === 'running'" spin />
                        <span>{{ getLatestRun(record.id)?.status?.toUpperCase() }}</span>
                      </span>
                      <span v-if="getLatestRun(record.id)?.duration_ms" class="run-duration">
                        {{ formatDuration(getLatestRun(record.id)?.duration_ms) }}
                      </span>
                    </div>
                    <div class="run-date-line">
                      {{ formatShortTime(getLatestRun(record.id)?.created_at) }}
                    </div>
                  </template>
                  <span v-else class="run-tag tag-none">未执行</span>
                </div>
              </template>
              <template v-else-if="column.key === 'review_status'">
                <a-tag :color="reviewStatusColor(record.review_status)" class="review-status-tag">
                  {{ reviewStatusLabel(record.review_status) }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'action'">
                <a-space wrap size="small">
                  <a-button type="link" size="small" @click="openDetail(record.id)">{{ t('case.actions.detail') }}</a-button>
                  <a-tooltip :title="canModifyCases ? t('case.actions.edit') : t('case.msg.read_only_role')">
                    <a-button type="link" size="small" :disabled="!canModifyCases" @click="openEdit(asCase(record))">{{ t('case.actions.edit') }}</a-button>
                  </a-tooltip>
                  <a-tooltip :title="runDisabledTip(asCase(record))">
                    <a-button
                      type="link"
                      size="small"
                      :loading="runningId === record.id"
                      :disabled="!record.is_ready_for_execution || !canRunCases"
                      @click="handleRun(asCase(record))"
                    >
                      {{ t('case.actions.run') }}
                    </a-button>
                  </a-tooltip>
                  <a-dropdown>
                    <a-button type="link" size="small">
                      {{ t('common.more') }} <DownOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item key="copy" :disabled="!canModifyCases" @click="handleCopy(record.id)">{{ t('case.actions.copy') }}</a-menu-item>
                        <a-menu-item key="history" @click="openHistory(record.id)">
                          <HistoryOutlined /> {{ t('case.actions.history') }}
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item v-if="canSubmitReview(asCase(record))" key="submit-review" @click="handleWorkflow(asCase(record), 'submitReview')">
                          {{ t('case.actions.submit_review') }}
                        </a-menu-item>
                        <a-menu-item v-if="canApprove(asCase(record))" key="approve" @click="handleWorkflow(asCase(record), 'approve')">
                          {{ t('case.actions.approve') }}
                        </a-menu-item>
                        <a-menu-item v-if="canReject(asCase(record))" key="reject" @click="handleWorkflow(asCase(record), 'reject')">
                          {{ t('case.actions.reject') }}
                        </a-menu-item>
                        <a-menu-item v-if="canDeprecate(asCase(record))" key="deprecate" @click="handleWorkflow(asCase(record), 'deprecate')">
                          {{ t('case.actions.deprecate') }}
                        </a-menu-item>
                        <a-menu-item v-if="canReactivate(asCase(record))" key="reactivate" @click="handleWorkflow(asCase(record), 'reactivate')">
                          {{ t('case.actions.reactivate') }}
                        </a-menu-item>
                        <a-menu-divider />
                        <a-menu-item key="delete" :disabled="!canModifyCases" @click="confirmDelete(asCase(record))">
                          {{ t('case.actions.delete') }}
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-space>
              </template>
            </template>
            <template #emptyText>
              <div v-if="activeCategoryTab === 'web'" class="category-empty-guide">
                <GlobalOutlined class="empty-guide-icon" style="color: #722ed1" />
                <h4>当前暂无 Web UI 自动化用例</h4>
                <p>使用 Playwright 浏览器录制或低代码编排 Web 自动化端到端测试用例。</p>
                <a-button type="primary" size="small" :disabled="!canModifyCases" @click="openCreate('web')">
                  + 新建第一个 Web UI 用例
                </a-button>
              </div>
              <div v-else-if="activeCategoryTab === 'mobile'" class="category-empty-guide">
                <MobileOutlined class="empty-guide-icon" style="color: #389e0d" />
                <h4>当前暂无 APP 移动端自动化用例</h4>
                <p>连接真机设备或使用低代码录制器创建 Android / iOS 移动端测试。</p>
                <a-button type="primary" size="small" :disabled="!canModifyCases" @click="openCreate('android')">
                  + 新建第一个移动端用例
                </a-button>
              </div>
              <div v-else-if="activeCategoryTab === 'api'" class="category-empty-guide">
                <ApiOutlined class="empty-guide-icon" style="color: #1677ff" />
                <h4>当前暂无接口自动化用例</h4>
                <p>支持 HTTP、GraphQL、WebSocket 与 gRPC 多接口流转与自动化测试。</p>
                <a-button type="primary" size="small" :disabled="!canModifyCases" @click="openCreate('api')">
                  + 新建第一个接口用例
                </a-button>
              </div>
              <a-empty v-else :description="t('common.no_data')" />
            </template>
          </a-table>
          </a-card>
        </div>
      </div>
    </template>

    <a-result
      v-else
      status="info"
      :title="t('case.select_project_result')"
      :sub-title="t('case.select_project_subtitle')"
    >
      <template #extra>
        <a-space>
          <a-button
            v-if="projectOptions.length"
            type="primary"
            @click="handleSelectFirstProject"
          >
            {{ projectOptions[0]?.label ? t('case.enter_project', { name: projectOptions[0]?.label }) : t('case.select_project') }}
          </a-button>
          <a-button @click="router.push({ name: 'projects' })">
            {{ t('case.project_management') }}
          </a-button>
        </a-space>
      </template>
    </a-result>

    <CaseFormDrawer
      :open="drawerOpen"
      :module-id="selectedModuleId"
      :project-id="selectedProjectId"
      :edit-case="editingCase"
      :default-case-type="createCaseType"
      @close="drawerOpen = false"
      @saved="onSaved"
    />

    <WebCaseDrawer
      :open="webDrawerOpen"
      :module-id="selectedModuleId"
      :project-id="selectedProjectId"
      :edit-case="webEditingCase"
      @close="webDrawerOpen = false"
      @saved="onSaved"
    />

    <AndroidCaseDrawer
      :open="androidDrawerOpen"
      :module-id="selectedModuleId"
      :project-id="selectedProjectId"
      :edit-case="androidEditingCase"
      @close="androidDrawerOpen = false"
      @saved="onSaved"
    />

    <a-modal
      v-model:open="runModalOpen"
      :title="t('case.run_modal_title')"
      :ok-text="t('case.actions.run')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="runConfirming"
      @ok="confirmRun"
    >
      <p class="run-tip">{{ t('case.run_modal_tip') }}</p>
      <a-select
        v-model:value="(runEnvId as number | undefined)"
        :placeholder="t('case.no_environment')"
        allow-clear
        style="width: 100%"
        :options="runEnvOptions"
        :loading="runEnvLoading"
      />
    </a-modal>

    <a-modal
      v-model:open="batchMoveOpen"
      :title="t('case.batch_move_title')"
      :ok-text="t('case.confirm_move')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="batchMoveLoading"
      @ok="submitBatchMove"
    >
      <p class="run-tip">{{ t('case.batch_move_tip', { count: selectedRowKeys.length }) }}</p>
      <a-select
        v-model:value="(batchMoveTargetId as number | undefined)"
        :placeholder="t('case.select_target_module')"
        style="width: 100%"
        :options="moduleSelectOptions"
        show-search
        :filter-option="filterModuleOption"
      />
    </a-modal>

    <CaseHistoryDrawer
      :open="historyOpen"
      :case-id="historyCaseId"
      @close="historyOpen = false"
      @rolled="handleHistoryRolled"
    />

    <AIGenerateDrawer
      :open="aiDrawerOpen"
      :project-id="selectedProjectId"
      :module-id="selectedModuleId"
      :initial-dataset-id="aiGenerationContext.datasetId"
      :initial-dataset-version="aiGenerationContext.datasetVersion"
      :initial-mock-rule-ids="aiGenerationContext.mockRuleIds"
      @close="handleAIDrawerClose"
      @saved="onSaved"
    />

    <a-modal
      v-model:open="importPreviewOpen"
      :title="t('case.import_preview.title')"
      :ok-text="t('case.import_preview.confirm')"
      :cancel-text="t('common.cancel')"
      :confirm-loading="importConfirming"
      :ok-button-props="{ disabled: !importPreview?.valid_count }"
      width="720px"
      @ok="confirmBatchImport"
    >
      <template v-if="importPreview">
        <a-alert
          class="import-preview-alert"
          :type="importPreview.invalid_count ? 'warning' : 'success'"
          show-icon
          :message="t('case.import_preview.summary', {
            total: importPreview.total,
            valid: importPreview.valid_count,
            invalid: importPreview.invalid_count,
          })"
        />
        <a-table
          size="small"
          :pagination="false"
          :columns="importPreviewColumns"
          :data-source="importPreview.preview_cases"
          row-key="row"
          :scroll="{ x: 620 }"
        />
        <div v-if="importPreview.errors.length" class="import-error-list">
          <div class="import-error-title">{{ t('case.import_preview.errors') }}</div>
          <a-alert
            v-for="error in importPreview.errors.slice(0, 8)"
            :key="error"
            type="error"
            show-icon
            :message="error"
          />
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  DownOutlined,
  FileTextOutlined,
  HistoryOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  AppstoreOutlined,
  ApiOutlined,
  GlobalOutlined,
  MobileOutlined,
  AndroidOutlined,
  AppleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  FilterOutlined,
  DownloadOutlined,
  UploadOutlined,
  ClusterOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import { caseApi, environmentApi, projectApi, runApi, type RunDetailItem } from '@/api'
import type {
  AutomationStatus,
  CaseLevel,
  CasePriority,
  CaseQueryParams,
  CaseStatus,
  CaseSummaryItem,
  CaseType,
  ProjectItem,
  ReviewStatus,
} from '@/api'
import ModuleTree from '@/components/common/ModuleTree.vue'
import CaseFormDrawer from '@/components/common/CaseFormDrawer.vue'
import WebCaseDrawer from '@/views/case/WebCaseDrawer.vue'
import AndroidCaseDrawer from '@/views/case/AndroidCaseDrawer.vue'
import CaseHistoryDrawer from '@/views/case/CaseHistoryDrawer.vue'
import AIGenerateDrawer from '@/views/case/AIGenerateDrawer.vue'
import BatchOperationBar from '@/components/common/BatchOperationBar.vue'
import { canEditProjectByRole } from '@/utils/permissions'
import {
  buildCaseDetailLocation,
  buildCasesQuery,
  readCaseRouteSelection,
} from '@/utils/caseNavigation'
import { buildEnvironmentOptions, buildRunDetailLocation, buildRunPayload } from '@/utils/caseExecution'
import {
  caseWorkflowGuards,
  collectActiveFilters,
  countFlakyCases,
  countPendingReviews,
  filterCasesByLevel,
  flattenModules,
} from '@/utils/caseList'
import { useAuthStore } from '@/stores/auth'

type WorkflowAction = 'submitReview' | 'approve' | 'reject' | 'deprecate' | 'reactivate'
type FilterKey = 'keyword' | 'type' | 'priority' | 'level' | 'status' | 'review_status' | 'automation_status'
type FilterTag = { key: FilterKey; label: string }
type ImportPreview = {
  total: number
  valid_count: number
  invalid_count: number
  preview_cases: Array<{ row: number; name: string; case_type: string; priority: string; step_count: number }>
  errors: string[]
}
type ErrorLike = {
  message?: unknown
  response?: {
    data?: {
      detail?: unknown
    }
  }
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { t } = useI18n()

const caseTypeOptions = computed<Array<{ label: string; value: CaseType }>>(() => [
  { label: t('case.types.api'), value: 'api' },
  { label: t('case.types.graphql'), value: 'graphql' },
  { label: t('case.types.websocket'), value: 'websocket' },
  { label: t('case.types.grpc'), value: 'grpc' },
  { label: t('case.types.web'), value: 'web' },
  { label: t('case.types.android'), value: 'android' },
  { label: t('case.types.ios'), value: 'ios' },
])

const priorityOptions: Array<{ label: string; value: CasePriority }> = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
]

const statusOptions = computed<Array<{ label: string; value: CaseStatus }>>(() => [
  { label: t('case.statuses.draft'), value: 'draft' },
  { label: t('case.statuses.active'), value: 'active' },
  { label: t('case.statuses.deprecated'), value: 'deprecated' },
])

const reviewStatusOptions = computed<Array<{ label: string; value: ReviewStatus }>>(() => [
  { label: t('case.review_statuses.pending'), value: 'pending' },
  { label: t('case.review_statuses.approved'), value: 'approved' },
  { label: t('case.review_statuses.rejected'), value: 'rejected' },
])

const automationStatusOptions = computed<Array<{ label: string; value: AutomationStatus }>>(() => [
  { label: t('case.automation_statuses.manual'), value: 'manual' },
  { label: t('case.automation_statuses.semi_auto'), value: 'semi_auto' },
  { label: t('case.automation_statuses.auto'), value: 'auto' },
])

const projects = ref<ProjectItem[]>([])
const selectedProjectId = ref<number | null>(null)
const moduleNameMap = ref<Record<number, string>>({})
const cases = ref<CaseSummaryItem[]>([])
// a-table #bodyCell 的 record 类型是 Record<string, any>；本表数据源恒为 CaseSummaryItem
const asCase = (record: unknown) => record as CaseSummaryItem
const loading = ref(false)
const selectedModuleId = ref<number | null>(null)
const keyword = ref('')
const filterType = ref<CaseType | undefined>(undefined)
const filterPriority = ref<CasePriority | undefined>(undefined)
const filterLevel = ref<CaseLevel | undefined>(undefined)
const filterStatus = ref<CaseStatus | undefined>(undefined)
const filterReviewStatus = ref<ReviewStatus | undefined>(undefined)
const filterAutomationStatus = ref<AutomationStatus | undefined>(undefined)
const drawerOpen = ref(false)
const editingCase = ref<CaseSummaryItem | null>(null)
const createCaseType = ref<CaseType>('api')
const webDrawerOpen = ref(false)
const webEditingCase = ref<CaseSummaryItem | null>(null)
const androidDrawerOpen = ref(false)
const androidEditingCase = ref<CaseSummaryItem | null>(null)
const runningId = ref<number | null>(null)
const selectedRowKeys = ref<number[]>([])
const batchMoveOpen = ref(false)
const batchMoveTargetId = ref<number | null>(null)
const batchMoveLoading = ref(false)
const historyOpen = ref(false)
const historyCaseId = ref<number | null>(null)
const aiDrawerOpen = ref(false)
type AIGenerationContext = { datasetId: number | null; datasetVersion: number | null; mockRuleIds: number[] }
const pendingAiGeneration = ref<AIGenerationContext | null>(null)
const aiGenerationContext = ref<AIGenerationContext>({ datasetId: null, datasetVersion: null, mockRuleIds: [] })
const importPreviewOpen = ref(false)
const importPreviewLoading = ref(false)
const importConfirming = ref(false)
const pendingImportFile = ref<File | null>(null)
const importPreview = ref<ImportPreview | null>(null)

const runModalOpen = ref(false)
const runEnvId = ref<number | null>(null)
const runEnvOptions = ref<Array<{ label: string; value: number }>>([])
const runEnvLoading = ref(false)
const runConfirming = ref(false)
const pendingRunCase = ref<CaseSummaryItem | null>(null)

const columns = computed(() => [
  { title: t('case.columns.case'), key: 'name', minWidth: 420 },
  { title: t('case.columns.module'), key: 'module', width: 130 },
  { title: '用例分级', key: 'level_priority', width: 95, align: 'center' as const },
  { title: '最新执行', key: 'latest_run', width: 140 },
  { title: t('case.columns.review_status'), key: 'review_status', width: 90, align: 'center' as const },
  { title: t('case.columns.action'), key: 'action', width: 180, fixed: 'right' as const },
])

function formatShortTime(value?: string | null): string {
  if (!value) return ''
  return value.slice(5, 16).replace('T', ' ')
}

type CaseCategory = 'all' | 'api' | 'web' | 'mobile'
const activeCategoryTab = ref<CaseCategory>('all')
const showAdvancedFilters = ref(false)
const recentRuns = ref<RunDetailItem[]>([])

const categoryCounts = computed(() => {
  const all = cases.value.length
  let api = 0
  let web = 0
  let mobile = 0
  cases.value.forEach((c) => {
    if (['api', 'graphql', 'websocket', 'grpc'].includes(c.case_type)) api++
    else if (c.case_type === 'web') web++
    else if (['android', 'ios'].includes(c.case_type)) mobile++
  })
  return { all, api, web, mobile }
})

function handleCategoryTabChange(cat: CaseCategory) {
  activeCategoryTab.value = cat
  apiSubFilter.value = 'all'
}
function isApiType(type: string): boolean {
  return ['api', 'graphql', 'websocket', 'grpc'].includes(type)
}

function caseTypeShortLabel(type?: unknown): string {
  if (typeof type !== 'string') return ''
  if (type === 'api') return 'API'
  if (type === 'graphql') return 'GQL'
  if (type === 'websocket') return 'WS'
  if (type === 'grpc') return 'gRPC'
  if (type === 'web') return 'Web'
  if (type === 'android') return 'Android'
  if (type === 'ios') return 'iOS'
  return type.toUpperCase()
}

function getApiMethod(record: unknown): string {
  const c = record as CaseSummaryItem
  if (!isApiType(c?.case_type)) return ''
  if (c.case_type === 'graphql') return 'GRAPHQL'
  if (c.case_type === 'websocket') return 'WS'
  const summary = c.summary || ''
  const m = summary.match(/^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)/i)
  return m ? m[1].toUpperCase() : ''
}

function getApiPath(record: unknown): string {
  const c = record as CaseSummaryItem
  if (!isApiType(c?.case_type)) return ''
  const summary = c.summary || ''
  const parts = summary.split(' ')
  if (parts.length > 1 && (parts[1].startsWith('/') || parts[1].startsWith('http'))) {
    return parts[1]
  }
  return ''
}

function cleanSummary(record: unknown): string {
  const c = record as CaseSummaryItem
  const s = (c?.summary || '').trim()
  if (!s || s === c?.name) return ''
  return s
}

function getLatestRun(caseId: number): RunDetailItem | undefined {
  return recentRuns.value.find((r) => r.case_id === caseId)
}

function formatDuration(value?: number | null) {
  if (value == null) return ''
  return value < 1000 ? `${value}ms` : `${(value / 1000).toFixed(1)}s`
}

async function loadRecentRuns() {
  if (!selectedProjectId.value) {
    recentRuns.value = []
    return
  }
  try {
    const res = await runApi.list({ page_size: 100, project_id: selectedProjectId.value })
    recentRuns.value = res.items || []
  } catch {
    recentRuns.value = []
  }
}

const importPreviewColumns = computed(() => [
  { title: t('case.import_preview.columns.row'), dataIndex: 'row', key: 'row', width: 80 },
  { title: t('case.import_preview.columns.name'), dataIndex: 'name', key: 'name', width: 260 },
  { title: t('case.import_preview.columns.type'), dataIndex: 'case_type', key: 'case_type', width: 120 },
  { title: t('case.import_preview.columns.priority'), dataIndex: 'priority', key: 'priority', width: 100 },
  { title: t('case.import_preview.columns.steps'), dataIndex: 'step_count', key: 'step_count', width: 100 },
])

const projectOptions = computed(() =>
  projects.value.map((project) => ({ label: project.name, value: project.id })),
)

const currentProjectName = computed(() =>
  projects.value.find((project) => project.id === selectedProjectId.value)?.name ?? '-',
)

const moduleCount = computed(() => Object.keys(moduleNameMap.value).length)

const activeModuleName = computed(() =>
  selectedModuleId.value ? (moduleNameMap.value[selectedModuleId.value] ?? t('case.module_fallback', { id: selectedModuleId.value })) : t('common.all'),
)

const apiSubFilter = ref<'all' | 'scenario' | 'single'>('all')

const apiCategoryCases = computed(() => cases.value.filter((c) => isApiType(c.case_type)))
const apiCategoryCount = computed(() => apiCategoryCases.value.length)
const apiScenarioCount = computed(() =>
  apiCategoryCases.value.filter((c) => c.case_mode === 'scenario' || Boolean(c.is_scenario)).length,
)
const apiSingleCount = computed(() =>
  apiCategoryCases.value.filter((c) => c.case_mode !== 'scenario' && !c.is_scenario).length,
)

const filteredCases = computed(() => {
  let list = cases.value
  if (activeCategoryTab.value === 'api') {
    list = list.filter((c) => isApiType(c.case_type))
    if (apiSubFilter.value === 'scenario') {
      list = list.filter((c) => c.case_mode === 'scenario' || Boolean(c.is_scenario))
    } else if (apiSubFilter.value === 'single') {
      list = list.filter((c) => c.case_mode !== 'scenario' && !c.is_scenario)
    }
  } else if (activeCategoryTab.value === 'web') {
    list = list.filter((c) => c.case_type === 'web')
  } else if (activeCategoryTab.value === 'mobile') {
    list = list.filter((c) => ['android', 'ios'].includes(c.case_type))
  }
  return filterCasesByLevel(list, filterLevel.value)
})

const pendingReviewCount = computed(() => countPendingReviews(filteredCases.value))

const flakyCaseCount = computed(() => countFlakyCases(filteredCases.value))

const selectedProjectRole = computed(() =>
  projects.value.find((project) => project.id === selectedProjectId.value)?.current_user_role,
)
const canModifyCases = computed(() => canEditProjectByRole(auth.user?.role, selectedProjectRole.value))
const canApproveCases = canModifyCases
const canRunCases = canModifyCases
const caseCreateDisabledTip = computed(() => {
  if (!canModifyCases.value) return t('case.msg.read_only_role')
  if (!selectedModuleId.value) return t('case.msg.select_module_first')
  return t('case.new_case')
})

// 非空筛选收集在 utils/caseList；此处仅做 i18n 标签渲染
const filterTagLabelers: Record<FilterKey, (value: string) => string> = {
  keyword: (value) => t('case.filter_tags.keyword', { value }),
  type: (value) => t('case.filter_tags.type', { value: caseTypeLabel(value as CaseType) }),
  priority: (value) => t('case.filter_tags.priority', { value }),
  level: (value) => t('case.filter_tags.level', { value: caseLevelLabel(value as CaseLevel) }),
  status: (value) => t('case.filter_tags.status', { value: statusLabel(value as CaseStatus) }),
  review_status: (value) => t('case.filter_tags.review_status', { value: reviewStatusLabel(value as ReviewStatus) }),
  automation_status: (value) => t('case.filter_tags.automation_status', { value: automationStatusLabel(value as AutomationStatus) }),
}

const activeFilterTags = computed<FilterTag[]>(() =>
  collectActiveFilters({
    keyword: keyword.value,
    type: filterType.value,
    priority: filterPriority.value,
    level: filterLevel.value,
    status: filterStatus.value,
    review_status: filterReviewStatus.value,
    automation_status: filterAutomationStatus.value,
  }).map(({ key, value }) => ({ key, label: filterTagLabelers[key](value) })),
)

function filterModuleOption(input: string, option?: { label?: unknown }) {
  return String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
}

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error !== null) {
    const typed = error as ErrorLike
    if (typeof typed.response?.data?.detail === 'string') return typed.response.data.detail
    if (typeof typed.message === 'string') return typed.message
  }
  return fallback
}

const moduleSelectOptions = computed(() =>
  Object.entries(moduleNameMap.value).map(([id, name]) => ({
    value: Number(id),
    label: name,
  })),
)


function caseTypeLabel(type: CaseType) {
  return caseTypeOptions.value.find((item) => item.value === type)?.label ?? type
}


function caseLevelLabel(level: CaseLevel) {
  return {
    smoke: t('case.levels.smoke'),
    core: t('case.levels.core'),
    regression: t('case.levels.regression'),
    extended: t('case.levels.extended'),
  }[level]
}

function priorityColor(priority: CasePriority) {
  return {
    P0: 'red',
    P1: 'orange',
    P2: 'gold',
    P3: 'default',
  }[priority]
}

function reviewStatusLabel(status: ReviewStatus) {
  return {
    pending: t('case.review_statuses.pending'),
    approved: t('case.review_statuses.approved'),
    rejected: t('case.review_statuses.rejected'),
  }[status]
}

function reviewStatusColor(status: ReviewStatus) {
  return {
    pending: 'processing',
    approved: 'success',
    rejected: 'error',
  }[status]
}

function statusLabel(status: CaseStatus) {
  return {
    draft: t('case.statuses.draft'),
    active: t('case.statuses.active'),
    deprecated: t('case.statuses.deprecated'),
  }[status]
}


function automationStatusLabel(status: AutomationStatus) {
  return {
    manual: t('case.automation_statuses.manual'),
    semi_auto: t('case.automation_statuses.semi_auto'),
    auto: t('case.automation_statuses.auto'),
  }[status]
}



const workflowAbility = computed(() => ({ canModify: canModifyCases.value, canApprove: canApproveCases.value }))

function canSubmitReview(testCase: CaseSummaryItem) {
  return caseWorkflowGuards(testCase, workflowAbility.value).submitReview
}

function canApprove(testCase: CaseSummaryItem) {
  return caseWorkflowGuards(testCase, workflowAbility.value).approve
}

function canReject(testCase: CaseSummaryItem) {
  return caseWorkflowGuards(testCase, workflowAbility.value).reject
}

function canDeprecate(testCase: CaseSummaryItem) {
  return caseWorkflowGuards(testCase, workflowAbility.value).deprecate
}

function canReactivate(testCase: CaseSummaryItem) {
  return caseWorkflowGuards(testCase, workflowAbility.value).reactivate
}

function runDisabledTip(testCase: CaseSummaryItem) {
  if (!canRunCases.value) return t('case.msg.read_only_role')
  return testCase.is_ready_for_execution ? t('case.actions.run') : t('case.detail.run_disabled_tooltip')
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch (error: unknown) {
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      projects.value = [
        { id: 1, name: 'LexGuard Mobile Clean' } as unknown as ProjectItem,
        { id: 2, name: 'ATP 移动端核心业务' } as unknown as ProjectItem,
      ]
      if (!selectedProjectId.value) {
        selectedProjectId.value = 1
        await handleProjectChange(1)
      }
      return
    }
    message.error(errorMessage(error, t('case.msg.load_projects_failed')))
    projects.value = []
  }
}

async function loadModules() {
  if (!selectedProjectId.value) {
    moduleNameMap.value = {}
    return
  }

  try {
    const tree = await projectApi.getModules(selectedProjectId.value)
    moduleNameMap.value = flattenModules(tree)
    if (selectedModuleId.value && !moduleNameMap.value[selectedModuleId.value]) {
      selectedModuleId.value = null
    }
  } catch (error: unknown) {
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      moduleNameMap.value = { 1: '用户鉴权', 2: '结算服务', 3: '商品中心' }
      return
    }
    moduleNameMap.value = {}
    message.error(errorMessage(error, t('case.msg.load_modules_failed')))
  }
}

async function loadCases() {
  if (!selectedProjectId.value) {
    cases.value = []
    return
  }

  loading.value = true
  try {
    const params: CaseQueryParams = {
      project_id: selectedProjectId.value,
      module_id: selectedModuleId.value ?? undefined,
      case_type: filterType.value,
      priority: filterPriority.value,
      status: filterStatus.value,
      review_status: filterReviewStatus.value,
      automation_status: filterAutomationStatus.value,
      keyword: keyword.value.trim() || undefined,
    }
    cases.value = await caseApi.list(params)
    void loadRecentRuns()
  } catch (error: unknown) {
    if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA === 'true') {
      cases.value = [
        {
          id: 101,
          name: '手机验证码登录流程鉴权校验',
          case_type: 'android',
          priority: 'P0',
          status: 'active',
          review_status: 'approved',
          automation_status: 'automated',
          module_id: 1,
          module_name: '用户鉴权',
          updated_at: new Date().toISOString(),
        },
        {
          id: 102,
          name: '电商下单金额计算与促销优惠券抵扣校验',
          case_type: 'api',
          priority: 'P0',
          status: 'active',
          review_status: 'approved',
          automation_status: 'automated',
          module_id: 2,
          module_name: '结算服务',
          updated_at: new Date(Date.now() - 3600000).toISOString(),
        },
        {
          id: 103,
          name: '商品列表页面翻页与条件组合筛选',
          case_type: 'web',
          priority: 'P1',
          status: 'active',
          review_status: 'pending',
          automation_status: 'manual',
          module_id: 3,
          module_name: '商品中心',
          updated_at: new Date(Date.now() - 7200000).toISOString(),
        },
      ] as unknown as CaseSummaryItem[]
      return
    }
    message.error(errorMessage(error, t('case.msg.load_cases_failed')))
    cases.value = []
  } finally {
    loading.value = false
  }
}

function syncRoute() {
  const generationContext = pendingAiGeneration.value
  const query = buildCasesQuery({
    projectId: selectedProjectId.value,
    moduleId: selectedModuleId.value,
    keyword: keyword.value,
    reviewStatus: filterReviewStatus.value,
    aiGenerate: !!generationContext,
    aiDatasetId: generationContext?.datasetId,
    aiDatasetVersion: generationContext?.datasetVersion,
    aiMockRuleIds: generationContext?.mockRuleIds,
  })
  const {
    projectId: currentProjectId,
    moduleId: currentModuleId,
    keyword: currentKeyword,
    reviewStatus: currentReviewStatus,
  } = readCaseRouteSelection(route)
  if (
    currentProjectId === selectedProjectId.value
    && currentModuleId === selectedModuleId.value
    && currentKeyword === (keyword.value.trim() || undefined)
    && currentReviewStatus === filterReviewStatus.value
  ) {
    return
  }

  void router.replace({ name: 'cases', query })
}

function replaceRouteWithoutAIGeneration() {
  const query = buildCasesQuery({
    projectId: selectedProjectId.value,
    moduleId: selectedModuleId.value,
    keyword: keyword.value,
    reviewStatus: filterReviewStatus.value,
  })
  void router.replace({ name: 'cases', query })
}

function openPendingAIGeneration() {
  if (!pendingAiGeneration.value || !selectedModuleId.value) return
  aiGenerationContext.value = {
    datasetId: pendingAiGeneration.value.datasetId,
    datasetVersion: pendingAiGeneration.value.datasetVersion,
    mockRuleIds: [...pendingAiGeneration.value.mockRuleIds],
  }
  pendingAiGeneration.value = null
  aiDrawerOpen.value = true
  replaceRouteWithoutAIGeneration()
}

function clearPendingAiGeneration() {
  pendingAiGeneration.value = null
  aiGenerationContext.value = { datasetId: null, datasetVersion: null, mockRuleIds: [] }
  replaceRouteWithoutAIGeneration()
}

function handleAIDrawerClose() {
  aiDrawerOpen.value = false
  aiGenerationContext.value = { datasetId: null, datasetVersion: null, mockRuleIds: [] }
}

async function applyRouteSelection(useDefaultProject = false) {
  const {
    projectId: routeProjectId,
    moduleId: routeModuleId,
    keyword: routeKeyword,
    reviewStatus: routeReviewStatus,
    aiGenerate: routeAIGenerate,
    aiDatasetId: routeAIDatasetId,
    aiDatasetVersion: routeAIDatasetVersion,
    aiMockRuleIds: routeAIMockRuleIds,
  } = readCaseRouteSelection(route)
  const fallbackProjectId = useDefaultProject ? (projects.value[0]?.id ?? null) : selectedProjectId.value
  const nextProjectId = routeProjectId ?? fallbackProjectId
  const projectChanged = nextProjectId !== selectedProjectId.value

  selectedProjectId.value = nextProjectId
  keyword.value = routeKeyword ?? ''
  filterReviewStatus.value = routeReviewStatus
  pendingAiGeneration.value = routeAIGenerate
    ? { datasetId: routeAIDatasetId, datasetVersion: routeAIDatasetVersion, mockRuleIds: routeAIMockRuleIds }
    : null

  if (projectChanged) {
    selectedModuleId.value = null
    await loadModules()
  }

  if (!selectedProjectId.value) {
    cases.value = []
    return
  }

  if (!projectChanged && Object.keys(moduleNameMap.value).length === 0) {
    await loadModules()
  }

  selectedModuleId.value = routeModuleId && moduleNameMap.value[routeModuleId] ? routeModuleId : null
  await loadCases()

  if (pendingAiGeneration.value && selectedModuleId.value) {
    openPendingAIGeneration()
  }

  if (!routeProjectId && selectedProjectId.value) {
    syncRoute()
  }
}

// a-select @change 的参数类型是 SelectValue；本列选项 value 恒为 number（allow-clear 时为 undefined）
function handleProjectChange(projectId: unknown) {
  selectedProjectId.value = typeof projectId === 'number' ? projectId : null
  selectedModuleId.value = null
  pendingAiGeneration.value = null
  aiGenerationContext.value = { datasetId: null, datasetVersion: null, mockRuleIds: [] }
  syncRoute()
}

function handleSelectFirstProject() {
  if (projectOptions.value.length) {
    const firstOption = projectOptions.value[0]
    if (firstOption && typeof firstOption.value === 'number') {
      handleProjectChange(firstOption.value)
    }
  }
}
function onModuleSelect(moduleId: number | null) {
  selectedModuleId.value = moduleId
  if (moduleId && pendingAiGeneration.value) {
    openPendingAIGeneration()
    return
  }
  syncRoute()
}

function clearModuleFilter() {
  selectedModuleId.value = null
  syncRoute()
}

async function refreshCurrentProject() {
  await loadProjects()
  await loadModules()
  await loadCases()
}

function handleSearch() {
  void loadCases()
  syncRoute()
}

function clearFilter(key: FilterKey) {
  if (key === 'keyword') keyword.value = ''
  if (key === 'type') filterType.value = undefined
  if (key === 'priority') filterPriority.value = undefined
  if (key === 'level') filterLevel.value = undefined
  if (key === 'status') filterStatus.value = undefined
  if (key === 'review_status') filterReviewStatus.value = undefined
  if (key === 'automation_status') filterAutomationStatus.value = undefined
  void loadCases()
  syncRoute()
}

function handleResetFilters() {
  keyword.value = ''
  filterType.value = undefined
  filterPriority.value = undefined
  filterLevel.value = undefined
  filterStatus.value = undefined
  filterReviewStatus.value = undefined
  filterAutomationStatus.value = undefined
  void loadCases()
  syncRoute()
}

function resolveActiveModuleId(): number | null {
  if (selectedModuleId.value) return selectedModuleId.value
  const firstId = Object.keys(moduleNameMap.value)[0]
  if (firstId) {
    selectedModuleId.value = Number(firstId)
    return Number(firstId)
  }
  return null
}

function openCreate(type: CaseType) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  resolveActiveModuleId()
  if (!selectedModuleId.value) {
    message.warning(t('case.msg.select_module_first'))
    return
  }

  if (type === 'web') {
    webEditingCase.value = null
    webDrawerOpen.value = true
  } else if (type === 'android') {
    androidEditingCase.value = null
    androidDrawerOpen.value = true
  } else {
    editingCase.value = null
    createCaseType.value = type
    drawerOpen.value = true
  }
}
function openAiGenerate() {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  resolveActiveModuleId()
  aiDrawerOpen.value = true
}

function quickFilterPriority(p: CasePriority) {
  filterPriority.value = p
  void loadCases()
}

function quickFilterLevel(lvl: CaseLevel) {
  filterLevel.value = lvl
  void loadCases()
}

function quickFilterKeyword(kw: string) {
  keyword.value = kw
  void loadCases()
}


async function openEdit(testCase: CaseSummaryItem) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  try {
    const detail = await caseApi.get(testCase.id)
    if (testCase.case_type === 'web') {
      webEditingCase.value = detail
      webDrawerOpen.value = true
    } else if (testCase.case_type === 'android') {
      androidEditingCase.value = detail
      androidDrawerOpen.value = true
    } else {
      editingCase.value = detail
      drawerOpen.value = true
    }
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.load_failed') || '加载用例详情失败'))
  }
}

function openDetail(caseId: number) {
  void router.push(buildCaseDetailLocation(caseId, {
    projectId: selectedProjectId.value,
    moduleId: selectedModuleId.value,
  }))
}

function onSaved() {
  void loadCases()
}

async function handleRun(testCase: CaseSummaryItem) {
  if (!canRunCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  if (!selectedProjectId.value) {
    return
  }

  pendingRunCase.value = testCase
  runEnvId.value = null
  runModalOpen.value = true
  runEnvLoading.value = true
  try {
    const environments = await environmentApi.list(selectedProjectId.value)
    runEnvOptions.value = buildEnvironmentOptions(environments)
  } catch {
    runEnvOptions.value = []
    message.warning(t('case.msg.load_env_failed'))
  } finally {
    runEnvLoading.value = false
  }
}

async function confirmRun() {
  const testCase = pendingRunCase.value
  if (!testCase) {
    return
  }

  runConfirming.value = true
  runningId.value = testCase.id
  try {
    const run = await caseApi.run(testCase.id, buildRunPayload(runEnvId.value))
    runModalOpen.value = false
    message.success(t('case.msg.run_started'))
    void router.push(buildRunDetailLocation(run.id))
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.run_failed')))
  } finally {
    runConfirming.value = false
    runningId.value = null
  }
}

async function handleCopy(caseId: number) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  try {
    const copied = await caseApi.copy(caseId)
    message.success(t('case.msg.copied', { code: copied.case_code }))
    await loadCases()
    openDetail(copied.id)
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.copy_failed')))
  }
}

async function handleWorkflow(testCase: CaseSummaryItem, action: WorkflowAction) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  try {
    switch (action) {
      case 'submitReview':
        await caseApi.submitReview(testCase.id)
        message.success(t('case.msg.submit_review_done'))
        break
      case 'approve':
        await caseApi.approve(testCase.id)
        message.success(t('case.msg.approve_done'))
        break
      case 'reject':
        await caseApi.reject(testCase.id)
        message.success(t('case.msg.reject_done'))
        break
      case 'deprecate':
        await caseApi.deprecate(testCase.id)
        message.success(t('case.msg.deprecate_done'))
        break
      case 'reactivate':
        await caseApi.reactivate(testCase.id)
        message.success(t('case.msg.reactivate_done'))
        break
    }
    await loadCases()
  } catch (error: unknown) {
    message.error(errorMessage(error, t('case.msg.workflow_failed')))
  }
}

function confirmDelete(testCase: CaseSummaryItem) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  Modal.confirm({
    title: t('case.msg.delete_title', { name: testCase.name }),
    content: t('case.msg.delete_content'),
    okText: t('common.delete'),
    cancelText: t('common.cancel'),
    okType: 'danger',
    async onOk() {
      await caseApi.delete(testCase.id)
      message.success(t('case.msg.deleted'))
      await loadCases()
    },
  })
}

async function handleBatchDelete() {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  if (!selectedRowKeys.value.length) return
  try {
    const result = await caseApi.batchDelete(selectedRowKeys.value)
    message.success(t('case.msg.batch_delete_success', { processed: result.processed, requested: result.requested }))
    selectedRowKeys.value = []
    await loadCases()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.batch_delete_failed')))
  }
}

async function handleBatchExport() {
  if (!selectedRowKeys.value.length) return
  try {
    const blob = await caseApi.batchExportCsv(selectedRowKeys.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `cases-export-${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(t('case.msg.export_success', { count: selectedRowKeys.value.length }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.export_failed')))
  }
}

async function handleBatchExportZip() {
  if (!selectedRowKeys.value.length) return
  try {
    const blob = await caseApi.batchExportZip(selectedRowKeys.value)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `cases-export-${new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')}.zip`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(t('case.msg.export_zip_success', { count: selectedRowKeys.value.length }))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.export_failed')))
  }
}

async function handleDownloadImportTemplate() {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  try {
    const blob = await caseApi.downloadImportTemplate()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'case-import-template.zip'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success(t('case.msg.template_downloaded'))
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.template_download_failed')))
  }
}

function handleBatchImportBeforeUpload(file: File) {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return false
  }
  resolveActiveModuleId()
  if (!selectedModuleId.value) {
    message.warning(t('case.msg.select_target_module_first'))
    return false
  }
  ;(async () => {
    importPreviewLoading.value = true
    try {
      importPreview.value = await caseApi.previewImportZip(file)
      pendingImportFile.value = file
      importPreviewOpen.value = true
    } catch (e: unknown) {
      message.error(errorMessage(e, t('case.msg.import_preview_failed')))
    } finally {
      importPreviewLoading.value = false
    }
  })()
  return false
}

async function confirmBatchImport() {
  if (!pendingImportFile.value || !selectedModuleId.value) {
    return
  }
  importConfirming.value = true
  try {
    const result = await caseApi.batchImportZip(pendingImportFile.value, selectedModuleId.value)
    if (result.errors.length) {
      message.warning(t('case.msg.import_done_with_skips', { imported: result.imported, skipped: result.skipped_count }))
    } else {
      message.success(t('case.msg.import_success', { imported: result.imported }))
    }
    importPreviewOpen.value = false
    pendingImportFile.value = null
    importPreview.value = null
    await loadCases()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.import_failed')))
  } finally {
    importConfirming.value = false
  }
}

function openBatchMove() {
  if (!canModifyCases.value) {
    message.warning(t('case.msg.read_only_role'))
    return
  }
  if (!selectedRowKeys.value.length) return
  batchMoveTargetId.value = null
  batchMoveOpen.value = true
}

async function submitBatchMove() {
  if (!batchMoveTargetId.value) {
    message.warning(t('case.msg.select_target_module_first'))
    return
  }
  batchMoveLoading.value = true
  try {
    const result = await caseApi.batchMove(selectedRowKeys.value, batchMoveTargetId.value)
    message.success(t('case.msg.move_success', { processed: result.processed, requested: result.requested }))
    batchMoveOpen.value = false
    selectedRowKeys.value = []
    await loadCases()
  } catch (e: unknown) {
    message.error(errorMessage(e, t('case.msg.move_failed')))
  } finally {
    batchMoveLoading.value = false
  }
}

function openHistory(caseId: number) {
  historyCaseId.value = caseId
  historyOpen.value = true
}

function handleHistoryRolled() {
  void loadCases()
}

watch(
  () => [route.params.projectId, route.query.project_id, route.query.module_id, route.query.keyword, route.query.review_status].join('|'),
  () => {
    void applyRouteSelection(false)
  },
)

onMounted(async () => {
  await loadProjects()
  await applyRouteSelection(true)
})
</script>

<style scoped>
.case-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.case-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 48px;
  padding: 0 16px;
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.toolbar-icon {
  color: var(--c-primary);
  font-size: 16px;
}
.toolbar-title {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  color: var(--c-text);
  white-space: nowrap;
}
.toolbar-divider {
  color: var(--c-text-tertiary);
  font-size: 13px;
}
.toolbar-subtitle {
  color: var(--c-text-secondary);
  font-size: 12px;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.case-bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
.case-bento-tile {
  background: var(--c-bg-elevated);
  border: 1px solid var(--c-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.2s ease;
}
.case-bento-tile:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--c-border-strong);
}
.tile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.tile-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.tile-value {
  font-size: 26px;
  font-weight: 700;
  font-family: 'JetBrains Mono', var(--font-sans);
  color: var(--c-text);
  line-height: 1.15;
  margin: 2px 0;
}
.tile-value.value-warn {
  color: var(--c-warning);
}
.tile-value.value-danger {
  color: var(--c-error);
}
.tile-footer {
  font-size: 11px;
  color: var(--c-text-tertiary);
  display: flex;
  align-items: center;
  gap: 4px;
}
.tile-footer b {
  color: var(--c-text);
  font-weight: 600;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 300px) minmax(0, 1fr);
  gap: 18px;
  align-items: stretch;
  min-height: 580px;
}

.side-panel {
  min-width: 0;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-lg);
  padding: 16px;
  overflow-y: auto;
  background: var(--c-bg-elevated);
  box-shadow: var(--shadow-sm);
}

.side-panel :deep(.tree-header) {
  margin-bottom: 12px;
  padding: 2px 2px 12px;
  border-bottom: 1px solid var(--c-border);
}

.side-panel :deep(.ant-tree) {
  background: transparent;
  color: var(--c-text);
}
.side-panel :deep(.ant-tree .ant-tree-node-content-wrapper) {
  border-radius: var(--radius-sm);
  padding: 3px 6px;
  transition: all 0.16s ease;
}
.side-panel :deep(.ant-tree .ant-tree-node-content-wrapper:hover) {
  background: var(--c-bg-subtle);
}
.side-panel :deep(.ant-tree .ant-tree-node-selected) {
  background: var(--c-primary-soft) !important;
  color: var(--c-primary) !important;
  font-weight: 600;
}
.side-panel :deep(.ant-tree-switcher) {
  line-height: 28px;
}
.main-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.toolbar-card,
.table-card {
  border-radius: var(--radius-lg);
  border: 1px solid var(--c-border);
  box-shadow: var(--shadow-sm);
  background: var(--c-bg-elevated);
}

.toolbar-card :deep(.ant-card-body) {
  padding: 14px 18px;
}

.table-card :deep(.ant-card-body) {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-main {
  flex: 1 1 960px;
  min-width: 0;
}

.toolbar-actions {
  flex: 0 0 auto;
  margin-left: auto;
}

.toolbar-actions :deep(.ant-space) {
  justify-content: flex-end;
}

.active-filter-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.ai-route-notice {
  margin-bottom: 16px;
  border-radius: var(--radius-md);
}

.active-filter-label {
  color: var(--c-text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.case-link {
  padding-inline: 0;
  font-weight: 600;
  font-size: 13px;
  color: var(--c-primary);
}

.case-link:hover {
  color: var(--c-primary-hover);
}

.case-summary {
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.case-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.review-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.review-cell :deep(.ant-btn-link) {
  height: auto;
  padding: 0;
  font-size: 12px;
}

.run-tip {
  margin-bottom: 12px;
  color: var(--c-text-secondary);
  font-size: 12px;
}

.import-preview-alert {
  margin-bottom: 12px;
}

.import-error-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.filter-primary-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-advanced-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding: 8px 12px;
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px dashed var(--c-border, #e2e8f0);
  border-radius: 6px;
}

.adv-filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.case-category-tabs-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-bottom: 1px solid var(--c-border);
  background: var(--c-bg-subtle, #f8fafc);
  flex-wrap: wrap;
  gap: 10px;
}

.category-tabs-pill {
  display: inline-flex;
  align-items: center;
  background: var(--c-bg-muted, #f1f5f9);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 3px;
  gap: 3px;
}

.category-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  height: 28px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--c-text-secondary, #64748b);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.category-pill-btn:hover {
  color: var(--c-text, #1e293b);
}

.category-pill-btn.is-active {
  background: var(--c-bg-elevated, #fff);
  color: var(--c-text, #1e293b);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04);
}

.category-pill-btn.pill-api.is-active { color: #1677ff; }
.category-pill-btn.pill-web.is-active { color: #722ed1; }
.category-pill-btn.pill-mobile.is-active { color: #389e0d; }

.pill-icon {
  font-size: 13px;
}

.pill-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  font-size: 10.5px;
  font-weight: 700;
  background: var(--c-border, #e2e8f0);
  color: var(--c-text-tertiary, #94a3b8);
}

.category-pill-btn.is-active .pill-count {
  background: var(--c-primary-soft, #e6f4ff);
  color: var(--c-primary, #1677ff);
}

.category-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sub-tool-btn {
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 8px;
  height: 28px;
}

.sub-tool-btn:hover {
  color: var(--c-primary, #1677ff);
}

.case-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 2px 0;
}

.case-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  min-width: 0;
  line-height: 1.4;
}

.case-type-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 5px;
  font-size: 10.5px;
  font-weight: 700;
  border-radius: 3px;
  border: 1px solid transparent;
  flex-shrink: 0;
  white-space: nowrap;
}

.badge-api, .badge-graphql, .badge-websocket, .badge-grpc {
  background: #e6f4ff;
  color: #0958d9;
  border-color: #91caff;
}

.badge-web {
  background: #f9f0ff;
  color: #722ed1;
  border-color: #d3adf7;
}

.badge-android, .badge-ios {
  background: #f6ffed;
  color: #389e0d;
  border-color: #b7eb8f;
}

.case-link-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--c-text, #1e293b);
  cursor: pointer;
  transition: color 0.15s ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 1;
  padding: 0;
  margin: 0;
}

.case-link-title:hover {
  color: var(--c-primary, #1677ff);
  text-decoration: underline;
}

.case-code-badge {
  font-size: 11px;
  font-family: monospace;
  color: var(--c-text-tertiary, #94a3b8);
  background: var(--c-bg-subtle, #f1f5f9);
  padding: 1px 5px;
  border-radius: 3px;
  border: 1px solid var(--c-border, #e2e8f0);
  white-space: nowrap;
  flex-shrink: 0;
}

.case-meta-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  font-size: 11.5px;
  min-width: 0;
}

.method-tag {
  display: inline-block;
  padding: 1px 5px;
  font-size: 10px;
  font-weight: 700;
  border-radius: 3px;
  flex-shrink: 0;
  white-space: nowrap;
}

.method-GET { background: #e6f4ff; color: #0958d9; }
.method-POST { background: #f6ffed; color: #389e0d; }
.method-PUT { background: #fff7e6; color: #d46b08; }
.method-DELETE { background: #fff1f0; color: #cf1322; }

.path-text {
  font-size: 11px;
  font-family: monospace;
  color: var(--c-text-secondary, #64748b);
  background: var(--c-bg-subtle, #f8fafc);
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
  white-space: nowrap;
}

.summary-text {
  font-size: 11.5px;
  color: var(--c-text-tertiary, #94a3b8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.automation-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 10px;
  font-weight: 600;
  color: #1677ff;
  background: #e6f4ff;
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
  white-space: nowrap;
}

.ai-chip {
  font-size: 10px;
  font-weight: 600;
  color: #722ed1;
  background: #f9f0ff;
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
  white-space: nowrap;
}

.tag-chip {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
  background: var(--c-bg-muted, #f1f5f9);
  padding: 1px 4px;
  border-radius: 3px;
  flex-shrink: 0;
  white-space: nowrap;
}

.tag-chip-more {
  font-size: 10px;
  color: var(--c-text-tertiary, #94a3b8);
  flex-shrink: 0;
}

.run-status-cell {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  white-space: nowrap;
}

.run-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.tag-passed { background: #f6ffed; color: #389e0d; border: 1px solid #b7eb8f; }
.tag-failed { background: #fff1f0; color: #cf1322; border: 1px solid #ffa39e; }
.tag-running { background: #fffbe6; color: #d46b08; border: 1px solid #ffe58f; }
.tag-none { color: var(--c-text-tertiary, #94a3b8); font-size: 11px; }

.run-duration {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  font-family: monospace;
  white-space: nowrap;
}
.case-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  line-height: 1.4;
}

.case-link-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--c-text, #1e293b);
  cursor: pointer;
  transition: color 0.15s ease;
  line-height: 1.35;
  padding: 0;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-link-title:hover {
  color: var(--c-primary, #1677ff);
  text-decoration: underline;
}

.level-priority-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.priority-tag {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  padding: 0 6px;
}

.level-sub-text {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
}

.run-badge-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.run-date-line {
  font-size: 11px;
  color: var(--c-text-tertiary, #94a3b8);
  margin-top: 2px;
  font-family: monospace;
}

.review-status-tag {
  margin: 0;
  font-size: 11px;
}

.module-text {
  display: block;
  font-size: 12px;
  color: var(--c-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-card :deep(.ant-table-selection-column) {
  width: 36px !important;
  min-width: 36px !important;
  max-width: 36px !important;
  padding-left: 12px !important;
  padding-right: 0 !important;
  text-align: center;
}

.table-card :deep(.ant-table-tbody > tr > td:nth-child(2)),
.table-card :deep(.ant-table-thead > tr > th:nth-child(2)) {
  padding-left: 6px !important;
}

.import-error-title {
  color: var(--c-text-secondary);
  font-size: 12px;
}

@media (max-width: 1024px) {
  .case-bento-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 960px) {
  .page-header,
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace {
    grid-template-columns: 1fr;
  }
  .toolbar-main,
  .toolbar-actions {
    flex: 1 1 auto;
    margin-left: 0;
  }
}

@media (max-width: 640px) {
  .page-header :deep(.ant-space),
  .toolbar-main :deep(.ant-space),
  .toolbar-actions :deep(.ant-space) {
    width: 100%;
  }

  .page-header :deep(.ant-space-item),
  .toolbar-main :deep(.ant-space-item),
  .toolbar-actions :deep(.ant-space-item) {
    max-width: 100%;
  }

  .page-header :deep(.ant-select),
  .page-header :deep(.ant-btn),
  .toolbar-main :deep(.ant-input-search),
  .toolbar-main :deep(.ant-select),
  .toolbar-main :deep(.ant-btn),
  .toolbar-actions :deep(.ant-dropdown-trigger),
  .toolbar-actions :deep(.ant-btn) {
    width: 100% !important;
  }

  .side-panel {
    max-height: 320px;
  }

  .case-bento-grid {
    grid-template-columns: 1fr;
  }
  .table-card {
    overflow: hidden;
  }
}
.category-empty-guide {
  padding: 36px 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.empty-guide-icon {
  font-size: 36px;
  margin-bottom: 4px;
}

.category-empty-guide h4 {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text);
  margin: 0;
}

.category-empty-guide p {
  font-size: 13px;
  color: var(--c-text-secondary);
  max-width: 460px;
  margin: 0 0 8px;
}

.priority-tag,
.level-sub-text {
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.priority-tag:hover,
.level-sub-text:hover {
  opacity: 0.8;
  text-decoration: underline;
}
.api-sub-category-pills {
  display: inline-flex;
  align-items: center;
  background: var(--c-bg-subtle, #f0f2f5);
  padding: 2px 4px;
  border-radius: 8px;
  margin-left: 12px;
  gap: 2px;
}
.sub-pill-btn {
  border: none;
  background: transparent;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  color: var(--c-text-secondary, #666);
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.sub-pill-btn:hover {
  color: var(--c-text, #14142b);
}
.sub-pill-btn.is-active {
  background: #ffffff;
  color: var(--c-primary, #5850ec);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}
.sub-pill-btn.btn-scenario.is-active {
  color: #722ed1;
}
.sub-pill-btn.btn-single.is-active {
  color: #0958d9;
}
.scenario-pipeline-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 7px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
  color: #722ed1;
  background: rgba(114, 46, 209, 0.08);
  border: 1px solid rgba(114, 46, 209, 0.25);
}
.single-api-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #0958d9;
  background: rgba(22, 119, 255, 0.08);
}
.goto-workbench-link {
  font-size: 12px;
  padding: 0 6px;
}
.single-point-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #389e0d;
  background: rgba(82, 196, 26, 0.08);
}
</style>
