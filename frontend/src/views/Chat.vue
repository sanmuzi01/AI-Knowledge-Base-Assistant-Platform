<template>
  <div class="h-screen flex bg-transparent">
    <!-- 左侧会话栏 -->
    <aside class="w-72 border-r border-sky-200/70 bg-white/78 text-slate-900 shadow-2xl shadow-sky-900/10 backdrop-blur-xl flex flex-col">
      <!-- 助手信息 -->
      <div class="p-4 border-b border-sky-200/70">
        <button
          @click="$router.push('/agents')"
          class="text-sm text-sky-600 hover:text-sky-800 mb-2 inline-flex items-center gap-1"
        >
          ← 返回工作台
        </button>
        <h2 class="font-semibold text-slate-900 truncate">{{ currentAgent?.name || '加载中...' }}</h2>
      </div>

            <!-- 新建会话按钮 + 知识库管理 -->
      <div class="px-3 py-3 space-y-2 border-b border-sky-100">
        <!-- 新建会话（主按钮：蓝底 + hover 深一点 + 柔和阴影） -->
                <!-- 新建会话（主按钮：淡蓝色 + 柔和蓝色） -->
        <button
          @click="createNewConversation"
          :disabled="loading"
          class="group w-full h-10 px-3 flex items-center gap-2 rounded-lg
                 bg-blue-50 border border-blue-100 text-blue-700 text-sm font-medium
                 hover:bg-blue-100 hover:border-blue-200 hover:shadow-sm
                 active:translate-y-px transition-all duration-200
                 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <!-- 图标方块：主色当视觉锚点 -->
          <span class="w-5 h-5 shrink-0 rounded bg-blue-500 text-white flex items-center justify-center group-hover:bg-blue-600 transition-colors">
            <PlusCircle :size="13" :stroke-width="2.25" />
          </span>
          <span>新建会话</span>
          <span class="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-600 font-normal">Ctrl N</span>
        </button>

        <!-- 知识库管理（次按钮：白底 + 绿色文字边框，点击感略低于主按钮） -->
        <button
          @click="router.push(`/agents/${agentId}/knowledge`)"
          class="w-full h-9 px-3 flex items-center gap-2 rounded-lg
                 border border-emerald-200 bg-emerald-50/60 text-emerald-700 text-sm
                 hover:border-emerald-300 hover:bg-emerald-50
                 active:translate-y-px transition-all duration-200"
        >
          <span class="w-5 h-5 shrink-0 rounded bg-emerald-500/10 flex items-center justify-center text-emerald-600">
            <BookOpen :size="13" :stroke-width="2" />
          </span>
          <span>个人资料</span>
        </button>
      </div>

      <div class="border-b border-gray-100 px-3 py-3">
        <div class="relative">
          <Search class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" :size="14" />
          <input
            v-model="conversationQuery"
            type="text"
            class="h-9 w-full rounded-lg border border-gray-200 bg-white pl-8 pr-3 text-sm text-gray-700 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            placeholder="搜索会话"
          />
        </div>
        <div class="mt-2 grid grid-cols-3 gap-1 rounded-lg bg-gray-100 p-1 text-xs">
          <button
            v-for="item in conversationFilters"
            :key="item.value"
            @click="conversationFilter = item.value"
            :class="conversationFilter === item.value ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
            class="h-7 rounded-md transition"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

            <!-- 会话列表 -->
      <div class="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5 pt-1">
        <div
          v-for="c in filteredConversations"
          :key="c.id"
          class="group relative rounded-lg"
        >
          <!-- 行主体 -->
          <div
            @click="selectConversation(c.id)"
            :class="[
              'flex items-center h-9 px-2 cursor-pointer text-sm transition-colors',
              currentConversationId === c.id
                ? 'bg-blue-50 text-blue-700 font-medium rounded-lg'
                : 'text-gray-700 hover:bg-gray-100 rounded-lg'
            ]"
          >
            <!-- 固定/归档 图标（锚点前预留图标） -->
            <span class="w-5 shrink-0 text-xs text-gray-400 mr-1 flex items-center justify-center">
              <Pin v-if="isPinned(c.id)" :size="13" class="text-amber-500 fill-amber-200" />
              <Archive v-else-if="isArchived(c.id)" :size="13" class="text-gray-400" />
            </span>
            <!-- 标题（重命名时变成 input） -->
            <span v-if="!(editingConvId === c.id)" class="truncate flex-1 pr-2">{{ c.title }}</span>
            <input
              v-else
              ref="renameInputRef"
              v-model="renameText"
              @keydown.enter="commitRename(c.id)"
              @keydown.esc="cancelRename"
              @click.stop
              @blur="commitRename(c.id)"
              class="flex-1 h-7 px-2 rounded border border-blue-400 bg-white text-sm text-gray-800 outline-none focus:ring-2 focus:ring-blue-300"
            />
            <!-- 右侧 更多功能按钮（hover 才显） -->
            <button
              v-if="editingConvId !== c.id"
              @click.stop="openMenu(c.id)"
              :class="[
                'w-6 h-6 shrink-0 rounded flex items-center justify-center transition-opacity',
                currentConversationId === c.id
                  ? 'opacity-100 text-blue-600 hover:bg-blue-100'
                  : 'opacity-0 group-hover:opacity-100 text-gray-400 hover:bg-gray-200 hover:text-gray-600'
              ]"
              title="更多"
            >
              <MoreHorizontal :size="14" :stroke-width="2" />
            </button>
          </div>

          <!-- 操作弹窗（绝对定位在此行右下方） -->
          <div
            v-if="menuConvId === c.id"
            class="absolute right-1 top-9 z-30 w-36 py-1 bg-white rounded-lg shadow-lg border border-gray-200 text-sm overflow-hidden"
            @click.stop
          >
            <button
              @click="startRename(c)"
              class="w-full px-3 h-8 flex items-center gap-2 text-gray-700 hover:bg-gray-100"
            >
              <Pencil :size="13" /> 重命名
            </button>
            <button
              @click="togglePin(c.id)"
              class="w-full px-3 h-8 flex items-center gap-2 text-gray-700 hover:bg-gray-100"
            >
              <Pin :size="13" /> {{ isPinned(c.id) ? '取消置顶' : '置顶' }}
            </button>
            <button
              @click="toggleArchive(c)"
              class="w-full px-3 h-8 flex items-center gap-2 text-gray-700 hover:bg-gray-100"
            >
              <Archive :size="13" /> {{ isArchived(c.id) ? '取消归档' : '归档' }}
            </button>
            <div class="h-px bg-gray-100 my-1"></div>
            <button
              @click="handleDeleteConv(c)"
              class="w-full px-3 h-8 flex items-center gap-2 text-red-600 hover:bg-red-50"
            >
              <Trash2 :size="13" /> 删除
            </button>
            <div class="h-px bg-gray-100 my-1"></div>
            <button
              @click="handleExportConv(c, 'markdown')"
              class="w-full px-3 h-8 flex items-center gap-2 text-gray-700 hover:bg-gray-100"
            >
              <Download :size="13" /> 导出 MD
            </button>
            <button
              @click="handleExportConv(c, 'json')"
              class="w-full px-3 h-8 flex items-center gap-2 text-gray-700 hover:bg-gray-100"
            >
              <Download :size="13" /> 导出 JSON
            </button>
          </div>
        </div>

        <div v-if="filteredConversations.length === 0" class="text-sm text-gray-400 text-center py-8 px-4">
          {{ conversations.length === 0 ? '暂无会话，发送第一条消息会自动创建' : '没有匹配的会话' }}
        </div>
      </div>
    </aside>

    <!-- 右侧聊天区 -->
    <section class="flex-1 flex flex-col min-w-0">
      <div class="border-b border-sky-100 bg-white/70 px-6 py-2">
        <AgentSubnav :agent-id="agentId" :agent-name="currentAgent?.name" active="chat" />
      </div>
      <!-- 消息区域 -->
      <div ref="messageListRef" class="flex-1 overflow-y-auto px-8 pb-28 pt-6 space-y-5">
        <div class="mx-auto max-w-4xl rounded-lg border border-slate-200 bg-white px-4 py-3">
          <div class="flex flex-wrap items-center gap-2 text-xs">
            <span class="font-medium text-slate-700">{{ currentAgent?.name || '当前助手' }}</span>
            <span :class="hasCurrentModelKey ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'" class="rounded px-2 py-1">
              模型 {{ hasCurrentModelKey ? '已配置' : '缺密钥' }}
            </span>
            <span :class="currentAgent?.rag_enabled === 1 ? (hasEmbeddingKey ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700') : 'bg-slate-100 text-slate-500'" class="rounded px-2 py-1">
              资料 {{ currentAgent?.rag_enabled === 1 ? (hasEmbeddingKey ? '可用' : '缺密钥') : '关闭' }}
            </span>
            <span :class="currentAgent?.memory_enabled === 1 ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-500'" class="rounded px-2 py-1">
              记忆 {{ currentAgent?.memory_enabled === 1 ? '开启' : '关闭' }}
            </span>
            <span v-if="currentAgent?.skills?.length" class="rounded bg-violet-50 px-2 py-1 text-violet-700">
              能力 {{ currentAgent.skills.length }} 个
            </span>
          </div>
        </div>

        <div v-if="messages.length === 0" class="h-full flex items-center justify-center text-gray-400">
          开始和助手对话吧
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']"
        >
          <div class="max-w-2xl">
            <div
              :class="[
                'px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-md'
                  : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md'
              ]"
              v-html="msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content"
            ></div>
            <CitationList v-if="msg.role === 'assistant'" :citations="msg.citations" />
          </div>
        </div>

        <!-- 思考/工具调用事件展示 -->
        <div v-for="(evt, i) in eventTraces" :key="'evt-'+i" class="flex justify-start">
          <div class="max-w-2xl w-full px-4 py-2 rounded-lg border border-gray-200 bg-gray-50 text-xs text-gray-500 font-mono space-y-1">
            <div v-if="evt.type === 'thinking'">
              <span class="text-purple-500 font-semibold">🤔 思考</span>
              <div class="whitespace-pre-wrap mt-1">{{ short(evt.content, 200) }}</div>
            </div>
            <div v-else-if="evt.type === 'tool_call'">
              <span class="text-blue-500 font-semibold">调用工具</span> {{ evt.name }}
              <pre class="mt-1 text-xs text-gray-600">{{ JSON.stringify(evt.args, null, 2) }}</pre>
            </div>
            <div v-else-if="evt.type === 'tool_result'">
              <span class="text-green-500 font-semibold">工具结果</span> {{ evt.name }}
              <div class="mt-1 text-gray-600">{{ short(evt.result, 200) }}</div>
            </div>
            <div v-else-if="evt.type === 'retrieval'">
              <span class="text-amber-500 font-semibold">资料检索</span> 命中 {{ evt.hit_count }} 条
            </div>
          </div>
        </div>

        <div v-if="loading" class="flex justify-start">
          <div class="px-4 py-3 rounded-2xl bg-white border border-gray-200 rounded-bl-md">
            <div class="flex gap-1">
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></span>
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="p-4 border-t border-gray-200 bg-white">
        <div class="max-w-4xl mx-auto flex gap-3 items-end">
          <div
            v-if="!chatReady"
            class="mb-2 flex w-full items-center justify-between gap-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
          >
            <div class="flex min-w-0 items-center gap-2">
              <AlertTriangle :size="16" class="shrink-0" />
              <span class="truncate">{{ chatBlockedReason }}</span>
            </div>
            <button
              @click="router.push('/llm-configs')"
              class="shrink-0 rounded border border-amber-300 bg-white px-2 py-1 text-xs text-amber-800 hover:bg-amber-100"
            >
              连接模型
            </button>
          </div>
        </div>
        <div class="max-w-4xl mx-auto flex gap-3 items-end">
          <textarea
            v-model="inputText"
            :disabled="loading || !chatReady"
            rows="1"
            @keydown.enter.exact.prevent="sendMessage"
            :placeholder="chatReady ? '输入消息，Enter 发送，Shift+Enter 换行' : chatBlockedReason"
            class="flex-1 resize-none px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
          ></textarea>
          <button
            v-if="loading"
            @click="stopGenerating"
            class="px-4 py-3 border border-slate-200 text-slate-600 text-sm font-medium rounded-xl hover:bg-slate-50 transition-colors"
          >
            停止
          </button>
          <button
            @click="sendMessage"
            :disabled="loading || !inputText.trim() || !chatReady"
            class="px-5 py-3 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:bg-blue-300 transition-colors"
          >
            发送
          </button>
        </div>
      </div>
    </section>
          <!-- 右下角：运行轨迹浮动按钮（仅本轮对话有 run 时可用） -->
    <div class="fixed bottom-24 right-6 z-30 flex flex-col items-end gap-2">
      <!-- 当前会话下产生的 run 数徽标 -->
      <button
        @click="showTraceDrawer = true"
        :disabled="runs.length === 0"
        class="group relative flex items-center gap-2 h-10 pl-3 pr-4 rounded-full
               bg-white border border-gray-200 shadow-sm
               hover:shadow hover:border-gray-300
               disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        <span class="w-6 h-6 rounded-full bg-purple-50 text-purple-600 flex items-center justify-center">
          <GitBranch :size="14" :stroke-width="2" />
        </span>
        <span class="text-sm font-medium text-gray-700">回答过程</span>
        <span v-if="runs.length > 0" class="text-xs px-1.5 h-5 rounded-full bg-purple-100 text-purple-700 flex items-center">
          {{ runs.length }}
        </span>
      </button>
    </div>

    <!-- Drawer 遮罩 -->
    <Transition name="fade">
      <div
        v-if="showTraceDrawer"
        class="fixed inset-0 bg-black/30 z-40"
        @click="showTraceDrawer = false"
      />
    </Transition>

    <!-- Drawer 面板（右侧滑入） -->
    <Transition name="slide">
      <aside
        v-if="showTraceDrawer"
        class="fixed top-0 right-0 h-full w-[480px] max-w-[92vw] bg-white shadow-2xl z-50 flex flex-col"
      >
        <!-- Drawer Header -->
        <header class="h-14 px-5 border-b border-gray-200 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-2">
            <span class="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <GitBranch :size="16" />
            </span>
            <div>
              <h3 class="text-sm font-semibold text-gray-800">回答过程</h3>
              <p class="text-xs text-gray-500">{{ currentAgent?.name || '' }}</p>
            </div>
          </div>
          <button
            @click="showTraceDrawer = false"
            class="w-8 h-8 rounded flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          >
            <X :size="16" />
          </button>
        </header>

        <!-- Drawer Body: 左列 Run 列表 + 右列 Step 详情（小屏折叠成上下） -->
        <div class="flex-1 min-h-0 flex">
          <!-- 左列：Run 列表 -->
          <div class="w-[210px] shrink-0 border-r border-gray-200 flex flex-col bg-gray-50/70">
            <div class="px-3 py-2 border-b border-gray-200">
              <div class="flex items-center justify-between">
                <span class="text-xs font-medium text-gray-500">最近回答</span>
                <button
                  @click="loadRuns()"
                  class="text-xs text-purple-600 hover:text-purple-700"
                >刷新</button>
              </div>
            </div>
            <div class="flex-1 overflow-y-auto p-2 space-y-1">
              <div v-if="runs.length === 0" class="text-xs text-gray-400 text-center py-8 px-2">
                暂无回答记录<br>发送一次对话后出现
              </div>
              <button
                v-for="r in runs"
                :key="r.id"
                @click="selectRun(r.id)"
                :class="[
                  'w-full text-left p-2.5 rounded-lg border transition-colors',
                  selectedRunId === r.id
                    ? 'border-purple-300 bg-purple-50'
                    : 'border-transparent hover:border-gray-200 hover:bg-white'
                ]"
              >
                <div class="flex items-center gap-1.5 mb-1">
                  <span :class="statusDot(r.status).dot" class="inline-block w-1.5 h-1.5 rounded-full"></span>
                  <span class="text-[11px] text-gray-400">#{{ r.id }}</span>
                  <span :class="statusDot(r.status).text" class="text-[10px] ml-auto font-medium">
                    {{ r.status === 'finished' ? '成功' : r.status === 'failed' ? '失败' : '运行中' }}
                  </span>
                </div>
                <p class="text-xs text-gray-700 line-clamp-2 leading-snug">{{ r.user_message }}</p>
                <p class="text-[10px] text-gray-400 mt-1.5">{{ r.started_at?.slice(5, 16) }} · {{ r.total_steps }}步</p>
              </button>
            </div>
          </div>

          <!-- 右列：Step 详情时间轴 -->
          <div class="flex-1 min-w-0 flex flex-col">
            <div v-if="!selectedRunDetail" class="flex-1 flex items-center justify-center text-xs text-gray-400 px-4 text-center">
              从左侧选择一次回答，查看详细步骤
            </div>
            <template v-else>
              <!-- Run 概览 -->
              <div class="px-4 py-3 border-b border-gray-100">
                <p class="text-xs text-gray-500 mb-1">用户问题</p>
                <p class="text-sm text-gray-800 leading-snug">{{ selectedRunDetail.user_message }}</p>
                <div v-if="selectedRunDetail.final_answer" class="mt-2">
                  <p class="text-xs text-gray-500 mb-1">最终回答</p>
                  <p class="text-xs text-gray-700 leading-relaxed max-h-24 overflow-y-auto">
                    {{ selectedRunDetail.final_answer }}
                  </p>
                </div>
              </div>

              <!-- Steps 时间轴 -->
              <div class="flex-1 overflow-y-auto px-4 py-3 space-y-4">
                <div v-if="selectedRunDetail.steps.length === 0" class="text-xs text-gray-400 text-center py-8">
                  该次运行没有步骤记录
                </div>
                <div v-for="step in selectedRunDetail.steps" :key="step.step_no" class="relative pl-6">
                  <!-- 时间轴竖线 -->
                  <div class="absolute left-1.5 top-3 bottom-[-16px] w-px bg-gray-200"></div>
                  <!-- 时间轴节点 -->
                  <div
                    :class="[
                      'absolute -left-0.5 top-1 w-4 h-4 rounded-full border-2 bg-white flex items-center justify-center shrink-0',
                      stepIcon(step).border
                    ]"
                  >
                    <component :is="stepIcon(step).icon" :size="10" :class="stepIcon(step).text" />
                  </div>

                  <!-- Step 卡片 -->
                  <div class="border border-gray-200 rounded-lg p-3 bg-white hover:shadow-sm transition-shadow">
                    <div class="flex items-center gap-2 mb-1.5">
                      <span :class="['text-[10px] font-medium px-1.5 h-4 rounded flex items-center', stepIcon(step).tag]">
                        Step {{ step.step_no }} · {{ stepLabel(step) }}
                      </span>
                      <span v-if="step.tokens" class="text-[10px] text-gray-400 ml-auto">
                        约 {{ step.tokens }} 字符消耗
                      </span>
                    </div>

                    <!-- thought / LLM 思考 -->
                    <div v-if="step.thought" class="text-xs text-gray-600 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded p-2 mb-2">
                      {{ step.thought.length > 400 ? step.thought.slice(0, 400) + '...' : step.thought }}
                    </div>

                    <!-- Tool 调用信息 -->
                    <div v-if="step.tool_name" class="space-y-1 text-xs">
                      <div class="flex items-start gap-2">
                        <span class="shrink-0 text-purple-600 font-medium">🔧 {{ step.tool_name }}</span>
                      </div>
                      <details class="group">
                        <summary class="text-gray-500 cursor-pointer select-none hover:text-gray-700 list-none">
                          <span class="inline-flex items-center gap-1">
                            <span class="group-open:rotate-90 transition-transform">▶</span>
                            工具参数
                          </span>
                        </summary>
                        <pre class="mt-1 p-2 rounded bg-gray-50 text-[11px] text-gray-700 overflow-x-auto">{{ prettyJson(step.tool_args) }}</pre>
                      </details>
                      <details v-if="step.tool_result" class="group">
                        <summary class="text-gray-500 cursor-pointer select-none hover:text-gray-700 list-none">
                          <span class="inline-flex items-center gap-1">
                            <span class="group-open:rotate-90 transition-transform">▶</span>
                            返回结果
                          </span>
                        </summary>
                        <pre class="mt-1 p-2 rounded bg-emerald-50 text-[11px] text-emerald-800 overflow-x-auto max-h-48 overflow-y-auto">{{ step.tool_result }}</pre>
                      </details>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </aside>
    </Transition>
    
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed, onBeforeUnmount } from 'vue'
import { useRoute ,useRouter } from 'vue-router'
import { marked } from 'marked'
import * as agentApi from '../api/agent'
import * as convApi from '../api/conversation'
import * as chatApi from '../api/chat'
import * as llmConfigApi from '../api/llmConfig'
import * as runApi from '../api/run'
import type { LlmConfig } from '../api/llmConfig'
import type { AgentRun, RunDetail } from '../api/run'
import type { Citation } from '../api/chat'
import CitationList from '../components/knowledge/CitationList.vue'
import AgentSubnav from '../components/agent/AgentSubnav.vue'
import {
  BookOpen, PlusCircle, MoreHorizontal, Pencil, Trash2, Pin, Archive,
  GitBranch, X, Wrench, Sparkles, AlertTriangle, Download, Search
} from 'lucide-vue-next'
import { toastError, toastSuccess } from '../utils/toast'
import { getErrorMessage } from '../utils/request'
const router = useRouter()
const route = useRoute()
const agentId = computed(() => Number(route.params.agentId))

