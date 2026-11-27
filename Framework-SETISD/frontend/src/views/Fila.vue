<template>
  <div class="flex h-full min-h-0">
    <nav v-if="!compacto" class="hidden lg:block w-60 shrink-0 border-r border-line bg-paper-bg overflow-y-auto py-4" aria-label="Unidades">
      <p class="flex items-baseline justify-between px-4 pb-2 text-xs font-bold text-ink-muted">
        <span>Unidades</span>
        <span class="font-semibold">exames</span>
      </p>
      <ul class="space-y-px px-2">
        <li v-for="u in opcoesUnidade" :key="u.valor ?? 'todas'">
          <button
            type="button"
            @click="trocarUnidade(u.valor)"
            :aria-current="unidade === u.valor ? 'true' : undefined"
            :class="unidade === u.valor ? 'bg-surface text-ink shadow-[0_1px_2px_rgba(43,41,37,0.08)] ring-1 ring-line' : 'text-ink-muted hover:bg-surface/70 hover:text-ink'"
            class="w-full flex items-baseline justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors"
          >
            <span class="font-semibold leading-snug">{{ u.rotulo }}</span>
            <span class="tabular text-xs text-ink-muted shrink-0">{{ u.exames }}</span>
          </button>
        </li>
      </ul>
      <p class="px-4 pt-4 text-xs leading-relaxed text-ink-muted">
        A fila agrupa os exames de cada paciente e mostra o motivo de cada posição.
      </p>
    </nav>

    <section id="conteudo-fila" class="flex-1 min-w-0 flex flex-col">
      <div class="px-6 pt-4 pb-3 border-b border-line bg-paper-bg space-y-3">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
          <label class="relative flex-1 min-w-[14rem] max-w-md">
            <span class="sr-only">Buscar paciente por nome ou prontuário</span>
            <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-muted" aria-hidden="true" />
            <input
              ref="campoBusca"
              v-model="busca"
              type="search"
              placeholder="Buscar por nome ou prontuário"
              aria-keyshortcuts="/"
              class="w-full rounded-md border border-campo bg-surface pl-9 pr-9 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-acao focus:outline-none focus:ring-2 focus:ring-acao/25"
            />
            <kbd class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-line-strong px-1.5 text-xs text-ink-muted" aria-hidden="true">/</kbd>
          </label>
          <select
            v-model="unidadeSelect"
            :class="compacto ? '' : 'lg:hidden'"
            class="rounded-md border border-campo bg-surface px-3 py-2 text-sm text-ink"
            aria-label="Unidade"
          >
            <option v-for="u in opcoesUnidade" :key="u.valor ?? 'todas'" :value="u.valor ?? ''">{{ u.rotulo }} ({{ u.exames }})</option>
          </select>
          <p v-if="busca.trim() && dados" class="text-xs font-semibold text-ink-muted" aria-live="polite">
            {{ gruposFiltrados.length }} {{ gruposFiltrados.length === 1 ? 'paciente encontrado' : 'pacientes encontrados' }}
          </p>
          <div class="ml-auto flex min-w-0 items-center gap-2 text-xs text-ink-muted">
            <span v-if="dados" class="truncate" :title="`${dados.fonte} · lido ${horaLeitura}`">
              <template v-if="!compacto">{{ dados.fonte }} · </template>lido {{ horaLeitura }}
            </span>
            <button
              type="button"
              @click="carregar()"
              :disabled="carregando"
              class="inline-flex items-center gap-1 rounded-md px-2 py-1 font-semibold text-acao hover:bg-acao-suave disabled:opacity-50"
            >
              <ArrowPathIcon :class="{ 'animate-spin': carregando }" class="h-4 w-4" aria-hidden="true" />
              Atualizar
            </button>
          </div>
        </div>

        <dl
          v-if="dados"
          :class="compacto ? 'flex flex-nowrap gap-x-4 overflow-hidden whitespace-nowrap text-xs' : 'grid grid-cols-2 xl:flex xl:flex-wrap gap-x-8 gap-y-1 text-sm'"
          class="items-baseline"
        >
          <div class="flex items-baseline gap-1.5">
            <dd :class="compacto ? 'text-sm' : 'text-xl'" class="tabular font-extrabold text-ink">{{ dados.resumo.pacientes }}</dd>
            <dt class="text-ink-muted">pacientes<template v-if="!compacto"> · {{ dados.resumo.exames }} exames</template></dt>
          </div>
          <div class="flex items-baseline gap-1.5">
            <dd :class="compacto ? 'text-sm' : 'text-xl'" class="tabular font-extrabold text-lista-ink">{{ dados.resumo.prioritarios }}</dd>
            <dt class="text-ink-muted">{{ compacto ? 'na lista' : 'na lista de prioridade' }}</dt>
          </div>
          <div class="flex items-baseline gap-1.5">
            <dd :class="compacto ? 'text-sm' : 'text-xl'" class="tabular font-extrabold text-ink">{{ dados.resumo.com_alerta }}</dd>
            <dt class="text-ink-muted">{{ compacto ? 'com alerta' : 'com alerta de combinação' }}</dt>
          </div>
          <div class="flex items-baseline gap-1.5">
            <dd :class="[compacto ? 'text-sm' : 'text-xl', dados.resumo.espera_mediana > dados.regra.espera_limite_dias ? 'text-espera-ink' : 'text-ink']" class="tabular font-extrabold">{{ dados.resumo.espera_mediana }}</dd>
            <dt class="text-ink-muted">dias de espera mediana<template v-if="!compacto"> · máx. {{ dados.resumo.espera_maxima }}</template></dt>
          </div>
        </dl>

        <div v-if="dados" :class="compacto ? 'flex-nowrap overflow-hidden whitespace-nowrap' : 'flex-wrap'" class="flex items-center gap-x-2 gap-y-1.5 text-xs text-ink-muted">
          <span class="font-bold text-ink">Ordenação</span>
          <template v-for="(c, i) in dados.regra.criterios" :key="c">
            <ChevronRightIcon v-if="i > 0" class="h-3.5 w-3.5" aria-hidden="true" />
            <span :class="CORES_CRITERIO[c]" class="rounded px-1.5 py-px font-bold">
              {{ c === 'ESPERA_LIMITE' ? `Espera > ${dados.regra.espera_limite_dias} dias` : ROTULO_CRITERIO[c] }}
            </span>
          </template>
          <span v-if="!compacto" class="whitespace-nowrap">· regra {{ nomeUnidade(dados.regra.unidade) }} v{{ dados.regra.versao }}<template v-if="dados.regra.exemplo"> (exemplo)</template></span>
          <router-link to="/regras" class="whitespace-nowrap font-semibold text-acao underline underline-offset-2 hover:text-acao-hover">Editar regra</router-link>
        </div>
      </div>

      <div class="relative flex-1 min-h-0 overflow-y-auto" ref="areaTabela">
        <div v-if="erro && dados" class="flex items-center gap-3 border-b border-line bg-separar-bg px-6 py-2 text-sm text-separar-ink" role="alert">
          <span class="font-bold">Não foi possível atualizar.</span>
          <span>Mostrando a última leitura. {{ erro }}</span>
          <button type="button" @click="carregar()" class="ml-auto font-bold underline underline-offset-2">Tentar de novo</button>
        </div>

        <div v-if="erro && !dados" class="m-6 rounded-md border border-separar-bg bg-surface p-4 text-sm" role="alert">
          <p class="font-bold text-separar-ink">Não foi possível carregar a fila.</p>
          <p class="text-ink-muted mt-1">{{ erro }}</p>
          <button type="button" @click="carregar()" class="mt-3 rounded-md bg-acao px-3 py-1.5 text-sm font-bold text-white hover:bg-acao-hover">Tentar de novo</button>
        </div>

        <table v-else class="w-full table-fixed text-sm" aria-describedby="ajuda-teclado">
          <thead ref="cabecalho" class="sticky top-0 z-10 bg-paper-bg/95 backdrop-blur-sm text-left text-xs font-bold text-ink-muted">
            <tr class="border-b border-line">
              <th scope="col" class="w-[4.75rem] pl-6 pr-1 py-2">Posição</th>
              <th scope="col" :class="compacto ? 'w-[12rem]' : 'w-[16rem]'" class="px-2 py-2">Paciente</th>
              <th scope="col" class="px-2 py-2">Exames pendentes</th>
              <th scope="col" class="w-[4.5rem] px-2 py-2 text-right">Espera</th>
              <th scope="col" :class="compacto ? 'w-[10.5rem] pr-6' : 'w-[11.5rem]'" class="px-2 py-2">Motivo da posição</th>
              <th v-if="!compacto" scope="col" class="w-[9.5rem] pl-2 pr-6 py-2">Combinação</th>
            </tr>
          </thead>
          <tbody v-if="carregando && !dados">
            <tr v-for="n in 10" :key="n" class="border-b border-line">
              <td :colspan="compacto ? 5 : 6" class="px-6 py-3">
                <div class="h-4 rounded bg-line/70 animate-pulse" :style="{ width: `${50 + (n * 37) % 45}%` }"></div>
              </td>
            </tr>
          </tbody>
          <TransitionGroup v-else tag="tbody" name="fila" :class="{ 'opacity-60 transition-opacity': trocandoUnidade }">
            <tr
              v-for="(g, idx) in gruposVisiveis"
              :key="g.chave"
              :data-chave="g.chave"
              :ref="(el) => registrarLinha(el, idx)"
              :tabindex="idx === indiceFoco ? 0 : -1"
              :aria-current="selecionado?.chave === g.chave ? 'true' : undefined"
              :aria-expanded="selecionado?.chave === g.chave"
              aria-controls="detalhe-paciente"
              :aria-label="`${g.posicao}º, ${g.nome}, ${g.motivo.rotulo}`"
              @focus="indiceFoco = idx"
              @click="selecionar(g, idx)"
              @keydown="teclaNaLinha($event, g, idx)"
              :class="selecionado?.chave === g.chave
                ? 'bg-acao-suave shadow-[inset_0_0_0_1px_var(--color-acao)]'
                : movidos[g.chave] ? 'bg-lista-bg/50 hover:bg-lista-bg/70' : 'bg-surface hover:bg-surface-sunken'"
              class="border-b border-line align-top cursor-pointer focus-visible:outline-2 focus-visible:outline-ink focus-visible:-outline-offset-2"
            >
              <td class="pl-6 pr-1 py-2.5">
                <div class="flex flex-wrap items-center gap-1">
                  <span class="tabular text-base font-extrabold text-ink">{{ g.posicao }}</span>
                  <span
                    v-if="movidos[g.chave]"
                    class="inline-flex items-center gap-0.5 rounded bg-lista-ink px-1 text-xs font-bold text-white"
                    :title="`Subiu ${movidos[g.chave]} posições`"
                  >
                    <ArrowUpIcon class="h-3 w-3" aria-hidden="true" />{{ movidos[g.chave] }}
                    <span class="sr-only">posições acima</span>
                  </span>
                </div>
              </td>
              <td class="px-2 py-2.5">
                <p class="font-bold text-ink leading-snug break-words">{{ g.nome }}</p>
                <p class="tabular text-xs text-ink-muted">
                  <template v-if="g.sem_prontuario">Sem prontuário no extrato</template>
                  <template v-else>Pront. {{ g.prontuario }}</template>
                </p>
              </td>
              <td class="px-2 py-2.5">
                <ul class="space-y-1.5">
                  <li
                    v-for="i in g.itens"
                    :key="i.codigo_solicitacao + i.codigo_exame"
                    class="min-w-0"
                    :class="i.na_unidade ? 'text-ink' : 'text-ink-muted'"
                  >
                    <p class="leading-snug" :class="i.na_unidade ? 'font-semibold' : ''">{{ exameCurto(i.nome_exame) }}</p>
                    <p class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-ink-muted">
                      <span class="tabular">{{ dataCurta(i.data_solicitacao) }}</span>
                      <span v-if="(i.quantidade ?? 1) > 1" class="tabular">× {{ i.quantidade }}</span>
                      <span v-if="!i.na_unidade">{{ nomeUnidade(i.unidade) }}</span>
                      <StatusTag :status="i.status" :quando="i.status_info?.criado_em" :quem="i.status_info?.usuario" />
                    </p>
                  </li>
                </ul>
              </td>
              <td class="px-2 py-2.5 text-right">
                <span class="tabular font-bold" :class="g.espera_dias > (dados?.regra.espera_limite_dias ?? 60) ? 'text-espera-ink' : 'text-ink'">{{ g.espera_dias }}</span>
                <span class="text-xs text-ink-muted"> dias</span>
              </td>
              <td class="px-2 py-2.5" :class="compacto ? 'pr-6' : ''">
                <div class="flex flex-col items-start gap-1">
                  <MotivoChip :motivo="g.motivo" />
                  <template v-if="compacto">
                    <AlertaCombinacao v-for="a in g.alertas" :key="a.exames.join()" :alerta="a" />
                  </template>
                </div>
              </td>
              <td v-if="!compacto" class="pl-2 pr-6 py-2.5">
                <div class="flex flex-col items-start gap-1">
                  <AlertaCombinacao v-for="a in g.alertas" :key="a.exames.join()" :alerta="a" />
                </div>
              </td>
            </tr>
          </TransitionGroup>
        </table>

        <div v-if="dados && !gruposFiltrados.length && busca.trim()" class="px-6 py-12 text-center">
          <p class="font-bold text-ink">Nenhum paciente encontrado para “{{ busca }}”{{ unidade ? ` em ${nomeUnidade(unidade)}` : '' }}.</p>
          <p class="mt-1 text-sm text-ink-muted">Busque pelo nome como aparece no AGHU ou pelo número do prontuário.</p>
          <div class="mt-3 flex justify-center gap-4 text-sm font-semibold">
            <button v-if="unidade" type="button" @click="trocarUnidade(null)" class="text-acao underline underline-offset-2">Buscar em todas as unidades</button>
            <button type="button" @click="busca = ''" class="text-acao underline underline-offset-2">Limpar busca</button>
          </div>
        </div>
        <div v-else-if="dados && !gruposFiltrados.length" class="px-6 py-12 text-center">
          <p class="font-bold text-ink">Fila vazia {{ unidade ? `em ${nomeUnidade(unidade)}` : 'em todas as unidades' }}.</p>
          <p class="mt-1 text-sm text-ink-muted">Todas as solicitações lidas do AGHU já têm resultado registrado. Novas solicitações entram na próxima leitura.</p>
        </div>

        <div v-if="gruposFiltrados.length > limite" class="px-6 py-4 flex items-center gap-3 text-sm text-ink-muted">
          <span>Mostrando {{ limite }} de {{ gruposFiltrados.length }} pacientes</span>
          <button type="button" @click="limite += 60" class="rounded-md border border-campo bg-surface px-3 py-1.5 font-semibold text-ink hover:bg-surface-sunken">Mostrar mais 60</button>
        </div>

        <p id="ajuda-teclado" class="px-6 py-4 text-xs text-ink-muted">
          Teclado: ↑ ↓ para percorrer, Enter abre o paciente, R registra o resultado do primeiro exame, Esc fecha, Home e End vão ao início e ao fim, / busca.
        </p>
      </div>
    </section>

    <Transition name="painel">
      <aside
        v-if="selecionado"
        id="detalhe-paciente"
        class="w-[22rem] 2xl:w-[25rem] shrink-0 border-l border-line bg-surface overflow-y-auto"
        aria-label="Detalhe do paciente"
        @keydown.esc="fecharDetalhe"
      >
        <DetalhePaciente
          :key="`${selecionado.chave}:${versaoDetalhe}`"
          :chave="selecionado.chave"
          :posicao="selecionado.posicao"
          :motivo="selecionado.motivo"
          :unidade="unidade"
          @fechar="fecharDetalhe"
          @alterado="aoAlterar"
        />
      </aside>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { MagnifyingGlassIcon, ArrowPathIcon, ArrowUpIcon, ChevronRightIcon } from '@heroicons/vue/20/solid';
