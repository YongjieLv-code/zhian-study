<script setup lang="ts">
import { computed } from "vue";
import { sessionStorageError } from "../session";
import { focusStorageError } from "../focus";
import {
  lastSynced,
  loading,
  refreshWorkspace,
  syncError,
  workspace,
} from "../workspace";
const time = computed(() => {
  if (!lastSynced.value) return "";
  const value = new Date(lastSynced.value);
  return `${String(value.getHours()).padStart(2, "0")}:${String(value.getMinutes()).padStart(2, "0")}`;
});
</script>
<template>
  <view v-if="syncError" class="message error">
    <text>{{ syncError }}</text>
    <text v-if="workspace" class="saved-hint">当前显示上次同步的数据。</text>
    <button class="text-button" :disabled="loading" @click="refreshWorkspace()">
      重新同步
    </button>
  </view>
  <view v-else-if="loading && !workspace" class="message"
    >正在读取你的学习记录…</view
  >
  <view v-if="sessionStorageError || focusStorageError" class="message error">{{
    sessionStorageError || focusStorageError
  }}</view>
  <text v-if="time && !syncError" class="sync-time">{{
    loading ? "正在同步…" : `已同步 ${time} · 下拉可刷新`
  }}</text>
</template>
<style scoped>
.sync-time {
  display: block;
  color: #a0a895;
  font-size: 21rpx;
  margin: 16rpx 0 22rpx;
}
.saved-hint {
  display: block;
  margin-top: 8rpx;
}
</style>
