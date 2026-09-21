<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { request } from "../../api";
import { goLogin, session, setSession } from "../../session";
import type { MiniSession } from "../../types";
import { errorText, toast } from "../../utils";
import { refreshWorkspace } from "../../workspace";

const mode = ref("password");
const current = ref("");
const password = ref("");
const repeated = ref("");
const busy = ref(false);
const error = ref("");
onLoad((query) => {
  if (!session.value) goLogin();
  mode.value = query?.mode === "unbind" ? "unbind" : "password";
});
async function save() {
  if (busy.value) return;
  error.value = "";
  if (!current.value) {
    error.value = "请输入当前密码";
    return;
  }
  if (mode.value === "password") {
    if (password.value.length < 10 || password.value.length > 128) {
      error.value = "新密码需为 10–128 位";
      return;
    }
    if (password.value !== repeated.value) {
      error.value = "两次输入的新密码不一致";
      return;
    }
  }
  busy.value = true;
  try {
    const result = await request<MiniSession>(
      mode.value === "unbind"
        ? "/mini/auth/wechat/unbind"
        : "/mini/auth/password",
      "POST",
      mode.value === "unbind"
        ? { current_password: current.value }
        : { current_password: current.value, new_password: password.value },
    );
    setSession(result);
    current.value = "";
    password.value = "";
    repeated.value = "";
    await refreshWorkspace();
    toast(mode.value === "unbind" ? "已解除微信绑定" : "密码已更新");
    uni.navigateBack({
      fail: () => uni.switchTab({ url: "/pages/mine/index" }),
    });
  } catch (caught) {
    error.value = errorText(caught);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <view class="page">
    <text class="eyebrow">我的账号 · {{ session?.account.username }}</text
    ><text class="page-title">{{
      mode === "unbind" ? "管理微信绑定" : "修改登录密码"
    }}</text>
    <text class="subtitle">{{
      mode === "unbind"
        ? "解除后，微信将无法直接登录此账号；账号密码仍可使用。"
        : "修改后，其他设备需要使用新密码重新登录。"
    }}</text>
    <view class="card account-form"
      ><view class="field"
        ><text class="field-label">当前密码</text
        ><input
          v-model="current"
          class="input"
          password
          placeholder="验证当前账号"
          maxlength="128"
          :disabled="busy" /></view
      ><template v-if="mode === 'password'"
        ><view class="field"
          ><text class="field-label">新密码</text
          ><input
            v-model="password"
            class="input"
            password
            placeholder="至少 10 位"
            maxlength="128"
            :disabled="busy" /></view
        ><view class="field"
          ><text class="field-label">再次输入新密码</text
          ><input
            v-model="repeated"
            class="input"
            password
            placeholder="确认新密码"
            maxlength="128"
            :disabled="busy" /></view></template
    ></view>
    <view v-if="error" class="message error account-error">{{ error }}</view
    ><button
      class="button safe-actions"
      :class="{ danger: mode === 'unbind' }"
      :disabled="busy"
      :loading="busy"
      @click="save"
    >
      {{ mode === "unbind" ? "验证密码并解除绑定" : "保存新密码" }}
    </button>
  </view>
</template>
<style scoped>
.account-form,
.account-error {
  margin-top: 30rpx;
}
</style>