import api from '../services/api';
import MotivoChip from '../components/MotivoChip.vue';
import StatusTag from '../components/StatusTag.vue';
import AlertaCombinacao from '../components/AlertaCombinacao.vue';
import DetalhePaciente from '../components/DetalhePaciente.vue';
import ToastDesfazer from '../components/ToastDesfazer.vue';
import { ROTULO_CRITERIO, dataCurta, exameCurto, nomeUnidade, type GrupoFila, type Regra, type Motivo } from '../lib/agenda';

interface RespostaFila {
  fonte: string;
  gerado_em: string;
  unidade: string | null;
  regra: Regra;
  resumo: { pacientes: number; exames: number; prioritarios: number; com_alerta: number; espera_mediana: number; espera_maxima: number };
  unidades: { unidade: string; exames: number; pacientes: number }[];
  total_exames: number;
  grupos: GrupoFila[];
}

interface EventoAlteracao {
  tipo: 'prioridade' | 'tratamento';
  mensagem: string;
  desfazerPrioridadeId?: number;
  desfazerTratamento?: { codigo_solicitacao: string; codigo_exame: string; rotulo: string };
}

const CORES_CRITERIO: Record<string, string> = {
  LISTA_PRIORIDADE: 'bg-lista-bg text-lista-ink',
  ESPERA_LIMITE: 'bg-espera-bg text-espera-ink',
  ORDEM_CHEGADA: 'bg-chegada-bg text-chegada-ink',
};

