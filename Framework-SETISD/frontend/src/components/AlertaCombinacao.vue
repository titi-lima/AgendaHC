<template>
  <span
    :class="classes"
    class="inline-flex items-center gap-1 rounded px-1.5 py-px text-xs font-bold whitespace-nowrap"
    :title="alerta.orientacao"
  >
    <component :is="icone" class="h-3.5 w-3.5" aria-hidden="true" />
    {{ ROTULO_COMBINACAO[alerta.tipo] }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { ExclamationTriangleIcon, ArrowLongRightIcon, LinkIcon, DocumentDuplicateIcon } from '@heroicons/vue/20/solid';
import { ROTULO_COMBINACAO, type Alerta } from '../lib/agenda';

const props = defineProps<{ alerta: Alerta }>();

const classes = computed(() => ({
  SEPARAR: 'bg-separar-bg text-separar-ink',
  ORDEM: 'bg-ordem-bg text-ordem-ink',
  AGRUPAR: 'bg-agrupar-bg text-agrupar-ink',
  DUPLICIDADE: 'bg-surface text-ink ring-1 ring-inset ring-line-strong',
}[props.alerta.tipo]));

const icone = computed(() => ({
  SEPARAR: ExclamationTriangleIcon,
  ORDEM: ArrowLongRightIcon,
  AGRUPAR: LinkIcon,
  DUPLICIDADE: DocumentDuplicateIcon,
}[props.alerta.tipo]));
</script>
