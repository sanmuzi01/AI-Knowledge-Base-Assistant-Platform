<template>
  <div class="flex min-h-screen flex-col bg-transparent">
    <header class="border-b border-sky-200/70 bg-white/78 px-5 py-4 text-slate-900 shadow-lg shadow-sky-900/8 backdrop-blur-xl">
      <div class="mx-auto flex max-w-7xl flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex min-w-0 items-center gap-3">
          <button
            @click="router.push('/agents')"
            class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded border border-sky-200 bg-white/80 text-slate-500 hover:bg-sky-50"
          title="返回工作台"
          >
            <ArrowLeft :size="16" />
          </button>
          <div class="min-w-0">
            <h1 class="truncate text-base font-semibold text-slate-950">本助手知识库</h1>
            <p class="truncate text-xs text-slate-500">
              {{ currentAgent?.name || `助手 #${agentId}` }} ·
              <button class="text-sky-600 hover:underline" @click="router.push('/knowledge-spaces')">
                在「知识库中心」统一管理所有知识库 →
              </button>
            </p>
          </div>
        </div>
        <div class="grid grid-cols-3 gap-2 text-xs sm:w-[360px]">
          <div class="rounded border border-sky-200 bg-white/72 px-3 py-2">
            <p class="text-slate-400">可检索</p>
            <p class="mt-1 text-sm font-semibold text-slate-900">{{ docStats.ready }}</p>
          </div>
          <div class="rounded border border-sky-200 bg-white/72 px-3 py-2">
            <p class="text-slate-400">处理中</p>
            <p class="mt-1 text-sm font-semibold text-sky-700">{{ docStats.working }}</p>
          </div>
          <div class="rounded border border-sky-200 bg-white/72 px-3 py-2">
            <p class="text-slate-400">失败</p>
            <p class="mt-1 text-sm font-semibold text-red-600">{{ docStats.failed }}</p>
          </div>
        </div>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto px-5 py-5">
      <div class="mx-auto grid max-w-7xl grid-cols-1 gap-5 xl:grid-cols-[minmax(480px,560px)_1fr]">
        <section class="space-y-5">
          <div class="sci-panel rounded-lg">
            <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-900">知识库体检</h2>
                <p class="mt-1 text-xs text-slate-500">检查资料能不能上传、抓取、入库和检索。</p>
              </div>
              <div class="text-right">
                <p class="text-2xl font-semibold text-slate-950">{{ diagnostics?.score ?? diagnosticFallbackScore }}</p>
                <p class="text-xs text-slate-400">健康分</p>
              </div>
            </div>
            <div class="grid gap-3 p-4 sm:grid-cols-2">
              <div class="rounded-lg border border-slate-100 bg-white/72 p-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-slate-500">资料检索模型</span>
                  <span class="rounded px-2 py-0.5 text-xs" :class="diagnostics?.embedding.ready ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'">
                    {{ diagnostics?.embedding.ready ? '已连接' : '待配置' }}
                  </span>
                </div>
                <p class="mt-2 truncate text-sm font-medium text-slate-900">{{ diagnostics?.embedding.models.join('、') || '暂无可用检索模型' }}</p>
              </div>
              <div class="rounded-lg border border-slate-100 bg-white/72 p-3">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-slate-500">网页抓取方式</span>
                  <span class="rounded bg-sky-50 px-2 py-0.5 text-xs text-sky-700">
                    {{ diagnostics?.crawler.browser_fallback ? '兼容动态网页' : '普通网页抓取' }}
                  </span>
                </div>
                <p class="mt-2 text-sm font-medium text-slate-900">
                  超时 {{ diagnostics?.crawler.timeout_seconds ?? 10 }}s · 最大 {{ formatSize(diagnostics?.crawler.max_bytes ?? 0) }}
                </p>
              </div>
            </div>
            <div v-if="diagnostics?.recommendations.length" class="border-t border-slate-100 px-4 py-3">
              <div class="space-y-2">
                <button
                  v-for="item in diagnostics.recommendations"
                  :key="item.key"
                  @click="handleDiagnosticAction(item)"
                  class="w-full rounded-lg border bg-white/70 p-3 text-left hover:bg-sky-50"
                  :class="recommendationClass(item.level)"
                >
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-sm font-semibold text-slate-900">{{ item.title }}</span>
                    <span class="shrink-0 text-xs text-slate-400">{{ item.action_text }}</span>
                  </div>
                  <p class="mt-1 text-xs leading-5 text-slate-500">{{ item.description }}</p>
                </button>
              </div>
            </div>
          </div>

          <div class="sci-panel rounded-lg">
            <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-900">添加资料</h2>
                <p class="mt-1 text-xs text-slate-500">资料完成入库后才会参与聊天和检索。</p>
              </div>
              <button @click="loadPage" class="inline-flex h-8 items-center gap-2 rounded border border-slate-200 px-3 text-xs text-slate-600 hover:bg-slate-50">
                <RefreshCw :size="14" />
                刷新
              </button>
            </div>

            <div v-if="!canUseRag" class="m-4 flex items-center justify-between gap-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <span>{{ ragBlockedReason }}</span>
              <button @click="router.push('/llm-configs')" class="shrink-0 rounded border border-amber-300 bg-white px-2 py-1 hover:bg-amber-100">
                去连接
              </button>
            </div>

            <div class="border-b border-slate-100 px-4 pt-4">
              <div class="inline-flex rounded border border-slate-200 bg-slate-50 p-1">
                <button
                  @click="activeInputMode = 'file'"
                  :class="activeInputMode === 'file' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'"
                  class="inline-flex h-8 items-center gap-2 rounded px-3 text-xs font-medium"
                >
                  <UploadCloud :size="14" />
                  文件
                </button>
                <button
                  @click="activeInputMode = 'web'"
                  :class="activeInputMode === 'web' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'"
                  class="inline-flex h-8 items-center gap-2 rounded px-3 text-xs font-medium"
                >
                  <Link2 :size="14" />
                  网页
                </button>
              </div>
            </div>

            <div class="p-4">
              <div v-if="activeInputMode === 'file'">
                <div
                  @dragover.prevent="dragOver = true"
                  @dragleave.prevent="dragOver = false"
                  @drop.prevent="handleDrop"
                  @click="canUseRag && fileInput?.click()"
                  :class="[
                    dragOver && canUseRag ? 'border-blue-500 bg-blue-50' : 'border-slate-300',
                    canUseRag ? 'cursor-pointer hover:border-slate-400' : 'cursor-not-allowed bg-slate-50 opacity-70',
                  ]"
                  class="rounded-lg border-2 border-dashed p-8 text-center transition-colors"
                >
                  <input ref="fileInput" type="file" class="hidden" accept=".txt,.md,.pdf,.docx" multiple :disabled="!canUseRag" @change="handleFileSelect" />
                  <UploadCloud :size="30" class="mx-auto mb-3 text-slate-400" />
                  <p class="text-sm font-medium text-slate-700">{{ uploadTitle }}</p>
                  <p class="mt-1 text-xs text-slate-500">{{ uploading ? uploadProgress : uploadHint }}</p>
                </div>
                <p v-if="uploadError" class="mt-2 text-sm text-red-600">{{ uploadError }}</p>
              </div>

              <div v-else>
                <textarea
                  v-model="crawlUrlsText"
                  :disabled="crawling || !canUseRag"
                  rows="5"
                  class="w-full resize-none rounded border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:cursor-not-allowed disabled:bg-slate-100"
                  placeholder="https://example.com/article&#10;example.com/docs/page"
                ></textarea>
                <div class="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p class="text-xs text-slate-400">已识别 {{ crawlUrlList.length }} 个 URL，最多 10 个；没有协议时会自动按 https:// 处理。</p>
                  <div class="flex gap-2">
                    <button
                      @click="handleCrawlCheck"
                      :disabled="checkingUrls || crawlUrlList.length === 0"
                      class="inline-flex h-9 items-center justify-center gap-2 rounded border border-sky-200 bg-white px-3 text-sm text-sky-700 hover:bg-sky-50 disabled:text-slate-300"
                    >
                      <ShieldCheck :size="15" />
                      {{ checkingUrls ? '检测中...' : '检测网址' }}
                    </button>
                    <button
                      @click="handleCrawl"
                      :disabled="crawling || !canUseRag || crawlUrlList.length === 0"
                      class="sci-primary inline-flex h-9 items-center justify-center gap-2 rounded px-4 text-sm font-medium text-white disabled:bg-slate-300 disabled:shadow-none"
                    >
                      <Link2 :size="15" />
                      {{ crawling ? '抓取中...' : '抓取并入库' }}
                    </button>
                  </div>
                </div>
                <p v-if="crawlSummary" class="mt-2 text-sm text-emerald-700">{{ crawlSummary }}</p>
                <p v-if="crawlError" class="mt-2 text-sm text-red-600">{{ crawlError }}</p>
                <div v-if="crawlCheckItems.length" class="mt-3 rounded border border-sky-200 bg-sky-50/70 p-3">
                  <p class="text-xs font-semibold text-slate-800">网址检测结果</p>
                  <div class="mt-2 space-y-2">
                    <div v-for="item in crawlCheckItems" :key="item.url" class="rounded bg-white/76 px-3 py-2 text-xs">
                      <div class="flex items-center justify-between gap-3">
                        <span class="break-all font-medium text-slate-800">{{ item.normalized_url || item.url }}</span>
                        <span class="shrink-0 rounded px-2 py-0.5" :class="item.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'">
                          {{ item.ok ? '可抓取' : '被拦截' }}
                        </span>
                      </div>
                      <p v-if="item.error" class="mt-1 text-red-600">{{ item.error }}</p>
                    </div>
                  </div>
                </div>
                <div v-if="crawlFailedItems.length" class="mt-3 rounded border border-amber-200 bg-amber-50 p-3">
                  <p class="text-xs font-semibold text-amber-800">以下网址没有抓取成功</p>
                  <div class="mt-2 space-y-2">
                    <div v-for="item in crawlFailedItems" :key="item.url" class="text-xs leading-5 text-amber-800">
                      <p class="break-all font-medium">{{ item.url }}</p>
                      <p class="text-amber-700">{{ item.error }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="sci-panel rounded-lg">
            <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-900">从其他助手复制资料（旧方式）</h2>
                <p class="mt-1 text-xs text-slate-500">
                  更推荐在
                  <button class="text-sky-600 hover:underline" @click="router.push('/knowledge-spaces')">知识库中心</button>
                  建独立知识库，之后由多个助手共用（无需复制）。
                </p>
              </div>
              <span class="text-xs text-slate-400">{{ reusableDocs.length }} 个可导入</span>
            </div>
            <div v-if="myDocsError" class="m-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {{ myDocsError }}
            </div>
            <div v-else-if="reusableDocs.length === 0" class="px-4 py-8 text-center text-sm text-slate-500">
              暂无可复用资料。你在其他助手添加资料后会显示在这里。
            </div>
            <div v-else class="max-h-60 overflow-y-auto divide-y divide-slate-100">
              <article v-for="doc in reusableDocs" :key="doc.id" class="flex items-center justify-between gap-3 px-4 py-3">
                <div class="min-w-0">
                  <h3 class="truncate text-sm font-medium text-slate-900">{{ doc.file_name }}</h3>
                  <p class="mt-1 text-xs text-slate-500">
                    来自 {{ doc.agent_name || `助手 #${doc.agent_id}` }} · {{ statusText(doc.status) }} · {{ doc.chunk_count }} 块
                  </p>
                </div>
                <button
                  @click="handleImport(doc)"
                  :disabled="importingId === doc.id || !canUseRag"
                  class="shrink-0 rounded border border-sky-200 bg-white px-3 py-1.5 text-xs text-sky-700 hover:bg-sky-50 disabled:text-slate-300"
                >
                  {{ importingId === doc.id ? '导入中...' : '导入' }}
                </button>
              </article>
            </div>
          </div>

          <div class="sci-panel rounded-lg">
            <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-900">处理进度</h2>
                <p class="mt-1 text-xs text-slate-500">{{ workingTasks.length ? '正在排队或解析资料' : '暂无进行中的任务' }}</p>
              </div>
              <button @click="router.push('/tasks')" class="text-xs text-slate-500 hover:text-slate-900">任务中心</button>
            </div>
            <div v-if="tasks.length" class="divide-y divide-slate-100">
              <article v-for="task in tasks" :key="task.id" class="px-4 py-3">
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0">
                    <p class="truncate text-sm font-medium text-slate-800">{{ task.title }}</p>
                    <p class="mt-0.5 text-xs text-slate-400">{{ task.created_at || '刚刚创建' }}</p>
                  </div>
                  <span :class="taskStatusClass(task.status)" class="shrink-0 rounded px-2 py-1 text-xs">
                    {{ taskStatusText(task.status) }}
                  </span>
                </div>
                <div class="mt-2 h-1.5 rounded bg-slate-200">
                  <div class="h-1.5 rounded bg-blue-500 transition-all" :style="{ width: `${task.progress || 0}%` }"></div>
                </div>
                <p v-if="task.error_msg" class="mt-2 line-clamp-2 text-xs text-red-600">{{ task.error_msg }}</p>
                <div v-if="task.status === 'failed' || task.status === 'queued'" class="mt-3 flex justify-end gap-2">
                  <button
                    v-if="task.status === 'failed'"
                    @click="handleRetryTask(task)"
                    class="rounded border border-amber-200 bg-white px-3 py-1.5 text-xs text-amber-700 hover:bg-amber-50"
                  >
                    重试
                  </button>
                  <button
                    v-if="task.status === 'queued'"
                    @click="handleCancelTask(task)"
                    class="rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                  >
                    取消
                  </button>
                </div>
              </article>
            </div>
            <div v-else class="px-4 py-10 text-center text-sm text-slate-500">上传文件或抓取网页后，进度会显示在这里。</div>
          </div>

          <div class="sci-panel rounded-lg">
            <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h2 class="text-sm font-semibold text-slate-900">资料列表</h2>
              <span class="text-xs text-slate-400">{{ docs.length }} 个</span>
            </div>

            <div v-if="docs.length === 0" class="px-4 py-12 text-center text-sm text-slate-500">
              暂无资料。
            </div>

            <div v-else class="max-h-[480px] overflow-y-auto divide-y divide-slate-100">
              <article v-for="doc in docs" :key="doc.id" class="px-4 py-3 hover:bg-slate-50">
                <div class="flex items-start justify-between gap-3">
                  <div class="flex min-w-0 gap-3">
                    <span class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded bg-slate-100 text-slate-600">
                      <component :is="fileIcon(doc.file_type)" :size="17" />
                    </span>
                    <div class="min-w-0">
                      <h3 class="truncate text-sm font-medium text-slate-900">{{ doc.file_name }}</h3>
                      <p class="mt-1 text-xs text-slate-500">
                        {{ doc.file_type.toUpperCase() }} · {{ formatSize(doc.file_size) }} · {{ doc.chunk_count }} 块
                      </p>
                      <p v-if="doc.status === 'failed' && doc.error_msg" class="mt-1 line-clamp-2 text-xs text-red-600">{{ doc.error_msg }}</p>
                    </div>
                  </div>
                  <span :class="statusClass(doc.status)" class="shrink-0 rounded px-2 py-1 text-xs">
                    {{ statusText(doc.status) }}
                  </span>
                </div>
                <div class="mt-3 flex flex-wrap justify-end gap-2">
                  <button
                    @click="handleToggleEnabled(doc)"
                    :disabled="togglingEnabledId === doc.id"
                    :class="doc.is_enabled === 1 ? 'border-amber-100 text-amber-700 hover:bg-amber-50' : 'border-emerald-100 text-emerald-700 hover:bg-emerald-50'"
                    class="rounded border px-3 py-1.5 text-xs disabled:text-slate-300"
                    :title="doc.is_enabled === 1 ? '禁用后不会从这份资料里找答案' : '启用后会从这份资料里找答案'"
                  >
                    {{ togglingEnabledId === doc.id ? '更新中...' : doc.is_enabled === 1 ? '禁用' : '启用' }}
                  </button>
                  <button
                    @click="handleReindex(doc)"
                    :disabled="!canUseRag || reindexingId === doc.id"
                    class="rounded border border-blue-100 px-3 py-1.5 text-xs text-blue-700 hover:bg-blue-50 disabled:text-slate-300"
                    title="重新入库"
                  >
                    {{ reindexingId === doc.id ? '重建中...' : '重建' }}
                  </button>
                  <button
                    @click="openChunks(doc)"
                    class="rounded border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                    title="查看片段"
                  >
                    片段
                  </button>
                  <button
                    @click="handleDelete(doc)"
                    class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-red-50 hover:text-red-600"
                    title="删除文档"
                  >
                    <Trash2 :size="15" />
                  </button>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section class="sci-panel rounded-lg">
          <div class="border-b border-slate-200 p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-900">检索验证</h2>
                <p class="mt-1 text-xs text-slate-500">当前可检索资料 {{ searchableDocs.length }} 个。</p>
              </div>
              <Search :size="17" class="text-slate-400" />
            </div>
            <div class="mb-3 grid grid-cols-1 gap-2 md:grid-cols-[1fr_96px]">
              <select
                v-model="selectedKnowledgeId"
                class="h-9 rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-blue-500"
              >
                <option :value="0">全部已入库文档</option>
                <option v-for="doc in searchableDocs" :key="doc.id" :value="doc.id">
                  {{ doc.file_name }}
                </option>
              </select>
              <select
                v-model.number="topK"
                class="h-9 rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-blue-500"
              >
                <option :value="3">显示 3 条</option>
                <option :value="5">显示 5 条</option>
                <option :value="10">显示 10 条</option>
              </select>
            </div>
            <div class="flex gap-2">
              <input
                v-model="searchQuery"
                type="text"
                class="h-10 flex-1 rounded border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                placeholder="输入问题或关键词，看看会命中哪些资料内容"
                @keydown.enter="handleSearch"
              />
              <button
                @click="handleSearch"
                :disabled="searching || !searchQuery.trim() || !canUseRag"
                class="sci-primary inline-flex items-center gap-2 rounded px-4 py-2 text-sm font-medium text-white disabled:bg-blue-300 disabled:shadow-none"
              >
                <Search :size="15" />
                {{ searching ? '检索中...' : '检索' }}
              </button>
            </div>
            <p v-if="searchError" class="mt-2 text-sm text-red-600">{{ searchError }}</p>
            <p v-else-if="searchingSlow" class="mt-2 text-xs text-amber-700">
              检索仍在处理。如果长时间没有返回，请确认后端服务正常、资料检索模型已连接，或查看运行日志。
            </p>
            <p v-else-if="!canUseRag" class="mt-2 text-xs text-amber-700">{{ ragBlockedReason }}</p>
          </div>

          <div class="min-h-0 flex-1 overflow-y-auto p-5">
            <div v-if="searchResults.length === 0 && !searching" class="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 text-center text-sm text-slate-500">
              {{ hasSearched ? '没有命中相关片段。可以换个关键词，或确认文档状态为已完成。' : '检索结果会显示在这里。' }}
            </div>

            <div v-else class="space-y-3">
              <article
                v-for="(result, i) in searchResults"
                :key="i"
                class="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-xs font-medium text-blue-700">片段 {{ i + 1 }}</span>
                  <span v-if="typeof result.score === 'number'" class="text-xs text-slate-400">分数 {{ formatScore(result.score) }}</span>
                </div>
                <div class="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span v-if="result.file_name">{{ result.file_name }}</span>
                  <span v-if="typeof result.chunk_index === 'number'">第 {{ result.chunk_index + 1 }} 块</span>
                  <span v-if="typeof result.distance === 'number'">距离 {{ result.distance.toFixed(4) }}</span>
                </div>
                <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ result.content }}</p>
              </article>
            </div>
          </div>
        </section>
      </div>
    </main>

    <div v-if="showChunks" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" @click.self="closeChunks">
      <div class="flex max-h-[82vh] w-full max-w-3xl flex-col rounded-lg bg-white shadow-xl">
        <header class="flex h-14 items-center justify-between border-b border-slate-200 px-5">
          <div class="min-w-0">
            <h2 class="truncate text-base font-semibold text-slate-900">{{ chunkDoc?.file_name || '文档片段' }}</h2>
            <p class="text-xs text-slate-500">{{ chunks.length }} 个片段</p>
          </div>
          <button @click="closeChunks" class="inline-flex h-8 w-8 items-center justify-center rounded text-slate-400 hover:bg-slate-100" title="关闭">
            ×
          </button>
        </header>
        <main class="min-h-0 flex-1 overflow-y-auto p-5">
          <div v-if="chunksLoading" class="py-16 text-center text-sm text-slate-500">加载中...</div>
          <div v-else-if="chunks.length === 0" class="py-16 text-center text-sm text-slate-500">暂无片段。</div>
          <div v-else class="space-y-3">
            <article v-for="chunk in chunks" :key="chunk.id" class="rounded border border-slate-200 p-4">
              <div class="mb-2 flex items-center justify-between text-xs text-slate-400">
                <span>片段 {{ chunk.chunk_index + 1 }}</span>
                <span>{{ chunk.token_count }} 字符估算</span>
              </div>
              <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ chunk.content }}</p>
            </article>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, File, FileText, Link2, RefreshCw, Search, ShieldCheck, Trash2, UploadCloud } from 'lucide-vue-next'
