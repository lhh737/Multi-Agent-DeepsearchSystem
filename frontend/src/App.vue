<template>
  <div class="app" :class="{ dark: isDark }">
    <!-- Home -->
    <div v-if="!expanded" class="home">
      <button class="theme-toggle" @click="isDark = !isDark" :title="isDark ? '亮色模式' : '暗色模式'">
        {{ isDark ? '☀️' : '🌙' }}
      </button>
      <h1>Deep Research Agent</h1>
      <p class="subtitle">基于 LangGraph 多智能体协作的深度研究系统</p>
      <div class="tags">
        <span>Planner → Executor → Reporter → Critic</span>
        <span>Postgres + Redis + LangSmith</span>
      </div>

      <form @submit.prevent="start" class="search-form">
        <textarea
          v-model="topic"
          placeholder="输入你想研究的主题，例如：大模型 Agent 在 2025 年的落地进展"
          rows="3"
          :disabled="loading"
        ></textarea>
        <div class="form-actions">
          <button type="submit" class="btn-primary" :disabled="loading || !topic.trim()">
            <span v-if="loading" class="spinner"></span>
            {{ loading ? '研究进行中...' : '开始研究' }}
          </button>
          <button v-if="loading" type="button" class="btn-secondary" @click="cancel">取消</button>
        </div>
      </form>

      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <!-- Research view -->
    <div v-else class="research-view">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div class="sidebar-top">
          <button class="back-btn" @click="reset" :disabled="loading">&larr; 返回首页</button>
          <button class="theme-toggle sm" @click="isDark = !isDark">{{ isDark ? '☀️' : '🌙' }}</button>
        </div>

        <div class="meta">
          <div class="meta-item">
            <label>研究主题</label>
            <p class="topic-text">{{ topic }}</p>
          </div>
          <div class="meta-item">
            <label>当前阶段</label>
            <p class="stage">{{ stageLabel }}</p>
          </div>
          <div class="meta-item" v-if="totalTasks > 0">
            <label>任务进度</label>
            <div class="progress-bar">
              <div class="fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
            <p class="progress-text">{{ completedTasks }} / {{ totalTasks }}</p>
          </div>
          <div class="meta-item" v-if="criticScore > 0">
            <label>Critic 评分</label>
            <p class="score">
              {{ criticScore.toFixed(1) }}<span class="score-max">/5.0</span>
              <span class="iterations">({{ iterations }}轮迭代)</span>
            </p>
          </div>
          <div class="meta-item" v-if="sessionId">
            <label>会话 ID</label>
            <p class="session-id">{{ sessionId.slice(0, 12) }}…</p>
          </div>
        </div>

        <!-- Iteration timeline -->
        <div class="iterations-panel" v-if="iterationHistory.length > 0">
          <label>迭代历史</label>
          <div class="iter-list">
            <div v-for="(it, i) in iterationHistory" :key="i" class="iter-item" :class="{ active: i === iterationHistory.length - 1 }">
              <span class="iter-num">#{{ i + 1 }}</span>
              <span class="iter-score">{{ it.score.toFixed(1) }}</span>
              <span class="iter-label">{{ it.label }}</span>
            </div>
          </div>
        </div>

        <div class="sidebar-actions" v-if="finalReport">
          <button class="action-btn" @click="copyReport">
            📋 复制报告
          </button>
          <button class="action-btn" @click="downloadReport">
            📥 下载 Markdown
          </button>
          <button class="action-btn" @click="startNew">
            🔄 开始新研究
          </button>
        </div>
      </aside>

      <!-- Main content -->
      <main class="content">
        <!-- Live logs -->
        <div v-if="logs.length && !finalReport" class="timeline">
          <div v-for="(msg, i) in logs" :key="i" class="log-entry">{{ msg }}</div>
        </div>

        <!-- Task cards -->
        <div v-if="tasks.length" class="tasks-grid">
          <div
            v-for="task in tasks"
            :key="task.id"
            class="task-card"
            :class="'status-' + task.status"
            @click="activeTaskId = task.id"
          >
            <div class="task-header">
              <h3>{{ task.title }}</h3>
              <span class="badge" :class="task.status">{{ statusLabel(task.status) }}</span>
            </div>
            <p class="task-intent">{{ task.intent }}</p>

            <!-- Expanded task detail -->
            <div v-if="activeTaskId === task.id && task.summary" class="task-detail">
              <div class="task-summary" v-html="renderMd(task.summary)"></div>
              <div v-if="task.sources" class="task-sources">
                <h4>信息来源</h4>
                <div v-html="renderMd(task.sources)"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Final report -->
        <div v-if="finalReport" class="report-section">
          <div class="report-header">
            <h2>研究报告</h2>
            <div class="report-actions">
              <button class="action-btn sm" @click="copyReport">📋 复制</button>
              <button class="action-btn sm" @click="downloadReport">📥 下载</button>
            </div>
          </div>

          <div v-if="criticScore > 0" class="report-score">
            Critic 终评 {{ criticScore.toFixed(1) }}/5.0 · {{ iterations }}轮迭代 · {{ finalReport.length }}字
          </div>

          <div class="report-body markdown-body" v-html="renderMd(finalReport)"></div>
        </div>

        <!-- Empty state -->
        <div v-if="!tasks.length && !finalReport && loading" class="loading-state">
          <div class="pulse"></div>
          <p>正在启动多智能体协作…</p>
        </div>
      </main>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="toast" :class="toast.type">{{ toast.msg }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from "vue";
import { marked } from "marked";
import { streamResearch, type SSEEvent, type ResearchRequest } from "./services/api";

// --- Markdown setup ---
marked.setOptions({ breaks: true, gfm: true });

function renderMd(text: string): string {
  if (!text) return "";
  try {
    return marked.parse(text) as string;
  } catch {
    return text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}

// --- State ---
const topic = ref("");
const loading = ref(false);
const expanded = ref(false);
const error = ref("");
const logs = ref<string[]>([]);
const stage = ref("初始化");
const criticScore = ref(0);
const iterations = ref(0);
const sessionId = ref("");
const isDark = ref(false);
const toast = ref<{ msg: string; type: string } | null>(null);
const activeTaskId = ref<number | null>(null);

const tasks = ref<TaskView[]>([]);
const finalReport = ref("");
const iterationHistory = ref<Array<{ score: number; label: string }>>([]);

let controller: AbortController | null = null;

interface TaskView {
  id: number; title: string; intent: string; query: string;
  status: string; summary: string; sources: string;
}

const totalTasks = computed(() => tasks.value.length);
const completedTasks = computed(() => tasks.value.filter((t) => t.status === "completed").length);
const progressPercent = computed(() =>
  totalTasks.value ? Math.round((completedTasks.value / totalTasks.value) * 100) : 0
);
const stageLabel = computed(() => {
  if (finalReport.value) return "已完成";
  if (criticScore.value > 0 && !finalReport.value) return "迭代优化中";
  if (tasks.value.some((t) => t.status === "completed")) return "任务执行中";
  if (tasks.value.length > 0) return "任务规划完成";
  return "初始化";
});

function statusLabel(s: string): string {
  return { pending: "待执行", in_progress: "进行中", completed: "已完成", skipped: "已跳过" }[s] || s;
}

function showToast(msg: string, type = "info") {
  toast.value = { msg, type };
  setTimeout(() => (toast.value = null), 2500);
}

// --- Event handler ---
function handleEvent(event: SSEEvent) {
  const { type, data } = event;
  switch (type) {
    case "status":
      logs.value.push(data.message as string);
      break;

    case "todo_list": {
      const list = data.tasks as Array<Record<string, unknown>>;
      tasks.value = list.map((t, i) => ({
        id: (t.id as number) || i + 1,
        title: (t.title as string) || `任务${i + 1}`,
        intent: (t.intent as string) || "",
        query: (t.query as string) || "",
        status: (t.status as string) || "pending",
        summary: "",
        sources: "",
      }));
      if (tasks.value.length) activeTaskId.value = tasks.value[0].id;
      stage.value = "任务规划完成";
      break;
    }

    case "task_status": {
      const taskId = data.task_id as number;
      const task = tasks.value.find((t) => t.id === taskId);
      if (!task) return;
      task.status = data.status as string;
      if (data.summary) task.summary = data.summary as string;
      if (data.sources) task.sources = data.sources as string;
      if (task.status === "completed") logs.value.push(`✅ ${task.title}`);
      else if (task.status === "skipped") logs.value.push(`⚠️ ${task.title}（无结果）`);
      else if (task.status === "in_progress") logs.value.push(`🔍 ${task.title}`);
      if (task.status === "completed" || task.status === "skipped") {
        activeTaskId.value = task.id;
      }
      break;
    }

    case "critic_result": {
      const score = data.score as number;
      criticScore.value = score;
      if (data.iteration) iterations.value = data.iteration as number;
      iterationHistory.value.push({
        score,
        label: score >= 4 ? "通过" : "需优化",
      });
      logs.value.push(`📊 Critic #${iterations.value}: ${score}/5 → ${score >= 4 ? '通过' : '继续优化'}`);
      break;
    }

    case "final_report": {
      finalReport.value = data.report as string;
      if (data.session_id) sessionId.value = data.session_id as string;
      logs.value.push("📝 报告已生成");
      break;
    }

    case "error": {
      error.value = data.detail as string;
      logs.value.push(`❌ ${data.detail}`);
      break;
    }
  }
}

async function start() {
  if (!topic.value.trim()) return;
  if (controller) controller.abort();

  loading.value = true; expanded.value = true; error.value = "";
  logs.value = []; tasks.value = []; finalReport.value = "";
  criticScore.value = 0; iterations.value = 0;
  sessionId.value = ""; activeTaskId.value = null;
  iterationHistory.value = [];
  stage.value = "初始化";
  controller = new AbortController();

  try {
    await streamResearch({ topic: topic.value.trim() }, handleEvent, controller.signal);
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      logs.value.push("已取消");
    } else {
      error.value = err instanceof Error ? err.message : "请求失败";
    }
  } finally {
    loading.value = false;
    controller = null;
  }
}

function cancel() { controller?.abort(); }
function reset() { cancel(); expanded.value = false; tasks.value = []; finalReport.value = ""; logs.value = []; }
function startNew() { reset(); topic.value = ""; }

async function copyReport() {
  if (!finalReport.value) return;
  try {
    await navigator.clipboard.writeText(finalReport.value);
    showToast("报告已复制到剪贴板", "success");
  } catch {
    showToast("复制失败，请手动复制", "error");
  }
}

function downloadReport() {
  if (!finalReport.value) return;
  const blob = new Blob([finalReport.value], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `research-${topic.value.slice(0, 20)}.md`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("报告已下载", "success");
}

onBeforeUnmount(() => controller?.abort());
</script>

<style scoped>
/* ====== Base ====== */
.app {
  min-height: 100vh;
  --bg: #f8fafc; --surface: #fff; --border: #e2e8f0;
  --text: #1e293b; --muted: #64748b; --primary: #3b82f6;
  --accent: #8b5cf6; --success: #22c55e; --warning: #f59e0b;
  background: var(--bg); color: var(--text);
  font-family: "Inter", system-ui, -apple-system, sans-serif;
  line-height: 1.6;
}
.app.dark {
  --bg: #0f172a; --surface: #1e293b; --border: #334155;
  --text: #f1f5f9; --muted: #94a3b8; --primary: #60a5fa;
  --accent: #a78bfa;
}

/* Home */
.home { max-width: 640px; margin: 0 auto; padding: 100px 24px; text-align: center; }
.home h1 { font-size: 32px; font-weight: 700; margin-bottom: 8px; }
.subtitle { color: var(--muted); font-size: 15px; margin-bottom: 20px; }
.tags { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-bottom: 32px; }
.tags span {
  padding: 4px 12px; border-radius: 99px; font-size: 12px; font-weight: 500;
  background: var(--surface); border: 1px solid var(--border); color: var(--muted);
}
.theme-toggle {
  position: absolute; top: 16px; right: 16px;
  padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface); cursor: pointer; font-size: 16px;
}
.theme-toggle.sm { position: static; font-size: 14px; padding: 4px 8px; }

.search-form { display: flex; flex-direction: column; gap: 16px; }
.search-form textarea {
  width: 100%; padding: 16px; border: 1px solid var(--border); border-radius: 12px;
  font-size: 15px; resize: vertical; background: var(--surface); color: var(--text);
  font-family: inherit;
}
.search-form textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }
.form-actions { display: flex; gap: 12px; justify-content: center; }
.btn-primary {
  padding: 12px 28px; background: linear-gradient(135deg, var(--primary), var(--accent));
  color: #fff; border: none; border-radius: 12px; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;
}
.btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(59,130,246,0.3); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary {
  padding: 12px 24px; background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; font-size: 14px; cursor: pointer; color: var(--text);
}
.spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 6px; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { margin-top: 16px; padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; color: #ef4444; font-size: 14px; }

/* Research view */
.research-view { display: flex; min-height: 100vh; }
.sidebar {
  width: 320px; min-width: 320px; padding: 24px; background: var(--surface);
  border-right: 1px solid var(--border); display: flex; flex-direction: column;
  gap: 20px; overflow-y: auto; max-height: 100vh; position: sticky; top: 0;
}
.sidebar-top { display: flex; justify-content: space-between; align-items: center; }
.back-btn {
  padding: 8px 16px; background: transparent; border: 1px solid var(--border);
  border-radius: 8px; cursor: pointer; color: var(--muted); font-size: 14px;
}
.back-btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.back-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.meta { display: flex; flex-direction: column; gap: 16px; }
.meta-item label { display: block; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin-bottom: 4px; }
.meta-item p { font-size: 14px; }
.topic-text { font-weight: 600; padding: 8px 12px; background: rgba(59,130,246,0.08); border-radius: 8px; border-left: 3px solid var(--primary); }
.stage { color: var(--primary); font-weight: 600; }
.score { font-size: 20px; font-weight: 700; color: var(--primary); }
.score-max { font-size: 14px; color: var(--muted); }
.iterations { font-size: 12px; color: var(--muted); font-weight: 400; }
.session-id { font-size: 12px; font-family: monospace; color: var(--muted); }
.progress-bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.progress-bar .fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--accent)); border-radius: 4px; transition: width 0.5s ease; }
.progress-text { font-size: 13px; color: var(--muted); margin-top: 4px; }

