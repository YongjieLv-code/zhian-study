<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  Archive,
  ArrowDownToLine,
  ArrowRight,
  BookMarked,
  BookOpen,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock3,
  Flame,
  Flower2,
  House,
  Leaf,
  LoaderCircle,
  LockKeyhole,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sprout,
  Target,
  Timer,
  Trash2,
  TrendingUp,
  Upload,
  X,
} from "lucide-vue-next";
import { ApiError, api, download, request, setSession } from "./api";
import type {
  EditorMode,
  AuthStatus,
  Overview,
  Page,
  Plan,
  Profile,
  ReviewItem,
  StudyLog,
  Subject,
  TimerState,
} from "./types";
import {
  addDays,
  clockText,
  dateLabel,
  formatMinutes,
  monday,
  percentage,
  studyToday,
} from "./utils";
import { useTimer } from "./useTimer";
import ActivityChart from "./components/ActivityChart.vue";
import AccountPanel from "./components/AccountPanel.vue";
import AuthForm from "./components/AuthForm.vue";
import BackupDialog from "./components/BackupDialog.vue";
import BaseModal from "./components/BaseModal.vue";
import EditorDialog from "./components/EditorDialog.vue";
import FocusDialog from "./components/FocusDialog.vue";
import PlanRow from "./components/PlanRow.vue";
import ReviewSession from "./components/ReviewSession.vue";
import StudyCalendar from "./components/StudyCalendar.vue";

const nav = [
  { id: "today" as Page, title: "今日概览", short: "今日", icon: House },
  { id: "plan" as Page, title: "学习计划", short: "计划", icon: CalendarDays },
  { id: "review" as Page, title: "复习卡片", short: "复习", icon: BookMarked },
  {
    id: "records" as Page,
    title: "学习记录",
    short: "记录",
    icon: ClipboardList,
  },
  {
    id: "insights" as Page,
    title: "数据复盘",
    short: "复盘",
    icon: TrendingUp,
  },
];
const page = ref<Page>("today");
const overview = ref<Overview | null>(null);
const subjects = ref<Subject[]>([]),
  plans = ref<Plan[]>([]),
  logs = ref<StudyLog[]>([]),
  reviews = ref<ReviewItem[]>([]);
const loading = ref(true),
  refreshing = ref(false),
  loadError = ref("");
const toast = ref("");
const auth = ref<AuthStatus | null>(null);
const authOpen = ref(false),
  backupOpen = ref(false),
  accountBusy = ref(false),
  exportBusy = ref(false);
const syncedAt = ref("");
let toastTimeout: ReturnType<typeof setTimeout>;
let loadGeneration = 0;
const today = computed(() => overview.value?.date ?? studyToday());
const profile = computed<Profile>(
  () =>
    overview.value?.profile ?? {
      id: 1,
      name: "备考者",
      exam_name: "我的备考计划",
      exam_date: null,
      daily_goal_minutes: 120,
    },
);
const subjectMap = computed(() =>
  Object.fromEntries(subjects.value.map((subject) => [subject.id, subject])),
);
const pageTitle = computed(
  () => nav.find((item) => item.id === page.value)?.title ?? "我的目标",
);
const weekLogs = computed(() =>
  logs.value.filter(
    (log) =>
      log.study_date >= addDays(today.value, -6) &&
      log.study_date <= today.value,
  ),
);
const weekMinutes = computed(() =>
  weekLogs.value.reduce((sum, log) => sum + log.duration_minutes, 0),
);
const weekQuestions = computed(() =>
  weekLogs.value.reduce((sum, log) => sum + log.question_count, 0),
);
const weekAccuracy = computed(() =>
  percentage(
    weekLogs.value.reduce((sum, log) => sum + log.correct_count, 0),
    weekQuestions.value,
  ),
);
const todayPlans = computed(() =>
  plans.value
    .filter((plan) => plan.scheduled_date === today.value)
    .sort((a, b) => Number(a.completed) - Number(b.completed)),
);
const completedTodayPlans = computed(
  () => todayPlans.value.filter((plan) => plan.completed).length,
);
const overduePlans = computed(() =>
  plans.value.filter(
    (plan) => plan.scheduled_date < today.value && !plan.completed,
  ),
);
const dueReviews = computed(() =>
  reviews.value.filter(
    (item) => !item.archived && item.due_date <= today.value,
  ),
);
const goalPercent = computed(() =>
  Math.min(
    100,
    Math.round(
      ((overview.value?.today.minutes ?? 0) /
        profile.value.daily_goal_minutes) *
        100,
    ),
  ),
);

interface EditorState {
  mode: EditorMode;
  plan?: Plan;
  log?: StudyLog;
  review?: ReviewItem;
  initialDate?: string;
  timer?: TimerState;
  timerMinutes?: number;
}
const editor = ref<EditorState | null>(null);
const reviewSession = ref<ReviewItem | null>(null);
const focusOpen = ref(false),
  focusPlan = ref<Plan>();
const focus = useTimer();
const { timer, elapsed, storageAvailable } = focus;
const confirm = ref<{
  title: string;
  description: string;
  path: string;
} | null>(null);
const actionBusy = ref(false),
  actionError = ref("");

async function load() {
  const generation = ++loadGeneration;
  refreshing.value = true;
  try {
    const data = await api.workspace();
    if (generation !== loadGeneration) return;
    acceptAuth(data.auth);
    if (!overview.value || selectedPlanDate.value === overview.value.date) {
      selectedPlanDate.value = data.overview.date;
    }
    [overview.value, subjects.value, plans.value, logs.value, reviews.value] = [
      data.overview,
      data.subjects,
      data.plans,
      data.logs,
      data.reviews,
    ];
    syncedAt.value = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    loadError.value = "";
  } catch (err) {
    if (generation !== loadGeneration) return;
    if (err instanceof ApiError && err.status === 401) {
      clearWorkspace();
      auth.value = null;
      setSession(null);
      try {
        const current = await api.auth();
        if (generation !== loadGeneration) return;
        acceptAuth(current);
        loadError.value = "";
        if (current.account) await load();
      } catch (authError) {
        if (generation === loadGeneration)
          loadError.value = (authError as Error).message;
      }
    } else loadError.value = (err as Error).message;
  } finally {
    if (generation === loadGeneration) {
      loading.value = false;
      refreshing.value = false;
    }
  }
}

function clearWorkspace() {
  overview.value = null;
  subjects.value = [];
  plans.value = [];
  logs.value = [];
  reviews.value = [];
  editor.value = reviewSession.value = confirm.value = null;
  focusOpen.value = backupOpen.value = authOpen.value = false;
  focusPlan.value = undefined;
  focus.selectWorkspace(null);
  planSubject.value = reviewSubject.value = recordSubject.value = "all";
  recordSearch.value = reviewSearch.value = recordDate.value = "";
  syncedAt.value = "";
}
function acceptAuth(value: AuthStatus) {
  if (auth.value?.account?.id !== value.account?.id) clearWorkspace();
  auth.value = value;
  setSession(value);
  focus.selectWorkspace(value.account?.id ?? null);
}
function broadcastSession() {
  try {
    localStorage.setItem("zhian.auth.changed", crypto.randomUUID());
  } catch {
    /* Focus and visibility refresh also detect changes. */
  }
}
async function authenticated(value: AuthStatus) {
  acceptAuth(value);
  authOpen.value = false;
  broadcastSession();
  await load();
  notify("已登录，学习空间已同步。");
}
async function passwordChanged(value: AuthStatus) {
  acceptAuth(value);
  broadcastSession();
  notify("密码已更新，其他设备需要重新登录。");
}
async function signOut() {
  if (accountBusy.value) return;
  accountBusy.value = true;
  focus.pause();
  try {
    await request("/auth/logout", "POST");
    ++loadGeneration;
    clearWorkspace();
    auth.value = null;
    setSession(null);
    broadcastSession();
    await load();
  } catch (err) {
    notify((err as Error).message);
  } finally {
    accountBusy.value = false;
  }
}
let checkingSession = false;
async function sessionChanged() {
  if (checkingSession) return;
  checkingSession = true;
  ++loadGeneration;
  clearWorkspace();
  auth.value = null;
  setSession(null);
  loading.value = true;
  try {
    await load();
  } finally {
    checkingSession = false;
  }
}
function storageChanged(event: StorageEvent) {
  if (event.key === "zhian.auth.changed") void sessionChanged();
}
async function exportData(kind: "json" | "csv") {
  if (exportBusy.value) return;
  exportBusy.value = true;
  try {
    await download(
      kind === "json" ? "/backup" : "/logs/export.csv",
      `zhian-${kind === "json" ? "backup" : "records"}-${today.value}.${kind}`,
    );
  } catch (err) {
    notify((err as Error).message);
  } finally {
    exportBusy.value = false;
  }
}
async function restored(message: string) {
  backupOpen.value = false;
  await load();
  notify(message);
}

