<script setup lang="ts">
import { computed, ref } from "vue";
import { request } from "../../api";
import EmptyState from "../../components/EmptyState.vue";
import SyncState from "../../components/SyncState.vue";
import type { ReviewItem } from "../../types";
import { dateLabel, errorText, openEditor, toast } from "../../utils";
import {
  refreshWorkspace,
  studyDate,
  subjectFor,
  useWorkspacePage,
  workspace,
} from "../../workspace";

useWorkspacePage();
const filter = ref("due");
const busy = ref("");
const error = ref("");
const cards = computed(() =>
  (workspace.value?.reviews || []).filter((card) =>
    filter.value === "archived"
      ? card.archived
      : !card.archived &&
        (filter.value === "all" || card.due_date <= studyDate.value),
  ),
);
const due = computed(() => workspace.value?.overview.review_due || 0);
function begin(card: ReviewItem) {
  uni.navigateTo({ url: `/pages/review-session/index?id=${card.id}` });
}
async function archive(card: ReviewItem) {
  if (busy.value) return;
  busy.value = card.id;
  error.value = "";
  try {
    await request(`/reviews/${card.id}/archive`, "POST", {
      archived: !card.archived,
    });
    await refreshWorkspace();
    toast(card.archived ? "已恢复复习卡片" : "已归档，可在归档中恢复");
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
        ><text class="eyebrow">温故，而知新</text
        ><text class="page-title">把知识，记牢。</text></view
      ><button class="button secondary compact" @click="openEditor('review')">
        ＋ 新卡片
      </button></view
    >
    <SyncState />
    <view v-if="workspace" class="review-summary"
      ><text class="summary-number">{{ due }}</text
      ><view
        ><text class="strong">张卡片，等待回忆</text
        ><text class="card-note">先试着回想，再翻看笔记。</text></view
      ></view
    >
    <view class="segments"
      ><button
        class="segment"
        :class="{ active: filter === 'due' }"
        @click="filter = 'due'"
      >
        到期复习</button
      ><button
        class="segment"
        :class="{ active: filter === 'all' }"
        @click="filter = 'all'"
      >
        全部卡片</button
      ><button
        class="segment"
        :class="{ active: filter === 'archived' }"
        @click="filter = 'archived'"
      >
        已归档
      </button></view
    >
    <view v-if="error" class="message error">{{ error }}</view>
    <template v-if="workspace"
      ><EmptyState
        v-if="!cards.length"
        :title="filter === 'due' ? '当前没有到期卡片' : '这里还没有卡片'"
        :description="
          filter === 'due'
            ? '保持节奏，知识会慢慢扎根。'
            : '把易错点和重要知识整理成卡片。'
        "
      /><view v-else class="stack"
        ><view v-for="card in cards" :key="card.id" class="card"
          ><view class="row between"
            ><view class="row"
              ><text
                class="dot"
                :style="{ background: subjectFor(card.subject_id)?.color }"
              /><text class="small muted">{{
                subjectFor(card.subject_id)?.name
              }}</text></view
            ><text
              class="pill"
              :class="{ amber: !card.archived && card.due_date < studyDate }"
              >{{
                card.archived
                  ? "已归档"
                  : card.due_date <= studyDate
                    ? "待复习"
                    : `${dateLabel(card.due_date)}复习`
              }}</text
            ></view
          ><text class="card-title review-title">{{ card.title }}</text
          ><text class="card-note"
            >已复习 {{ card.review_count }} 次<text v-if="card.source">
              · {{ card.source }}</text
            ></text
          ><button
            v-if="!card.archived && card.due_date <= studyDate"
            class="button secondary start-review"
            @click="begin(card)"
          >
            开始回忆 →</button
          ><view class="row between review-actions"
            ><button
              class="text-button"
              :disabled="!!busy"
              @click="openEditor('review', `id=${card.id}`)"
            >
              编辑卡片</button
            ><button
              class="text-button muted"
              :disabled="!!busy"
              @click="archive(card)"
            >
              {{
                busy === card.id
                  ? "保存中…"
                  : card.archived
                    ? "恢复复习"
                    : "归档"
              }}
            </button></view
          ></view
        ></view
      ></template
    >
  </view>
</template>
<style scoped>
.review-summary {
  display: flex;
  align-items: center;
  gap: 26rpx;
  background: #eaf0e1;
  border: 1rpx solid #e0e7d6;
  border-radius: 28rpx;
  padding: 28rpx 32rpx;
}
.summary-number {
  font-size: 68rpx;
  font-weight: 550;
  line-height: 1.2;
  color: #6b845a;
}
.review-title {
  margin-top: 22rpx;
}
.start-review {
  margin-top: 24rpx;
  min-height: 76rpx;
  padding: 16rpx 24rpx;
  font-size: 26rpx;
}
.review-actions {
  margin-top: 12rpx;
}
</style>
