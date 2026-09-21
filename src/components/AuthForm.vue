<script setup lang="ts">
import { computed, ref } from "vue";
import { ArrowRight, LoaderCircle, LockKeyhole } from "lucide-vue-next";
import { request } from "../api";
import type { AuthStatus } from "../types";

const props = defineProps<{
  status: AuthStatus;
  initialMode?: "login" | "register";
}>();
const emit = defineEmits<{
  authenticated: [status: AuthStatus];
  busy: [value: boolean];
}>();
const mode = ref(
  props.initialMode ??
    (props.status.first_account && props.status.can_register
      ? "register"
      : "login"),
);
const username = ref(""),
  password = ref(""),
  confirmation = ref(""),
  bootstrap = ref("");
const busy = ref(false),
  error = ref("");
const registering = computed(() => mode.value === "register");

function switchMode() {
  mode.value = registering.value ? "login" : "register";
  password.value = confirmation.value = error.value = "";
}
async function submit() {
  if (busy.value) return;
  error.value = "";
  if (registering.value && password.value !== confirmation.value) {
    error.value = "两次输入的密码不一致。";
    return;
  }
  busy.value = true;
  emit("busy", true);
  try {
    const result = await request<AuthStatus>(`/auth/${mode.value}`, "POST", {
      username: username.value,
      password: password.value,
      ...(registering.value ? { bootstrap_token: bootstrap.value } : {}),
    });
    password.value = confirmation.value = bootstrap.value = "";
    emit("authenticated", result);
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    busy.value = false;
    emit("busy", false);
  }
}
</script>

<template>
  <form class="editor-form auth-form" @submit.prevent="submit">
    <p class="auth-intro">
      {{
        registering
          ? status.first_account
            ? "创建首个账户后，当前学习记录会保留，并需要登录才能访问。"
            : "为自己创建一个独立的学习空间。"
          : "登录后，继续积累属于你的每一步。"
      }}
    </p>
    <label
      >用户名<input
        v-model="username"
        name="username"
        autocomplete="username"
        placeholder="3–32 位字母、数字或下划线"
        minlength="3"
        maxlength="32"
        pattern="[a-zA-Z0-9_]+"
        required
        :disabled="busy"
    /></label>
    <label
      >密码<input
        v-model="password"
        name="password"
        type="password"
        :autocomplete="registering ? 'new-password' : 'current-password'"
        placeholder="至少 10 个字符"
        minlength="10"
        maxlength="128"
        required
        :disabled="busy"
    /></label>
    <label v-if="registering"
      >确认密码<input
        v-model="confirmation"
        name="password-confirmation"
        type="password"
        autocomplete="new-password"
        minlength="10"
        maxlength="128"
        required
        :disabled="busy"
    /></label>
    <label v-if="registering && status.requires_bootstrap"
      >初始化口令<input
        v-model="bootstrap"
        type="password"
        autocomplete="off"
        placeholder="由服务部署者设置"
        maxlength="256"
        required
        :disabled="busy"
    /></label>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <button class="button primary auth-submit" :disabled="busy">
      <LoaderCircle v-if="busy" :size="17" class="spin" /><ArrowRight
        v-else
        :size="17"
      />{{ registering ? "创建账户并进入" : "登录学习空间" }}
    </button>
    <button
      v-if="status.can_register && !status.first_account"
      type="button"
      class="text-button auth-switch"
      :disabled="busy"
      @click="switchMode"
    >
      {{ registering ? "已有账户，去登录" : "创建新账户" }}
    </button>
    <p class="form-tip">
      <LockKeyhole
        :size="14"
      />在其他设备打开同一个服务地址，使用同一账户即可查看已保存的学习记录。
    </p>
  </form>
</template>