const currentAgent = ref<any>(null)
const configs = ref<LlmConfig[]>([])
const conversations = ref<any[]>([])
const conversationQuery = ref('')
const conversationFilter = ref<'all' | 'active' | 'archived'>('active')
const currentConversationId = ref<number | null>(null)
const messages = ref<any[]>([])
const inputText = ref('')
const loading = ref(false)
const abortController = ref<AbortController | null>(null)
const messageListRef = ref<HTMLElement | null>(null)
const eventTraces = ref<any[]>([])
const configLoadError = ref('')
// ====== 运行轨迹 Drawer ======
const showTraceDrawer = ref(false)
const runs = ref<AgentRun[]>([])
const selectedRunId = ref<number | null>(null)
const selectedRunDetail = ref<RunDetail | null>(null)

const loadRuns = async (convId?: number | null) => {
  // 没有当前会话时 → 清空轨迹（新会话还没产生 run）
  const targetConvId = convId !== undefined ? convId : currentConversationId.value
  if (!targetConvId) {
    runs.value = []
    selectedRunId.value = null
    selectedRunDetail.value = null
    return
  }
  try {
    runs.value = await runApi.listRuns(agentId.value, 30, targetConvId)
    // 自动选中最新一条 run
    if (runs.value.length > 0 && selectedRunId.value === null) {
      await selectRun(runs.value[0].id)
    }
  } catch (e: any) {
    console.error('加载运行轨迹失败:', e)
    toastError(getErrorMessage(e, '加载运行轨迹失败'))
    runs.value = []
  }
}
const selectRun = async (runId: number) => {
  selectedRunId.value = runId
  try {
    selectedRunDetail.value = await runApi.getRunSteps(runId)
  } catch (e: any) {
    console.error('加载运行步骤失败:', e)
    toastError(getErrorMessage(e, '加载运行步骤失败'))
  }
}
// 运行状态颜色标签
const statusDot = (s: string) => ({
  running: { dot: 'bg-amber-400', text: 'text-amber-600' },
  finished: { dot: 'bg-emerald-500', text: 'text-emerald-600' },
  failed: { dot: 'bg-red-500', text: 'text-red-600' },
}[s] || { dot: 'bg-gray-400', text: 'text-gray-500' })