function notify(message: string) {
  toast.value = message;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.value = "";
  }, 6500);
}
function readRoute() {
  const value = location.hash.replace("#/", "");
  page.value = [...nav.map((item) => item.id), "settings"].includes(value)
    ? (value as Page)
    : "today";
}
function navigate(value: Page) {
  page.value = value;
  location.hash = `/${value}`;
  window.scrollTo({ top: 0, behavior: "instant" });
}
function edit(mode: EditorMode, data: Omit<EditorState, "mode"> = {}) {
  if (!overview.value) return;
  editor.value = { mode, ...data };
}
async function editorSaved(message: string) {
  if (editor.value?.timer?.id === timer.value?.id && editor.value?.timer)
    focus.reset();
  editor.value = null;
  await load();
  notify(message);
}
async function reviewSaved(message: string) {
  reviewSession.value = null;
  await load();
  notify(message);
}
function openFocus(plan?: Plan) {
  if (!overview.value) return;
  focusPlan.value = timer.value ? undefined : plan;
  focusOpen.value = true;
  if (timer.value && plan && timer.value.plan_id !== plan.id)
    notify("已有一段专注计时，保存或放弃后即可开始新计划");
}
function finishFocus() {
  focus.pause();
  focusOpen.value = false;
  if (timer.value)
    edit("log", {
      timer: {
        ...timer.value,
        plan_id: plans.value.some((plan) => plan.id === timer.value?.plan_id)
          ? timer.value.plan_id
          : null,
      },
      timerMinutes: Math.max(1, Math.ceil(elapsed.value / 60)),
    });
}
function discardFocus() {
  focus.reset();
  focusOpen.value = false;
  notify("本次计时已清除");
}
function removePlan(plan: Plan) {
  actionError.value = "";
  confirm.value = {
    title: "删除这项计划？",
    description: `“${plan.title}”将从计划中移除，已经保存的学习记录会保留。`,
    path: `/plans/${plan.id}`,
  };
}
function removeLog(log: StudyLog) {
  actionError.value = "";
  confirm.value = {
    title: "删除这条学习记录？",
    description:
      "删除后会重新计算学习时长与打卡；关联计划没有其他记录时会恢复待办。已完成的复习排期仍会保留。",
    path: `/logs/${log.id}`,
  };
}
async function confirmRemove() {
  if (!confirm.value || actionBusy.value) return;
  actionBusy.value = true;
  try {
    await request(confirm.value.path, "DELETE");
    confirm.value = null;
    await load();
    notify("已删除，相关统计已更新");
  } catch (err) {
    actionError.value = (err as Error).message;
  } finally {
    actionBusy.value = false;
  }
}
async function archive(item: ReviewItem) {
  if (actionBusy.value) return;
  actionBusy.value = true;
  try {
    await request(`/reviews/${item.id}/archive`, "PATCH", {
      archived: !item.archived,
    });
    await load();
    notify(
      item.archived ? "卡片已恢复到复习列表" : "卡片已归档，可在“已归档”中恢复",
    );
  } catch (err) {
    notify((err as Error).message);
  } finally {
    actionBusy.value = false;
  }
}

const selectedPlanDate = ref(studyToday()),
  weekOffset = ref(0);
const planScope = ref("day"),
  planSubject = ref("all");
const weekDates = computed(() =>
  Array.from({ length: 7 }, (_, index) =>
    addDays(monday(today.value), weekOffset.value * 7 + index),
  ),
);
const visiblePlans = computed(() =>
  plans.value
    .filter(
      (plan) =>
        (planSubject.value === "all" ||
          plan.subject_id === planSubject.value) &&
        (planScope.value === "day"
          ? plan.scheduled_date === selectedPlanDate.value
          : planScope.value === "pending"
            ? !plan.completed
            : plan.completed),
    )
    .sort(
      (a, b) =>
        Number(a.completed) - Number(b.completed) ||
        a.scheduled_date.localeCompare(b.scheduled_date),
    ),
);
function moveWeek(amount: number) {
  weekOffset.value += amount;
  selectedPlanDate.value =
    weekOffset.value === 0 ? today.value : weekDates.value[0]!;
  planScope.value = "day";
}

const reviewScope = ref("due"),
  reviewSubject = ref("all"),
  reviewSearch = ref("");
const visibleReviews = computed(() =>
  reviews.value.filter((item) => {
    const scope =
      reviewScope.value === "archived"
        ? item.archived
        : !item.archived &&
          (reviewScope.value === "due"
            ? item.due_date <= today.value
            : reviewScope.value === "upcoming"
              ? item.due_date > today.value
              : true);
    return (
      scope &&
      (reviewSubject.value === "all" ||
        item.subject_id === reviewSubject.value) &&
      `${item.title} ${item.note} ${item.source}`
        .toLowerCase()
        .includes(reviewSearch.value.toLowerCase())
    );
  }),
);
const recordDate = ref(""),
  recordSubject = ref("all"),
  recordSearch = ref("");
const visibleLogs = computed(() =>
  logs.value.filter(
    (log) =>
      (!recordDate.value || log.study_date === recordDate.value) &&
      (recordSubject.value === "all" ||
        log.subject_id === recordSubject.value) &&
      `${log.title} ${log.note}`
        .toLowerCase()
        .includes(recordSearch.value.toLowerCase()),
  ),
);
const logGroups = computed(() => {
  const groups: Record<string, StudyLog[]> = {};
  for (const log of visibleLogs.value)
    (groups[log.study_date] ??= []).push(log);
  return Object.entries(groups)
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, items]) => ({
      date,
      items,
      minutes: items.reduce((sum, log) => sum + log.duration_minutes, 0),
    }));
});
function selectRecordDate(value: string) {
  recordDate.value = value;
  navigate("records");
}

const insightDays = ref(7);
const periodLogs = computed(() =>
  logs.value.filter(
    (log) =>
      log.study_date >= addDays(today.value, 1 - insightDays.value) &&
      log.study_date <= today.value,
  ),
);
const periodMinutes = computed(() =>
  periodLogs.value.reduce((sum, log) => sum + log.duration_minutes, 0),
);
const periodDays = computed(
  () => new Set(periodLogs.value.map((log) => log.study_date)).size,
);
const subjectStats = computed(() =>
  subjects.value
    .map((subject) => {
      const list = periodLogs.value.filter(
        (log) => log.subject_id === subject.id,
      );
      const minutes = list.reduce((sum, log) => sum + log.duration_minutes, 0);
      const questions = list.reduce((sum, log) => sum + log.question_count, 0);
      const correct = list.reduce((sum, log) => sum + log.correct_count, 0);
      return {
        ...subject,
        minutes,
        questions,
        correct,
        accuracy: percentage(correct, questions),
      };
    })
    .sort((a, b) => b.minutes - a.minutes),
);
const practiceStats = computed(() =>
  subjectStats.value.filter((subject) => subject.questions > 0),
);
const periodPlans = computed(() =>
  plans.value.filter(
    (plan) =>
      plan.scheduled_date >= addDays(today.value, 1 - insightDays.value) &&
      plan.scheduled_date <= today.value,
  ),
);
const planCompletion = computed(() =>
  periodPlans.value.length
    ? Math.round(
        (periodPlans.value.filter((plan) => plan.completed).length /
          periodPlans.value.length) *
          100,
      )
    : null,
);
const reviewForecast = computed(() =>
  Array.from({ length: 7 }, (_, index) => {
    const date = addDays(today.value, index);
    return {
      date,
      count: reviews.value.filter(
        (item) =>
          !item.archived &&
          (index === 0 ? item.due_date <= date : item.due_date === date),
      ).length,
    };
  }),
);