/* Iteration timeline */
.iterations-panel { padding-top: 8px; border-top: 1px solid var(--border); }
.iterations-panel > label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); }
.iter-list { display: flex; gap: 8px; margin-top: 8px; }
.iter-item {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 8px 14px; border-radius: 10px; background: var(--bg); border: 1px solid var(--border);
}
.iter-item.active { border-color: var(--primary); background: rgba(59,130,246,0.08); }
.iter-num { font-size: 11px; color: var(--muted); }
.iter-score { font-size: 18px; font-weight: 700; }
.iter-label { font-size: 11px; color: var(--muted); }

.sidebar-actions { display: flex; flex-direction: column; gap: 8px; padding-top: 12px; border-top: 1px solid var(--border); }
.action-btn {
  padding: 10px 16px; border: 1px solid var(--border); border-radius: 10px;
  background: var(--surface); color: var(--text); font-size: 14px; cursor: pointer;
  text-align: left; transition: border-color 0.2s, background 0.2s;
}
.action-btn:hover { border-color: var(--primary); background: rgba(59,130,246,0.05); }
.action-btn.sm { font-size: 12px; padding: 6px 12px; }

/* Content */
.content { flex: 1; padding: 28px 32px; overflow-y: auto; max-width: 960px; }
.timeline { margin-bottom: 20px; }
.log-entry {
  padding: 6px 12px; margin-bottom: 4px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; font-size: 13px; color: var(--muted);
}