import * as agentApi from '../api/agent'
import type { AgentInfo } from '../api/agent'
import * as llmConfigApi from '../api/llmConfig'
import type { LlmConfig } from '../api/llmConfig'
import * as knowledgeApi from '../api/knowledge'
import type { CrawlCheckResult, KnowledgeChunk, KnowledgeDiagnostics, KnowledgeDoc, KnowledgeRecommendation, SearchResult } from '../api/knowledge'
import * as taskApi from '../api/task'
import type { BackgroundTask } from '../api/task'
import { getErrorMessage } from '../utils/request'

const router = useRouter()
const route = useRoute()
const agentId = computed(() => Number(route.params.agentId))
const currentAgent = ref<AgentInfo | null>(null)
const configs = ref<LlmConfig[]>([])
const configError = ref('')
const diagnostics = ref<KnowledgeDiagnostics | null>(null)

const docs = ref<KnowledgeDoc[]>([])
const myDocs = ref<KnowledgeDoc[]>([])
const myDocsError = ref('')
const importingId = ref<number | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
const activeInputMode = ref<'file' | 'web'>('file')
const uploading = ref(false)
const uploadProgress = ref('')
const uploadError = ref('')
const crawling = ref(false)
const crawlUrlsText = ref('')
const crawlError = ref('')
const crawlSummary = ref('')
const crawlFailedItems = ref<Array<{ url: string; error: string }>>([])
const checkingUrls = ref(false)
const crawlCheckItems = ref<CrawlCheckResult['items']>([])
const searchQuery = ref('')
const searching = ref(false)
const searchingSlow = ref(false)
const searchResults = ref<SearchResult[]>([])
const searchError = ref('')
const hasSearched = ref(false)
const selectedKnowledgeId = ref(0)
const topK = ref(5)
const showChunks = ref(false)
const chunksLoading = ref(false)
const chunks = ref<KnowledgeChunk[]>([])
const chunkDoc = ref<KnowledgeDoc | null>(null)
const reindexingId = ref<number | null>(null)
const togglingEnabledId = ref<number | null>(null)
const tasks = ref<BackgroundTask[]>([])
let pollTimer: number | undefined
let searchSlowTimer: number | undefined
let taskPollTimer: number | undefined

