<script setup lang="ts">
import { computed, ref } from "vue";
import { request } from "../../api";
import EmptyState from "../../components/EmptyState.vue";
import SyncState from "../../components/SyncState.vue";
import type { StudyLog } from "../../types";
import {
  confirmAction,
  dateLabel,
  errorText,
  formatMinutes,
  openEditor,
  toast,
} from "../../utils";
import {
  refreshWorkspace,
  studyDate,
  subjectFor,
  subjects,
  useWorkspacePage,
  workspace,
} from "../../workspace";

useWorkspacePage();
const date = ref("");
const subject = ref("");
const keyword = ref("");
const busy = ref("");
const error = ref("");
const choices = computed(() => [
  { id: "", name: "全部科目" },
  ...subjects.value,
]);
const selectedSubject = computed(
  () =>
    choices.value.find((item) => item.id === subject.value)?.name || "全部科目",
);
const logs = computed(() =>
  (workspace.value?.logs || []).filter(
    (log) =>
      (!date.value || log.study_date === date.value) &&
      (!subject.value || log.subject_id === subject.value) &&
      (!keyword.value.trim() ||
        `${log.title}\n${log.note}`.includes(keyword.value.trim())),
  ),
);
const total = computed(() =>
  logs.value.reduce((sum, log) => sum + log.duration_minutes, 0),
);
async function remove(log: StudyLog) {
  if (
    busy.value ||
    !(await confirmAction(
      "删除这条学习记录？",
      "学习时长与打卡统计会重新计算。若它来自复习，已完成的复习排期仍会保留。",
    ))
  )
    return;
  busy.value = log.id;
  error.value = "";
  try {
    await request(`/logs/${log.id}`, "DELETE");
    await refreshWorkspace();
    toast("学习记录已删除");
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
        ><text class="eyebrow">每一次努力都有迹可循</text
        ><text class="page-title">积累，看得见。</text></view
      ><button class="button secondary compact" @click="openEditor('log')">
        ＋ 记一笔
      </button></view
    >
    <SyncState />
    <view class="card filters"
      ><input
        v-model="keyword"
        class="input"
        placeholder="搜索学习内容或笔记"
        maxlength="100"
      /><view class="row filter-row"
        ><picker
          class="grow"
          mode="date"
          :value="date || studyDate"
          :end="studyDate"
          @change="date = $event.detail.value"
          ><view class="picker"
            ><text>{{ date || "全部日期" }}</text
            ><text>⌄</text></view
          ></picker
        ><picker
          class="grow"
          :range="choices"
          range-key="name"
          @change="subject = choices[Number($event.detail.value)]?.id || ''"
          ><view class="picker"
            ><text>{{ selectedSubject }}</text
            ><text>⌄</text></view
          ></picker
        ></view
      ><button
        v-if="date || subject || keyword"
        class="text-button clear-filter"
        @click="
          date = '';
          subject = '';
          keyword = '';
        "
      >
        清除筛选
      </button></view
    >
    <view v-if="error" class="message error">{{ error }}</view>
    <template v-if="workspace"
      ><view class="section-head list-heading"
        ><text class="section-title">{{ logs.length }} 条记录</text
        ><text class="section-meta">共 {{ formatMinutes(total) }}</text></view
      ><EmptyState
        v-if="!logs.length"
        title="还没有符合条件的记录"
        description="试试其他筛选条件，或记下今天的学习。"
      /><view v-else class="stack"
        ><view v-for="log in logs" :key="log.id" class="card"
          ><view class="row between"
            ><view class="row"
              ><text
                class="dot"
                :style="{ background: subjectFor(log.subject_id)?.color }"
              /><text class="small muted"
                >{{ subjectFor(log.subject_id)?.name }} ·
                {{ dateLabel(log.study_date) }}</text
              ></view
            ><text class="pill">{{
              formatMinutes(log.duration_minutes)
            }}</text></view
          ><text class="card-title log-title">{{ log.title }}</text
          ><text v-if="log.question_count" class="card-note"
            >{{ log.correct_count }} / {{ log.question_count }} 题正确</text
          ><text v-if="log.note" class="card-note">{{ log.note }}</text
          ><view class="row between log-actions"
            ><button
              class="text-button"
              :disabled="!!busy"
              @click="openEditor('log', `id=${log.id}`)"
            >
              修改记录</button
            ><button
              class="text-button danger"
              :disabled="!!busy"
              @click="remove(log)"
            >
              {{ busy === log.id ? "删除中…" : "删除" }}
            </button></view
          ></view
        ></view
      ></template
    >
  </view>
</template>
<style scoped>
.filters {
  padding: 22rpx;
}
.filter-row {
  margin-top: 14rpx;
}
.picker {
  padding: 16rpx;
  font-size: 24rpx;
}
.clear-filter {
  margin-top: 8rpx;
}
.list-heading {
  margin-top: 32rpx;
}
.log-title {
  margin-top: 20rpx;
}
.log-actions {
  margin-top: 18rpx;
}
</style>