const route = useRoute();
const router = useRouter();
const versaoDetalhe = ref(0);
const toast = useToast();
const dados = ref<RespostaFila | null>(null);
const carregando = ref(false);
const trocandoUnidade = ref(false);
const erro = ref('');
const unidade = ref<string | null>(typeof route.query.unidade === 'string' ? route.query.unidade : null);
const busca = ref('');
const limite = ref(60);
const selecionado = ref<{ chave: string; posicao: number; motivo: Motivo } | null>(null);
const movidos = ref<Record<string, number>>({});
const linhas: (HTMLElement | null)[] = [];
const indiceFoco = ref(0);
const areaTabela = ref<HTMLElement | null>(null);
const cabecalho = ref<HTMLElement | null>(null);
const campoBusca = ref<HTMLInputElement | null>(null);

const opcoesUnidade = computed(() => {
  const lista = dados.value?.unidades ?? [];
  const total = lista.reduce((s, u) => s + u.exames, 0);
  return [
    { valor: null as string | null, rotulo: 'Todas as unidades', exames: total },
    ...lista.map((u) => ({ valor: u.unidade as string | null, rotulo: nomeUnidade(u.unidade), exames: u.exames })),
  ];
});

const unidadeSelect = computed({
  get: () => unidade.value ?? '',
  set: (v: string) => trocarUnidade(v || null),
});

