<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import SubjectPicker from "../../components/SubjectPicker.vue";
import SyncState from "../../components/SyncState.vue";
import {
  clearFocus,
  focus,
  focusElapsed,
  pauseFocus,
  resumeFocus,
  startFocus,
  tickFocus,
} from "../../focus";
import { clockText, confirmAction, openEditor } from "../../utils";
import {
  studyDate,
  subjectFor,
  subjects,
  useWorkspacePage,
  workspace,
} from "../../workspace";

useWorkspacePage();
const planId = ref("");
const title = ref("");
const subject = ref("");
const error = ref("");
const plan = computed(() =>
  workspace.value?.plans.find((item) => item.id === planId.value),
);
onLoad((query) => {
  planId.value = query?.plan || "";
});
onShow(tickFocus);
watch(
  [subjects, plan],
  () => {
    if (plan.value) subject.value = plan.value.subject_id;
    else if (!subject.value) subject.value = subjects.value[0]?.id || "";
    if (!title.value && plan.value) title.value = plan.value.title;
  },
  { immediate: true },
);
watch(workspace, (value) => {
  if (focus.value && value?.logs.some((log) => log.id === focus.value?.id))
    clearFocus();
});

function begin() {
  error.value = "";
  if (planId.value && (!plan.value || plan.value.completed)) {
    error.value = "关联计划已完成或不存在，请返回计划列表重新选择。";
    return;
  }
  if (!title.value.trim()) {
    error.value = "先写下这次要学习的内容";
    return;
  }
  if (!subjectFor(subject.value)) {
    error.value = "请选择有效的学习科目";
    return;
  }
  startFocus({
    title: title.value.trim(),
    subject_id: subject.value,
    plan_id: planId.value || null,
    study_date: studyDate.value,
  });
}
function finish() {
  pauseFocus();
  openEditor("log", "timer=1");
}
async function discard() {
  if (
    await confirmAction(
      "放弃本次计时？",
      "尚未保存的计时将清除，已有学习记录不受影响。",
    )
  )
    clearFocus();
}
</script>

<template>
  <view class="page">
    <text class="eyebrow">一次只做一件事</text
    ><text class="page-title">把注意力，留给当下。</text>
    <SyncState />
    <view v-if="focus" class="focus-card">
      <text class="pill">{{
        focus.started_at === null ? "已暂停" : "专注中"
      }}</text>
      <text class="focus-title">{{ focus.title }}</text>
      <text class="subtitle"
        >{{ subjectFor(focus.subject_id)?.name }} · {{ focus.study_date }}</text
      >
      <text class="timer number">{{ clockText(focusElapsed) }}</text>
      <text class="timer-note">{{
        focusElapsed >= 86400
          ? "已达到 24 小时上限，请核对并保存记录。"
          : focus.started_at === null
            ? "计时已暂停，可以继续专注，或结束后保存记录。"
            : "切到其他页面或暂时离开后，计时会继续。"
      }}</text>
      <view class="actions"
        ><button
          v-if="focus.started_at !== null"
          class="button secondary"
          @click="pauseFocus"
        >
          暂停一下</button
        ><button
          v-else
          class="button secondary"
          :disabled="focusElapsed >= 86400"
          @click="resumeFocus"
        >
          继续专注</button
        ><button class="button" @click="finish">结束并记录</button></view
      >
      <button class="text-button discard" @click="discard">放弃本次计时</button>
      <text class="field-hint"
        >保存后才计入学习时长与打卡；可以在保存时核对日期和时长。</text
      >
    </view>
    <view v-else-if="workspace" class="card setup-card">
      <text class="section-title">这一段时间，学什么？</text>
      <view class="field first-field"
        ><text class="field-label">学习内容</text
        ><input
          v-model="title"
          class="input"
          maxlength="150"
          placeholder="例如：资料分析 · 增长率专项"
      /></view>
      <view class="field"
        ><text class="field-label">学习科目</text
        ><SubjectPicker
          v-model="subject"
          :subjects="subjects"
          :disabled="!!planId"
      /></view>
      <view v-if="plan" class="message plan-tip"
        >关联计划：{{ plan.title }}。保存学习记录后，计划会标记完成。</view
      >
      <view v-if="error" class="message error plan-tip">{{ error }}</view>
      <button class="button begin-button" @click="begin">开始专注</button>
      <text class="field-hint"
        >计时按当前账号保存在手机，回到这里可以继续。</text
      >
    </view>
  </view>
</template>

<style scoped>
.setup-card,
.focus-card {
  margin-top: 26rpx;
}
.first-field {
  margin-top: 30rpx;
}
.plan-tip {
  margin: 24rpx 0 0;
}
.begin-button {
  margin: 32rpx 0 16rpx;
}
.focus-card {
  text-align: center;
  background: linear-gradient(155deg, #e9efdf, #fafbf7);
  padding: 46rpx 28rpx 32rpx;
  border-radius: 32rpx;
  border: 1rpx solid #dfe7d3;
}
.focus-title {
  display: block;
  margin-top: 32rpx;
  font-size: 34rpx;
  font-weight: 550;
  word-break: break-word;
}
.timer {
  display: block;
  margin-top: 52rpx;
  font-size: 83rpx;
  color: #45634c;
  letter-spacing: 1rpx;
  font-weight: 500;
}
.timer-note {
  display: block;
  color: #97a08a;
  font-size: 24rpx;
  margin: 20rpx 0 38rpx;
}
.discard {
  margin: 28rpx auto 20rpx;
  color: #9b9f92;
}
</style>
