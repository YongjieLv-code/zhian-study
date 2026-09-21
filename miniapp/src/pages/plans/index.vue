<script setup lang="ts">
import { computed, ref } from "vue";
import { request } from "../../api";
import EmptyState from "../../components/EmptyState.vue";
import SyncState from "../../components/SyncState.vue";
import type { Plan } from "../../types";
import {
  addDays,
  confirmAction,
  dateLabel,
  errorText,
  formatMinutes,
  monday,
  openEditor,
  toast,
} from "../../utils";
import {
  refreshWorkspace,
  studyDate,
  subjectFor,
  useWorkspacePage,
  workspace,
} from "../../workspace";

useWorkspacePage();
const offset = ref(0);
const filter = ref("week");
const selected = ref("");
const busy = ref("");
const error = ref("");
const start = computed(() =>
  addDays(monday(studyDate.value), offset.value * 7),
);
const end = computed(() => addDays(start.value, 6));
const days = computed(() =>
  ["一", "二", "三", "四", "五", "六", "日"].map((label, index) => ({
    label,
    date: addDays(start.value, index),
    number: Number(addDays(start.value, index).slice(8)),
    count:
      workspace.value?.plans.filter(
        (plan) => plan.scheduled_date === addDays(start.value, index),
      ).length || 0,
  })),
);
const plans = computed(() =>
  (workspace.value?.plans || []).filter((plan) =>
    filter.value === "pending"
      ? !plan.completed
      : filter.value === "completed"
        ? plan.completed
        : selected.value
          ? plan.scheduled_date === selected.value
          : plan.scheduled_date >= start.value &&
            plan.scheduled_date <= end.value,
  ),
);
const completed = computed(
  () => plans.value.filter((plan) => plan.completed).length,
);
function moveWeek(direction: number) {
  offset.value += direction;
  selected.value = "";
}
function thisWeek() {
  offset.value = 0;
  selected.value = "";
}
function begin(plan: Plan) {
  uni.navigateTo({
    url: `/pages/focus/index?plan=${encodeURIComponent(plan.id)}`,
  });
}
function actual(plan: Plan) {
  return formatMinutes(
    workspace.value?.logs
      .filter((log) => log.plan_id === plan.id)
      .reduce((sum, log) => sum + log.duration_minutes, 0) || 0,
  );
}
async function remove(plan: Plan) {
  if (
    busy.value ||
    !(await confirmAction(
      "删除这项计划？",
      "删除安排后，已保存的学习记录仍会保留。",
    ))
  )
    return;
  busy.value = plan.id;
  error.value = "";
  try {
    await request(`/plans/${plan.id}`, "DELETE");
    await refreshWorkspace();
    toast("计划已删除");
  } catch (caught) {
    error.value = errorText(caught);
  } finally {
    busy.value = "";
  }
}
</script>

