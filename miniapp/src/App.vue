<script setup lang="ts">
import { onHide, onLaunch, onShow } from "@dcloudio/uni-app";
import { persistFocus, tickFocus } from "./focus";
import { restoreSession, session } from "./session";
import { refreshWorkspace } from "./workspace";

let syncInterval: ReturnType<typeof setInterval> | undefined;
let tickInterval: ReturnType<typeof setInterval> | undefined;

function stopIntervals() {
  clearInterval(syncInterval);
  clearInterval(tickInterval);
}

onLaunch(() => restoreSession());
onShow(() => {
  stopIntervals();
  tickFocus();
  if (session.value) void refreshWorkspace();
  syncInterval = setInterval(() => {
    if (session.value) void refreshWorkspace();
  }, 30000);
  tickInterval = setInterval(tickFocus, 1000);
});
onHide(() => {
  persistFocus();
  stopIntervals();
});
</script>

<style>
@import "./style.css";
</style>
