<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId } from "vue";
import { X } from "lucide-vue-next";

const props = defineProps<{
  title: string;
  eyebrow?: string;
  wide?: boolean;
  busy?: boolean;
}>();
const emit = defineEmits<{ close: [] }>();
const panel = ref<HTMLElement>();
const titleId = useId();
let previous: HTMLElement | null = null;
let oldOverflow = "";

function keydown(event: KeyboardEvent) {
  if (event.key === "Escape" && !props.busy) {
    event.preventDefault();
    emit("close");
  }
  if (event.key !== "Tab") return;
  const items = Array.from(
    panel.value?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]',
    ) ?? [],
  ).filter((item) => item.getClientRects().length > 0);
  const first = items[0],
    last = items[items.length - 1];
  if (!first) {
    event.preventDefault();
    return;
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

onMounted(async () => {
  previous = document.activeElement as HTMLElement;
  oldOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  const root = document.getElementById("app");
  if (root) root.inert = true;
  document.addEventListener("keydown", keydown);
  await nextTick();
  const initialFocus =
    panel.value?.querySelector<HTMLElement>("[data-autofocus]") ??
    panel.value?.querySelector<HTMLElement>("input, textarea") ??
    panel.value?.querySelector<HTMLElement>("button");
  initialFocus?.focus();
});
onBeforeUnmount(() => {
  document.body.style.overflow = oldOverflow;
  const root = document.getElementById("app");
  if (root) root.inert = false;
  document.removeEventListener("keydown", keydown);
  previous?.focus();
});
</script>

<template>
  <Teleport to="body">
    <div class="modal-backdrop" @click.self="!busy && emit('close')">
      <section
        ref="panel"
        class="modal-panel"
        :class="{ wide }"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
      >
        <div class="modal-header">
          <div>
            <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
            <h2 :id="titleId">{{ title }}</h2>
          </div>
          <button
            class="icon-button"
            :disabled="busy"
            aria-label="关闭弹窗"
            @click="emit('close')"
          >
            <X :size="20" />
          </button>
        </div>
        <slot />
      </section>
    </div>
  </Teleport>
</template>
