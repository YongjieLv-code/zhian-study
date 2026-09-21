<script setup lang="ts">
import { computed } from "vue";
import EmptyState from "../../components/EmptyState.vue";
import SyncState from "../../components/SyncState.vue";
import { focus, focusElapsed } from "../../focus";
import {
  clockText,
  dateLabel,
  formatMinutes,
  openEditor,
  percentage,
} from "../../utils";
import {
  studyDate,
  subjectFor,
  useWorkspacePage,
  workspace,
} from "../../workspace";

useWorkspacePage();
const overview = computed(() => workspace.value?.overview);
const progress = computed(() =>
  Math.min(
    100,
    Math.round(
      ((overview.value?.today.minutes || 0) /
        (overview.value?.profile.daily_goal_minutes || 120)) *
        100,
    ),
  ),
);
const todayPlans = computed(
  () =>
    workspace.value?.plans
      .filter((plan) => plan.scheduled_date === studyDate.value)
      .slice(0, 4) || [],
);
const recentLogs = computed(() => workspace.value?.logs.slice(0, 3) || []);
const accuracy = computed(() =>
  percentage(
    overview.value?.today.correct || 0,
    overview.value?.today.questions || 0,
  ),
);
function openFocus(planId?: string) {
  uni.navigateTo({
    url: `/pages/focus/index${planId ? `?plan=${encodeURIComponent(planId)}` : ""}`,
  });
}
function showPlans() {
  uni.switchTab({ url: "/pages/plans/index" });
}
function showReviews() {
  uni.switchTab({ url: "/pages/reviews/index" });
}
function showRecords() {
  uni.navigateTo({ url: "/pages/records/index" });
}
</script>

<template>
  <view class="page">
    <text class="eyebrow">{{ dateLabel(studyDate) }} · 今天也向前一步</text>
    <text class="page-title">把今天，学扎实。</text>
    <SyncState />
    <template v-if="overview">
      <view class="hero">
        <view class="row between"
          ><text class="hero-label"
            >{{ overview.profile.name }}，今日已学习</text
          ><text
            class="pill"
            :class="{ amber: overview.today.minutes === 0 }"
            >{{ overview.today.minutes > 0 ? "今日已打卡" : "等待点亮" }}</text
          ></view
        >
        <view class="hero-number"
          ><text class="hero-value number">{{ overview.today.minutes }}</text
          ><text class="hero-unit">分钟</text></view
        >
        <view class="row between progress-label"
          ><text>每日目标 {{ overview.profile.daily_goal_minutes }} 分钟</text
          ><text>{{ progress }}%</text></view
        >
        <view class="progress"
          ><view class="progress-fill" :style="{ width: `${progress}%` }"
        /></view>
        <view class="hero-bottom"
          ><text>{{
            overview.days_until_exam === null
              ? "认真积累，自会抵达。"
              : overview.days_until_exam >= 0
                ? `距离${overview.profile.exam_name}还有 ${overview.days_until_exam} 天`
                : "新的学习目标，等你继续书写。"
          }}</text
          ><text class="sprout">✦</text></view
        >
      </view>
      <view class="metrics metric-row">
        <view class="metric"
          ><text class="metric-value number"
            >{{ overview.streak }}<text class="unit">天</text></text
          ><text class="metric-label">连续学习</text></view
        >
        <view class="metric"
          ><text class="metric-value number"
            >{{ overview.review_due }}<text class="unit">张</text></text
          ><text class="metric-label">到期复习</text></view
        >
        <view class="metric"
          ><text class="metric-value number">{{
            accuracy === null ? "—" : `${accuracy}%`
          }}</text
          ><text class="metric-label">今日正确率</text></view
        >
      </view>
      <view class="actions main-actions">
        <button class="button grow" @click="openFocus()">
          {{ focus ? `继续专注 · ${clockText(focusElapsed)}` : "开始一段专注"
          }}<text>→</text>
        </button>
        <button
          class="button secondary record-button"
          @click="openEditor('log')"
        >
          ＋ 记一笔
        </button>
      </view>
      <view v-if="overview.review_due > 0" class="review-callout"
        ><view class="grow"
          ><text class="strong">让记忆，再深一点</text
          ><text class="card-note"
            >{{ overview.review_due }} 张卡片等你回顾</text
          ></view
        ><button class="text-button" @click="showReviews">
          去复习 →
        </button></view
      >
      <view class="section">
        <view class="section-head"
          ><text class="section-title">今天的安排</text
          ><button class="text-button" @click="showPlans">
            全部计划 →
          </button></view
        >
        <EmptyState
          v-if="!todayPlans.length"
          title="给今天一个小目标"
          description="从一项能完成的计划开始。"
          ><button class="text-button empty-action" @click="openEditor('plan')">
            ＋ 添加学习计划
          </button></EmptyState
        >
        <view v-else class="stack"
          ><view
            v-for="plan in todayPlans"
            :key="plan.id"
            class="card plan-card"
            ><view class="row"
              ><view
                class="plan-check"
                :class="{ completed: plan.completed }"
                >{{ plan.completed ? "✓" : "" }}</view
              ><view class="grow"
                ><text class="card-title">{{ plan.title }}</text
                ><view class="row plan-meta"
                  ><text
                    class="dot"
                    :style="{ background: subjectFor(plan.subject_id)?.color }"
                  /><text
                    >{{ subjectFor(plan.subject_id)?.name }} ·
                    {{ plan.minutes }} 分钟</text
                  ></view
                ></view
              ><button
                v-if="!plan.completed"
                class="button secondary compact"
                @click="openFocus(plan.id)"
              >
                开始</button
              ><text v-else class="pill">已完成</text></view
            ></view
          ></view
        >
      </view>
      <view class="section">
        <view class="section-head"
          ><text class="section-title">最近的努力</text
          ><button class="text-button" @click="showRecords">
            学习记录 →
          </button></view
        >
        <EmptyState
          v-if="!recentLogs.length"
          title="你的第一笔努力，值得记录"
          description="完成学习后保存记录，即可点亮打卡。"
        />
        <view v-else class="card"
          ><view
            v-for="(log, index) in recentLogs"
            :key="log.id"
            class="log-row"
            :class="{ separated: index > 0 }"
            ><view class="grow"
              ><text class="card-title">{{ log.title }}</text
              ><text class="card-note"
                >{{ dateLabel(log.study_date) }} ·
                {{ subjectFor(log.subject_id)?.name }}</text
              ></view
            ><text class="log-duration">{{
              formatMinutes(log.duration_minutes)
            }}</text></view
          ></view
        >
      </view>
      <text class="closing-note">日拱一卒，功不唐捐。</text>
    </template>
  </view>