const gruposFiltrados = computed(() => {
  const termo = busca.value.trim().toLowerCase();
  const grupos = dados.value?.grupos ?? [];
  if (!termo) return grupos;
  return grupos.filter((g) => g.nome.toLowerCase().includes(termo) || g.prontuario.includes(termo));
});

const gruposVisiveis = computed(() => gruposFiltrados.value.slice(0, limite.value));

const compacto = computed(() => !!selecionado.value);

const horaLeitura = computed(() => {
  if (!dados.value) return '';
  return `às ${new Date(dados.value.gerado_em).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`;
});

function registrarLinha(el: unknown, idx: number) {
  linhas[idx] = (el as HTMLElement) ?? null;
}

function linhaDaChave(chave: string | undefined) {
  if (!chave) return null;
  return areaTabela.value?.querySelector<HTMLElement>(`[data-chave="${CSS.escape(chave)}"]`) ?? null;
}

async function focarLinha(idx: number) {
  const total = gruposFiltrados.value.length;
  if (!total) return;
  const alvo = Math.max(0, Math.min(idx, total - 1));
  if (alvo >= limite.value) {
    limite.value = Math.ceil((alvo + 1) / 60) * 60;
    await nextTick();
  }
  indiceFoco.value = alvo;
  linhas[alvo]?.focus();
  if (compacto.value) {
    const g = gruposVisiveis.value[alvo];
    if (g) selecionado.value = { chave: g.chave, posicao: g.posicao, motivo: g.motivo };
  }
}

