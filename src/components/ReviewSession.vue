<script setup lang="ts">
import { computed, ref } from "vue";
import { BookOpen, Eye, History, LoaderCircle } from "lucide-vue-next";
import BaseModal from "./BaseModal.vue";
import { api, request } from "../api";
import type { Rating, ReviewAttempt, ReviewItem, Subject } from "../types";
import { dateLabel } from "../utils";

const props = defineProps<{
  item: ReviewItem;
  subject?: Subject;
  today: string;
}>();
const emit = defineEmits<{ close: []; saved: [message: string] }>();
const revealed = ref(false),
  busy = ref(false),
  error = ref(""),
  duration = ref(5);
const history = ref<ReviewAttempt[] | null>(null);
const historyBusy = ref(false);
const requestId = crypto.randomUUID();
const labels: Record<Rating, string> = {
  again: "还不会",
  hard: "有些模糊",
  good: "已经掌握",
  easy: "十分熟练",
};
const canReview = computed(
  () => !props.item.archived && props.item.due_date <= props.today,
);

async function complete(rating: Rating) {
  if (busy.value) return;
  if (
    !Number.isInteger(Number(duration.value)) ||
    duration.value < 1 ||
    duration.value > 240
  ) {
    error.value = "请填写 1–240 分钟的实际复习时长";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const result = await request<ReviewItem>(
      `/reviews/${props.item.id}/complete`,
      "POST",
      {
        id: requestId,
        rating,
        duration_minutes: Number(duration.value),
        expected_version: props.item.version,
      },
    );
    emit(
      "saved",
      `复习完成，下次见面在 ${dateLabel(result.due_date)}。用时已计入学习记录`,
    );
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    busy.value = false;
  }
}

async function loadHistory() {
  historyBusy.value = true;
  try {
    history.value = await api.history(props.item.id);
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    historyBusy.value = false;
  }
}
</script>

<template>
  <BaseModal
    title="给记忆一点时间"
    eyebrow="RECALL · REFLECT · REMEMBER"
    :busy="busy"
    @close="emit('close')"
  >
    <div class="review-session">
      <span class="subject-tag" :style="{ '--subject': subject?.color }"
        ><span />{{ subject?.name }}</span
      >
      <h3>{{ item.title }}</h3>
      <p class="muted">
        {{ item.source || "自己的知识卡片" }} · 已复习
        {{ item.review_count }} 次
      </p>
      <div class="recall-box">
        <template v-if="!revealed"
          ><BookOpen :size="29" />
          <p>先停一会儿，试着在脑海里回忆。</p>
          <button class="button secondary" @click="revealed = true">
            <Eye :size="16" />查看笔记与答案
          </button></template
        >
        <template v-else
          ><p class="eyebrow">我的笔记</p>
          <p class="preserve-text">
            {{
              item.note ||
              "这张卡片还没有笔记。可以回到列表，通过编辑补充你的思路。"
            }}
          </p></template
        >
      </div>
      <template v-if="canReview && revealed">
        <label class="review-duration"
          >本次复习用时<input
            v-model="duration"
            aria-label="本次复习用时"
            type="number"
            min="1"
            max="240"
          />分钟</label
        >
        <p class="form-tip">
          按真实感受选择，系统会安排下一次复习，并记下本次学习时长。
        </p>
        <div class="rating-grid">
          <button
            v-for="rating in ['again', 'hard', 'good', 'easy'] as Rating[]"
            :key="rating"
            :class="['rating', rating]"
            :disabled="busy"
            @click="complete(rating)"
          >
            <strong>{{ labels[rating] }}</strong
            ><small>{{ item.interval_options[rating] }} 天后</small>
          </button>
        </div>
      </template>
      <p v-else-if="!canReview" class="form-tip">
        {{
          item.archived
            ? "这张卡片已归档，复习历史会继续保留。"
            : `下次复习：${dateLabel(item.due_date)}。今天可以先查看笔记。`
        }}
      </p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <button
        v-if="history === null"
        class="text-button history-button"
        :disabled="historyBusy"
        @click="loadHistory"
      >
        <LoaderCircle v-if="historyBusy" :size="15" class="spin" /><History
          v-else
          :size="15"
        />查看复习足迹
      </button>
      <div v-else class="review-history">
        <p v-if="!history.length" class="muted">从第一次认真回忆开始。</p>
        <div v-for="attempt in history" :key="attempt.id">
          <span>{{
            new Date(
              attempt.reviewed_at.endsWith("Z") ||
                /[+-]\d\d:\d\d$/.test(attempt.reviewed_at)
                ? attempt.reviewed_at
                : `${attempt.reviewed_at}Z`,
            ).toLocaleDateString("zh-CN")
          }}</span
          ><strong>{{ labels[attempt.rating] }}</strong
          ><span>{{ attempt.next_interval_days }} 天后复习</span>
        </div>
      </div>
    </div>
  </BaseModal>
</template>
