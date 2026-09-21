<script setup lang="ts">
import { computed, ref } from "vue";
import EmptyState from "../../components/EmptyState.vue";
import SyncState from "../../components/SyncState.vue";
import {
  addDays,
  dateKey,
  dateLabel,
  formatMinutes,
  percentage,
} from "../../utils";
import {
  studyDate,
  subjectFor,
  useWorkspacePage,
  workspace,
} from "../../workspace";

useWorkspacePage();
const range = ref(7);
const monthOffset = ref(0);
const chosenDay = ref("");
const fromDate = computed(() => addDays(studyDate.value, -(range.value - 1)));
const logs = computed(
  () =>
    workspace.value?.logs.filter(
      (log) =>
        log.study_date >= fromDate.value && log.study_date <= studyDate.value,
    ) || [],
);
const minutes = computed(() =>
  logs.value.reduce((sum, log) => sum + log.duration_minutes, 0),
);
const activeDays = computed(
  () => new Set(logs.value.map((log) => log.study_date)).size,
);
const accuracy = computed(() =>
  percentage(
    logs.value.reduce((sum, log) => sum + log.correct_count, 0),
    logs.value.reduce((sum, log) => sum + log.question_count, 0),
  ),
);
const trend = computed(() =>
  Array.from({ length: range.value }, (_, index) => {
    const date = addDays(fromDate.value, index);
    return {
      date,
      minutes: logs.value
        .filter((log) => log.study_date === date)
        .reduce((sum, log) => sum + log.duration_minutes, 0),
      label: Number(date.slice(8)),
    };
  }),
);
const peak = computed(() =>
  Math.max(30, ...trend.value.map((day) => day.minutes)),
);
const bySubject = computed(() =>
  (workspace.value?.subjects || [])
    .map((subject) => {
      const items = logs.value.filter((log) => log.subject_id === subject.id);
      const duration = items.reduce(
        (sum, log) => sum + log.duration_minutes,
        0,
      );
      const rate = percentage(
        items.reduce((sum, log) => sum + log.correct_count, 0),
        items.reduce((sum, log) => sum + log.question_count, 0),
      );
      return {
        ...subject,
        minutes: duration,
        rate,
        share: minutes.value ? Math.round((duration / minutes.value) * 100) : 0,
      };
    })
    .filter((row) => row.minutes > 0)
    .sort((a, b) => b.minutes - a.minutes),
);
const monthStart = computed(() => {
  const [year, month] = studyDate.value.split("-").map(Number);
  return dateKey(new Date(Date.UTC(year, month - 1 + monthOffset.value, 1)));
});
const monthLabel = computed(
  () =>
    `${monthStart.value.slice(0, 4)} 年 ${Number(monthStart.value.slice(5, 7))} 月`,
);
const calendar = computed(() => {
  const [year, month] = monthStart.value.split("-").map(Number);
  const count = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const weekday = new Date(`${monthStart.value}T12:00:00Z`).getUTCDay();
  const padding = weekday === 0 ? 6 : weekday - 1;
  return Array.from(
    { length: Math.ceil((count + padding) / 7) * 7 },
    (_, index) => {
      const number = index - padding + 1;
      const date =
        number > 0 && number <= count
          ? addDays(monthStart.value, number - 1)
          : "";
      const duration = date
        ? workspace.value?.overview.daily.find((day) => day.date === date)
            ?.minutes || 0
        : 0;
      return {
        index,
        date,
        number,
        minutes: duration,
        strength:
          duration === 0 ? 0 : duration < 60 ? 1 : duration < 120 ? 2 : 3,
      };
    },
  );
});
const selectedDate = computed(() => chosenDay.value || studyDate.value);
const selectedLogs = computed(
  () =>
    workspace.value?.logs.filter(
      (log) => log.study_date === selectedDate.value,
    ) || [],
);
const selectedMinutes = computed(() =>
  selectedLogs.value.reduce((sum, log) => sum + log.duration_minutes, 0),
);
const forecast = computed(() =>
  Array.from({ length: 7 }, (_, index) => {
    const date = addDays(studyDate.value, index);
    return {
      date,
      label: index === 0 ? "今天" : dateLabel(date),
      count:
        workspace.value?.reviews.filter(
          (card) =>
            !card.archived &&
            (index === 0 ? card.due_date <= date : card.due_date === date),
        ).length || 0,
    };
  }),
);
function goRecords() {
  uni.navigateTo({ url: "/pages/records/index" });
}
</script>

