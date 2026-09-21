<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { request } from "../../api";
import SubjectPicker from "../../components/SubjectPicker.vue";
import { clearFocus, focus, focusElapsed, pauseFocus } from "../../focus";
import { goLogin, session } from "../../session";
import { createId, errorText, toast } from "../../utils";
import {
  refreshWorkspace,
  studyDate,
  subjectFor,
  subjects,
  workspace,
} from "../../workspace";

type Kind = "log" | "plan" | "review" | "profile" | "subject";
const kind = ref<Kind>("log");
const editId = ref("");
const recordId = ref(createId());
const fromTimer = ref(false);
const ready = ref(false);
const busy = ref(false);
const saved = ref(false);
const error = ref("");
const planId = ref<string | null>(null);
const form = reactive({
  title: "",
  subject_id: "",
  date: "",
  minutes: "30",
  questions: "",
  correct: "",
  note: "",
  source: "",
  add_review: false,
  name: "",
  exam_name: "",
  exam_date: "",
  goal: "120",
  subject_kind: "practice" as "practice" | "essay",
});
const headings: Record<Kind, string> = {
  log: "记录这一次努力",
  plan: "给学习一个方向",
  review: "留下值得记住的知识",
  profile: "朝自己的目标前进",
  subject: "添加学习科目",
};
const heading = computed(() =>
  editId.value
    ? {
        log: "修改学习记录",
        plan: "调整学习计划",
        review: "编辑复习卡片",
        profile: "修改学习目标",
        subject: "添加学习科目",
      }[kind.value]
    : headings[kind.value],
);
const essay = computed(() => subjectFor(form.subject_id)?.kind === "essay");
const subjectKinds = ["客观题练习", "申论 / 主观题"];

onLoad(async (query) => {
  if (!session.value) {
    goLogin();
    return;
  }
  const requested = query?.kind || "log";
  if (!["log", "plan", "review", "profile", "subject"].includes(requested)) {
    error.value = "此编辑页面不存在，请返回重试";
    return;
  }
  kind.value = requested as Kind;
  editId.value = query?.id || "";
  fromTimer.value = kind.value === "log" && query?.timer === "1";
  try {
    if (!(await refreshWorkspace()) || !workspace.value)
      throw new Error("暂时无法读取学习数据，请返回后重新打开");
    form.date = studyDate.value;
    form.subject_id = subjects.value[0]?.id || "";
    if (kind.value === "profile") {
      const profile = workspace.value.overview.profile;
      form.name = profile.name;
      form.exam_name = profile.exam_name;
      form.exam_date = profile.exam_date || "";
      form.goal = String(profile.daily_goal_minutes);
    } else if (editId.value) {
      if (kind.value === "log") {
        const row = workspace.value.logs.find(
          (item) => item.id === editId.value,
        );
        if (!row) throw new Error("这条记录已不存在，请返回刷新");
        recordId.value = row.id;
        planId.value = row.plan_id;
        Object.assign(form, {
          title: row.title,
          subject_id: row.subject_id,
          date: row.study_date,
          minutes: String(row.duration_minutes),
          questions: String(row.question_count),
          correct: String(row.correct_count),
          note: row.note,
        });
      } else if (kind.value === "plan") {
        const row = workspace.value.plans.find(
          (item) => item.id === editId.value,
        );
        if (!row || row.completed)
          throw new Error("计划已完成或不存在，请到学习记录中查看实际学习情况");
        Object.assign(form, {
          title: row.title,
          subject_id: row.subject_id,
          date: row.scheduled_date,
          minutes: String(row.minutes),
          note: row.note,
        });
      } else if (kind.value === "review") {
        const row = workspace.value.reviews.find(
          (item) => item.id === editId.value,
        );
        if (!row) throw new Error("这张卡片已不存在，请返回刷新");
        Object.assign(form, {
          title: row.title,
          subject_id: row.subject_id,
          date: row.due_date,
          note: row.note,
          source: row.source,
        });
      }
    } else if (fromTimer.value) {
      if (!focus.value) throw new Error("未找到待保存的计时，请返回专注页面");
      if (workspace.value.logs.some((item) => item.id === focus.value?.id)) {
        clearFocus();
        throw new Error("这次计时已经保存，请到学习记录中查看");
      }
      pauseFocus();
      const timer = focus.value!;
      recordId.value = timer.id;
      planId.value = timer.plan_id;
      Object.assign(form, {
        title: timer.title,
        subject_id: timer.subject_id,
        date: timer.study_date,
        minutes: String(Math.max(1, Math.ceil(focusElapsed.value / 60))),
      });
    } else if (kind.value === "log" && query?.plan) {
      const plan = workspace.value.plans.find((item) => item.id === query.plan);
      if (!plan || plan.completed)
        throw new Error("计划已完成或不存在，请返回计划列表");
      planId.value = plan.id;
      Object.assign(form, {
        title: plan.title,
        subject_id: plan.subject_id,
        minutes: String(plan.minutes),
      });
    }
    ready.value = true;
    uni.setNavigationBarTitle({ title: heading.value });
  } catch (caught) {
    error.value = errorText(caught);
  }
});