function teclaNaLinha(evento: KeyboardEvent, g: GrupoFila, idx: number) {
  const passos: Record<string, number> = { ArrowDown: 1, ArrowUp: -1, PageDown: 10, PageUp: -10 };
  if (evento.key in passos) {
    evento.preventDefault();
    focarLinha(idx + passos[evento.key]);
  } else if (evento.key === 'Home') {
    evento.preventDefault();
    focarLinha(0);
  } else if (evento.key === 'End') {
    evento.preventDefault();
    focarLinha(gruposFiltrados.value.length - 1);
  } else if (evento.key === 'Enter') {
    evento.preventDefault();
    selecionar(g, idx, true);
  } else if (evento.key === 'Escape') {
    fecharDetalhe();
  }
}

function atalhoGlobal(evento: KeyboardEvent) {
  const alvo = evento.target as HTMLElement | null;
  const digitando = alvo && (alvo.tagName === 'INPUT' || alvo.tagName === 'TEXTAREA' || alvo.tagName === 'SELECT' || alvo.isContentEditable);
  if (evento.key === '/' && !digitando) {
    evento.preventDefault();
    campoBusca.value?.focus();
  } else if ((evento.key === 'r' || evento.key === 'R') && !digitando && selecionado.value && !evento.metaKey && !evento.ctrlKey) {
    const botao = document.querySelector<HTMLButtonElement>('#detalhe-paciente button[aria-label^="Registrar resultado"]');
    if (botao) {
      evento.preventDefault();
      botao.click();
    }
  }
}