const searchableDocs = computed(() => docs.value.filter((doc) => doc.status === 'done' && doc.chunk_count > 0 && doc.is_enabled !== 0))
const reusableDocs = computed(() => {
  const currentSignatures = new Set(docs.value.map((doc) => `${doc.file_name}|${doc.file_type}|${doc.file_size}`))
  return myDocs.value.filter((doc) => (
    doc.agent_id !== agentId.value
    && !currentSignatures.has(`${doc.file_name}|${doc.file_type}|${doc.file_size}`)
  ))
})
const workingTasks = computed(() => tasks.value.filter((task) => task.status === 'queued' || task.status === 'running'))
const docStats = computed(() => ({
  ready: searchableDocs.value.length,
  working: docs.value.filter((doc) => doc.status === 'pending' || doc.status === 'processing').length + workingTasks.value.length,
  failed: docs.value.filter((doc) => doc.status === 'failed').length + tasks.value.filter((task) => task.status === 'failed').length,
}))
const diagnosticFallbackScore = computed(() => {
  let score = 100
  if (!hasEmbeddingKey.value) score -= 40
  if (docStats.value.ready === 0) score -= 22
  if (docStats.value.failed > 0) score -= Math.min(24, docStats.value.failed * 8)
  return Math.max(0, Math.min(100, score))
})
const hasEmbeddingKey = computed(() => configs.value.some((config) => {
  const model = config.model_name.toLowerCase()
  return model.includes('embedding') || model.startsWith('baai/') || model === 'glm-4'
}))
const ragBlockedReason = computed(() => {
  if (configError.value) return configError.value
  if (!hasEmbeddingKey.value) return '当前用户还没有连接资料检索模型'
  return ''
})
const canUseRag = computed(() => !ragBlockedReason.value)
const uploadTitle = computed(() => {
  if (uploading.value) return '正在创建入库任务...'
  if (!canUseRag.value) return '请先连接资料检索模型'
  return '点击或拖拽文件到这里'
})
const uploadHint = computed(() => canUseRag.value ? '支持批量选择 txt / md / pdf / docx' : '配置后才能上传、切块和检索')
const crawlUrlList = computed(() => {
  const urls = crawlUrlsText.value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
  return Array.from(new Set(urls)).slice(0, 10)
})

