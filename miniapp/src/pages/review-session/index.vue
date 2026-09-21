<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { ApiError, request } from "../../api";
import { goLogin, session } from "../../session";
import type { Rating, ReviewItem } from "../../types";
import { createId, errorText, toast } from "../../utils";
import {
  refreshWorkspace,
  studyDate,
  subjectFor,
  workspace,
} from "../../workspace";

const card = ref<ReviewItem | null>(null);
const cardId = ref("");
const revealed = ref(false);
const minutes = ref("");
const busy = ref(false);
const done = ref(false);
const stale = ref(false);
const error = ref("");
const attemptId = ref(createId());
const pending = ref<{
  id: string;
  rating: Rating;
  duration_minutes: number;
  expected_version: number;
} | null>(null);
const ratings: { value: Rating; label: string; note: string }[] = [
  { value: "again", label: "不会", note: "重新认识它" },
  { value: "hard", label: "模糊", note: "再巩固一下" },
  { value: "good", label: "掌握", note: "记得很清楚" },
  { value: "easy", label: "熟练", note: "已经很稳了" },
];

onLoad((query) => {
  cardId.value = query?.id || "";
  void loadCard();
});
async function loadCard() {
  if (!session.value) {
    goLogin();
    return;
  }
  busy.value = true;
  error.value = "";
  stale.value = false;
  pending.value = null;
  try {
    if (!(await refreshWorkspace()))
      throw new Error("暂时无法读取复习卡片，请重试");
    const item = workspace.value?.reviews.find(
      (value) => value.id === cardId.value,
    );
    if (!item || item.archived || item.due_date > studyDate.value)
      throw new Error("这张卡片已完成、未到期或已归档，请返回复习列表");
    card.value = { ...item };
    revealed.value = false;
    attemptId.value = createId();
  } catch (caught) {
    card.value = null;
    error.value = errorText(caught);
  } finally {
    busy.value = false;
  }
}

async function submit(rating?: Rating) {
  if (busy.value || done.value || !card.value || !revealed.value || stale.value)
    return;
  error.value = "";
  if (!pending.value) {
    if (
      !/^\d+$/.test(minutes.value) ||
      Number(minutes.value) < 1 ||
      Number(minutes.value) > 240
    ) {
      error.value = "请填写实际复习用时，范围为 1–240 分钟";
      return;
    }
    if (!rating) return;
    pending.value = {
      id: attemptId.value,
      rating,
      duration_minutes: Number(minutes.value),
      expected_version: card.value.version,
    };
  }
  busy.value = true;
  try {
    await request(`/reviews/${card.value.id}/complete`, "POST", pending.value);
    done.value = true;
    await refreshWorkspace();
    toast("复习已记录，下次再见");
    uni.navigateBack({
      fail: () => uni.switchTab({ url: "/pages/reviews/index" }),
    });
  } catch (caught) {
    error.value = errorText(caught);
    if (
      caught instanceof ApiError &&
      caught.status > 0 &&
      caught.status < 500
    ) {
      pending.value = null;
      if (caught.status === 409) stale.value = true;
    }
  } finally {
    busy.value = false;
  }
}
function goBack() {
  uni.switchTab({ url: "/pages/reviews/index" });
}
</script>

<template>
  <view class="page">
    <text class="eyebrow">给记忆一次主动练习</text
    ><text class="page-title">先回忆，再确认。</text>
    <view v-if="error" class="message error review-message">{{ error }}</view>
    <view v-if="busy && !card" class="message review-message"
      >正在准备复习卡片…</view
    >
    <template v-if="card"
      ><view class="card question-card"
        ><view class="row"
          ><text
            class="dot"
            :style="{ background: subjectFor(card.subject_id)?.color }"
          /><text class="small muted"
            >{{ subjectFor(card.subject_id)?.name }} · 第
            {{ card.review_count + 1 }} 次复习</text
          ></view
        ><text class="question-title">{{ card.title }}</text
        ><text v-if="card.source" class="card-note"
          >来源：{{ card.source }}</text
        ><view v-if="!revealed" class="recall-hint"
          ><text>试着说出关键步骤、公式或易错点。</text
          ><button class="button secondary reveal" @click="revealed = true">
            想好了，查看笔记
          </button></view
        ><view v-else class="answer"
          ><text class="answer-label">答案与笔记</text
          ><text class="note-text">{{
            card.note || "这张卡片尚未填写笔记，可在卡片编辑页补充。"
          }}</text></view
        ></view
      >
      <view v-if="revealed" class="section"
        ><view class="field"
          ><text class="field-label">本次实际复习用时（分钟）</text
          ><input
            v-model="minutes"
            class="input duration-input"
            type="number"
            maxlength="3"
            placeholder="填写真实用时"
            :disabled="busy || !!pending || done || stale"
          /><text class="field-hint"
            >保存后，这段时间会计入今天的学习记录。</text
          ></view
        ><text class="section-title feedback-title">这次记得怎么样？</text
        ><view class="rating-grid"
          ><button
            v-for="rating in ratings"
            :key="rating.value"
            class="rating-card"
            :class="rating.value"
            :disabled="busy || !!pending || done || stale"
            @click="submit(rating.value)"
          >
            <text class="rating-label">{{ rating.label }}</text
            ><text class="rating-note">{{ rating.note }}</text
            ><text class="rating-next"
              >{{ card.interval_options[rating.value] }} 天后再见</text
            >
          </button></view
        ><button
          v-if="pending && !busy && !done"
          class="button safe-actions"
          @click="submit()"
        >
          重试保存本次反馈</button
        ><button
          v-if="stale"
          class="button secondary safe-actions"
          @click="loadCard"
        >
          重新读取卡片
        </button></view
      >
    </template>
    <button
      v-if="!busy && (!card || stale)"
      class="text-button back-button"
      @click="goBack"
    >
      返回复习列表
    </button>
  </view>
</template>
<style scoped>
.review-message,
.question-card {
  margin-top: 28rpx;
}
.question-title {
  display: block;
  font-size: 38rpx;
  line-height: 1.7;
  font-weight: 550;
  margin: 32rpx 0 16rpx;
  word-break: break-word;
}
.recall-hint {
  margin-top: 36rpx;
  padding-top: 28rpx;
  border-top: 1rpx solid #edf0e7;
  color: #959e89;
  font-size: 25rpx;
}
.reveal {
  margin-top: 24rpx;
}
.answer {
  margin-top: 30rpx;
  padding-top: 26rpx;
  border-top: 1rpx solid #e8edde;
}
.answer-label {
  display: block;
  color: #8da17b;
  font-size: 23rpx;
  margin-bottom: 18rpx;
}
.duration-input {
  background: white;
}
.feedback-title {
  display: block;
  margin-top: 32rpx;
}
.rating-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 18rpx;
  margin-top: 20rpx;
}
.rating-card {
  width: calc(50% - 9rpx);
  text-align: left;
  padding: 26rpx;
  border-radius: 22rpx;
  background: #edf0e7;
  color: #607250;
}
.rating-card.again {
  background: #f3e9e2;
  color: #9b7a65;
}
.rating-card.hard {
  background: #f3efde;
  color: #a1925f;
}
.rating-card.easy {
  background: #e2ece4;
  color: #688571;
}
.rating-label {
  display: block;
  font-size: 31rpx;
  font-weight: 550;
}
.rating-note {
  display: block;
  font-size: 22rpx;
  margin-top: 6rpx;
  opacity: 0.8;
}
.rating-next {
  display: block;
  font-size: 23rpx;
  margin-top: 20rpx;
}
.back-button {
  margin: 28rpx auto 0;
}
</style>