</template>

<style scoped>
.hero {
  padding: 32rpx;
  border: 1rpx solid #dfe7d3;
  border-radius: 30rpx;
  background: linear-gradient(125deg, #e9efdf, #f3f5e9);
}
.hero-label {
  color: #6e7d63;
  font-size: 25rpx;
}
.hero-number {
  display: flex;
  gap: 14rpx;
  align-items: baseline;
  margin: 22rpx 0 14rpx;
}
.hero-value {
  font-size: 96rpx;
  letter-spacing: -5rpx;
  line-height: 1.15;
  font-weight: 550;
  color: #40543b;
}
.hero-unit {
  font-size: 26rpx;
  color: #7a896c;
}
.progress-label {
  font-size: 23rpx;
  color: #879477;
  margin: 20rpx 0 12rpx;
}
.hero-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 26rpx;
  font-size: 23rpx;
  color: #8a977b;
}
.sprout {
  color: #acba96;
  font-size: 33rpx;
}
.metric-row {
  margin-top: 20rpx;
}
.unit {
  font-size: 21rpx;
  margin-left: 6rpx;
  font-weight: 400;
  color: #8e9885;
}
.main-actions {
  margin-top: 24rpx;
}
.record-button {
  flex: 0 0 184rpx;
}
.main-actions > .grow {
  font-size: 26rpx;
}
.review-callout {
  display: flex;
  gap: 16rpx;
  align-items: center;
  margin-top: 24rpx;
  padding: 24rpx;
  border-radius: 22rpx;
  background: #f0eddf;
  color: #7e7759;
}
.review-callout .card-note {
  color: #a49b7c;
  margin-top: 3rpx;
}
.plan-card {
  padding: 25rpx;
}
.plan-check {
  width: 36rpx;
  height: 36rpx;
  flex-shrink: 0;
  border: 2rpx solid #dbe4d0;
  border-radius: 12rpx;
  text-align: center;
  line-height: 34rpx;
  color: #7d9468;
}
.plan-check.completed {
  background: #edf3e5;
  border-color: #edf3e5;
}
.plan-meta {
  font-size: 23rpx;
  color: #8e9885;
  gap: 10rpx;
  margin-top: 7rpx;
}
.log-row {
  display: flex;
  gap: 20rpx;
  align-items: center;
}
.separated {
  border-top: 1rpx solid #edf0e7;
  padding-top: 24rpx;
  margin-top: 24rpx;
}
.log-duration {
  font-size: 25rpx;
  color: #69815b;
  white-space: nowrap;
}
.closing-note {
  display: block;
  text-align: center;
  font-size: 23rpx;
  color: #a4ad96;
  letter-spacing: 3rpx;
  margin-top: 46rpx;
}
.empty-action {
  margin: 16rpx auto 0;
}
</style>