const normalizeTaskStatus = (status?: string): BackgroundTask['status'] => {
  if (status === 'queued' || status === 'running' || status === 'finished' || status === 'failed' || status === 'cancelled') {
    return status
  }
  return 'queued'
}

const loadCurrentAgent = async () => {
  try {
    const agentList = await agentApi.listAgents()
    currentAgent.value = agentList.find((agent) => agent.id === agentId.value) || null
  } catch {
    currentAgent.value = null
  }
}

const loadConfigs = async () => {
  configError.value = ''
  try {
    configs.value = await llmConfigApi.listConfigs()
  } catch (e: any) {
    configs.value = []
    configError.value = getErrorMessage(e, '无法读取模型连接')
  }
}

const loadDocs = async () => {
  try {
    docs.value = await knowledgeApi.listDocuments(agentId.value)
    updatePolling()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '读取知识库文档失败')
    docs.value = []
    updatePolling()
  }
}

const loadMyDocs = async () => {
  myDocsError.value = ''
  try {
    myDocs.value = await knowledgeApi.listMyDocuments()
  } catch (e: any) {
    myDocs.value = []
    myDocsError.value = getErrorMessage(e, '读取我的资料空间失败')
  }
}

const loadDiagnostics = async () => {
  try {
    diagnostics.value = await knowledgeApi.getDiagnostics(agentId.value)
  } catch {
    diagnostics.value = null
  }
}