function onVisibility() {
  if (document.visibilityState === "visible" && !refreshing.value) void load();
}
let rolloverInterval: ReturnType<typeof setInterval>;
onMounted(() => {
  readRoute();
  void load();
  window.addEventListener("hashchange", readRoute);
  document.addEventListener("visibilitychange", onVisibility);
  window.addEventListener("focus", onVisibility);
  window.addEventListener("storage", storageChanged);
  window.addEventListener("zhian:session-changed", sessionChanged);
  rolloverInterval = setInterval(() => {
    if (
      document.visibilityState === "visible" &&
      auth.value?.account &&
      !refreshing.value
    )
      void load();
  }, 30000);
});
onBeforeUnmount(() => {
  window.removeEventListener("hashchange", readRoute);
  document.removeEventListener("visibilitychange", onVisibility);
  window.removeEventListener("focus", onVisibility);
  window.removeEventListener("storage", storageChanged);
  window.removeEventListener("zhian:session-changed", sessionChanged);
  clearInterval(rolloverInterval);
  clearTimeout(toastTimeout);
});
</script>

<template>
  <div v-if="!loading && auth && !auth.account" class="auth-gate">
    <section class="auth-gate-card">
      <p class="eyebrow">ZHI AN · STUDY</p>
      <span class="auth-gate-icon"
        ><LockKeyhole :size="28" :stroke-width="1.5"
      /></span>
      <h1>
        {{ auth.first_account ? "从这里，开启积累。" : "欢迎回到知岸。" }}
      </h1>
      <p class="auth-gate-subtitle">每一步，都算数。</p>
      <AuthForm :status="auth" @authenticated="authenticated" />
    </section>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#/today" aria-label="知岸首页"
        ><span class="brand-mark"
          ><svg viewBox="0 0 40 40" fill="none">
            <path
              d="M8 28h24M11 23l9-13 9 13M15 23l5-7 5 7"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <circle cx="31" cy="10" r="2" fill="#e6cc84" /></svg></span
        ><span class="brand-type">知岸<small>ZHI AN · STUDY</small></span></a
      >
      <div class="sidebar-caption">每一步，都算数。</div>
      <div class="nav-label">我的学习空间</div>
      <nav class="primary-nav" aria-label="主要导航">
        <a
          v-for="item in nav"
          :key="item.id"
          :href="`#/${item.id}`"
          :class="{ active: page === item.id }"
          :aria-current="page === item.id ? 'page' : undefined"
          @click.prevent="navigate(item.id)"
          ><component :is="item.icon" :size="19" :stroke-width="1.65" /><span>{{
            item.title
          }}</span
          ><span
            v-if="item.id === 'review' && dueReviews.length"
            class="nav-count"
            >{{ dueReviews.length }}</span
          ><span v-else-if="page === item.id" class="nav-dot"
        /></a>
      </nav>
      <button
        class="sidebar-goal"
        :disabled="!overview"
        @click="edit('profile')"
      >
        <div class="goal-icon"><Target :size="19" /></div>
        <p>下一站，理想的岸</p>
        <strong>{{
          profile.exam_date ? profile.exam_name : "设定你的备考目标"
        }}</strong>
        <div
          v-if="
            overview?.days_until_exam !== null &&
            overview?.days_until_exam !== undefined
          "
          class="countdown"
        >
          <span>{{ Math.max(0, overview.days_until_exam) }}</span> 天
          <small>{{
            overview.days_until_exam < 0 ? "考试日期已过" : "距离目标日"
          }}</small>
        </div>
        <span v-else class="goal-link"
          >从一个小目标开始 <ArrowRight :size="14" /></span
        ><svg class="goal-decoration" viewBox="0 0 110 80" fill="none">
          <path
            d="M8 78C8 18 77 6 85 42S45 86 55 51 99 11 104 6"
            stroke="currentColor"
            stroke-width="1.2"
          />
          <circle cx="103" cy="7" r="4" fill="currentColor" />
        </svg>
      </button>
      <div class="sidebar-bottom">
        <button v-if="timer" class="timer-mini" @click="openFocus()">
          <span class="live-dot" :class="{ paused: !timer.started_at }" /><span
            >{{ clockText(elapsed)
            }}<small>{{
              timer.started_at ? "专注进行中" : "计时已暂停"
            }}</small></span
          ><ChevronRight :size="16" /></button
        ><button
          class="settings-nav"
          :class="{ active: page === 'settings' }"
          @click="navigate('settings')"
        >
          <Settings2 :size="18" />我的目标与设置
        </button>
        <div class="sidebar-user">
          <span class="avatar">{{ profile.name.slice(0, 1) }}</span
          ><span
            ><strong>{{ profile.name }}</strong
            ><small>向理想靠近一点</small></span
          ><Leaf :size="16" />
        </div>
      </div>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div class="breadcrumb">
          <span class="mobile-brand">知岸</span
          ><span class="desktop-breadcrumb">我的学习空间</span
          ><span class="breadcrumb-slash">/</span
          ><strong>{{ pageTitle }}</strong>
        </div>
        <div class="topbar-actions">
          <button
            class="button quiet focus-top"
            :disabled="!overview"
            @click="openFocus()"
          >
            <Timer :size="17" /><span>{{
              timer ? clockText(elapsed) : "专注计时"
            }}</span
            ><i v-if="timer?.started_at" class="live-dot" /></button
          ><button
            class="button primary compact"
            :disabled="!overview"
            @click="edit('log')"
          >
            <Plus :size="17" /><span>记录学习</span></button
          ><button
            class="avatar top-avatar"
            aria-label="我的目标与设置"
            @click="navigate('settings')"
          >
            {{ profile.name.slice(0, 1) }}
          </button>
        </div>
      </header>
      <main class="main-content">
        <div v-if="loading" class="loading-state">
          <LoaderCircle class="spin" :size="29" />
          <h2>正在打开你的学习空间</h2>
          <p>把今天的积累，认真记下来。</p>
        </div>
        <div v-else-if="!overview" class="connection-empty">
          <Sprout :size="46" />
          <h2>学习空间还没有连接上</h2>
          <p>{{ loadError }}</p>
          <button class="button primary" :disabled="refreshing" @click="load">
            <RefreshCw :size="16" />重新连接
          </button>
        </div>
        <template v-else>
          <div v-if="loadError" class="connection-banner" role="alert">
            <span>{{ loadError }} 当前展示上次加载的数据。</span
            ><button class="text-button" :disabled="refreshing" @click="load">
              重试
            </button>
          </div>

          <template v-if="page === 'today'">
            <div class="page-heading">
              <div>
                <div class="eyebrow">A LITTLE BETTER, EVERY DAY</div>
                <h1>
                  {{
                    profile.name === "备考者"
                      ? "今天，也向前一步。"
                      : `${profile.name}，今天也向前一步。`
                  }}
                </h1>
                <p>
                  {{
                    dateLabel(today, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                      weekday: "long",
                    })
                  }}<span
                    class="heading-divider"
                  />给努力一点时间，答案正在路上。
                </p>
              </div>
              <div class="date-stamp">
                <CalendarDays :size="16" /><span>{{
                  today.replaceAll("-", ".")
                }}</span>
              </div>
            </div>
            <section class="hero-card">
              <div class="hero-copy">
                <span class="hero-kicker"><span />保持自己的节奏</span>
                <h2>今天的积累，<br />是明天的底气。</h2>
                <p>
                  {{
                    overview.today.minutes >= profile.daily_goal_minutes
                      ? "今天的学习目标已达成，好好休息也是前进的一部分。"
                      : "不必一次走很远，认真完成眼前的一小步就好。"
                  }}
                </p>
                <div class="hero-actions">
                  <button class="button dark" @click="openFocus()">
                    <Play :size="15" fill="currentColor" />{{
                      timer ? "回到专注" : "开始一段专注"
                    }}<ArrowRight :size="16" /></button
                  ><button class="text-button" @click="navigate('plan')">
                    看看今日计划 <ArrowRight :size="15" />
                  </button>
                </div>
              </div>
              <div class="hero-illustration" aria-hidden="true">
                <svg viewBox="0 0 380 260" fill="none">
                  <circle cx="212" cy="136" r="104" fill="#dfe6cb" />
                  <circle
                    cx="212"
                    cy="136"
                    r="81"
                    stroke="#bcc9a8"
                    stroke-dasharray="3 7"
                  />
                  <path
                    d="M57 227c37-77 183 24 214-48 32-72-107-46-66-111"
                    stroke="#fbfbf3"
                    stroke-width="39"
                    stroke-linecap="round"
                  />
                  <path
                    d="M57 227c37-77 183 24 214-48 32-72-107-46-66-111"
                    stroke="#9aaf8b"
                    stroke-width="1.4"
                    stroke-dasharray="4 6"
                  />
                  <path
                    d="M205 68v-32m0 1c23-19 37-14 38-14-4 24-17 29-38 25m0-6c-24 0-26-16-26-16 18-8 26 3 26 16"
                    stroke="#536e4c"
                    stroke-width="2.5"
                    fill="#9eaf79"
                    stroke-linecap="round"
                  />
                  <circle cx="125" cy="194" r="8" fill="#607c55" />
                  <circle cx="276" cy="160" r="8" fill="#d1b469" />
                  <path
                    d="m124 192 2 3 4-5"
                    stroke="white"
                    stroke-width="1.3"
                  />
                  <path
                    d="M312 69h12m-6-6v12M92 112h9m-4.5-4.5v9"
                    stroke="#a2b18b"
                    stroke-width="1.5"
                  />
                  <circle cx="291" cy="224" r="3" fill="#c9b879" />
                  <circle cx="113" cy="64" r="5" stroke="#b2bd98" />
                  <rect
                    x="229"
                    y="69"
                    width="102"
                    height="31"
                    rx="15.5"
                    fill="#fffdf3"
                    transform="rotate(8 229 69)"
                  />
                  <path
                    d="m243 85 3 3 5-5"
                    stroke="#69805a"
                    stroke-width="1.5"
                  />
                  <text
                    x="257"
                    y="88"
                    fill="#69805a"
                    font-size="10"
                    font-family="sans-serif"
                    transform="rotate(8 257 88)"
                  >
                    一点点，也很好
                  </text></svg
                ><span class="illustration-caption">GROW AT YOUR OWN PACE</span>
              </div>
            </section>
            <section class="stat-grid" aria-label="今日学习概况">
              <article class="stat-card">
                <div class="stat-title">
                  <span>今日专注</span><Clock3 :size="17" />
                </div>
                <div class="stat-value">
                  {{ overview.today.minutes }}<span>分钟</span
                  ><span class="stat-goal"
                    >/ {{ profile.daily_goal_minutes }}</span
                  >
                </div>
                <div class="mini-progress">
                  <span :style="{ width: `${goalPercent}%` }" />
                </div>
                <p>
                  今日目标已完成 <strong>{{ goalPercent }}%</strong>
                </p>
              </article>
              <article class="stat-card">
                <div class="stat-title">
                  <span>连续打卡</span><Flame :size="17" />
                </div>
                <div class="stat-value">
                  {{ overview.streak }}<span>天</span
                  ><span v-if="overview.today.minutes" class="small-badge"
                    ><Check :size="11" />今日已打卡</span
                  >
                </div>
                <p class="stat-bottom">
                  {{
                    overview.today.minutes
                      ? "你的坚持，正在悄悄发芽"
                      : "记录一次学习，点亮今天"
                  }}<Sprout :size="18" />
                </p>
              </article>
              <button class="stat-card interactive" @click="navigate('review')">
                <div class="stat-title">
                  <span>待复习</span><BookOpen :size="17" />
                </div>
                <div class="stat-value">
                  {{ dueReviews.length }}<span>张卡片</span>
                </div>
                <p class="stat-bottom">
                  {{
                    dueReviews.length
                      ? "趁记忆还在，再巩固一次"
                      : "把值得记住的内容收进卡片"
                  }}<ArrowRight :size="16" />
                </p>
              </button>
              <article class="stat-card">
                <div class="stat-title">
                  <span>近 7 天正确率</span><Target :size="17" />
                </div>
                <div class="stat-value">
                  {{ weekAccuracy ?? "—" }}<span>%</span>
                </div>
                <p class="stat-bottom">
                  {{
                    weekQuestions
                      ? `来自 ${weekQuestions} 道客观题练习`
                      : "记录题量后，进步会更清晰"
                  }}<span class="tiny-bars"><i /><i /><i /><i /><i /></span>
                </p>
              </article>
            </section>
            <div class="dashboard-grid">
              <section class="card plan-card">
                <div class="card-heading">
                  <div>
                    <h2>
                      <span class="heading-accent" />今日计划
                      <span class="count-label"
                        >{{ completedTodayPlans }} /
                        {{ todayPlans.length }}</span
                      >
                    </h2>
                    <p>把大目标，拆成今天的小行动。</p>
                  </div>
                  <button class="text-button" @click="edit('plan')">
                    <Plus :size="15" />添加计划
                  </button>
                </div>
                <div v-if="todayPlans.length" class="plan-list">
                  <PlanRow
                    v-for="plan in todayPlans.slice(0, 4)"
                    :key="plan.id"
                    :plan="plan"
                    :subject="subjectMap[plan.subject_id]"
                    :today="today"
                    @complete="edit('log', { plan })"
                    @focus="openFocus(plan)"
                    @edit="edit('plan', { plan })"
                    @remove="removePlan(plan)"
                  />
                </div>
                <div v-else class="empty-state plan-empty">
                  <div class="empty-icon">
                    <ClipboardList :size="27" :stroke-width="1.3" />
                  </div>
                  <h3>今天，想先完成哪件小事？</h3>
                  <p>安排一两个具体任务，让开始变得轻松。</p>
                  <button class="button secondary small" @click="edit('plan')">
                    <Plus :size="15" />写下第一个计划
                  </button>
                </div>
                <div class="card-bottom">
                  <span>{{
                    overduePlans.length
                      ? `还有 ${overduePlans.length} 项过往计划待调整`
                      : "完成计划时，顺手记录实际学习情况"
                  }}</span
                  ><button class="text-button" @click="navigate('plan')">
                    全部计划 <ArrowRight :size="14" />
                  </button>
                </div>
              </section>
              <section class="card review-preview">
                <div class="card-heading">
                  <div>
                    <h2>
                      <span class="heading-accent amber" />温故知新
                      <span v-if="dueReviews.length" class="count-label">{{
                        dueReviews.length
                      }}</span>
                    </h2>
                    <p>让知识留下来，而不只是学过。</p>
                  </div>
                  <BookMarked :size="20" :stroke-width="1.5" />
                </div>
                <div v-if="dueReviews.length" class="due-list">
                  <button
                    v-for="item in dueReviews.slice(0, 3)"
                    :key="item.id"
                    @click="reviewSession = item"
                  >
                    <span
                      class="review-marker"
                      :style="{
                        background: subjectMap[item.subject_id]?.color,
                      }"
                    />
                    <div>
                      <span class="review-subject"
                        >{{ subjectMap[item.subject_id]?.name }} ·
                        {{
                          item.due_date < today ? "已到期" : "今日复习"
                        }}</span
                      ><strong>{{ item.title }}</strong>
                    </div>
                    <ChevronRight :size="16" />
                  </button>
                </div>
                <div v-else class="empty-state review-empty">
                  <div class="empty-icon warm">
                    <Flower2 :size="29" :stroke-width="1.25" />
                  </div>
                  <h3>给记忆留一点生长的空间</h3>
                  <p>
                    {{
                      reviews.length
                        ? "今天没有到期卡片，按自己的节奏学习。"
                        : "把易错点和学习心得，变成未来的提醒。"
                    }}
                  </p>
                  <button class="text-button" @click="edit('review')">
                    创建一张复习卡 <Plus :size="14" />
                  </button>
                </div>
                <div class="review-note">
                  <Sparkles :size="15" /><span>{{
                    overview.today.reviews
                      ? `今天已巩固 ${overview.today.reviews} 张卡片，很棒的积累。`
                      : "先回忆，再查看笔记，记忆会更牢固。"
                  }}</span>
                </div>
              </section>
              <section class="card activity-card">
                <div class="card-heading">
                  <div>
                    <h2><span class="heading-accent" />学习的足迹</h2>
                    <p>
                      最近 7 天，累计专注
                      <strong>{{ formatMinutes(weekMinutes) }}</strong>
                    </p>
                  </div>
                  <button class="text-button" @click="navigate('insights')">
                    查看复盘 <ArrowRight :size="14" />
                  </button>
                </div>
                <ActivityChart
                  :daily="overview.daily"
                  :end-date="today"
                  :goal="profile.daily_goal_minutes"
                />
              </section>
              <section class="card calendar-card">
                <div class="card-heading">
                  <div>
                    <h2><span class="heading-accent" />每一天，都算数</h2>
                    <p>
                      累计学习
                      <strong>{{ overview.total_days }}</strong> 天，慢慢变好。
                    </p>
                  </div>
                  <CalendarDays :size="19" :stroke-width="1.5" />
                </div>
                <StudyCalendar
                  :daily="overview.daily"
                  :today="today"
                  @select="selectRecordDate"
                />
              </section>
            </div>
          </template>

          <template v-else-if="page === 'plan'">
            <div class="page-heading">
              <div>
                <p class="eyebrow">MAKE ROOM FOR PROGRESS</p>
                <h1>把目标，放进每一天。</h1>
                <p>计划留一点余地，让坚持多一点可能。</p>
              </div>
              <button
                class="button primary"
                @click="edit('plan', { initialDate: selectedPlanDate })"
              >
                <Plus :size="17" />新建计划
              </button>
            </div>
            <section class="card week-planner">
              <div class="week-heading">
                <h2>
                  {{
                    dateLabel(weekDates[0]!, { year: "numeric", month: "long" })
                  }}
                </h2>
                <div class="week-actions">
                  <button
                    class="text-button"
                    @click="
                      weekOffset = 0;
                      selectedPlanDate = today;
                      planScope = 'day';
                    "
                  >
                    回到今天</button
                  ><button
                    class="icon-button"
                    aria-label="上一周"
                    @click="moveWeek(-1)"
                  >
                    <ChevronLeft :size="17" /></button
                  ><button
                    class="icon-button"
                    aria-label="下一周"
                    @click="moveWeek(1)"
                  >
                    <ChevronRight :size="17" />
                  </button>
                </div>
              </div>
              <div class="week-days">
                <button
                  v-for="date in weekDates"
                  :key="date"
                  :class="{
                    selected: selectedPlanDate === date,
                    today: date === today,
                  }"
                  @click="
                    selectedPlanDate = date;
                    planScope = 'day';
                  "
                >
                  <span>{{
                    date === today
                      ? "今天"
                      : dateLabel(date, { weekday: "short" })
                  }}</span
                  ><strong>{{ Number(date.slice(8)) }}</strong
                  ><small>{{
                    plans.filter((plan) => plan.scheduled_date === date).length
                      ? `${plans.filter((plan) => plan.scheduled_date === date).length} 项计划`
                      : "留一点空白"
                  }}</small>
                </button>
              </div>
            </section>
            <div class="list-toolbar">
              <div class="segmented">
                <button
                  v-for="scope in [
                    { id: 'day', label: '当天计划' },
                    { id: 'pending', label: '所有待办' },
                    { id: 'completed', label: '已完成' },
                  ]"
                  :key="scope.id"
                  :class="{ active: planScope === scope.id }"
                  @click="planScope = scope.id"
                >
                  {{ scope.label }}
                </button>
              </div>
              <label class="select-filter"
                ><SlidersHorizontal :size="15" /><select
                  v-model="planSubject"
                  aria-label="筛选计划科目"
                >
                  <option value="all">全部科目</option>
                  <option
                    v-for="subject in subjects"
                    :key="subject.id"
                    :value="subject.id"
                  >
                    {{ subject.name }}
                  </option>
                </select></label
              >
            </div>
            <section class="card">
              <div class="card-heading">
                <h2>
                  {{
                    planScope === "day"
                      ? dateLabel(selectedPlanDate, {
                          month: "long",
                          day: "numeric",
                          weekday: "long",
                        })
                      : planScope === "pending"
                        ? "等待完成的小目标"
                        : "已经走过的每一步"
                  }}<span class="count-label"
                    >{{ visiblePlans.length }} 项</span
                  >
                </h2>
                <span class="muted"
                  >{{
                    formatMinutes(
                      visiblePlans.reduce((sum, plan) => sum + plan.minutes, 0),
                    )
                  }}
                  计划用时</span
                >
              </div>
              <PlanRow
                v-for="plan in visiblePlans"
                :key="plan.id"
                :plan="plan"
                :subject="subjectMap[plan.subject_id]"
                :today="today"
                :show-date="planScope !== 'day'"
                @complete="edit('log', { plan })"
                @focus="openFocus(plan)"
                @edit="edit('plan', { plan })"
                @remove="removePlan(plan)"
              />
              <div v-if="!visiblePlans.length" class="empty-state large">
                <CalendarDays :size="38" :stroke-width="1.3" />
                <h3>
                  {{
                    planScope === "completed"
                      ? "每一个完成，都值得被记下"
                      : "给这一天，一个小小的方向"
                  }}
                </h3>
                <p>具体到一个知识点、一组练习，开始就会容易一些。</p>
                <button
                  class="button secondary"
                  @click="edit('plan', { initialDate: selectedPlanDate })"
                >
                  <Plus :size="15" />安排学习计划
                </button>
              </div>
            </section>
          </template>

          <template v-else-if="page === 'review'">
            <div class="page-heading">
              <div>
                <p class="eyebrow">LET KNOWLEDGE TAKE ROOT</p>
                <h1>学过的，也要记得。</h1>
                <p>每一次主动回忆，都在让知识扎根。</p>
              </div>
              <button class="button primary" @click="edit('review')">
                <Plus :size="17" />新建复习卡
              </button>
            </div>
            <div class="review-summary">
              <div class="review-summary-icon">
                <BookOpen :size="26" :stroke-width="1.5" />
              </div>
              <div>
                <h2>
                  今天有 <strong>{{ dueReviews.length }}</strong> 张卡片等你温习
                </h2>
                <p>
                  {{
                    overview.today.reviews
                      ? `已经完成 ${overview.today.reviews} 次复习，继续保持自己的节奏。`
                      : "不会、模糊、掌握、熟练，按真实感受安排下一次见面。"
                  }}
                </p>
              </div>
              <button
                v-if="dueReviews.length"
                class="button secondary"
                @click="reviewSession = dueReviews[0]!"
              >
                开始复习 <ArrowRight :size="16" />
              </button>
            </div>
            <div class="list-toolbar wrap">
              <div class="segmented">
                <button
                  v-for="scope in [
                    { id: 'due', label: '待复习' },
                    { id: 'upcoming', label: '未到期' },
                    { id: 'all', label: '全部卡片' },
                    { id: 'archived', label: '已归档' },
                  ]"
                  :key="scope.id"
                  :class="{ active: reviewScope === scope.id }"
                  @click="reviewScope = scope.id"
                >
                  {{ scope.label
                  }}<span v-if="scope.id === 'due' && dueReviews.length">{{
                    dueReviews.length
                  }}</span>
                </button>
              </div>
              <div class="filters-inline">
                <label class="search-field"
                  ><Search :size="16" /><input
                    v-model="reviewSearch"
                    aria-label="搜索复习卡片"
                    placeholder="搜索知识点或笔记" /></label
                ><select v-model="reviewSubject" aria-label="筛选复习科目">
                  <option value="all">全部科目</option>
                  <option
                    v-for="subject in subjects"
                    :key="subject.id"
                    :value="subject.id"
                  >
                    {{ subject.name }}
                  </option>
                </select>
              </div>
            </div>
            <div v-if="visibleReviews.length" class="review-card-grid">
              <article
                v-for="item in visibleReviews"
                :key="item.id"
                class="card knowledge-card"
              >
                <div class="knowledge-card-top">
                  <span
                    class="subject-tag"
                    :style="{ '--subject': subjectMap[item.subject_id]?.color }"
                    ><span />{{ subjectMap[item.subject_id]?.name }}</span
                  ><span
                    :class="[
                      'due-tag',
                      { due: item.due_date <= today && !item.archived },
                    ]"
                    >{{
                      item.archived
                        ? "已归档"
                        : item.due_date <= today
                          ? "等待温习"
                          : dateLabel(item.due_date)
                    }}</span
                  >
                </div>
                <button class="card-title-button" @click="reviewSession = item">
                  <h2>{{ item.title }}</h2>
                </button>
                <p class="knowledge-note">
                  {{ item.note || "还没有笔记，试着用自己的话解释一遍。" }}
                </p>
                <div class="knowledge-source">
                  <BookMarked :size="13" />{{ item.source || "我的知识积累" }}
                </div>
                <div class="knowledge-footer">
                  <span>已复习 {{ item.review_count }} 次</span>
                  <div>
                    <button
                      class="icon-button small"
                      :aria-label="`编辑卡片：${item.title}`"
                      title="编辑卡片"
                      @click="edit('review', { review: item })"
                    >
                      <Pencil :size="14" /></button
                    ><button
                      class="icon-button small"
                      :disabled="actionBusy"
                      :aria-label="`${item.archived ? '恢复' : '归档'}卡片：${item.title}`"
                      :title="item.archived ? '恢复卡片' : '归档卡片'"
                      @click="archive(item)"
                    >
                      <RefreshCw v-if="item.archived" :size="14" /><Archive
                        v-else
                        :size="14"
                      /></button
                    ><button class="text-button" @click="reviewSession = item">
                      {{
                        !item.archived && item.due_date <= today
                          ? "开始复习"
                          : "查看卡片"
                      }}<ArrowRight :size="14" />
                    </button>
                  </div>
                </div>
              </article>
            </div>
            <section v-else class="card empty-state large">
              <Flower2 :size="44" :stroke-width="1.2" />
              <h3>
                {{
                  reviewSearch || reviewSubject !== "all"
                    ? "没有找到匹配的卡片"
                    : reviewScope === "due"
                      ? "今天的记忆花园，很安静"
                      : "知识，会从一张卡片开始生长"
                }}
              </h3>
              <p>
                {{
                  reviewScope === "due"
                    ? "没有到期任务时，可以安心学习新内容。"
                    : "记下一个易错点、一种方法，或一段申论素材。"
                }}
              </p>
              <button class="button secondary" @click="edit('review')">
                <Plus :size="15" />创建复习卡片
              </button>
            </section>
          </template>

          <template v-else-if="page === 'records'">
            <div class="page-heading">
              <div>
                <p class="eyebrow">YOUR EFFORT, MADE VISIBLE</p>
                <h1>认真走过的路，都在这里。</h1>
                <p>
                  累计 {{ logs.length }} 条学习记录，{{
                    formatMinutes(overview.total_minutes)
                  }}
                  的踏实积累。
                </p>
              </div>
              <button
                class="button secondary"
                :disabled="exportBusy"
                @click="exportData('csv')"
              >
                <ArrowDownToLine :size="16" />导出记录
              </button>
            </div>
            <div class="records-layout">
              <aside class="records-aside">
                <section class="card">
                  <div class="card-heading">
                    <h2>翻看某一天</h2>
                    <CalendarDays :size="18" />
                  </div>
                  <StudyCalendar
                    :daily="overview.daily"
                    :today="today"
                    :selected="recordDate"
                    @select="recordDate = recordDate === $event ? '' : $event"
                  />
                </section>
                <div class="gentle-note">
                  <Leaf :size="20" />
                  <p>不用每天都做到完美。<br />愿意继续，就已经很好。</p>
                </div>
              </aside>
              <div class="records-main">
                <div class="records-toolbar">
                  <label class="search-field"
                    ><Search :size="16" /><input
                      v-model="recordSearch"
                      aria-label="搜索学习记录"
                      placeholder="搜索学习内容或心得" /></label
                  ><select v-model="recordSubject" aria-label="筛选记录科目">
                    <option value="all">全部科目</option>
                    <option
                      v-for="subject in subjects"
                      :key="subject.id"
                      :value="subject.id"
                    >
                      {{ subject.name }}
                    </option>
                  </select>
                </div>
                <button
                  v-if="recordDate"
                  class="filter-chip"
                  @click="recordDate = ''"
                >
                  {{ dateLabel(recordDate) }} 的记录<X :size="14" />
                </button>
                <section
                  v-for="group in logGroups"
                  :key="group.date"
                  class="record-day"
                >
                  <div class="record-day-heading">
                    <h2>
                      {{
                        group.date === today
                          ? "今天"
                          : dateLabel(group.date, {
                              month: "long",
                              day: "numeric",
                              weekday: "long",
                            })
                      }}<span v-if="group.date === today">{{
                        dateLabel(group.date)
                      }}</span>
                    </h2>
                    <span>{{ formatMinutes(group.minutes) }}</span>
                  </div>
                  <article
                    v-for="log in group.items"
                    :key="log.id"
                    class="card log-card"
                  >
                    <div class="log-card-heading">
                      <span
                        class="subject-tag"
                        :style="{
                          '--subject': subjectMap[log.subject_id]?.color,
                        }"
                        ><span />{{ subjectMap[log.subject_id]?.name }}</span
                      >
                      <div class="row-actions">
                        <button
                          class="icon-button small"
                          :aria-label="`编辑记录：${log.title}`"
                          title="编辑记录"
                          @click="edit('log', { log })"
                        >
                          <Pencil :size="14" /></button
                        ><button
                          class="icon-button small"
                          :aria-label="`删除记录：${log.title}`"
                          title="删除记录"
                          @click="removeLog(log)"
                        >
                          <Trash2 :size="14" />
                        </button>
                      </div>
                    </div>
                    <h3>{{ log.title }}</h3>
                    <div class="log-metrics">
                      <span
                        ><Clock3 :size="14" />{{
                          formatMinutes(log.duration_minutes)
                        }}</span
                      ><span v-if="log.question_count"
                        ><ClipboardList :size="14" />{{
                          log.question_count
                        }}
                        题</span
                      ><span v-if="log.question_count"
                        ><Target :size="14" />正确率
                        {{
                          percentage(log.correct_count, log.question_count)
                        }}%</span
                      ><span v-if="log.plan_id"
                        ><CheckCheck :size="14" />关联学习计划</span
                      >
                    </div>
                    <p v-if="log.note" class="log-note preserve-text">
                      {{ log.note }}
                    </p>
                    <button
                      class="text-button log-review-action"
                      @click="edit('review', { log })"
                    >
                      <BookMarked :size="13" />收进复习卡片
                    </button>
                  </article>
                </section>
                <section
                  v-if="!logGroups.length"
                  class="card empty-state large"
                >
                  <BookOpen :size="40" :stroke-width="1.3" />
                  <h3>
                    {{
                      recordDate || recordSearch || recordSubject !== "all"
                        ? "这里暂时没有学习记录"
                        : "你的第一份积累，值得被记住"
                    }}
                  </h3>
                  <p>记录用时、练习情况，也留下一点今天的心得。</p>
                  <button
                    class="button primary"
                    @click="edit('log', { initialDate: recordDate || today })"
                  >
                    <Plus :size="16" />记录一次学习
                  </button>
                </section>
              </div>
            </div>
          </template>

          <template v-else-if="page === 'insights'">
            <div class="page-heading">
              <div>
                <p class="eyebrow">REFLECT, THEN MOVE FORWARD</p>
                <h1>看见进步，也看清方向。</h1>
                <p>用真实的学习足迹，安排下一步。</p>
              </div>
              <div class="segmented">
                <button
                  :class="{ active: insightDays === 7 }"
                  @click="insightDays = 7"
                >
                  近 7 天</button
                ><button
                  :class="{ active: insightDays === 30 }"
                  @click="insightDays = 30"
                >
                  近 30 天
                </button>
              </div>
            </div>
            <section class="stat-grid insights-stats">
              <article class="stat-card">
                <div class="stat-title">
                  <span>累计专注</span><Clock3 :size="17" />
                </div>
                <div class="stat-value">
                  {{ (periodMinutes / 60).toFixed(1) }}<span>小时</span>
                </div>
                <p>近 {{ insightDays }} 天共 {{ periodMinutes }} 分钟</p>
              </article>
              <article class="stat-card">
                <div class="stat-title">
                  <span>实际学习</span><CalendarDays :size="17" />
                </div>
                <div class="stat-value">{{ periodDays }}<span>天</span></div>
                <p>有记录，就有积累</p>
              </article>
              <article class="stat-card">
                <div class="stat-title">
                  <span>学习日均时长</span><TrendingUp :size="17" />
                </div>
                <div class="stat-value">
                  {{ periodDays ? Math.round(periodMinutes / periodDays) : 0
                  }}<span>分钟</span>
                </div>
                <p>按有学习记录的日期计算</p>
              </article>
              <article class="stat-card">
                <div class="stat-title">
                  <span>计划完成率</span><CheckCheck :size="17" />
                </div>
                <div class="stat-value">
                  {{ planCompletion ?? "—" }}<span>%</span>
                </div>
                <p>
                  {{ periodPlans.filter((plan) => plan.completed).length }} /
                  {{ periodPlans.length }} 项计划完成
                </p>
              </article>
            </section>
            <div class="insights-grid">
              <section class="card insights-trend">
                <div class="card-heading">
                  <div>
                    <h2><span class="heading-accent" />学习节奏</h2>
                    <p>保持适合自己的步幅，比一时冲刺更重要。</p>
                  </div>
                  <span class="muted">单位：分钟</span>
                </div>
                <ActivityChart
                  :daily="overview.daily"
                  :end-date="today"
                  :days="insightDays"
                  :goal="profile.daily_goal_minutes"
                />
              </section>
              <section class="card">
                <div class="card-heading">
                  <div>
                    <h2><span class="heading-accent" />时间都去了哪里</h2>
                    <p>各科目学习时间分布</p>
                  </div>
                </div>
                <div class="subject-distribution">
                  <div
                    v-for="subject in subjectStats.filter(
                      (item) => item.minutes > 0,
                    )"
                    :key="subject.id"
                    class="subject-progress"
                  >
                    <div>
                      <span
                        ><i :style="{ background: subject.color }" />{{
                          subject.name
                        }}</span
                      ><strong>{{ formatMinutes(subject.minutes) }}</strong>
                    </div>
                    <div class="distribution-track">
                      <span
                        :style="{
                          width: `${(subject.minutes / Math.max(periodMinutes, 1)) * 100}%`,
                          background: subject.color,
                        }"
                      />
                    </div>
                  </div>
                  <div v-if="!periodMinutes" class="empty-state">
                    <Sprout :size="32" :stroke-width="1.4" />
                    <p>记录后，就能看见时间的去向。</p>
                  </div>
                </div>
              </section>
              <section class="card">
                <div class="card-heading">
                  <div>
                    <h2><span class="heading-accent amber" />练习的反馈</h2>
                    <p>客观题正确率 · 结合题量和练习难度看变化</p>
                  </div>
                  <Target :size="19" />
                </div>
                <div v-if="practiceStats.length" class="accuracy-table">
                  <div class="accuracy-table-header">
                    <span>科目</span><span>正确 / 题量</span><span>正确率</span>
                  </div>
                  <div v-for="subject in practiceStats" :key="subject.id">
                    <span
                      class="subject-tag"
                      :style="{ '--subject': subject.color }"
                      ><span />{{ subject.name }}</span
                    ><span>{{ subject.correct }} / {{ subject.questions }}</span
                    ><strong>{{ subject.accuracy }}<small>%</small></strong>
                  </div>
                </div>
                <div v-else class="empty-state">
                  <Target :size="33" :stroke-width="1.3" />
                  <p>记录客观题练习结果，逐渐找到薄弱环节。</p>
                  <small>申论与主观题记录不参与正确率统计。</small>
                </div>
              </section>
              <section class="card">
                <div class="card-heading">
                  <div>
                    <h2><span class="heading-accent" />未来一周的复习</h2>
                    <p>今日数量包含已到期、尚未完成的卡片</p>
                  </div>
                  <BookMarked :size="19" />
                </div>
                <div class="forecast-grid">
                  <div
                    v-for="(day, index) in reviewForecast"
                    :key="day.date"
                    :class="{ current: index === 0 }"
                  >
                    <span>{{
                      index === 0
                        ? "今天"
                        : dateLabel(day.date, { weekday: "short" })
                    }}</span
                    ><strong>{{ day.count }}</strong
                    ><small>张</small>
                  </div>
                </div>
                <div class="insight-note">
                  <Sparkles :size="17" />
                  <p>
                    {{
                      subjectStats[0]?.minutes
                        ? `近 ${insightDays} 天，${subjectStats[0].name}是你投入最多的科目。结合练习反馈，看看下阶段是否需要调整分配。`
                        : "复盘从真实记录开始。学一点、记一点，再慢慢调整适合自己的计划。"
                    }}
                  </p>
                </div>
              </section>
            </div>
          </template>

          <template v-else-if="page === 'settings'">
            <div class="page-heading">
              <div>
                <p class="eyebrow">YOUR JOURNEY, YOUR PACE</p>
                <h1>向着自己的岸。</h1>
                <p>目标可以调整，积累始终属于你。</p>
              </div>
            </div>
            <div class="settings-grid">
              <AccountPanel
                v-if="auth"
                :key="auth.account?.id"
                :status="auth"
                :synced-at="syncedAt"
                :syncing="refreshing"
                :offline="!!loadError"
                :busy="accountBusy"
                @authenticate="authOpen = true"
                @sync="load"
                @logout="signOut"
                @changed="passwordChanged"
              />
              <section class="card profile-card">
                <div class="card-heading">
                  <h2><Target :size="19" />备考目标</h2>
                  <button class="text-button" @click="edit('profile')">
                    <Pencil :size="15" />编辑目标
                  </button>
                </div>
                <div class="profile-intro">
                  <span class="avatar large">{{
                    profile.name.slice(0, 1)
                  }}</span>
                  <div>
                    <h3>{{ profile.name }}</h3>
                    <p>{{ profile.exam_name }}</p>
                  </div>
                </div>
                <dl class="profile-facts">
                  <div>
                    <dt>目标考试日期</dt>
                    <dd>
                      {{
                        profile.exam_date
                          ? dateLabel(profile.exam_date, {
                              year: "numeric",
                              month: "long",
                              day: "numeric",
                            })
                          : "还没有设置"
                      }}
                    </dd>
                  </div>
                  <div>
                    <dt>每日学习目标</dt>
                    <dd>{{ formatMinutes(profile.daily_goal_minutes) }}</dd>
                  </div>
                  <div>
                    <dt>打卡方式</dt>
                    <dd>记录一次学习，自动点亮当天</dd>
                  </div>
                  <div>
                    <dt>学习日期时区</dt>
                    <dd>{{ overview.timezone }}</dd>
                  </div>
                </dl>
              </section>
              <section class="card">
                <div class="card-heading">
                  <div>
                    <h2><ShieldCheck :size="19" />留住每一份积累</h2>
                    <p>定期导出，让学习记录多一份保障。</p>
                  </div>
                </div>
                <div class="backup-options">
                  <button
                    class="backup-action"
                    :disabled="exportBusy"
                    @click="exportData('json')"
                  >
                    <span class="backup-icon"
                      ><Archive :size="22" :stroke-width="1.5"
                    /></span>
                    <div>
                      <strong>导出完整数据</strong>
                      <p>包含目标、计划、学习记录和复习历史 · JSON</p>
                    </div>
                    <ArrowDownToLine :size="18" /></button
                  ><button
                    class="backup-action"
                    :disabled="exportBusy"
                    @click="exportData('csv')"
                  >
                    <span class="backup-icon warm"
                      ><ClipboardList :size="22" :stroke-width="1.5"
                    /></span>
                    <div>
                      <strong>导出学习记录</strong>
                      <p>可用 Excel 打开，方便整理和复盘 · CSV</p>
                    </div>
                    <ArrowDownToLine :size="18" />
                  </button>
                  <button class="backup-action" @click="backupOpen = true">
                    <span class="backup-icon"
                      ><Upload :size="22" :stroke-width="1.5"
                    /></span>
                    <div>
                      <strong>导入与恢复</strong>
                      <p>预览 JSON 备份、合并记录，或恢复自动备份</p>
                    </div>
                    <ArrowRight :size="18" />
                  </button>
                </div>
                <p class="local-data-note">
                  <ShieldCheck
                    :size="15"
                  />数据保存在当前服务的数据库中，浏览器刷新不会丢失。
                </p>
              </section>
              <section class="card subject-settings">
                <div class="card-heading">
                  <div>
                    <h2><BookOpen :size="19" />我的学习科目</h2>
                    <p>客观题记录题量，主观题记录作答与反馈。</p>
                  </div>
                  <button class="text-button" @click="edit('subject')">
                    <Plus :size="15" />添加科目
                  </button>
                </div>
                <div class="subject-settings-list">
                  <div v-for="subject in subjects" :key="subject.id">
                    <span
                      class="subject-tag"
                      :style="{ '--subject': subject.color }"
                      ><span />{{ subject.name }}</span
                    ><small>{{
                      subject.kind === "essay"
                        ? "主观题 · 作答与反馈"
                        : "客观题 · 题量与正确率"
                    }}</small>
                  </div>
                </div>
              </section>
              <section class="card about-card">
                <div class="about-flower">
                  <Flower2 :size="45" :stroke-width="1" />
                </div>
                <p class="eyebrow">A NOTE FROM ZHI AN</p>
                <h2>每一步，都算数。</h2>
                <p>
                  知岸相信，备考是一个不断积累的过程。<br />在这里，记录努力，照顾节奏，<br />也给自己一点耐心。
                </p>
                <span>知岸 v0.3 · 让积累安心延续</span>
              </section>
            </div>
          </template>
          <footer class="page-footer">
            <span><Sprout :size="15" />不慌不忙，也是一种力量。</span
            ><span
              ><i :class="['connection-dot', { offline: !!loadError }]" />{{
                loadError ? "连接暂时中断" : `已同步 · ${syncedAt}`
              }}</span
            >
          </footer>
        </template>
      </main>
    </div>
    <nav class="mobile-nav" aria-label="移动端导航">
      <a
        v-for="item in nav"
        :key="item.id"
        :href="`#/${item.id}`"
        :class="{ active: page === item.id }"
        :aria-current="page === item.id ? 'page' : undefined"
        @click.prevent="navigate(item.id)"
        ><component :is="item.icon" :size="20" :stroke-width="1.7" /><span>{{
          item.short
        }}</span
        ><i v-if="item.id === 'review' && dueReviews.length"
      /></a>
    </nav>
    <div v-if="toast" class="toast" role="status">
      <Check :size="17" /><span>{{ toast }}</span
      ><button aria-label="关闭提示" @click="toast = ''">
        <X :size="15" />
      </button>
    </div>
    <EditorDialog
      v-if="editor"
      :key="`${editor.mode}-${editor.log?.id ?? editor.plan?.id ?? editor.review?.id ?? 'new'}`"
      v-bind="editor"
      :subjects="subjects"
      :today="today"
      :profile="profile"
      @close="editor = null"
      @saved="editorSaved"
    />
    <FocusDialog
      v-if="focusOpen"
      :timer="timer"
      :seconds="elapsed"
      :subjects="subjects"
      :today="today"
      :plan="focusPlan"
      :storage-available="storageAvailable"
      @close="focusOpen = false"
      @start="focus.start"
      @pause="focus.pause"
      @resume="focus.resume"
      @finish="finishFocus"
      @discard="discardFocus"
    />
    <ReviewSession
      v-if="reviewSession"
      :item="reviewSession"
      :subject="subjectMap[reviewSession.subject_id]"
      :today="today"
      @close="reviewSession = null"
      @saved="reviewSaved"
    />
    <BackupDialog
      v-if="backupOpen"
      :key="auth?.account?.id"
      :has-timer="!!timer"
      @close="backupOpen = false"
      @restored="restored"
      @save-timer="
        backupOpen = false;
        openFocus();
      "
    />
    <BaseModal
      v-if="authOpen && auth"
      title="开启账户保护"
      :busy="accountBusy"
      @close="authOpen = false"
      ><AuthForm
        :status="auth"
        initial-mode="register"
        @busy="accountBusy = $event"
        @authenticated="authenticated"
    /></BaseModal>
    <BaseModal
      v-if="confirm"
      :title="confirm.title"
      :busy="actionBusy"
      @close="confirm = null"
      ><div class="confirm-content">
        <p>{{ confirm.description }}</p>
        <p v-if="actionError" class="form-error" role="alert">
          {{ actionError }}
        </p>
        <div class="modal-actions">
          <button
            class="button secondary"
            :disabled="actionBusy"
            @click="confirm = null"
          >
            保留</button
          ><button
            class="button danger"
            :disabled="actionBusy"
            @click="confirmRemove"
          >
            <LoaderCircle v-if="actionBusy" :size="16" class="spin" /><Trash2
              v-else
              :size="16"
            />确认删除
          </button>
        </div>
      </div></BaseModal
    >
  </div>
</template>
