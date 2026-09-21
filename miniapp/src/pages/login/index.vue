<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { api, ApiError, wechatCode } from "../../api";
import { isWeChat } from "../../config";
import { session, setSession } from "../../session";
import type { AuthConfig, MiniSession } from "../../types";
import { errorText } from "../../utils";
import { refreshWorkspace } from "../../workspace";

const config = ref<AuthConfig | null>(null);
const mode = ref<"login" | "register">("login");
const username = ref("");
const password = ref("");
const repeated = ref("");
const bootstrap = ref("");
const busy = ref(false);
const loading = ref(true);
const error = ref("");
const binding = ref(false);
const bindingToken = ref("");
const fromAccount = ref(false);

async function loadConfig() {
  loading.value = true;
  error.value = "";
  try {
    config.value = await api.config();
    if (
      !binding.value &&
      config.value.first_account &&
      config.value.can_register
    )
      mode.value = "register";
  } catch (caught) {
    error.value = errorText(caught);
  } finally {
    loading.value = false;
  }
}

onLoad((query) => {
  fromAccount.value = query?.bind === "1" && !!session.value;
  binding.value = fromAccount.value;
  if (fromAccount.value) username.value = session.value!.account.username;
  void loadConfig();
});

async function finish(value: MiniSession) {
  setSession(value);
  password.value = "";
  repeated.value = "";
  bootstrap.value = "";
  bindingToken.value = "";
  await refreshWorkspace();
  uni.reLaunch({ url: "/pages/today/index" });
}

async function submit() {
  if (busy.value || loading.value) return;
  error.value = "";
  const name = username.value.trim().toLowerCase();
  if (!/^[a-z0-9_]{3,32}$/.test(name)) {
    error.value = "用户名需为 3–32 位字母、数字或下划线";
    return;
  }
  if (password.value.length < 10 || password.value.length > 128) {
    error.value = "密码需为 10–128 位";
    return;
  }
  if (
    !binding.value &&
    mode.value === "register" &&
    password.value !== repeated.value
  ) {
    error.value = "两次输入的密码不一致";
    return;
  }
  busy.value = true;
  try {
    const credentials = { username: name, password: password.value };
    let result: MiniSession;
    if (binding.value) {
      if (!bindingToken.value) {
        if (!isWeChat) throw new Error("请在微信小程序中完成绑定");
        const proof = await api.wechat(await wechatCode(), "bind");
        if (!proof.needs_binding) throw new Error("绑定凭证未取得，请重试");
        bindingToken.value = proof.binding_token;
      }
      result = await api.bind({
        ...credentials,
        binding_token: bindingToken.value,
      });
    } else {
      result =
        mode.value === "register"
          ? await api.register({
              ...credentials,
              bootstrap_token: bootstrap.value,
            })
          : await api.login(credentials);
    }
    await finish(result);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 400)
      bindingToken.value = "";
    error.value = errorText(caught);
  } finally {
    busy.value = false;
  }
}

async function loginWithWechat() {
  if (busy.value || !config.value?.wechat_enabled) return;
  busy.value = true;
  error.value = "";
  try {
    const result = await api.wechat(await wechatCode(), "login");
    if (result.needs_binding) {
      binding.value = true;
      bindingToken.value = result.binding_token;
      mode.value = "login";
    } else await finish(result);
  } catch (caught) {
    error.value = errorText(caught);
  } finally {
    busy.value = false;
  }
}

function cancelBinding() {
  if (fromAccount.value) {
    uni.navigateBack();
    return;
  }
  binding.value = false;
  bindingToken.value = "";
  error.value = "";
}

function changeMode() {
  mode.value = mode.value === "login" ? "register" : "login";
  password.value = "";
  repeated.value = "";
  error.value = "";
}
</script>