function integer(
  value: string,
  label: string,
  minimum: number,
  maximum: number,
  empty = false,
) {
  if (!value && empty) return 0;
  if (
    !/^\d+$/.test(value) ||
    Number(value) < minimum ||
    Number(value) > maximum
  )
    throw new Error(`${label}需为 ${minimum}–${maximum} 的整数`);
  return Number(value);
}

function goBack() {
  if (getCurrentPages().length > 1) uni.navigateBack();
  else uni.switchTab({ url: "/pages/today/index" });
}

function changeReview(event: unknown) {
  form.add_review = Boolean(
    (event as { detail?: { value?: boolean } }).detail?.value,
  );
}

async function save() {
  if (!ready.value || busy.value || saved.value) return;
  error.value = "";
  busy.value = true;
  try {
    if (
      ["log", "plan", "review"].includes(kind.value) &&
      (!form.title.trim() || !subjectFor(form.subject_id))
    )
      throw new Error("请填写学习内容并选择有效科目");
    let path = "";
    let payload: Record<string, unknown>;
    if (kind.value === "profile") {
      if (!form.name.trim() || !form.exam_name.trim())
        throw new Error("请填写称呼和考试名称");
      path = "/profile";
      payload = {
        name: form.name.trim(),
        exam_name: form.exam_name.trim(),
        exam_date: form.exam_date || null,
        daily_goal_minutes: integer(form.goal, "每日目标", 5, 1440),
      };
    } else if (kind.value === "subject") {
      if (!form.name.trim()) throw new Error("请填写科目名称");
      path = "/subjects";
      payload = { name: form.name.trim(), kind: form.subject_kind };
    } else if (kind.value === "log") {
      if (form.date > studyDate.value) throw new Error("学习日期不能晚于今天");
      const questions = essay.value
        ? 0
        : integer(form.questions, "总题数", 0, 5000, true);
      const correct = essay.value
        ? 0
        : integer(form.correct, "正确数", 0, 5000, true);
      if (correct > questions) throw new Error("正确题数不能超过总题数");
      path = editId.value ? `/logs/${editId.value}` : "/logs";
      payload = {
        id: recordId.value,
        title: form.title.trim(),
        subject_id: form.subject_id,
        study_date: form.date,
        duration_minutes: integer(form.minutes, "学习时长", 1, 1440),
        question_count: questions,
        correct_count: correct,
        note: form.note,
        plan_id: planId.value,
        add_to_review: !editId.value && form.add_review,
      };
    } else if (kind.value === "plan") {
      path = editId.value ? `/plans/${editId.value}` : "/plans";
      payload = {
        title: form.title.trim(),
        subject_id: form.subject_id,
        scheduled_date: form.date,
        minutes: integer(form.minutes, "计划时长", 1, 1440),
        note: form.note,
      };
    } else {
      path = editId.value ? `/reviews/${editId.value}` : "/reviews";
      payload = {
        title: form.title.trim(),
        subject_id: form.subject_id,
        due_date: form.date,
        note: form.note,
        source: form.source,
      };
    }
    await request(
      path,
      editId.value || kind.value === "profile" ? "PUT" : "POST",
      payload,
    );
    saved.value = true;
    if (fromTimer.value && focus.value?.id === recordId.value) clearFocus();
    await refreshWorkspace();
    toast("已保存，每一步都算数");
    if (fromTimer.value) uni.switchTab({ url: "/pages/today/index" });
    else goBack();
  } catch (caught) {
    error.value = errorText(caught);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <view class="page">
    <text class="eyebrow">{{
      kind === "log" ? "真实记录，稳步向前" : "为下一步做好准备"
    }}</text
    ><text class="page-title">{{ heading }}</text>
    <view v-if="error" class="message error editor-message">{{ error }}</view>
    <view v-if="!ready && !error" class="message editor-message"
      >正在准备…</view
    >
    <view v-if="ready" class="card editor-card">
      <template v-if="kind === 'profile'">
        <view class="field"
          ><text class="field-label">怎么称呼你</text
          ><input
            v-model="form.name"
            class="input"
            maxlength="40"
            :disabled="busy"
        /></view>
        <view class="field"
          ><text class="field-label">考试 / 备考目标</text
          ><input
            v-model="form.exam_name"
            class="input"
            maxlength="100"
            placeholder="例如：2027 年公务员考试"
            :disabled="busy"
        /></view>
        <view class="field"
          ><text class="field-label">考试日期（选填）</text
          ><picker
            mode="date"
            :value="form.exam_date || studyDate"
            :disabled="busy"
            @change="form.exam_date = $event.detail.value"
            ><view class="picker"
              ><text>{{ form.exam_date || "暂未确定" }}</text
              ><text class="muted">⌄</text></view
            ></picker
          ><button
            v-if="form.exam_date"
            class="text-button"
            :disabled="busy"
            @click="form.exam_date = ''"
          >
            清除考试日期
          </button></view
        >
        <view class="field"
          ><text class="field-label">每日学习目标（分钟）</text
          ><input
            v-model="form.goal"
            class="input"
            type="number"
            maxlength="4"
            :disabled="busy"
        /></view>
      </template>
      <template v-else-if="kind === 'subject'">
        <view class="field"
          ><text class="field-label">科目名称</text
          ><input
            v-model="form.name"
            class="input"
            maxlength="40"
            placeholder="例如：面试表达"
            :disabled="busy"
        /></view>
        <view class="field"
          ><text class="field-label">记录方式</text
          ><picker
            :range="subjectKinds"
            :value="form.subject_kind === 'essay' ? 1 : 0"
            :disabled="busy"
            @change="
              form.subject_kind =
                Number($event.detail.value) === 1 ? 'essay' : 'practice'
            "
            ><view class="picker"
              ><text>{{
                form.subject_kind === "essay"
                  ? subjectKinds[1]
                  : subjectKinds[0]
              }}</text
              ><text class="muted">⌄</text></view
            ></picker
          ><text class="field-hint"
            >主观题以作答与反馈记录，不计入客观题正确率。</text
          ></view
        >
      </template>
      <template v-else>
        <view class="field"
          ><text class="field-label">{{
            kind === "review" ? "卡片标题 / 自测问题" : "学习内容"
          }}</text
          ><input
            v-model="form.title"
            class="input"
            maxlength="150"
            placeholder="这一次，专注解决什么？"
            :disabled="busy"
        /></view>
        <view class="field"
          ><text class="field-label">学习科目</text
          ><SubjectPicker
            v-model="form.subject_id"
            :subjects="subjects"
            :disabled="busy || !!planId"
        /></view>
        <view class="field"
          ><text class="field-label">{{
            kind === "log"
              ? "学习日期"
              : kind === "plan"
                ? "计划日期"
                : "下次复习日期"
          }}</text
          ><picker
            mode="date"
            :value="form.date"
            :end="kind === 'log' ? studyDate : undefined"
            :disabled="busy"
            @change="form.date = $event.detail.value"
            ><view class="picker"
              ><text>{{ form.date }}</text
              ><text class="muted">⌄</text></view
            ></picker
          ></view
        >
        <view v-if="kind !== 'review'" class="field"
          ><text class="field-label">{{
            kind === "log" ? "实际学习时长（分钟）" : "计划时长（分钟）"
          }}</text
          ><input
            v-model="form.minutes"
            class="input"
            type="number"
            maxlength="4"
            :disabled="busy"
          /><text v-if="fromTimer" class="field-hint"
            >计时已暂停，按分钟向上取整；请按实际学习情况核对。跨午夜的计时默认归入开始日期。</text
          ><text v-else-if="kind === 'log' && planId && !editId" class="field-hint"
            >已填入计划时长，请核对实际用时。保存后会完成关联计划。</text
          ></view
        >
        <view v-if="kind === 'log' && !essay" class="form-row"
          ><view class="field"
            ><text class="field-label">总题数（选填）</text
            ><input
              v-model="form.questions"
              class="input"
              type="number"
              maxlength="4"
              placeholder="0"
              :disabled="busy" /></view
          ><view class="field"
            ><text class="field-label">正确数（选填）</text
            ><input
              v-model="form.correct"
              class="input"
              type="number"
              maxlength="4"
              placeholder="0"
              :disabled="busy" /></view
        ></view>
        <view class="field"
          ><text class="field-label">{{
            kind === "review"
              ? "答案与笔记"
              : essay
                ? "作答与反馈"
                : "心得与备注（选填）"
          }}</text
          ><textarea
            v-model="form.note"
            class="textarea"
            :maxlength="kind === 'plan' ? 2000 : 5000"
            :placeholder="
              kind === 'review'
                ? '复习时先回忆，再揭示这里的内容。'
                : '记下收获，也记下还没想明白的地方。'
            "
            :disabled="busy"
          />
        </view>
        <view v-if="kind === 'review'" class="field"
          ><text class="field-label">来源（选填）</text
          ><input
            v-model="form.source"
            class="input"
            maxlength="500"
            placeholder="教材章节、题目编号等"
            :disabled="busy"
        /></view>
        <view v-if="kind === 'log' && !editId" class="check-row"
          ><view class="grow"
            ><text>同时加入复习</text
            ><text class="field-hint"
              >将本次内容与笔记生成复习卡片。</text
            ></view
          ><switch
            :checked="form.add_review"
            color="#708a5d"
            :disabled="busy"
            @change="changeReview"
        /></view>
      </template>
    </view>
    <view v-if="ready" class="safe-actions"
      ><button
        class="button"
        :loading="busy"
        :disabled="busy || saved"
        @click="save"
      >
        {{ saved ? "已保存" : "保存" }}
      </button></view
    >
    <button
      v-if="error && !ready"
      class="button secondary safe-actions"
      @click="goBack"
    >
      返回
    </button>
  </view>
</template>

<style scoped>
.editor-card,
.editor-message {
  margin-top: 28rpx;
}
</style>