/* Tasks */
.tasks-grid { display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px; }
.task-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px 20px; cursor: pointer; transition: all 0.2s;
}
.task-card:hover { border-color: var(--primary); }
.task-card.status-completed { border-left: 4px solid var(--success); }
.task-card.status-in_progress { border-left: 4px solid var(--primary); animation: pulse-border 2s infinite; }
.task-card.status-skipped { border-left: 4px solid var(--warning); opacity: 0.65; }
@keyframes pulse-border { 0%,100% { border-color: var(--primary); } 50% { border-color: var(--accent); } }
.task-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
.task-header h3 { font-size: 15px; font-weight: 600; margin: 0; }
.badge { padding: 2px 10px; border-radius: 99px; font-size: 11px; font-weight: 500; }
.badge.pending { background: #f1f5f9; color: #64748b; }
.badge.in_progress { background: #eff6ff; color: #2563eb; }
.badge.completed { background: #f0fdf4; color: #16a34a; }
.badge.skipped { background: #fffbeb; color: #d97706; }
.task-intent { color: var(--muted); font-size: 13px; margin: 0; }
.task-detail { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.task-summary { font-size: 14px; line-height: 1.7; }
.task-sources { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 13px; }
.task-sources h4 { font-size: 13px; margin-bottom: 4px; color: var(--muted); }

/* Report */
.report-section { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 28px; }
.report-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.report-header h2 { margin: 0; font-size: 22px; }
.report-actions { display: flex; gap: 8px; }
.report-score {
  padding: 8px 14px; background: #f0fdf4; border: 1px solid #bbf7d0;
  border-radius: 8px; margin-bottom: 20px; color: #16a34a; font-size: 13px; font-weight: 500;
}

/* Markdown body */
.markdown-body { font-size: 15px; line-height: 1.8; }
.markdown-body :deep(h1) { font-size: 1.8em; margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 2px solid var(--border); }
.markdown-body :deep(h2) { font-size: 1.5em; margin: 24px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
.markdown-body :deep(h3) { font-size: 1.25em; margin: 20px 0 8px; }
.markdown-body :deep(h4) { font-size: 1.1em; margin: 16px 0 6px; }
.markdown-body :deep(p) { margin-bottom: 12px; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 8px 0 8px 24px; }
.markdown-body :deep(li) { margin-bottom: 4px; }
.markdown-body :deep(a) { color: var(--primary); }
.markdown-body :deep(strong) { font-weight: 600; }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px; }
.markdown-body :deep(th), .markdown-body :deep(td) { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
.markdown-body :deep(th) { background: var(--bg); font-weight: 600; }
.markdown-body :deep(code) { padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.06); font-size: 0.9em; }
.markdown-body :deep(pre) { padding: 16px; border-radius: 10px; overflow-x: auto; font-size: 13px; line-height: 1.5; }
.markdown-body :deep(pre code) { padding: 0; background: none; }
.markdown-body :deep(blockquote) { border-left: 3px solid var(--primary); padding: 4px 16px; margin: 12px 0; color: var(--muted); }
.markdown-body :deep(hr) { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
.dark .markdown-body :deep(code) { background: rgba(255,255,255,0.08); }

.loading-state { text-align: center; padding: 80px 0; color: var(--muted); }
.pulse { width: 48px; height: 48px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--accent)); margin: 0 auto 20px; animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.6; transform: scale(0.95); } }

/* Toast */
.toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 10px 24px; border-radius: 10px; font-size: 14px; z-index: 999; }
.toast.success { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
.toast.error { background: #fef2f2; color: #ef4444; border: 1px solid #fecaca; }
.toast.info { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }

@media (max-width: 768px) {
  .research-view { flex-direction: column; }
  .sidebar { width: 100%; min-width: 100%; max-height: auto; position: static; }
  .content { padding: 20px 16px; }
}
</style>
