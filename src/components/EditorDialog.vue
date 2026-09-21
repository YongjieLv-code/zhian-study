<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ArrowRight, Check, LoaderCircle } from "lucide-vue-next";
import BaseModal from "./BaseModal.vue";
import { request } from "../api";
import type {
  EditorMode,
  Plan,
  Profile,
  ReviewItem,
  StudyLog,
  Subject,
  TimerState,
} from "../types";

const props = defineProps<{
  mode: EditorMode;
  subjects: Subject[];
  today: string;
  profile: Profile;
  plan?: Plan;
  log?: StudyLog;
  review?: ReviewItem;
  initialDate?: string;
  timer?: TimerState;
  timerMinutes?: number;
}>();
const emit = defineEmits<{ close: []; saved: [message: string] }>();
const busy = ref(false);
const error = ref("");
const recordId = props.log?.id ?? crypto.randomUUID();
const form = reactive({
  title:
    props.log?.title ??
    props.review?.title ??
    props.timer?.title ??
    props.plan?.title ??
    "",
  subject_id:
    props.log?.subject_id ??
    props.review?.subject_id ??
    props.timer?.subject_id ??
    props.plan?.subject_id ??
    props.subjects[0]?.id ??
    "",
  date:
    (props.mode === "log"
      ? (props.log?.study_date ?? props.timer?.study_date)
      : undefined) ??
    (props.mode === "review" ? props.review?.due_date : undefined) ??
    (props.mode === "plan" ? props.plan?.scheduled_date : undefined) ??
    props.initialDate ??
    props.today,
  minutes:
    props.log?.duration_minutes ??
    props.timerMinutes ??
    props.plan?.minutes ??
    30,
  question_count: props.log?.question_count ?? 0,
  correct_count: props.log?.correct_count ?? 0,
  note: props.log?.note ?? props.review?.note ?? props.plan?.note ?? "",
  source: props.review?.source ?? (props.log ? "学习记录" : ""),
  add_to_review: false,
  name: props.mode === "subject" ? "" : props.profile.name,
  exam_name: props.profile.exam_name,
  exam_date: props.profile.exam_date ?? "",
  daily_goal_minutes: props.profile.daily_goal_minutes,
  kind: "practice",
});
const editing = computed(() =>
  props.mode === "log"
    ? !!props.log
    : props.mode === "plan"
      ? !!props.plan
      : props.mode === "review"
        ? !!props.review
        : false,
);
const titles = computed(() => ({
  log: editing.value ? "编辑学习记录" : "记录一次进步",
  plan: editing.value ? "调整学习计划" : "安排一件小事",
  review: editing.value ? "编辑复习卡片" : "留给未来的自己",
  profile: "我的备考目标",
  subject: "添加学习科目",
}));
const isEssay = computed(
  () =>
    props.subjects.find((subject) => subject.id === form.subject_id)?.kind ===
    "essay",
);
const planId =
  props.log?.plan_id ??
  props.timer?.plan_id ??
  (props.mode === "log" ? props.plan?.id : null) ??
  null;

