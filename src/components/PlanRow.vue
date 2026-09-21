<script setup lang="ts">
import { Check, Clock3, Pencil, Play, Trash2 } from "lucide-vue-next";
import type { Plan, Subject } from "../types";
import { dateLabel } from "../utils";

defineProps<{
  plan: Plan;
  subject?: Subject;
  today: string;
  showDate?: boolean;
}>();
const emit = defineEmits<{ complete: []; focus: []; edit: []; remove: [] }>();
</script>

<template>
  <div class="plan-row" :class="{ completed: plan.completed }">
    <button
      class="task-check"
      :class="{ checked: plan.completed }"
      :disabled="plan.completed"
      :aria-label="
        plan.completed ? `已完成：${plan.title}` : `完成计划：${plan.title}`
      "
      @click="emit('complete')"
    >
      <Check v-if="plan.completed" :size="14" />
    </button>
    <div class="plan-row-content">
      <h3>{{ plan.title }}</h3>
      <div class="task-meta">
        <span class="subject-tag" :style="{ '--subject': subject?.color }"
          ><span />{{ subject?.name }}</span
        ><span
          v-if="showDate"
          :class="{
            'overdue-text': plan.scheduled_date < today && !plan.completed,
          }"
          >{{ dateLabel(plan.scheduled_date) }}</span
        ><span class="task-time"
          ><Clock3 :size="12" />{{ plan.minutes }} 分钟</span
        >
      </div>
      <p v-if="plan.note" class="task-note">{{ plan.note }}</p>
    </div>
    <div class="row-actions">
      <button
        v-if="!plan.completed"
        class="icon-button play-button"
        :aria-label="`开始专注：${plan.title}`"
        title="开始专注"
        @click="emit('focus')"
      >
        <Play :size="15" /></button
      ><button
        v-if="!plan.completed"
        class="icon-button small"
        :aria-label="`编辑计划：${plan.title}`"
        title="编辑计划"
        @click="emit('edit')"
      >
        <Pencil :size="14" /></button
      ><button
        class="icon-button small subtle-action"
        :aria-label="`删除计划：${plan.title}`"
        title="删除计划"
        @click="emit('remove')"
      >
        <Trash2 :size="14" />
      </button>
    </div>
  </div>
</template>