const loadPage = async () => {
  await Promise.all([loadCurrentAgent(), loadConfigs()])
  await Promise.all([loadDocs(), loadMyDocs(), loadDiagnostics()])
  await loadTasks()
}

const updatePolling = () => {
  const hasWorkingDoc = docs.value.some((doc) => doc.status === 'pending' || doc.status === 'processing')
  const hasWorkingTask = tasks.value.some((task) => task.status === 'queued' || task.status === 'running')
  if (hasWorkingDoc && pollTimer === undefined) {
    pollTimer = window.setInterval(loadDocs, 3000)
  }
  if (!hasWorkingDoc && pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
  if (hasWorkingTask && taskPollTimer === undefined) {
    taskPollTimer = window.setInterval(loadTasks, 2500)
  }
  if (!hasWorkingTask && taskPollTimer !== undefined) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = undefined
  }
}

const loadTasks = async () => {
  try {
    const allTasks = await taskApi.listTasks(20)
    tasks.value = allTasks
      .filter((task) => task.agent_id === agentId.value && task.target_type === 'knowledge')
      .slice(0, 5)
  } catch {
    tasks.value = tasks.value.filter((task) => task.status === 'queued' || task.status === 'running')
  } finally {
    updatePolling()
    loadDiagnostics()
  }
}