function chavePosicoes() {
  return `agendahc:posicoes:${unidade.value ?? 'todas'}`;
}

function lerPosicoes(): Map<string, number> | null {
  try {
    const bruto = sessionStorage.getItem(chavePosicoes());
    return bruto ? new Map(Object.entries(JSON.parse(bruto) as Record<string, number>)) : null;
  } catch {
    return null;
  }
}

function salvarPosicoes(grupos: GrupoFila[]) {
  try {
    sessionStorage.setItem(chavePosicoes(), JSON.stringify(Object.fromEntries(grupos.map((g) => [g.chave, g.posicao]))));
  } catch {
    return;
  }
}

function quadro() {
  return new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
}

async function carregar(marcarMovimento = false) {
  carregando.value = true;
  erro.value = '';
  const mesmaUnidade = dados.value && (dados.value.unidade ?? null) === (unidade.value ?? null);
  const emMemoria = mesmaUnidade && dados.value
    ? new Map(dados.value.grupos.map((g) => [g.chave, g.posicao] as [string, number]))
    : null;
  const anteriores = emMemoria ?? lerPosicoes();
  try {
    const { data } = await api.get<RespostaFila>('/api/fila', { params: { unidade: unidade.value || undefined } });
    const novos: Record<string, number> = {};
    if (anteriores && (marcarMovimento || !emMemoria)) {
      for (const g of data.grupos) {
        const antes = anteriores.get(g.chave);
        if (antes && antes - g.posicao > 0) novos[g.chave] = antes - g.posicao;
      }
    }
    if (!emMemoria && anteriores && Object.keys(novos).length) {
      const ordemAntiga = [...data.grupos].sort(
        (a, b) => (anteriores.get(a.chave) ?? Number.MAX_SAFE_INTEGER) - (anteriores.get(b.chave) ?? Number.MAX_SAFE_INTEGER),
      );
      dados.value = { ...data, grupos: ordemAntiga };
      await nextTick();
      await quadro();
    }
    movidos.value = novos;
    salvarPosicoes(data.grupos);
    dados.value = data;
    if (selecionado.value) {
      const atual = data.grupos.find((g) => g.chave === selecionado.value?.chave);
      selecionado.value = atual ? { chave: atual.chave, posicao: atual.posicao, motivo: atual.motivo } : selecionado.value;
    }
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? 'Verifique a conexão com o servidor e tente de novo.';
  } finally {
    carregando.value = false;
    trocandoUnidade.value = false;
  }
}

function trocarUnidade(valor: string | null) {
  if (unidade.value === valor) return;
  unidade.value = valor;
  router.replace({ query: valor ? { unidade: valor } : {} });
  selecionado.value = null;
  trocandoUnidade.value = true;
  indiceFoco.value = 0;
  limite.value = 60;
  carregar();
}

async function selecionar(g: GrupoFila, idx: number, peloTeclado = false) {
  indiceFoco.value = idx;
  selecionado.value = { chave: g.chave, posicao: g.posicao, motivo: g.motivo };
  if (peloTeclado) {
    await nextTick();
    document.getElementById('detalhe-titulo')?.focus();
  }
}

async function fecharDetalhe() {
  const chave = selecionado.value?.chave;
  selecionado.value = null;
  await nextTick();
  linhaDaChave(chave)?.focus();
}

function rolarAteLinha(chave: string | undefined) {
  const linha = linhaDaChave(chave);
  const area = areaTabela.value;
  if (!linha || !area) return;
  const alturaCabecalho = cabecalho.value?.offsetHeight ?? 0;
  const topo = linha.offsetTop - alturaCabecalho - 8;
  const visivel = topo >= area.scrollTop && linha.offsetTop + linha.offsetHeight <= area.scrollTop + area.clientHeight;
  if (!visivel) area.scrollTo({ top: Math.max(0, topo), behavior: 'smooth' });
}