<template>
  <view class="page">
    <text class="eyebrow">回头看看，你已走了这么远</text
    ><text class="page-title">努力，正在积累。</text>
    <SyncState />
    <view class="segments range-switch"
      ><button
        class="segment"
        :class="{ active: range === 7 }"
        @click="range = 7"
      >
        最近 7 天</button
      ><button
        class="segment"
        :class="{ active: range === 30 }"
        @click="range = 30"
      >
        最近 30 天
      </button></view
    >
    <template v-if="workspace">
      <view class="metrics"
        ><view class="metric"
          ><text class="metric-value number">{{ minutes }}</text
          ><text class="metric-label">学习分钟</text></view
        ><view class="metric"
          ><text class="metric-value number">{{ activeDays }}</text
          ><text class="metric-label">学习天数</text></view
        ><view class="metric"
          ><text class="metric-value number">{{
            accuracy === null ? "—" : `${accuracy}%`
          }}</text
          ><text class="metric-label">客观题正确率</text></view
        ></view
      >
      <view class="card section"
        ><view class="section-head"
          ><text class="section-title">学习的节奏</text
          ><text class="section-meta">每日实际时长</text></view
        ><view class="chart"
          ><view v-for="day in trend" :key="day.date" class="chart-column"
            ><text v-if="range === 7" class="bar-value">{{
              day.minutes || ""
            }}</text
            ><view class="bar-space"
              ><view
                class="bar"
                :class="{ empty: day.minutes === 0 }"
                :style="{ height: `${(day.minutes / peak) * 100}%` }" /></view
            ><text class="bar-label">{{
              range === 7 || day.date === studyDate || day.date === fromDate
                ? day.label
                : ""
            }}</text></view
          ></view
        ><text class="field-hint"
          >{{ dateLabel(fromDate) }} — {{ dateLabel(studyDate) }} · 共
          {{ logs.length }} 次学习</text
        ></view
      >
      <view class="section"
        ><view class="section-head"
          ><text class="section-title">时间花在哪里</text
          ><text class="section-meta">按实际学习记录统计</text></view
        ><EmptyState
          v-if="!bySubject.length"
          title="还没有这一阶段的学习记录"
          description="保存学习后，这里会呈现你的投入。"
        /><view v-else class="card"
          ><view
            v-for="subject in bySubject"
            :key="subject.id"
            class="subject-row"
            ><view class="row between"
              ><view class="row"
                ><text
                  class="dot"
                  :style="{ background: subject.color }"
                /><text>{{ subject.name }}</text></view
              ><text class="small muted"
                >{{ formatMinutes(subject.minutes) }} ·
                {{ subject.share }}%</text
              ></view
            ><view class="progress subject-progress"
              ><view
                class="progress-fill"
                :style="{
                  width: `${subject.share}%`,
                  background: subject.color,
                }" /></view
            ><text v-if="subject.rate !== null" class="field-hint"
              >正确率 {{ subject.rate }}%</text
            ></view
          ></view
        ></view
      >
      <view class="section"
        ><view class="section-head"
          ><text class="section-title">把坚持，点亮</text
          ><text class="section-meta"
            >累计 {{ workspace.overview.total_days }} 天</text
          ></view
        ><view class="card calendar-card"
          ><view class="row between month-nav"
            ><button class="text-button month-arrow" @click="monthOffset--">
              ‹</button
            ><button
              class="text-button"
              @click="
                monthOffset = 0;
                chosenDay = '';
              "
            >
              {{ monthLabel }}</button
            ><button
              class="text-button month-arrow"
              :disabled="monthOffset >= 0"
              @click="monthOffset++"
            >
              ›
            </button></view
          ><view class="calendar-week"
            ><text
              v-for="day in ['一', '二', '三', '四', '五', '六', '日']"
              :key="day"
              >{{ day }}</text
            ></view
          ><view class="calendar-grid"
            ><view
              v-for="day in calendar"
              :key="day.index"
              class="calendar-cell"
              ><button
                v-if="day.date"
                class="calendar-day"
                :class="[
                  `strength-${day.strength}`,
                  {
                    selected: day.date === selectedDate,
                    today: day.date === studyDate,
                  },
                ]"
                :disabled="day.date > studyDate"
                @click="chosenDay = day.date"
              >
                {{ day.number }}
              </button></view
            ></view
          ><view class="calendar-legend"
            ><text>学习时长</text><view class="legend-box strength-0" /><view
              class="legend-box strength-1"
            /><view class="legend-box strength-2" /><view
              class="legend-box strength-3"
            /><text>由少到多</text></view
          ><view class="divider" /><view class="row between"
            ><text class="strong">{{ dateLabel(selectedDate) }}</text
            ><text class="small muted"
              >{{ selectedLogs.length }} 次 ·
              {{ formatMinutes(selectedMinutes) }}</text
            ></view
          ><text v-if="!selectedLogs.length" class="card-note"
            >这一天还没有学习记录。</text
          ><view v-for="log in selectedLogs" :key="log.id" class="calendar-log"
            ><view class="grow"
              ><text class="small">{{ log.title }}</text
              ><text class="field-hint">{{
                subjectFor(log.subject_id)?.name
              }}</text></view
            ><text class="small muted"
              >{{ log.duration_minutes }} 分钟</text
            ></view
          ><button class="text-button calendar-link" @click="goRecords">
            查看学习记录 →
          </button></view
        ></view
      >
      <view class="section"
        ><view class="section-head"
          ><text class="section-title">接下来，记得复习</text
          ><text class="section-meta">未来 7 天</text></view
        ><view class="card forecast"
          ><view v-for="day in forecast" :key="day.date" class="forecast-day"
            ><text class="forecast-count">{{ day.count }}</text
            ><text class="forecast-label">{{ day.label }}</text></view
          ></view
        ><text class="field-hint">今天包含已到期但尚未完成的卡片。</text></view
      >
    </template>
  </view>