const uploadFiles = async (files: File[]) => {
  if (!canUseRag.value) {
    uploadError.value = ragBlockedReason.value
    return
  }
  const uploadList = files.filter(Boolean)
  if (uploadList.length === 0) return
  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = uploadList.length === 1 ? uploadList[0].name : `${uploadList.length} 个文件`
  try {
    const result = uploadList.length === 1
      ? {
          items: [{
            file_name: uploadList[0].name,
            ...(await knowledgeApi.uploadDocument(agentId.value, uploadList[0])),
          }],
        }
      : await knowledgeApi.uploadDocuments(agentId.value, uploadList)
    const newTasks = (result.items || []).map((item: any) => ({
        id: item.task_id,
        user_id: 0,
        agent_id: agentId.value,
        task_type: 'knowledge_index',
        status: normalizeTaskStatus(item.status),
        title: `文档入库: ${item.file_name}`,
        target_type: 'knowledge',
        target_id: item.knowledge_id,
        progress: 0,
        result: null,
        error_msg: null,
        retry_count: 0,
        parent_task_id: null,
        created_at: null,
        started_at: null,
        finished_at: null,
        next_run_at: null,
    }))
    tasks.value.unshift(...newTasks)
    await loadDocs()
    await loadDiagnostics()
    updatePolling()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '上传失败')
  } finally {
    uploading.value = false
    uploadProgress.value = ''
  }
}

