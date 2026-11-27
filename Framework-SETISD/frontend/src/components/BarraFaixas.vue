<template>
  <div
    class="flex w-full gap-px overflow-hidden rounded-sm bg-surface"
    :class="alto ? 'h-4' : 'h-2.5'"
    role="img"
    :aria-label="descricao"
  >
    <span
      v-for="(f, i) in FAIXAS"
      :key="f.rotulo"
      v-show="faixas[i] > 0"
      :style="{ width: `${largura(i)}%`, background: f.cor }"
      :title="`${f.rotulo}: ${faixas[i]}`"
      class="h-full first:rounded-l-sm last:rounded-r-sm"
    ></span>
  </div>
</template>

<script lang="ts">
export const FAIXAS = [
  { rotulo: 'até 30 dias', cor: '#9fbfc0' },
  { rotulo: '31 a 60 dias', cor: '#5f8f90' },
  { rotulo: '61 a 90 dias', cor: '#d98a2b' },
  { rotulo: 'mais de 90 dias', cor: '#7a5100' },
];
</script>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ faixas: number[]; alto?: boolean }>();

const total = computed(() => props.faixas.reduce((s, n) => s + n, 0));

function largura(i: number) {
  return total.value ? (props.faixas[i] / total.value) * 100 : 0;
}

const descricao = computed(() => FAIXAS.map((f, i) => `${f.rotulo}: ${props.faixas[i]}`).join(', '));
</script>