</template>

<style scoped>
.range-switch {
  max-width: 410rpx;
}
.chart {
  display: flex;
  gap: 8rpx;
  height: 252rpx;
  align-items: end;
}
.chart-column {
  display: flex;
  flex: 1;
  min-width: 0;
  height: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: end;
}
.bar-space {
  height: 180rpx;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.bar {
  width: 66%;
  max-width: 40rpx;
  background: #94ab7c;
  border-radius: 7rpx 7rpx 2rpx 2rpx;
  min-height: 3rpx;
}
.bar.empty {
  background: #e8ecdf;
}
.bar-value {
  height: 34rpx;
  font-size: 20rpx;
  color: #95a188;
}
.bar-label {
  height: 38rpx;
  font-size: 21rpx;
  color: #99a08e;
  padding-top: 10rpx;
}
.subject-row + .subject-row {
  margin-top: 28rpx;
}
.subject-progress {
  margin-top: 16rpx;
  height: 10rpx;
}
.calendar-card {
  padding: 22rpx;
}
.month-nav {
  margin-bottom: 14rpx;
}
.month-arrow {
  font-size: 38rpx;
  width: 56rpx;
}
.calendar-week {
  display: flex;
  text-align: center;
  color: #a0a992;
  font-size: 22rpx;
  margin-bottom: 16rpx;
}
.calendar-week > text {
  width: 14.2857%;
}
.calendar-grid {
  display: flex;
  flex-wrap: wrap;
}
.calendar-cell {
  width: 14.2857%;
  padding: 5rpx;
}
.calendar-day {
  background: #f3f5ed;
  color: #939e86;
  border-radius: 14rpx;
  padding: 13rpx 0;
  height: 67rpx;
  font-size: 25rpx;
  border: 2rpx solid transparent;
}
.calendar-day.today {
  font-weight: 650;
}
.calendar-day.selected {
  border-color: #4e6c45;
}
.strength-0 {
  background: #f2f5ec;
}
.strength-1 {
  background: #e2ebd6;
  color: #7d9367;
}
.strength-2 {
  background: #b9cda1;
  color: #536944;
}
.strength-3 {
  background: #7f9b65;
  color: #fff;
}
.calendar-legend {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8rpx;
  font-size: 19rpx;
  color: #a0a891;
  margin: 20rpx 6rpx 0;
}
.legend-box {
  width: 19rpx;
  height: 19rpx;
  border-radius: 5rpx;
}
.calendar-log {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  margin-top: 20rpx;
}
.calendar-link {
  margin-top: 20rpx;
}
.forecast {
  display: flex;
  gap: 8rpx;
  padding: 24rpx 12rpx;
}
.forecast-day {
  flex: 1;
  text-align: center;
  min-width: 0;
}
.forecast-count {
  display: block;
  color: #7a9268;
  font-size: 32rpx;
}
.forecast-label {
  display: block;
  color: #9aa38d;
  font-size: 18rpx;
  margin-top: 10rpx;
}
</style>