<template>
  <view class="page">
    <view class="section-head"
      ><view
        ><text class="eyebrow">让努力有方向</text
        ><text class="page-title">一步一步来。</text></view
      ><button class="button secondary compact" @click="openEditor('plan')">
        ＋ 新计划
      </button></view
    >
    <SyncState />
    <view class="segments"
      ><button
        class="segment"
        :class="{ active: filter === 'week' }"
        @click="filter = 'week'"
      >
        按周查看</button
      ><button
        class="segment"
        :class="{ active: filter === 'pending' }"
        @click="filter = 'pending'"
      >
        所有待办</button
      ><button
        class="segment"
        :class="{ active: filter === 'completed' }"
        @click="filter = 'completed'"
      >
        已完成
      </button></view
    >
    <view v-if="filter === 'week'" class="card week-card"
      ><view class="row between week-title"
        ><button class="text-button week-arrow" @click="moveWeek(-1)">‹</button
        ><button class="text-button" @click="thisWeek">
          {{ dateLabel(start) }} — {{ dateLabel(end) }}</button
        ><button class="text-button week-arrow" @click="moveWeek(1)">
          ›
        </button></view
      ><view class="week-days"
        ><button
          v-for="day in days"
          :key="day.date"
          class="week-day"
          :class="{
            selected: selected === day.date,
            today: day.date === studyDate,
          }"
          @click="selected = selected === day.date ? '' : day.date"
        >
          <text class="weekday-label">{{ day.label }}</text
          ><text class="weekday-number">{{ day.number }}</text
          ><text
            class="day-dot"
            :class="{ filled: day.count > 0 }"
          /></button></view
    ></view>
    <view v-if="error" class="message error">{{ error }}</view>
    <template v-if="workspace"
      ><view class="section-head list-heading"
        ><text class="section-title">{{
          selected && filter === "week"
            ? dateLabel(selected)
            : filter === "pending"
              ? "待完成计划"
              : filter === "completed"
                ? "已完成计划"
                : "本周安排"
        }}</text
        ><text class="section-meta"
          >{{ plans.length }} 项 · 完成 {{ completed }} 项</text
        ></view
      >
      <EmptyState
        v-if="!plans.length"
        title="这里还没有计划"
        description="定一个小目标，让行动更容易开始。"
      />
      <view v-else class="stack"
        ><view v-for="plan in plans" :key="plan.id" class="card"
          ><view class="row between"
            ><text
              class="pill"
              :class="{
                amber: !plan.completed && plan.scheduled_date < studyDate,
              }"
              >{{
                plan.completed
                  ? "已完成"
                  : plan.scheduled_date < studyDate
                    ? "待补完成"
                    : "待学习"
              }}</text
            ><text class="small muted">{{
              dateLabel(plan.scheduled_date)
            }}</text></view
          ><text class="card-title plan-title">{{ plan.title }}</text
          ><view class="row"
            ><text
              class="dot"
              :style="{ background: subjectFor(plan.subject_id)?.color }"
            /><text class="small muted"
              >{{ subjectFor(plan.subject_id)?.name }} · 计划
              {{ formatMinutes(plan.minutes) }}</text
            ></view
          ><text v-if="plan.note" class="card-note">{{ plan.note }}</text
          ><text v-if="plan.completed" class="card-note"
            >实际已记录 {{ actual(plan) }}</text
          ><view v-if="!plan.completed" class="actions"
            ><button class="button secondary compact" @click="begin(plan)">
              开始专注</button
            ><button
              class="button outline compact"
              @click="openEditor('log', `plan=${plan.id}`)"
            >
              记录完成
            </button></view
          ><view class="row between plan-actions"
            ><button
              v-if="!plan.completed"
              class="text-button"
              :disabled="!!busy"
              @click="openEditor('plan', `id=${plan.id}`)"
            >
              调整计划</button
            ><view v-else /><button
              class="text-button danger"
              :disabled="!!busy"
              @click="remove(plan)"
            >
              {{ busy === plan.id ? "删除中…" : "删除" }}
            </button></view
          ></view
        ></view
      >
    </template>
  </view>
</template>

<style scoped>
.week-card {
  padding: 16rpx;
}
.week-title {
  margin-bottom: 12rpx;
}
.week-arrow {
  width: 60rpx;
  font-size: 38rpx;
}
.week-days {
  display: flex;
  gap: 6rpx;
}
.week-day {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  background: transparent;
  padding: 12rpx 0;
  border-radius: 16rpx;
  color: #53654a;
}
.week-day.today {
  background: #f0f4e9;
}
.week-day.selected {
  background: #789265;
  color: white;
}
.weekday-label {
  font-size: 21rpx;
  opacity: 0.6;
}
.weekday-number {
  font-size: 29rpx;
}
.day-dot {
  width: 6rpx;
  height: 6rpx;
  border-radius: 50%;
  background: transparent;
}
.day-dot.filled {
  background: currentColor;
}
.list-heading {
  margin-top: 32rpx;
}
.plan-title {
  margin: 18rpx 0 12rpx;
}
.plan-actions {
  margin-top: 12rpx;
}
</style>