async function reabrirPainel(chave: string | undefined) {
  const agora = dados.value?.grupos.find((g) => g.chave === chave);
  if (agora) {
    selecionado.value = { chave: agora.chave, posicao: agora.posicao, motivo: agora.motivo };
    versaoDetalhe.value += 1;
  }
  await nextTick();
  rolarAteLinha(chave);
  document.getElementById('detalhe-titulo')?.focus();
  return agora;
}

async function desfazerPrioridade(id: number, chave: string | undefined) {
  try {
    await api.delete(`/api/regras/prioritarios/${id}`);
    await carregar();
    const agora = await reabrirPainel(chave);
    toast.info(agora ? `Inclusão desfeita. Voltou para ${agora.posicao}º.` : 'Inclusão desfeita.');
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível desfazer. Remova em Regras de prioridade.');
  }
}

async function desfazerTratamento(alvo: NonNullable<EventoAlteracao['desfazerTratamento']>, chave: string | undefined) {
  try {
    await api.post('/api/fila/tratamentos', {
      codigo_solicitacao: alvo.codigo_solicitacao,
      codigo_exame: alvo.codigo_exame,
      status: 'PENDENTE',
      observacao: `Desfeito: o registro anterior era "${alvo.rotulo}".`,
    });
    await carregar();
    const agora = await reabrirPainel(chave);
    toast.info(agora ? `Registro desfeito. O paciente voltou para ${agora.posicao}º.` : 'Registro desfeito.');
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível desfazer o registro.');
  }
}

function avisoComDesfazer(mensagem: string, aoDesfazer: () => void) {
  const toastId = toast.success(
    { component: ToastDesfazer, props: { mensagem }, listeners: { desfazer: () => { toast.dismiss(toastId); aoDesfazer(); } } },
    { timeout: 9000, closeOnClick: false },
  );
}

async function aoAlterar(evento: EventoAlteracao) {
  const chave = selecionado.value?.chave;
  const antes = selecionado.value?.posicao;
  await carregar(evento.tipo === 'prioridade');
  const agora = dados.value?.grupos.find((g) => g.chave === chave);
  const tratamento = evento.desfazerTratamento;
  if (!agora) {
    const mensagem = `${evento.mensagem} Paciente saiu da fila.`;
    if (tratamento) avisoComDesfazer(mensagem, () => desfazerTratamento(tratamento, chave));
    else toast.success(mensagem);
    selecionado.value = null;
    await nextTick();
    focarLinha(Math.max(0, (antes ?? 1) - 1));
    return;
  }
  const mensagem = antes && agora.posicao < antes
    ? `${evento.mensagem} Subiu de ${antes}º para ${agora.posicao}º.`
    : evento.mensagem;
  const idPrioridade = evento.desfazerPrioridadeId;
  if (idPrioridade) avisoComDesfazer(mensagem, () => desfazerPrioridade(idPrioridade, chave));
  else if (tratamento) avisoComDesfazer(mensagem, () => desfazerTratamento(tratamento, chave));
  else toast.success(mensagem);
  await nextTick();
  rolarAteLinha(chave);
}

watch(busca, () => {
  limite.value = 60;
});

onMounted(() => {
  window.addEventListener('keydown', atalhoGlobal);
  carregar();
});

onBeforeUnmount(() => window.removeEventListener('keydown', atalhoGlobal));
</script>

<style scoped>
.fila-move {
  transition: transform 520ms cubic-bezier(0.16, 1, 0.3, 1);
}
.fila-enter-from,
.fila-leave-to {
  opacity: 0;
}
.fila-enter-active {
  transition: opacity 200ms ease-out;
}
.fila-leave-active {
  transition: opacity 160ms ease-out;
  position: absolute;
  width: 100%;
}
.painel-enter-from,
.painel-leave-to {
  opacity: 0;
  transform: translateX(12px);
}
.painel-enter-active,
.painel-leave-active {
  transition: opacity 180ms ease-out, transform 180ms ease-out;
}
@media (prefers-reduced-motion: reduce) {
  .fila-move,
  .fila-enter-active,
  .fila-leave-active,
  .painel-enter-active,
  .painel-leave-active {
    transition: none;
  }
}
</style>