const handleCrawl = async () => {
  if (!canUseRag.value) {
    crawlError.value = ragBlockedReason.value
    return
  }
  const urls = crawlUrlList.value
  if (!urls.length || crawling.value) return
  crawling.value = true
  crawlError.value = ''
  crawlSummary.value = ''
  crawlFailedItems.value = []
  crawlCheckItems.value = []
  try {
    const result = await knowledgeApi.crawlDocuments(agentId.value, urls)
    const newTasks = (result.items || []).map((item) => ({
      id: item.task_id,
      user_id: 0,
      agent_id: agentId.value,
      task_type: 'knowledge_index',
      status: normalizeTaskStatus(item.status),
      title: `网页入库: ${item.title || item.file_name}`,
      target_type: 'knowledge',
      target_id: item.knowledge_id,
      progress: 0,
      result: null,
      error_msg: null,
      retry_count: 0,
      parent_task_id: null,
      created_at: null,
      started_at: null,
      finished_at: null,
      next_run_at: null,
    }))
    tasks.value.unshift(...newTasks)
    crawlFailedItems.value = result.failed_items || []
    crawlSummary.value = result.failed_count
      ? `已成功抓取 ${result.count} 个网页，${result.failed_count} 个网页失败。成功的网页已进入入库队列。`
      : `已成功抓取 ${result.count} 个网页，正在入库。`
    crawlUrlsText.value = ''
    await loadDocs()
    await loadDiagnostics()
    updatePolling()
  } catch (e: any) {
    crawlError.value = getErrorMessage(e, '网页抓取失败')
    crawlFailedItems.value = []
  } finally {
    crawling.value = false
  }
}

const handleCrawlCheck = async () => {
  const urls = crawlUrlList.value
  if (!urls.length || checkingUrls.value) return
  checkingUrls.value = true
  crawlError.value = ''
  crawlCheckItems.value = []
  try {
    const result = await knowledgeApi.checkCrawlUrls(urls)
    crawlCheckItems.value = result.items
    if (result.failed_count > 0) {
      crawlError.value = `${result.failed_count} 个网址检测未通过，请按提示修改后再抓取。`
    }
  } catch (e: any) {
    crawlError.value = getErrorMessage(e, '网址检测失败')
  } finally {
    checkingUrls.value = false
  }
}

const handleFileSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  const files = Array.from(target.files || [])
  if (files.length) uploadFiles(files)
  target.value = ''
}

const handleDrop = (e: DragEvent) => {
  dragOver.value = false
  if (!canUseRag.value) return
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length) uploadFiles(files)
}

const handleDelete = async (doc: KnowledgeDoc) => {
  if (!confirm(`确认删除文档「${doc.file_name}」？相关资料片段和检索数据也会删除。`)) return
  await knowledgeApi.deleteDocument(agentId.value, doc.id)
  await loadDocs()
  await loadDiagnostics()
}

const handleReindex = async (doc: KnowledgeDoc) => {
  if (!canUseRag.value) {
    uploadError.value = ragBlockedReason.value
    return
  }
  if (!confirm(`确认重新入库「${doc.file_name}」？旧检索数据和资料片段会被重建。`)) return
  reindexingId.value = doc.id
  uploadError.value = ''
  try {
    const result = await knowledgeApi.reindexDocument(agentId.value, doc.id)
    if (result?.task_id) {
      tasks.value.unshift({
        id: result.task_id,
        user_id: 0,
        agent_id: agentId.value,
        task_type: 'knowledge_reindex',
        status: normalizeTaskStatus(result.status),
        title: `重建索引: ${doc.file_name}`,
        target_type: 'knowledge',
        target_id: doc.id,
        progress: 0,
        result: null,
        error_msg: null,
        retry_count: 0,
        parent_task_id: null,
        created_at: null,
        started_at: null,
        finished_at: null,
        next_run_at: null,
      })
    }
    await loadDocs()
    await loadDiagnostics()
    updatePolling()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '重新入库失败')
    await loadDocs()
  } finally {
    reindexingId.value = null
  }
}

const handleImport = async (doc: KnowledgeDoc) => {
  if (!canUseRag.value) {
    myDocsError.value = ragBlockedReason.value
    return
  }
  importingId.value = doc.id
  myDocsError.value = ''
  try {
    const result = await knowledgeApi.importDocumentToAgent(agentId.value, doc.id)
    if (result?.task_id) {
      tasks.value.unshift({
        id: result.task_id,
        user_id: 0,
        agent_id: agentId.value,
        task_type: 'knowledge_index',
        status: normalizeTaskStatus(result.status),
        title: `导入资料: ${doc.file_name}`,
        target_type: 'knowledge',
        target_id: result.knowledge_id,
        progress: 0,
        result: null,
        error_msg: null,
        retry_count: 0,
        parent_task_id: null,
        created_at: null,
        started_at: null,
        finished_at: null,
        next_run_at: null,
      })
    }
    await Promise.all([loadDocs(), loadMyDocs()])
    await loadDiagnostics()
    updatePolling()
  } catch (e: any) {
    myDocsError.value = getErrorMessage(e, '导入资料失败')
  } finally {
    importingId.value = null
  }
}

