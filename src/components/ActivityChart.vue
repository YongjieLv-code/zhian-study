<script setup lang="ts">
import { computed } from "vue";
import type { Daily } from "../types";
import { addDays, dateLabel, formatMinutes } from "../utils";

const props = withDefaults(
  defineProps<{
    daily: Daily[];
    endDate: string;
    days?: number;
    goal?: number;
  }>(),
  { days: 7, goal: 120 },
);
const items = computed(() =>
  Array.from({ length: props.days }, (_, i) => {
    const date = addDays(props.endDate, i - props.days + 1);
    return {
      date,
      minutes: props.daily.find((day) => day.date === date)?.minutes ?? 0,
    };
  }),
);
const max = computed(
  () =>
    Math.ceil(
      Math.max(props.goal, ...items.value.map((day) => day.minutes), 60) / 60,
    ) * 60,
);
const hasData = computed(() => items.value.some((day) => day.minutes > 0));
</script>

<template>
  <div class="activity-chart" :class="{ 'many-days': days > 7 }">
    <div class="chart-axis">
      <span>{{ max }}m</span><span>{{ max / 2 }}m</span><span>0</span>
    </div>
    <div class="chart-plot">
      <div class="chart-grid"><i /><i /><i /></div>
      <div class="chart-bars">
        <div
          v-for="(item, index) in items"
          :key="item.date"
          class="chart-column"
          :title="`${dateLabel(item.date)}：${formatMinutes(item.minutes)}`"
        >
          <div class="bar-track">
            <div
              class="chart-bar"
              :class="{ current: item.date === endDate, empty: !item.minutes }"
              :style="{ height: `${(item.minutes / max) * 100}%` }"
            >
              <span v-if="item.minutes && days <= 7" class="bar-value">{{
                item.minutes
              }}</span>
            </div>
          </div>
          <span class="bar-label" :class="{ current: item.date === endDate }">{{
            days <= 7
              ? dateLabel(item.date, { weekday: "short" }).replace("周", "")
              : index % 7 === 0 || index === days - 1
                ? `${Number(item.date.slice(5, 7))}/${Number(item.date.slice(8))}`
                : ""
          }}</span>
        </div>
      </div>
      <div v-if="!hasData" class="chart-empty">
        <p>积累，会在这里被看见</p>
        <small>完成第一次学习记录，点亮你的成长曲线</small>
      </div>
    </div>
  </div>
</template>
