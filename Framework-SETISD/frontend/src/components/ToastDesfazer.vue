<template>
  <div class="flex items-center gap-4">
    <span>{{ mensagem }}</span>
    <button
      type="button"
      @click.stop="emit('desfazer')"
      class="shrink-0 rounded px-2 py-1 text-sm font-extrabold text-ok-bg underline underline-offset-2 hover:bg-white/10"
    >
      Desfazer
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ mensagem: string }>();
const emit = defineEmits<{ (e: 'desfazer'): void }>();
</script>
