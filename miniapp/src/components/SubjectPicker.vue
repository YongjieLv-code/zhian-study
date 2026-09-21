<script setup lang="ts">
import { computed } from "vue";
import type { Subject } from "../types";
const props = defineProps<{
  modelValue: string;
  subjects: Subject[];
  disabled?: boolean;
}>();
const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();
const index = computed(() =>
  Math.max(
    0,
    props.subjects.findIndex((item) => item.id === props.modelValue),
  ),
);
const selected = computed(() =>
  props.subjects.find((item) => item.id === props.modelValue),
);
function change(event: { detail: { value: string | number } }) {
  const value = props.subjects[Number(event.detail.value)];
  if (value) emit("update:modelValue", value.id);
}
</script>
<template>
  <picker
    :range="subjects"
    range-key="name"
    :value="index"
    :disabled="disabled"
    @change="change"
  >
    <view class="picker"
      ><view class="row"
        ><text class="dot" :style="{ background: selected?.color }" /><text>{{
          selected?.name || "选择学习科目"
        }}</text></view
      ><text class="muted">⌄</text></view
    >
  </picker>
</template>
