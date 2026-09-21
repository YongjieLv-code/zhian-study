<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { api } from "../../api";
import SyncState from "../../components/SyncState.vue";
import { isWeChat } from "../../config";
import { focus } from "../../focus";
import { goLogin, session, sessionGeneration, setSession } from "../../session";
import {
  confirmAction,
  errorText,
  formatMinutes,
  openEditor,
} from "../../utils";
import {
  loading,
  refreshWorkspace,
  useWorkspacePage,
  workspace,
} from "../../workspace";

useWorkspacePage();
const wechatEnabled = ref(false);
const busy = ref(false);
const error = ref("");
onShow(async () => {
  if (!session.value) return;
  const generation = sessionGeneration();
  const results = await Promise.allSettled([api.account(), api.config()]);
  if (generation !== sessionGeneration()) return;
  if (results[0].status === "fulfilled" && session.value)
    setSession({ ...session.value, ...results[0].value });
  if (results[1].status === "fulfilled")
    wechatEnabled.value = results[1].value.wechat_enabled;
});
function records() {
  uni.navigateTo({ url: "/pages/records/index" });
}
function account(mode = "password") {
  uni.navigateTo({ url: `/pages/account/index?mode=${mode}` });
}
function bind() {
  uni.navigateTo({ url: "/pages/login/index?bind=1" });
}
async function logout() {
  if (
    busy.value ||
    !(await confirmAction(
      "退出当前账号？",
      focus.value
        ? "未保存的计时会暂停并保留，重新登录此账号可以继续。"
        : "学习记录已保存在服务中，重新登录后可以继续查看。",
    ))
  )
    return;
  busy.value = true;
  error.value = "";
  try {
    await api.logout();
    setSession(null);
    goLogin();
  } catch (caught) {
    error.value = errorText(caught);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <view class="page">
    <text class="eyebrow">与自己约定，向目标靠近</text
    ><text class="page-title"
      >你好，{{ workspace?.overview.profile.name || "备考者" }}。</text
    >
    <SyncState />
    <view v-if="error" class="message error">{{ error }}</view>
    <template v-if="workspace && session">
      <view class="profile-card"
        ><view class="avatar">{{
          workspace.overview.profile.name.slice(0, 1)
        }}</view
        ><view class="grow"
          ><text class="profile-name">{{
            workspace.overview.profile.name
          }}</text
          ><text class="profile-account"
            >@{{ session.account.username }}</text
          ></view
        ><button class="text-button" @click="openEditor('profile')">
          编辑目标 →
        </button></view
      >
      <view class="card goal-card"
        ><text class="eyebrow">我的备考目标</text
        ><text class="goal-title">{{
          workspace.overview.profile.exam_name
        }}</text
        ><view class="row between goal-meta"
          ><text
            >每日 {{ workspace.overview.profile.daily_goal_minutes }} 分钟</text
          ><text>{{
            workspace.overview.profile.exam_date || "考试日期待定"
          }}</text></view
        ><view class="divider" /><view class="row between"
          ><text class="small muted"
            >累计学习
            {{ formatMinutes(workspace.overview.total_minutes) }}</text
          ><text class="small muted"
            >已打卡 {{ workspace.overview.total_days }} 天</text
          ></view
        ></view
      >
      <view class="section"
        ><view class="section-head"
          ><text class="section-title">学习空间</text
          ><button
            class="text-button"
            :disabled="loading"
            @click="refreshWorkspace()"
          >
            {{ loading ? "同步中…" : "立即同步" }}
          </button></view
        ><view class="card menu"
          ><button class="menu-row" @click="records">
            <text>我的学习记录</text
            ><text class="menu-value"
              >{{ workspace.logs.length }} 条 ›</text
            ></button
          ><button class="menu-row" @click="openEditor('profile')">
            <text>考试与每日目标</text><text class="menu-value">›</text></button
          ><button class="menu-row" @click="openEditor('subject')">
            <text>添加学习科目</text
            ><text class="menu-value"
              >已有 {{ workspace.subjects.length }} 科 ›</text
            >
          </button></view
        ></view
      >
      <view class="section"
        ><view class="section-head"
          ><text class="section-title">账号与登录</text
          ><text class="section-meta">已保存记录可跨设备查看</text></view
        ><view class="card menu"
          ><button class="menu-row" @click="account()">
            <text>修改密码</text><text class="menu-value">›</text></button
          ><template v-if="isWeChat"
            ><button
              v-if="session.wechat_bound"
              class="menu-row"
              @click="account('unbind')"
            >
              <text>微信绑定</text
              ><text class="menu-value">已绑定 · 管理 ›</text></button
            ><button
              v-else
              class="menu-row"
              :disabled="!wechatEnabled"
              @click="bind"
            >
              <text>绑定微信</text
              ><text class="menu-value">{{
                wechatEnabled ? "绑定后可快捷登录 ›" : "暂未开通"
              }}</text>
            </button></template
          ><button class="menu-row logout" :disabled="busy" @click="logout">
            <text>退出登录</text><text class="menu-value">›</text>
          </button></view
        ></view
      >
      <text class="version-note">知岸 · 随身学习 v0.3.0</text
      ><text class="footnote">每一步，都算数。</text>
    </template>
  </view>
</template>
<style scoped>
.profile-card {
  display: flex;
  align-items: center;
  gap: 22rpx;
  padding: 22rpx 4rpx 30rpx;
}
.avatar {
  width: 92rpx;
  height: 92rpx;
  line-height: 92rpx;
  text-align: center;
  background: #e4ebd9;
  border-radius: 32rpx;
  font-size: 39rpx;
  color: #799365;
}
.profile-name {
  display: block;
  font-size: 33rpx;
  font-weight: 550;
}
.profile-account {
  display: block;
  font-size: 23rpx;
  color: #9ba38f;
  margin-top: 4rpx;
}
.goal-card {
  background: linear-gradient(135deg, #edf2e4, #f9faf4);
  border-color: #e0e7d6;
}
.goal-title {
  display: block;
  font-size: 35rpx;
  font-weight: 550;
  margin-top: 18rpx;
}
.goal-meta {
  font-size: 24rpx;
  color: #899779;
  margin-top: 18rpx;
}
.menu {
  padding: 4rpx 26rpx;
}
.menu-row {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding: 28rpx 0;
  text-align: left;
  background: transparent;
  color: #536549;
  font-size: 28rpx;
  border-radius: 0;
}
.menu-row + .menu-row {
  border-top: 1rpx solid #edf0e7;
}
.menu-value {
  font-size: 23rpx;
  color: #9da58f;
}
.logout {
  color: #9d8270;
}
.version-note,
.footnote {
  display: block;
  text-align: center;
  font-size: 22rpx;
  color: #a4ac98;
  margin-top: 38rpx;
}
.footnote {
  margin-top: 9rpx;
  letter-spacing: 3rpx;
}
</style>
