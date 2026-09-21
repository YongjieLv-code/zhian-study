<script setup lang="ts">
import { computed, ref } from "vue";
import { ChevronLeft, ChevronRight } from "lucide-vue-next";
import type { Daily } from "../types";
import { addDays, dateKey, dateLabel, formatMinutes } from "../utils";

const props = defineProps<{
  daily: Daily[];
  today: string;
  selected?: string;
}>();
const emit = defineEmits<{ select: [date: string] }>();
const month = ref(props.today.slice(0, 7));
const cells = computed(() => {
  const first = `${month.value}-01`;
  const weekday = new Date(`${first}T12:00:00`).getDay();
  const start = addDays(first, -(weekday === 0 ? 6 : weekday - 1));
  const end = new Date(
    Number(month.value.slice(0, 4)),
    Number(month.value.slice(5)),
    0,
  ).getDate();
  const count = Math.ceil(((weekday === 0 ? 6 : weekday - 1) + end) / 7) * 7;
  return Array.from({ length: count }, (_, index) => {
    const date = addDays(start, index);
    return {
      date,
      inMonth: date.startsWith(month.value),
      minutes: props.daily.find((day) => day.date === date)?.minutes ?? 0,
    };
  });
});
const monthDays = computed(
  () =>
    props.daily.filter(
      (day) => day.date.startsWith(month.value) && day.minutes > 0,
    ).length,
);
function move(amount: number) {
  const date = new Date(`${month.value}-01T12:00:00`);
  date.setMonth(date.getMonth() + amount);
  month.value = dateKey(date).slice(0, 7);
}
</script>

<template>
  <div class="study-calendar">
    <div class="calendar-title">
      <strong>{{
        dateLabel(`${month}-01`, { year: "numeric", month: "long" })
      }}</strong>
      <div>
        <button class="icon-button small" aria-label="上个月" @click="move(-1)">
          <ChevronLeft :size="16" /></button
        ><button class="icon-button small" aria-label="下个月" @click="move(1)">
          <ChevronRight :size="16" />
        </button>
      </div>
    </div>
    <div class="calendar-week">
      <span
        v-for="day in ['一', '二', '三', '四', '五', '六', '日']"
        :key="day"
        >{{ day }}</span
      >
    </div>
    <div class="calendar-grid">
      <button
        v-for="cell in cells"
        :key="cell.date"
        :class="{
          outside: !cell.inMonth,
          studied: cell.minutes > 0,
          today: cell.date === today,
          selected: cell.date === selected,
          future: cell.date > today,
        }"
        :disabled="cell.date > today"
        :title="`${dateLabel(cell.date)} · ${cell.minutes ? formatMinutes(cell.minutes) : '暂无学习记录'}`"
        :aria-label="`${cell.date}${cell.minutes ? '，已打卡' : ''}`"
        :aria-pressed="cell.date === selected"
        @click="emit('select', cell.date)"
      >
        {{ Number(cell.date.slice(8)) }}<i v-if="cell.minutes > 0" />
      </button>
    </div>
    <div class="calendar-legend">
      <span><i />有学习记录</span
      ><span
        >本月已积累 <strong>{{ monthDays }}</strong> 天</span
      >
    </div>
  </div>
</template>
