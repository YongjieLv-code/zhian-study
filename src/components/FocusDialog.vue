<script setup lang="ts">
import { ref } from "vue";
import { Check, Pause, Play, Sprout } from "lucide-vue-next";
import BaseModal from "./BaseModal.vue";
import type { Plan, Subject, TimerState } from "../types";
import { clockText } from "../utils";

const props = defineProps<{
  timer: TimerState | null;
  seconds: number;
  subjects: Subject[];
  today: string;
  plan?: Plan;
  storageAvailable: boolean;
}>();
const emit = defineEmits<{
  close: [];
  start: [
    data: Pick<TimerState, "title" | "subject_id" | "plan_id" | "study_date">,
  ];
  pause: [];
  resume: [];
  finish: [];
  discard: [];
}>();
const title = ref(props.plan?.title ?? "");
const subject = ref(props.plan?.subject_id ?? props.subjects[0]?.id ?? "");
const confirmDiscard = ref(false);
</script>

<template>
  <BaseModal
    title="把这一刻，留给专注"
    eyebrow="A LITTLE FOCUS, EVERY DAY"
    @close="emit('close')"
  >
    <form
      class="focus-content"
      @submit.prevent="
        emit('start', {
          title,
          subject_id: subject,
          plan_id: plan?.id ?? null,
          study_date: today,
        })
      "
    >
      <div class="focus-leaf"><Sprout :size="30" :stroke-width="1.4" /></div>
      <div class="focus-clock">{{ clockText(seconds) }}</div>
      <p class="focus-state">
        {{
          timer
            ? timer.started_at
              ? "正在专注 · 慢慢来，也是在向前"
              : "稍作休息，准备好了再继续"
            : "关掉杂念，从眼前这件小事开始"
        }}
      </p>
      <template v-if="!timer">
        <label class="sr-only" for="focus-title">专注内容</label
        ><input
          id="focus-title"
          v-model="title"
          required
          maxlength="150"
          placeholder="这次准备学点什么？"
        />
        <label class="sr-only" for="focus-subject">专注科目</label
        ><select
          id="focus-subject"
          v-model="subject"
          required
          :disabled="!!plan"
        >
          <option v-for="item in subjects" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
        <button class="button primary focus-start">
          <Play :size="17" fill="currentColor" />开始专注
        </button>
      </template>
      <template v-else>
        <p class="focus-topic">{{ timer.title }}</p>
        <div class="focus-actions">
          <button
            v-if="timer.started_at"
            type="button"
            class="button secondary"
            @click="emit('pause')"
          >
            <Pause :size="17" />暂停一下</button
          ><button
            v-else
            type="button"
            class="button secondary"
            :disabled="seconds >= 86400"
            @click="emit('resume')"
          >
            <Play :size="17" />继续专注</button
          ><button type="button" class="button primary" @click="emit('finish')">
            <Check :size="17" />结束并记录
          </button>
        </div>
        <div v-if="confirmDiscard" class="inline-confirm">
          <p>放弃这次计时？尚未保存的用时将被清除。</p>
          <button
            type="button"
            class="text-button"
            @click="confirmDiscard = false"
          >
            保留计时</button
          ><button
            type="button"
            class="text-button danger-text"
            @click="emit('discard')"
          >
            确认放弃
          </button>
        </div>
        <button
          v-else
          class="text-button focus-discard"
          type="button"
          @click="confirmDiscard = true"
        >
          放弃本次计时
        </button>
      </template>
      <p class="form-tip">
        {{
          storageAvailable
            ? "可以收起窗口继续学习，刷新页面后计时仍会保留。"
            : "当前浏览器无法保存计时，请在关闭页面前结束并记录。"
        }}
      </p>
      <p v-if="seconds >= 86400" class="form-error">
        本次计时已满 24 小时并自动暂停，请核对真实学习时间后保存。
      </p>
    </form>
  </BaseModal>
</template>
