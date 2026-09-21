<script setup lang="ts">
import { ref } from "vue";
import {
  Cloud,
  KeyRound,
  LoaderCircle,
  LogOut,
  RefreshCw,
  UserRound,
} from "lucide-vue-next";
import { request } from "../api";
import type { AuthStatus } from "../types";

defineProps<{
  status: AuthStatus;
  syncedAt: string;
  syncing: boolean;
  offline: boolean;
  busy: boolean;
}>();
const emit = defineEmits<{
  authenticate: [];
  sync: [];
  logout: [];
  changed: [status: AuthStatus];
}>();
const passwordOpen = ref(false),
  passwordBusy = ref(false),
  error = ref("");
const current = ref(""),
  next = ref(""),
  confirmation = ref("");
const serviceAddress = location.origin;
async function changePassword() {
  if (passwordBusy.value) return;
  error.value = "";
  if (next.value !== confirmation.value) {
    error.value = "两次新密码不一致。";
    return;
  }
  passwordBusy.value = true;
  try {
    const result = await request<AuthStatus>("/auth/password", "POST", {
      current_password: current.value,
      new_password: next.value,
    });
    current.value = next.value = confirmation.value = "";
    passwordOpen.value = false;
    emit("changed", result);
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    passwordBusy.value = false;
  }
}
</script>

<template>
  <section class="card account-card">
    <div class="card-heading">
      <div>
        <h2><UserRound :size="19" />账户与同步</h2>
        <p>
          {{
            status.local_mode
              ? "为现有记录开启账户保护。"
              : "已保存的积累，随账户一起继续。"
          }}
        </p>
      </div>
      <span class="account-badge">{{
        status.local_mode ? "本机使用" : "已登录"
      }}</span>
    </div>
    <div class="account-summary">
      <span class="backup-icon"><UserRound :size="22" /></span>
      <div>
        <strong>{{ status.account?.username ?? "尚未启用账户" }}</strong>
        <p>
          {{
            status.local_mode
              ? "创建账户后，当前学习数据会完整保留。"
              : `上次同步：${syncedAt || "等待连接"}`
          }}
        </p>
      </div>
    </div>
    <div class="account-actions">
      <button
        v-if="status.local_mode"
        class="button primary compact"
        @click="emit('authenticate')"
      >
        <KeyRound :size="16" />创建账户
      </button>
      <template v-else
        ><button
          class="button secondary compact"
          :disabled="busy || passwordBusy"
          @click="passwordOpen = !passwordOpen"
        >
          <KeyRound :size="16" />修改密码</button
        ><button
          class="text-button"
          :disabled="busy || passwordBusy"
          @click="emit('logout')"
        >
          <LogOut :size="16" />退出登录
        </button></template
      >
      <button
        class="button secondary compact"
        :disabled="syncing || busy"
        @click="emit('sync')"
      >
        <RefreshCw :size="16" :class="{ spin: syncing }" />立即同步
      </button>
    </div>
    <form
      v-if="passwordOpen"
      class="editor-form password-form"
      @submit.prevent="changePassword"
    >
      <label
        >当前密码<input
          v-model="current"
          type="password"
          autocomplete="current-password"
          required
          maxlength="128"
          :disabled="passwordBusy"
      /></label>
      <label
        >新密码<input
          v-model="next"
          type="password"
          autocomplete="new-password"
          required
          minlength="10"
          maxlength="128"
          placeholder="至少 10 个字符"
          :disabled="passwordBusy"
      /></label>
      <label
        >再次输入新密码<input
          v-model="confirmation"
          type="password"
          autocomplete="new-password"
          required
          minlength="10"
          maxlength="128"
          :disabled="passwordBusy"
      /></label>
      <p class="form-tip">修改后其他设备需要重新登录。</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <button class="button primary" :disabled="passwordBusy">
        <LoaderCircle v-if="passwordBusy" :size="16" class="spin" />保存新密码
      </button>
    </form>
    <p class="sync-detail" :class="{ 'sync-offline': offline }">
      <Cloud :size="16" /><span>{{
        offline
          ? "连接暂时中断，当前显示上次同步的数据。"
          : "页面打开时每 30 秒同步一次，回到页面也会刷新。专注计时在保存后同步。"
      }}</span>
    </p>
    <p class="service-address">
      当前服务 <code>{{ serviceAddress }}</code>
    </p>
  </section>
</template>