const handleRetryTask = async (task: BackgroundTask) => {
  try {
    const newTask = await taskApi.retryTask(task.id)
    tasks.value.unshift(newTask)
    await loadTasks()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '重试任务失败')
  }
}

const handleCancelTask = async (task: BackgroundTask) => {
  try {
    await taskApi.cancelTask(task.id)
    await loadTasks()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '取消任务失败')
  }
}

const handleDiagnosticAction = (item: KnowledgeRecommendation) => {
  if (item.action_path) {
    router.push(item.action_path)
    return
  }
  if (item.key === 'failed-index') {
    router.push('/tasks')
    return
  }
  if (item.key === 'no-searchable-doc') {
    activeInputMode.value = 'file'
  }
}

const handleToggleEnabled = async (doc: KnowledgeDoc) => {
  const next = doc.is_enabled === 1 ? 0 : 1
  togglingEnabledId.value = doc.id
  uploadError.value = ''
  try {
    await knowledgeApi.updateDocumentEnabled(agentId.value, doc.id, next)
    doc.is_enabled = next
    if (selectedKnowledgeId.value === doc.id && next === 0) {
      selectedKnowledgeId.value = 0
    }
    await loadDiagnostics()
  } catch (e: any) {
    uploadError.value = getErrorMessage(e, '更新文档状态失败')
  } finally {
    togglingEnabledId.value = null
  }
}

const handleSearch = async () => {
  const q = searchQuery.value.trim()
  if (!q || searching.value) return
  if (!canUseRag.value) {
    searchError.value = ragBlockedReason.value
    return
  }
  searching.value = true
  searchingSlow.value = false
  window.clearTimeout(searchSlowTimer)
  searchSlowTimer = window.setTimeout(() => {
    searchingSlow.value = true
  }, 8000)
  hasSearched.value = true
  searchError.value = ''
  searchResults.value = []
  try {
    searchResults.value = await knowledgeApi.searchKnowledge(agentId.value, {
      query: q,
      top_k: topK.value,
      knowledge_id: selectedKnowledgeId.value || null,
    })
  } catch (e: any) {
    searchError.value = getErrorMessage(e, '检索失败')
  } finally {
    searching.value = false
    searchingSlow.value = false
    window.clearTimeout(searchSlowTimer)
  }
}

const openChunks = async (doc: KnowledgeDoc) => {
  chunkDoc.value = doc
  showChunks.value = true
  chunksLoading.value = true
  chunks.value = []
  try {
    chunks.value = await knowledgeApi.listChunks(agentId.value, doc.id)
  } catch (e: any) {
    searchError.value = getErrorMessage(e, '读取片段失败')
    showChunks.value = false
  } finally {
    chunksLoading.value = false
  }
}

const closeChunks = () => {
  showChunks.value = false
  chunkDoc.value = null
  chunks.value = []
}

const fileIcon = (type: string) => {
  if (type === 'pdf') return File
  return FileText
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const formatScore = (score: number) => {
  if (score >= 0 && score <= 1) return `${(score * 100).toFixed(1)}%`
  return score.toFixed(4)
}

const recommendationClass = (level: string) => {
  if (level === 'danger') return 'border-red-200'
  if (level === 'warn') return 'border-amber-200'
  return 'border-sky-200'
}

const statusText = (s: string) => ({
  pending: '待处理',
  processing: '处理中',
  done: '已完成',
  failed: '失败',
}[s] || s)

const statusClass = (s: string) => ({
  pending: 'bg-slate-100 text-slate-600',
  processing: 'bg-blue-50 text-blue-700',
  done: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}[s] || 'bg-slate-100 text-slate-600')

const taskStatusText = (s: string) => ({
  queued: '排队中',
  running: '处理中',
  finished: '已完成',
  failed: '失败',
}[s] || s)

const taskStatusClass = (s: string) => ({
  queued: 'bg-slate-100 text-slate-600',
  running: 'bg-blue-50 text-blue-700',
  finished: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-red-50 text-red-700',
}[s] || 'bg-slate-100 text-slate-600')

onMounted(loadPage)
onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
  if (searchSlowTimer !== undefined) window.clearTimeout(searchSlowTimer)
  if (taskPollTimer !== undefined) window.clearInterval(taskPollTimer)
})
watch(agentId, async () => {
  selectedKnowledgeId.value = 0
  searchResults.value = []
  searchError.value = ''
  hasSearched.value = false
  closeChunks()
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
  if (taskPollTimer !== undefined) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = undefined
  }
  tasks.value = []
  await loadPage()
})
</script>
