<script setup lang="ts">
defineProps<{ title: string; description?: string }>();
</script>
<template>
  <view class="empty">
    <view class="empty-mark">·</view>
    <text class="empty-title">{{ title }}</text>
    <text v-if="description" class="empty-description">{{ description }}</text>
    <slot />
  </view>
</template>
<style scoped>
.empty {
  padding: 40rpx 24rpx;
  text-align: center;
  background: #fbfcf8;
  border: 1rpx dashed #dce4d2;
  border-radius: 24rpx;
}
.empty-mark {
  width: 60rpx;
  height: 60rpx;
  margin: 0 auto 16rpx;
  background: #edf2e5;
  border-radius: 22rpx;
  color: #9aad87;
  font-size: 44rpx;
  line-height: 50rpx;
}
.empty-title {
  display: block;
  color: #66785c;
  font-size: 27rpx;
}
.empty-description {
  display: block;
  font-size: 24rpx;
  color: #98a08f;
  margin-top: 10rpx;
}
</style>