async function save() {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const common = {
      title: form.title,
      subject_id: form.subject_id,
      note: form.note,
    };
    if (props.mode === "log") {
      await request(
        `/logs${props.log ? `/${props.log.id}` : ""}`,
        props.log ? "PUT" : "POST",
        {
          ...common,
          id: recordId,
          study_date: form.date,
          duration_minutes: Number(form.minutes),
          question_count: isEssay.value ? 0 : Number(form.question_count),
          correct_count: isEssay.value ? 0 : Number(form.correct_count),
          plan_id: planId,
          add_to_review: !props.log && form.add_to_review,
        },
      );
    } else if (props.mode === "plan") {
      await request(
        `/plans${props.plan ? `/${props.plan.id}` : ""}`,
        props.plan ? "PUT" : "POST",
        {
          ...common,
          scheduled_date: form.date,
          minutes: Number(form.minutes),
        },
      );
    } else if (props.mode === "review") {
      await request(
        `/reviews${props.review ? `/${props.review.id}` : ""}`,
        props.review ? "PUT" : "POST",
        {
          ...common,
          due_date: form.date,
          source: form.source,
        },
      );
    } else if (props.mode === "profile") {
      await request("/profile", "PUT", {
        name: form.name,
        exam_name: form.exam_name,
        exam_date: form.exam_date || null,
        daily_goal_minutes: Number(form.daily_goal_minutes),
      });
    } else {
      await request("/subjects", "POST", { name: form.name, kind: form.kind });
    }
    emit(
      "saved",
      props.mode === "log"
        ? "已记下这份努力，打卡与统计已更新"
        : props.mode === "review"
          ? "复习卡片已保存，到期会出现在复习列表"
          : "已保存，继续稳稳向前",
    );
  } catch (err) {
    error.value = (err as Error).message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <BaseModal
    :title="titles[mode]"
    eyebrow="ONE STEP AT A TIME"
    :busy="busy"
    @close="emit('close')"
  >
    <form class="editor-form" @submit.prevent="save">
      <template v-if="mode === 'profile'">
        <label
          >怎么称呼你<input
            v-model="form.name"
            required
            maxlength="40"
            placeholder="给自己起个名字"
            data-autofocus
        /></label>
        <label
          >备考目标<input
            v-model="form.exam_name"
            required
            maxlength="100"
            placeholder="例如：2027 年省考"
        /></label>
        <div class="form-columns">
          <label>考试日期<input v-model="form.exam_date" type="date" /></label
          ><label
            >每日学习目标 · 分钟<input
              v-model="form.daily_goal_minutes"
              type="number"
              required
              min="5"
              max="1440"
          /></label>
        </div>
        <p class="form-tip">
          考试日期由你填写，随时可以调整。记录一次学习，即点亮一天打卡。
        </p>
      </template>
      <template v-else-if="mode === 'subject'">
        <label
          >科目名称<input
            v-model="form.name"
            required
            maxlength="40"
            placeholder="例如：面试训练"
            data-autofocus
        /></label>
        <label
          >记录方式<select v-model="form.kind">
            <option value="practice">客观题练习 · 题量与正确率</option>
            <option value="essay">主观题学习 · 作答与反馈</option>
          </select></label
        >
      </template>
      <template v-else>
        <label
          >{{ mode === "review" ? "知识点 / 想要记住的问题" : "学习内容"
          }}<input
            v-model="form.title"
            required
            maxlength="150"
            :placeholder="
              mode === 'review'
                ? '例如：如何快速判断比重上升或下降？'
                : '例如：资料分析 · 比重变化专项练习'
            "
            data-autofocus
        /></label>
        <div class="form-columns">
          <label
            >学习科目<select
              v-model="form.subject_id"
              required
              :disabled="mode === 'log' && !!planId"
            >
              <option
                v-for="subject in subjects"
                :key="subject.id"
                :value="subject.id"
              >
                {{ subject.name }}
              </option>
            </select></label
          >
          <label
            >{{
              mode === "plan"
                ? "计划日期"
                : mode === "review"
                  ? "首次 / 下次复习日期"
                  : "学习日期"
            }}<input
              v-model="form.date"
              type="date"
              required
              :max="mode === 'log' ? today : undefined"
          /></label>
        </div>
        <label v-if="mode !== 'review'"
          >{{ mode === "plan" ? "预计用时" : "实际学习时长" }} · 分钟
          <div class="duration-input">
            <input
              v-model="form.minutes"
              type="number"
              required
              min="1"
              max="1440"
            />
            <div class="duration-presets">
              <button
                v-for="minutes in [15, 30, 60, 90]"
                :key="minutes"
                type="button"
                :class="{ selected: Number(form.minutes) === minutes }"
                @click="form.minutes = minutes"
              >
                {{ minutes }} 分
              </button>
            </div>
          </div>
        </label>
        <div v-if="mode === 'log' && !isEssay" class="form-columns">
          <label
            >练习题量<input
              v-model="form.question_count"
              type="number"
              min="0"
              max="5000"
              required
          /></label>
          <label
            >正确题数<input
              v-model="form.correct_count"
              type="number"
              min="0"
              :max="form.question_count"
              required
          /></label>
        </div>
        <label
          >{{
            mode === "review"
              ? "解题方法 / 笔记 / 参考答案"
              : isEssay && mode === "log"
                ? "作答摘要 / 批改意见 / 重写心得"
                : "学习心得与备注"
          }}<textarea
            v-model="form.note"
            :rows="mode === 'review' ? 5 : 3"
            :maxlength="mode === 'plan' ? 2000 : 5000"
            :placeholder="
              mode === 'review'
                ? '记录思路、易错点，复习时先回忆再查看…'
                : '今天有什么收获？哪一步还需要再练一遍？（选填）'
            "
          />
        </label>
        <label v-if="mode === 'review'"
          >内容来源<input
            v-model="form.source"
            maxlength="500"
            placeholder="例如：教材第 36 页 / 某套真题第 12 题（选填）"
        /></label>
        <label v-if="mode === 'log' && !log" class="checkbox-field"
          ><input v-model="form.add_to_review" type="checkbox" /><span
            >同时加入复习列表<small>保存记录后，自动安排一次巩固</small></span
          ></label
        >
        <p v-if="mode === 'log' && timer" class="form-tip">
          已填入计时时长，可核对并调整。取消后，计时仍会保留。
        </p>
      </template>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="modal-actions">
        <button
          type="button"
          class="button secondary"
          :disabled="busy"
          @click="emit('close')"
        >
          再想想</button
        ><button class="button primary" :disabled="busy">
          <LoaderCircle v-if="busy" :size="17" class="spin" /><Check
            v-else-if="editing"
            :size="17"
          />{{ busy ? "保存中…" : mode === "log" ? "保存学习记录" : "保存"
          }}<ArrowRight v-if="!busy && !editing" :size="16" />
        </button>
      </div>
    </form>
  </BaseModal>
</template>