// Step 图标 + 标签
const stepIcon = (s: any) => {
  const t = String(s.step_type || '').toLowerCase()
  // 知识库检索
  if (t.includes('retrieve') || s.thought?.includes('检索') || s.thought?.includes('RAG')) {
    return { icon: BookOpen, text: 'text-amber-600', border: 'border-amber-300', tag: 'bg-amber-50 text-amber-700' }
  }
  if (t.includes('permission')) {
    return { icon: AlertTriangle, text: 'text-red-600', border: 'border-red-300', tag: 'bg-red-50 text-red-700' }
  }
  // Tool 调用
  if (t.includes('tool') || s.tool_name) {
    return { icon: Wrench, text: 'text-blue-600', border: 'border-blue-300', tag: 'bg-blue-50 text-blue-700' }
  }
  // 默认 LLM 思考
  return { icon: Sparkles, text: 'text-purple-600', border: 'border-purple-300', tag: 'bg-purple-50 text-purple-700' }
}
const stepLabel = (s: any) => {
  const t = String(s.step_type || '').toLowerCase()
  if (t.includes('retrieve')) return '知识库检索'
  if (t.includes('permission')) return '权限拒绝'
  if (t.includes('tool')) return '工具执行'
  if (s.tool_name) return '工具 ' + s.tool_name
  return 'LLM 推理'
}
const prettyJson = (v: any) => {
  if (v == null) return ''
  if (typeof v === 'string') {
    try { return JSON.stringify(JSON.parse(v), null, 2) } catch { return v }
  }
  try { return JSON.stringify(v, null, 2) } catch { return String(v) }
}

