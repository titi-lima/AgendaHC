<template>
  <span
    :class="motivo.tipo === 'CHEGADA' ? 'gap-1 font-semibold text-ink-muted' : ['gap-1.5 rounded-full px-2.5 py-0.5 font-bold', classes]"
    class="inline-flex items-center text-xs whitespace-nowrap"
    :title="motivo.detalhe"
  >
    <component :is="icone" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
    {{ motivo.rotulo }}
    <span class="sr-only">({{ motivo.detalhe }})</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { ListBulletIcon, ClockIcon, ArrowDownTrayIcon, CheckCircleIcon } from '@heroicons/vue/20/solid';
import type { Motivo } from '../lib/agenda';

const props = defineProps<{ motivo: Motivo }>();

const classes = computed(() => ({
  LISTA: 'bg-lista-bg text-lista-ink',
  ESPERA: 'bg-espera-bg text-espera-ink',
  CHEGADA: '',
  FINAL: 'bg-ok-bg text-ok-ink',
}[props.motivo.tipo]));

const icone = computed(() => ({
  LISTA: ListBulletIcon,
  ESPERA: ClockIcon,
  CHEGADA: ArrowDownTrayIcon,
  FINAL: CheckCircleIcon,
}[props.motivo.tipo]));
</script>
