<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  ArrowDownToLine,
  Check,
  Clock3,
  FileJson,
  History,
  LoaderCircle,
  ShieldCheck,
  Upload,
} from "lucide-vue-next";
import BaseModal from "./BaseModal.vue";
import { download, request } from "../api";
import type { BackupCollection, BackupSnapshot, ImportPreview } from "../types";

const props = defineProps<{ hasTimer: boolean }>();
const emit = defineEmits<{
  close: [];
  restored: [message: string];
  saveTimer: [];
}>();
const mode = ref<"merge" | "replace">("merge");
const filename = ref(""),
  error = ref(""),
  historyError = ref("");
const busy = ref(false),
  historyLoading = ref(true),
  acknowledged = ref(false);
const selected = ref<Record<string, unknown> | null>(null);
const preview = ref<ImportPreview | null>(null);
const snapshots = ref<BackupSnapshot[]>([]);
const labels: Record<BackupCollection, string> = {
  subjects: "学习科目",
  plans: "学习计划",
  logs: "学习记录",
  reviews: "复习卡片",
  review_history: "复习历史",
};
const conflicts = computed(() =>
  Object.values(preview.value?.counts ?? {}).reduce(
    (sum, row) => sum + row.conflict,
    0,
  ),
);
const stamp = (value: string) =>
  new Date(
    /[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`,
  ).toLocaleString("zh-CN", { hour12: false });

async function makePreview() {
  if (!selected.value || busy.value) return;
  busy.value = true;
  error.value = "";
  preview.value = null;
  acknowledged.value = false;
  try {
    preview.value = await request<ImportPreview>("/backups/preview", "POST", {
      backup: selected.value,
      mode: mode.value,
    });
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    busy.value = false;
  }
}
async function selectFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || busy.value) return;
  preview.value = null;
  selected.value = null;
  filename.value = file.name;
  error.value = "";
  if (file.size > 10 * 1024 * 1024) {
    error.value = "请选择 10 MB 以内的备份文件。";
    return;
  }
  if (!file.name.toLowerCase().endsWith(".json")) {
    error.value = "请选择知岸导出的 JSON 备份。CSV 仅用于查看记录。";
    return;
  }
  try {
    const data = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
    if (!data || typeof data !== "object" || Array.isArray(data))
      throw new Error();
    selected.value = data;
  } catch {
    error.value = "文件不是有效的 JSON 备份，请检查文件是否完整。";
    return;
  }
  await makePreview();
}
async function selectSnapshot(item: BackupSnapshot) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  preview.value = null;
  selected.value = null;
  filename.value = `自动备份 · ${stamp(item.created_at)}`;
  try {
    selected.value = await request<Record<string, unknown>>(
      `/backups/${item.id}/download`,
    );
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    busy.value = false;
  }
  await makePreview();
}
async function saveSnapshot(item: BackupSnapshot) {
  if (busy.value) return;
  busy.value = true;
  historyError.value = "";
  try {
    await download(
      `/backups/${item.id}/download`,
      `zhian-snapshot-${item.id}.json`,
    );
  } catch (err) {
    historyError.value = (err as Error).message;
  } finally {
    busy.value = false;
  }
}
async function restore() {
  if (!preview.value || busy.value || props.hasTimer) return;
  busy.value = true;
  error.value = "";
  try {
    await request("/backups/apply", "POST", {
      id: preview.value.id,
      acknowledged: acknowledged.value,
    });
    emit(
      "restored",
      mode.value === "merge"
        ? "备份已合并，原有数据已自动备份。"
        : "学习数据已恢复，恢复前的数据已自动备份。",
    );
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    busy.value = false;
  }
}
watch(mode, () => {
  void makePreview();
});
async function loadHistory() {
  historyLoading.value = true;
  historyError.value = "";
  try {
    snapshots.value = await request<BackupSnapshot[]>("/backups/history");
  } catch (err) {
    historyError.value = (err as Error).message;
  } finally {
    historyLoading.value = false;
  }
}
onMounted(loadHistory);
</script>

<template>
  <BaseModal
    title="导入与恢复"
    eyebrow="KEEP EVERY STEP"
    wide
    :busy="busy"
    @close="emit('close')"
  >
    <div class="recovery-content">
      <p class="recovery-intro">选择知岸 JSON 备份，先核对内容，再恢复数据。</p>
      <label class="backup-picker"
        ><Upload :size="23" /><strong>选择 JSON 备份</strong
        ><span>{{
          filename || "支持当前版本与 v0.1 导出的备份，最大 10 MB"
        }}</span
        ><input
          type="file"
          accept=".json,application/json"
          aria-label="选择 JSON 备份"
          :disabled="busy"
          @change="selectFile"
      /></label>
      <fieldset class="restore-modes" :disabled="busy">
        <legend>恢复方式</legend>
        <label :class="{ selected: mode === 'merge' }"
          ><input
            v-model="mode"
            type="radio"
            value="merge"
            name="restore-mode"
          /><span
            ><strong>合并新增内容</strong
            ><small>保留当前目标和同编号内容，只加入新记录。</small></span
          ></label
        ><label :class="{ selected: mode === 'replace' }"
          ><input
            v-model="mode"
            type="radio"
            value="replace"
            name="restore-mode"
          /><span
            ><strong>完整替换</strong
            ><small>用备份中的目标、科目和记录替换当前学习数据。</small></span
          ></label
        >
      </fieldset>
      <p v-if="busy" class="recovery-busy" role="status">
        <LoaderCircle class="spin" :size="17" />正在处理，请稍候…
      </p>
      <div v-if="preview" class="import-preview">
        <div class="preview-heading">
          <h3><FileJson :size="18" />导入内容预览</h3>
          <span>10 分钟内有效</span>
        </div>
        <div
          class="preview-table-scroll"
          role="region"
          aria-label="备份内容对照"
          tabindex="0"
        >
          <table class="preview-table">
            <thead>
              <tr>
                <th>数据</th>
                <th>当前</th>
                <th>备份</th>
                <th>新增</th>
                <th>相同</th>
                <th>冲突</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(label, key) in labels" :key="key">
                <th scope="row">{{ label }}</th>
                <td>{{ preview.counts[key].current }}</td>
                <td>{{ preview.counts[key].incoming }}</td>
                <td>{{ preview.counts[key].new }}</td>
                <td>{{ preview.counts[key].duplicate }}</td>
                <td :class="{ 'has-conflict': preview.counts[key].conflict }">
                  {{ preview.counts[key].conflict }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="mode === 'merge'" class="preview-note">
          {{
            conflicts
              ? `${conflicts} 条同编号内容不同，将保留当前版本。`
              : "相同记录会自动跳过。"
          }}{{
            preview.profile_changed
              ? "备考目标不同，本次保留当前目标。"
              : "备考目标保持不变。"
          }}
        </p>
        <p v-else class="preview-note">
          将恢复为“{{ preview.profile.name }} ·
          {{ preview.profile.exam_name }}”，每日目标
          {{ preview.profile.daily_goal_minutes }} 分钟。
        </p>
        <label v-if="mode === 'replace'" class="checkbox-field replace-ack"
          ><input
            v-model="acknowledged"
            type="checkbox"
            :disabled="busy"
          /><span
            >我确认用这份备份替换当前学习数据<small
              >恢复前会自动保存完整备份，可在下方历史中找回。</small
            ></span
          ></label
        >
      </div>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div v-if="hasTimer" class="timer-restore-note">
        <Clock3 :size="18" />
        <p>还有一段未保存的专注计时，请先保存或放弃计时，再恢复数据。</p>
        <button class="text-button" :disabled="busy" @click="emit('saveTimer')">
          处理计时
        </button>
      </div>
      <p class="recovery-guarantee">
        <ShieldCheck
          :size="16"
        />写入前自动备份。数据校验或备份失败时，原记录会保留。
      </p>
      <div class="modal-actions">
        <button
          class="button secondary"
          :disabled="busy"
          @click="emit('close')"
        >
          暂不恢复</button
        ><button
          v-if="selected"
          class="button secondary"
          :disabled="busy"
          @click="makePreview"
        >
          重新预览</button
        ><button
          class="button primary"
          :disabled="
            !preview ||
            busy ||
            hasTimer ||
            (mode === 'replace' && !acknowledged)
          "
          @click="restore"
        >
          <Check :size="17" />{{ mode === "merge" ? "确认合并" : "确认替换" }}
        </button>
      </div>
      <section class="backup-history">
        <div class="preview-heading">
          <h3><History :size="18" />自动备份历史</h3>
          <button
            class="text-button"
            :disabled="historyLoading || busy"
            @click="loadHistory"
          >
            刷新
          </button>
        </div>
        <p class="history-note">
          保留最近 100 份备份的入口。可下载留存，或重新预览恢复。
        </p>
        <p v-if="historyLoading" class="history-empty">正在读取备份…</p>
        <p v-else-if="!snapshots.length && !historyError" class="history-empty">
          还没有自动备份。首次恢复或版本升级前会自动创建。
        </p>
        <p v-if="historyError" class="form-error" role="alert">
          {{ historyError }}
        </p>
        <ul v-if="snapshots.length" class="snapshot-list">
          <li v-for="item in snapshots" :key="item.id">
            <div>
              <strong>{{
                item.purpose === "before-upgrade" ? "版本升级前" : "数据恢复前"
              }}</strong
              ><span
                >{{ stamp(item.created_at) }} ·
                {{ Math.max(1, Math.ceil(item.size_bytes / 1024)) }} KB</span
              >
            </div>
            <div class="snapshot-actions">
              <button
                class="text-button"
                :disabled="busy"
                @click="selectSnapshot(item)"
              >
                预览恢复</button
              ><button
                class="icon-button"
                :aria-label="`下载 ${stamp(item.created_at)} 的备份`"
                :disabled="busy"
                @click="saveSnapshot(item)"
              >
                <ArrowDownToLine :size="17" />
              </button>
            </div>
          </li>
        </ul>
      </section>
    </div>
  </BaseModal>
</template>