const configuredModelNames = computed(() => new Set(configs.value.map((config) => config.model_name.toLowerCase())))
const hasCurrentModelKey = computed(() => {
  const modelName = String(currentAgent.value?.model_name || '').trim().toLowerCase()
  return Boolean(modelName && configuredModelNames.value.has(modelName))
})
const hasEmbeddingKey = computed(() => configs.value.some((config) => {
  const modelName = config.model_name.toLowerCase()
  return modelName.includes('embedding') || modelName.startsWith('baai/') || modelName === 'glm-4'
}))
const chatBlockedReason = computed(() => {
  if (configLoadError.value) return configLoadError.value
  if (!currentAgent.value) return '当前助手不存在或无权限访问'
  if (!hasCurrentModelKey.value) return `当前用户还没有配置「${currentAgent.value.model_name || '聊天模型'}」的密钥`
  if (currentAgent.value.rag_enabled === 1 && !hasEmbeddingKey.value) return '当前助手已开启资料库，但还没有配置资料检索模型密钥'
  return ''
})
const chatReady = computed(() => !chatBlockedReason.value)
const conversationFilters: Array<{ label: string; value: 'all' | 'active' | 'archived' }> = [
  { label: '正常', value: 'active' },
  { label: '全部', value: 'all' },
  { label: '归档', value: 'archived' },
]
const filteredConversations = computed(() => {
  const query = conversationQuery.value.trim().toLowerCase()
  return conversations.value.filter((conversation) => {
    if (conversationFilter.value === 'active' && conversation.is_archived === 1) return false
    if (conversationFilter.value === 'archived' && conversation.is_archived !== 1) return false
    if (!query) return true
    return String(conversation.title || '').toLowerCase().includes(query)
  })
})