<template>
  <view class="page login-page">
    <view class="brand"
      ><view class="brand-mark">知</view
      ><view
        ><text class="brand-name">知岸</text
        ><text class="brand-caption">每一步，都算数</text></view
      ></view
    >
    <text class="page-title">{{ "让今天的努力，\n成为明天的底气。" }}</text>
    <text class="subtitle">记录学习 · 按时复习 · 看见成长</text>
    <view class="card login-card">
      <text class="section-title">{{
        binding
          ? "绑定你的知岸账号"
          : mode === "register"
            ? "开启学习旅程"
            : "欢迎回来"
      }}</text>
      <text class="card-note">{{
        binding
          ? "验证账号后，微信登录将继续使用同一份学习记录。新用户可先返回创建账号。"
          : "手机和电脑，共享你的学习记录。"
      }}</text>
      <view v-if="loading" class="message form-message">正在连接学习服务…</view>
      <view
        v-if="config?.first_account && mode === 'register' && !binding"
        class="message form-message"
        >创建首个账号后，会保留此服务中已有的学习记录。</view
      >
      <view class="field first-field"
        ><text class="field-label">用户名</text
        ><input
          v-model="username"
          class="input"
          placeholder="3–32 位字母、数字或下划线"
          :disabled="busy || fromAccount"
          maxlength="32"
          :adjust-position="true"
      /></view>
      <view class="field"
        ><text class="field-label">密码</text
        ><input
          v-model="password"
          class="input"
          password
          placeholder="至少 10 位"
          :disabled="busy"
          maxlength="128"
          confirm-type="done"
          @confirm="submit"
      /></view>
      <view v-if="mode === 'register' && !binding" class="field"
        ><text class="field-label">再次输入密码</text
        ><input
          v-model="repeated"
          class="input"
          password
          placeholder="确认你的密码"
          :disabled="busy"
          maxlength="128"
      /></view>
      <view
        v-if="mode === 'register' && config?.requires_bootstrap && !binding"
        class="field"
        ><text class="field-label">初始化口令</text
        ><input
          v-model="bootstrap"
          class="input"
          password
          placeholder="由此学习服务的维护者提供"
          :disabled="busy"
          maxlength="256"
      /></view>
      <view v-if="error" class="message error form-message">{{ error }}</view>
      <button
        v-if="!config && !loading"
        class="button secondary form-message"
        @click="loadConfig"
      >
        重新连接
      </button>
      <button
        class="button submit"
        :loading="busy"
        :disabled="busy || loading || !config"
        @click="submit"
      >
        {{
          binding
            ? "验证并绑定微信"
            : mode === "register"
              ? "创建账号，开始学习"
              : "登录知岸"
        }}
      </button>
      <button
        v-if="binding"
        class="text-button switch-mode"
        :disabled="busy"
        @click="cancelBinding"
      >
        {{ fromAccount ? "返回我的账号" : "返回账号登录 / 注册" }}
      </button>
      <button
        v-else-if="config?.can_register"
        class="text-button switch-mode"
        :disabled="busy"
        @click="changeMode"
      >
        {{ mode === "login" ? "还没有账号？创建一个" : "已有账号？直接登录" }}
      </button>
      <template v-if="isWeChat && !binding && mode === 'login'">
        <view class="divider" />
        <button
          v-if="config?.wechat_enabled"
          class="button secondary"
          :disabled="busy"
          @click="loginWithWechat"
        >
          微信快捷登录
        </button>
        <text v-else class="field-hint"
          >微信快捷登录尚未开通，可使用账号密码登录。</text
        >
      </template>
    </view>
    <text class="login-footer">{{
      "不必急于抵达。每一次认真学习，\n都在让你离目标更近一点。"
    }}</text>
  </view>
</template>

<style scoped>
.login-page {
  padding-top: 36rpx;
  padding-bottom: 56rpx;
}
.brand {
  display: flex;
  gap: 18rpx;
  align-items: center;
  margin-bottom: 50rpx;
}
.brand-mark {
  width: 86rpx;
  height: 86rpx;
  line-height: 86rpx;
  text-align: center;
  border-radius: 28rpx 28rpx 28rpx 7rpx;
  color: #fff;
  background: #6e885f;
  font-size: 42rpx;
}
.brand-name {
  display: block;
  font-size: 35rpx;
  font-weight: 600;
  letter-spacing: 5rpx;
}
.brand-caption {
  display: block;
  font-size: 21rpx;
  color: #9aa28e;
  letter-spacing: 2rpx;
}
.page-title {
  font-size: 47rpx;
  line-height: 1.55;
  white-space: pre-line;
}
.login-card {
  margin-top: 38rpx;
  padding: 32rpx;
}
.first-field {
  margin-top: 32rpx;
}
.form-message {
  margin: 24rpx 0 0;
}
.submit {
  margin-top: 32rpx;
}
.switch-mode {
  margin: 22rpx auto 0;
}
.login-footer {
  display: block;
  margin-top: 32rpx;
  text-align: center;
  font-size: 23rpx;
  line-height: 1.9;
  color: #9ba38e;
  white-space: pre-line;
}
</style>