const renderMarkdown = (text: string) => marked.parse(text || '') as string
const short = (s: string, n: number) => {
  const s2 = s || ''
  return s2.length > n ? s2.slice(0, n) + '...' : s2
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const loadConversations = async () => {
  conversations.value = await convApi.listConversations(agentId.value)
}

const loadCurrentAgent = async () => {
  try {
    const agentList = await agentApi.listAgents()
    currentAgent.value = agentList.find((agent: any) => agent.id === agentId.value) || null
  } catch (e: any) {
    console.error('加载助手信息失败:', e)
    toastError(getErrorMessage(e, '加载助手信息失败'))
    currentAgent.value = null
  }
}

const loadConfigs = async () => {
  configLoadError.value = ''
  try {
    configs.value = await llmConfigApi.listConfigs()
  } catch (e: any) {
    configs.value = []
    configLoadError.value = getErrorMessage(e, '无法读取模型连接')
  }
}

const selectConversation = async (convId: number) => {
  currentConversationId.value = convId
  messages.value = await convApi.listMessages(convId)
  eventTraces.value = []
  // 切会话 → 清空旧 run 选中 + 加载该会话的 runs
  selectedRunId.value = null
  selectedRunDetail.value = null
  await loadRuns(convId)
  scrollToBottom()
}

const createNewConversation = () => {
  currentConversationId.value = null
  messages.value = []
  eventTraces.value = []
  selectedRunId.value = null
  selectedRunDetail.value = null
  runs.value = []
}
// ====== 会话项：更多功能菜单 ======
const menuConvId = ref<number | null>(null)
const editingConvId = ref<number | null>(null)
const renameText = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

const openMenu = (convId: number) => {
  // 关闭其它：有则无，无则打开当前行（再次点同个按钮就关闭）
  menuConvId.value = menuConvId.value === convId ? null : convId
}

// 点击空白处关闭菜单
const onDocClick = () => {
  if (!menuConvId.value) return
  // 点在按钮/弹窗里的已经用 @click.stop 吞了
  menuConvId.value = null
}
onMounted(() => { document.addEventListener('click', onDocClick) })
onBeforeUnmount(() => { document.removeEventListener('click', onDocClick) })
// 记得把 onBeforeUnmount 加到 import（没加就加在 vue 的 import 里）

const isPinned = (id: number) => conversations.value.find(c => c.id === id)?.is_pinned === 1
const isArchived = (id: number) => conversations.value.find(c => c.id === id)?.is_archived === 1

const togglePin = async (id: number) => {
  const next = isPinned(id) ? 0 : 1
  try {
    const updated = await convApi.updateConversationFlags(id, { is_pinned: next })
    const idx = conversations.value.findIndex(x => x.id === id)
    if (idx !== -1) conversations.value[idx] = { ...conversations.value[idx], ...updated }
    resortConversations()
  } catch (e: any) {
    toastError(getErrorMessage(e, '置顶失败'))
  } finally {
    menuConvId.value = null
  }
}

const toggleArchive = async (c: any) => {
  const next = isArchived(c.id) ? 0 : 1
  try {
    const updated = await convApi.updateConversationFlags(c.id, { is_archived: next })
    const idx = conversations.value.findIndex(x => x.id === c.id)
    if (idx !== -1) conversations.value[idx] = { ...conversations.value[idx], ...updated }
    resortConversations()
    if (currentConversationId.value === c.id && next === 1) {
      const nextConv = filteredConversations.value.find(x => x.id !== c.id && !isArchived(x.id))
      nextConv ? selectConversation(nextConv.id) : createNewConversation()
    }
  } catch (e: any) {
    toastError(getErrorMessage(e, '归档失败'))
  } finally {
    menuConvId.value = null
  }
}

// 归档的会话沉底；置顶的浮顶
const resortConversations = () => {
  const all = [...conversations.value]
  all.sort((a, b) => {
    const pa = isArchived(a.id) ? 2 : isPinned(a.id) ? 0 : 1
    const pb = isArchived(b.id) ? 2 : isPinned(b.id) ? 0 : 1
    if (pa !== pb) return pa - pb
    return String(b.update_time || '').localeCompare(String(a.update_time || ''))
  })
  conversations.value = all
}

// ====== 重命名 ======
const startRename = (c: any) => {
  editingConvId.value = c.id
  renameText.value = c.title
  menuConvId.value = null
  // DOM 更新后聚焦
  nextTick(() => {
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

const cancelRename = () => {
  editingConvId.value = null
  renameText.value = ''
}

const commitRename = async (convId: number) => {
  const newTitle = renameText.value.trim()
  if (newTitle && editingConvId.value === convId) {
    // 调 API 改标题
    try {
      const updated = await convApi.updateConversationTitle(convId, newTitle)
      const idx = conversations.value.findIndex(x => x.id === convId)
      if (idx !== -1 && updated) {
        conversations.value[idx] = { ...conversations.value[idx], ...updated }
      }
    } catch (e: any) {
      toastError(getErrorMessage(e, '重命名失败'))
    }
  }
  cancelRename()
}

// ====== 删除 ======
const handleDeleteConv = async (c: any) => {
  if (!confirm(`确认删除会话「${c.title}」？该操作不可恢复。`)) return
  try {
    await convApi.deleteConversation(c.id)
    menuConvId.value = null
    await loadConversations()
    resortConversations()
    if (currentConversationId.value === c.id) {
      createNewConversation()
      if (conversations.value.length > 0) selectConversation(conversations.value[0].id)
    }
  } catch (e: any) {
    toastError(getErrorMessage(e, '删除失败'))
  }
}

const handleExportConv = async (c: any, format: 'markdown' | 'json') => {
  try {
    const blob = await convApi.exportConversation(c.id, format)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${c.title || 'conversation'}_${c.id}.${format === 'json' ? 'json' : 'md'}`
    link.click()
    URL.revokeObjectURL(url)
    menuConvId.value = null
    toastSuccess('会话已导出')
  } catch (e: any) {
    toastError(getErrorMessage(e, '导出失败'))
  }
}
const sendMessage = async () => {
  const msg = inputText.value.trim()
  if (!msg || loading.value) return
  if (!chatReady.value) {
    toastError(chatBlockedReason.value)
    return
  }

  loading.value = true
  abortController.value = new AbortController()
  eventTraces.value = []
  // 先加 user 消息到 UI
  messages.value.push({ role: 'user', content: msg })
  inputText.value = ''
  scrollToBottom()

  // 临时占位 assistant 消息，流式往里面塞内容
  const placeholderIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '' })

  try {
    await chatApi.sendStream({
      agentId: agentId.value,
      conversationId: currentConversationId.value,
      message: msg,
      onEvent: async (evt) => {
                if (evt.type === 'ready' && evt.run_id) {
          // 可选：记 run_id 供轨迹
        } else if (evt.type === 'retrieval') {
          eventTraces.value.push({ type: 'retrieval', hit_count: evt.hit_count })
        } else if (evt.type === 'citations') {
          messages.value[placeholderIdx].citations = (evt.citations || []) as Citation[]
        } else if (evt.type === 'thinking') {
          eventTraces.value.push({ type: 'thinking', content: evt.content || '' })
        } else if (evt.type === 'tool_call') {
          eventTraces.value.push({ type: 'tool_call', name: evt.name, args: evt.args || {} })
        } else if (evt.type === 'tool_result') {
          eventTraces.value.push({ type: 'tool_result', name: evt.name, result: evt.result || '' })
        } else if (evt.type === 'answer') {
          // answer 事件：完整内容替换（因为是 answer 而不是 token 流）
          messages.value[placeholderIdx].content = evt.content || ''
               } else if (evt.type === 'done') {
          // 完成：刷新会话列表 + 按当前会话刷新运行轨迹
          if (evt.conversation_id) {
            currentConversationId.value = evt.conversation_id
            await loadConversations()
            resortConversations()
          }
          await loadRuns(evt.conversation_id || currentConversationId.value)
      
        } else if (evt.type === 'error') {
          messages.value[placeholderIdx].content = '发送失败：' + (evt.message || evt.detail || '后端处理出错')
        }
        scrollToBottom()
      },
      signal: abortController.value.signal,
    })
  } catch (e: any) {
    if (e?.name === 'AbortError') {
      messages.value[placeholderIdx].content = messages.value[placeholderIdx].content || '已停止生成'
    } else {
      messages.value[placeholderIdx].content = '发送失败：' + getErrorMessage(e, '后端处理出错')
    }
  } finally {
    loading.value = false
    abortController.value = null
    scrollToBottom()
  }
}

const stopGenerating = () => {
  abortController.value?.abort()
}

onMounted(async () => {
  await Promise.all([loadCurrentAgent(), loadConfigs()])
  await loadConversations()
  resortConversations()
  if (conversations.value.length > 0) {
    await selectConversation(conversations.value[0].id)  // ← 里面会 loadRuns(convId)
  } else {
    await loadRuns()  // 无会话 → 清空
  }
})

// 切 Agent 时刷新
watch(agentId, async () => {
  await Promise.all([loadCurrentAgent(), loadConfigs()])
  createNewConversation()              // 内部会清空 runs
  selectedRunId.value = null
  selectedRunDetail.value = null
  await loadConversations()
  resortConversations()
  if (conversations.value.length > 0) {
    await selectConversation(conversations.value[0].id)  // ← 里面会 loadRuns(convId)
  }
})
</script>
<style scoped>
/* 图标整体向上偏移 0.7px（SVG 字形设计的视觉中心略低于盒子中心） */
.icon-shift {
  transform: translateY(-0.7px);
  flex-shrink: 0;
}
/* Drawer 过渡 */
.fade-enter-from, .fade-leave-to { opacity: 0; }
.fade-enter-active, .fade-leave-active { transition: opacity .18s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }
.slide-enter-active, .slide-leave-active { transition: transform .24s ease; }
</style>
