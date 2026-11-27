<template>
  <div class="flex flex-col min-h-full">
    <div class="sticky top-0 z-10 bg-surface border-b border-line px-5 pt-4 pb-3">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h2 id="detalhe-titulo" tabindex="-1" class="text-lg font-extrabold text-ink leading-snug text-balance rounded focus-visible:outline-2 focus-visible:outline-acao">{{ paciente?.nome ?? '…' }}</h2>
          <p class="tabular flex items-center gap-1 text-xs text-ink-muted">
            <template v-if="paciente?.prontuario">
              Prontuário {{ paciente.prontuario }}
              <button
                type="button"
                @click="copiar(paciente.prontuario, 'prontuario')"
                :aria-label="copiado === 'prontuario' ? 'Prontuário copiado' : 'Copiar prontuário'"
                class="inline-flex items-center gap-0.5 rounded px-1 py-0.5 font-semibold text-acao hover:bg-acao-suave"
              >
                <component :is="copiado === 'prontuario' ? CheckIcon : ClipboardDocumentIcon" class="h-3.5 w-3.5" aria-hidden="true" />
                {{ copiado === 'prontuario' ? 'Copiado' : 'Copiar' }}
              </button>
            </template>
            <template v-else-if="paciente">Sem prontuário no extrato</template>
          </p>
        </div>
        <button type="button" @click="emit('fechar')" class="rounded-md p-1 text-ink-muted hover:bg-surface-sunken hover:text-ink" aria-label="Fechar detalhe">
          <XMarkIcon class="h-5 w-5" />
        </button>
      </div>
      <div class="mt-2 flex flex-wrap items-center gap-2 text-sm">
        <span class="tabular font-extrabold text-ink">{{ posicao !== null ? `${posicao}º na fila` : 'Finalizado hoje' }}</span>
        <MotivoChip :motivo="motivo" />
      </div>
      <p class="mt-1 text-xs text-ink-muted">{{ motivo.detalhe }}</p>
    </div>

    <div v-if="erroCarga && !paciente" class="p-5 text-sm" role="alert">
      <p class="font-bold text-separar-ink">Não foi possível abrir o paciente.</p>
      <p class="mt-1 text-ink-muted">{{ erroCarga }}</p>
      <button type="button" @click="carregar" class="mt-3 rounded-md bg-acao px-3 py-1.5 text-sm font-bold text-white hover:bg-acao-hover">Tentar de novo</button>
    </div>

    <div v-else-if="carregando && !paciente" class="p-5 space-y-3">
      <div v-for="n in 4" :key="n" class="h-10 rounded bg-line/70 animate-pulse"></div>
    </div>

    <div v-else-if="paciente" class="divide-y divide-line">
      <section v-if="paciente.alertas.length" class="px-5 py-4 space-y-3">
        <h3 class="text-xs font-bold text-ink-muted">Alertas</h3>
        <div v-for="a in paciente.alertas" :key="a.tipo + a.exames.join()" class="text-sm">
          <AlertaCombinacao :alerta="a" />
          <p class="mt-1.5 text-ink">{{ a.orientacao }}</p>
          <p class="mt-1 text-xs text-ink-muted">
            {{ a.exames.map(exameCurto).join(' + ') }}<template v-if="a.exemplo"> · regra de exemplo</template>
            <template v-if="a.tipo === 'DUPLICIDADE'"> · RF015</template>
          </p>
        </div>
      </section>

      <section class="px-5 py-4">
        <div class="mb-2 flex items-baseline justify-between gap-2">
          <h3 class="text-xs font-bold text-ink-muted">Exames do paciente</h3>
          <button
            v-if="ativos.length > 1 && !lote.aberto"
            type="button"
            @click="abrirLote"
            class="text-xs font-bold text-acao underline underline-offset-2 hover:text-acao-hover"
          >
            Registrar para os {{ ativos.length }} pendentes
          </button>
        </div>
        <form v-if="lote.aberto" id="form-lote" @submit.prevent="registrarLote" class="mb-3 space-y-2.5 rounded-md bg-surface-sunken p-3 ring-1 ring-line">
          <fieldset>
            <legend class="text-xs font-bold text-ink mb-1.5">Mesmo resultado para os {{ ativos.length }} exames pendentes</legend>
            <div class="grid grid-cols-3 gap-1.5">
              <label
                v-for="op in opcoesLote"
                :key="op.valor"
                :class="lote.status === op.valor ? 'bg-surface ring-2 ring-acao text-ink' : 'bg-surface ring-1 ring-line text-ink-muted hover:text-ink'"
                class="flex items-center gap-1.5 rounded-md px-2 py-2 text-xs font-semibold cursor-pointer has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-acao"
              >
                <input type="radio" class="sr-only" :value="op.valor" v-model="lote.status" />
                <component :is="op.icone" class="h-4 w-4 shrink-0" aria-hidden="true" />
                {{ op.rotulo }}
              </label>
            </div>
          </fieldset>
          <label class="block">
            <span class="text-xs font-bold text-ink">
              <template v-if="lote.status === 'CANCELADO'">Motivo do cancelamento</template>
              <template v-else>Observação <span class="font-normal text-ink-muted">(opcional)</span></template>
            </span>
            <textarea v-model="lote.observacao" :required="lote.status === 'CANCELADO'" rows="2" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink"></textarea>
          </label>
          <p class="text-xs text-ink-muted">O contato é com o paciente, então vale para todos. O agendamento continua exame a exame, porque cada um tem data própria.</p>
          <p v-if="erroLote" class="text-xs font-semibold text-separar-ink" role="alert">{{ erroLote }}</p>
          <div class="flex items-center gap-2">
            <button type="submit" :disabled="salvando || !lote.status" class="rounded-md bg-acao px-3 py-1.5 text-sm font-bold text-white hover:bg-acao-hover disabled:bg-paper-disabled disabled:text-ink-muted">
              {{ salvando ? 'Registrando…' : `Registrar nos ${ativos.length}` }}
            </button>
            <button type="button" @click="lote.aberto = false" class="rounded-md px-3 py-1.5 text-sm font-semibold text-ink-muted hover:text-ink">Cancelar</button>
          </div>
        </form>
        <ul class="divide-y divide-line">
          <li v-for="i in paciente.itens" :key="i.codigo_solicitacao + i.codigo_exame" class="py-3 first:pt-1 last:pb-0">
            <div>
              <div class="flex items-start justify-between gap-2">
                <p :id="`exame-${chaveDom(i)}`" tabindex="-1" class="font-bold text-ink text-sm leading-snug rounded focus-visible:outline-2 focus-visible:outline-acao">{{ exameCurto(i.nome_exame) }}</p>
                <StatusTag :status="i.status" :quando="i.status_info?.criado_em" :quem="i.status_info?.usuario" />
              </div>
              <p class="tabular mt-0.5 flex flex-wrap items-center gap-x-1 text-xs text-ink-muted">
                <span>{{ nomeUnidade(i.unidade) }} ·</span>
                <span>Solic. {{ i.codigo_solicitacao }}</span>
                <button
                  type="button"
                  @click="copiar(i.codigo_solicitacao, chaveItem(i))"
                  :aria-label="copiado === chaveItem(i) ? 'Número da solicitação copiado' : `Copiar solicitação ${i.codigo_solicitacao}`"
                  class="inline-flex items-center rounded p-0.5 text-acao hover:bg-acao-suave"
                >
                  <component :is="copiado === chaveItem(i) ? CheckIcon : ClipboardDocumentIcon" class="h-3.5 w-3.5" aria-hidden="true" />
                </button>
                <span>· {{ dataCompleta(i.data_solicitacao) }} · {{ i.espera_dias }} dias</span>
              </p>
              <p v-if="i.solicitante" class="mt-0.5 text-xs text-ink-muted">Pedido por {{ i.solicitante }}</p>
              <p v-if="i.vagas === 0 && !finalizado(i.status)" class="mt-1 text-xs font-semibold text-espera-ink">Agenda deste exame sem vagas abertas.</p>
              <p
                v-if="i.status === 'EM_CONTATO' && i.status_info?.horas !== null && i.status_info?.horas !== undefined"
                :class="i.status_info.prazo_vencido ? 'text-separar-ink' : 'text-ink-muted'"
                class="mt-1 text-xs font-semibold"
              >
                <template v-if="i.status_info.prazo_vencido">Sem resposta há {{ i.status_info.horas }}h: o prazo de {{ prazoRespostaHoras }}h venceu. Ofereça a vaga ao próximo.</template>
                <template v-else>Aguardando resposta há {{ i.status_info.horas }}h (prazo de {{ prazoRespostaHoras }}h).</template>
              </p>
              <p v-if="(i.status_info?.tentativas ?? 0) > 0 && !finalizado(i.status)" class="mt-0.5 text-xs text-ink-muted">
                {{ i.status_info?.tentativas }} {{ i.status_info?.tentativas === 1 ? 'tentativa de contato' : 'tentativas de contato' }}
              </p>
              <p v-if="(i.quantidade ?? 1) > 1" class="mt-1 text-xs text-ink-muted">
                Aparece {{ i.quantidade }} vezes na mesma solicitação do AGHU; o resultado vale para todas.
              </p>
              <p v-if="i.status_info?.data_agendada" :class="i.status === 'AGENDADO' ? 'text-ok-ink' : 'text-ink'" class="mt-1 text-xs font-semibold">
                {{ i.status === 'AGENDADO' ? 'Agendado para' : 'Data oferecida:' }} {{ dataCompleta(i.status_info.data_agendada) }}
                <button
                  v-if="i.status === 'AGENDADO' || i.status === 'EM_CONTATO'"
                  type="button"
                  @click="copiar(mensagemPara(i, i.status, i.status_info.data_agendada), `msg-${chaveItem(i)}`)"
                  class="ml-1 inline-flex items-center gap-0.5 rounded px-1 font-bold text-acao hover:bg-acao-suave"
                >
                  <component :is="copiado === `msg-${chaveItem(i)}` ? CheckIcon : ChatBubbleLeftEllipsisIcon" class="h-3.5 w-3.5" aria-hidden="true" />
                  {{ copiado === `msg-${chaveItem(i)}` ? 'Mensagem copiada' : 'Copiar mensagem' }}
                </button>
              </p>
              <p v-if="i.status_info?.observacao" class="mt-1 text-xs text-ink">“{{ i.status_info.observacao }}”</p>
              <details v-if="i.preparo && !finalizado(i.status)" class="mt-1.5 text-xs">
                <summary class="cursor-pointer font-semibold text-ink-muted hover:text-ink">
                  Preparo<template v-if="i.preparo.exemplo"> · texto de exemplo, a validar com a UDI</template>
                </summary>
                <p class="mt-1 text-ink text-pretty">{{ i.preparo.texto }}</p>
              </details>
              <button
                v-if="finalizado(i.status)"
                type="button"
                @click="desfazerRegistro(i)"
                :disabled="salvando"
                class="mt-2 text-xs font-bold text-acao hover:text-acao-hover underline underline-offset-2 disabled:opacity-60"
              >
                Desfazer este registro
              </button>
              <button
                v-if="!finalizado(i.status) && aberto !== chaveItem(i)"
                type="button"
                @click="abrirRegistro(i)"
                :aria-label="`Registrar resultado: ${exameCurto(i.nome_exame)}`"
                class="mt-2 text-xs font-bold text-acao hover:text-acao-hover underline underline-offset-2"
              >
                Registrar resultado
              </button>
            </div>

            <form v-if="aberto === chaveItem(i)" :id="`form-${chaveDom(i)}`" @submit.prevent="registrar(i)" class="mt-3 space-y-3">
              <fieldset>
                <legend class="text-xs font-bold text-ink mb-1.5">Resultado</legend>
                <div class="grid grid-cols-2 gap-1.5">
                  <label
                    v-for="op in opcoesStatus"
                    :key="op.valor"
                    :class="form.status === op.valor ? 'bg-surface ring-2 ring-acao text-ink' : 'bg-surface ring-1 ring-line text-ink-muted hover:text-ink'"
                    class="flex items-center gap-2 rounded-md px-2.5 py-2 text-xs font-semibold cursor-pointer has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-acao"
                  >
                    <input type="radio" class="sr-only" :value="op.valor" v-model="form.status" />
                    <component :is="op.icone" class="h-4 w-4 shrink-0" aria-hidden="true" />
                    {{ op.rotulo }}
                  </label>
                </div>
              </fieldset>
              <label v-if="form.status === 'AGENDADO' || form.status === 'EM_CONTATO'" class="block">
                <span class="text-xs font-bold text-ink">
                  <template v-if="form.status === 'AGENDADO'">Data marcada no AGHU</template>
                  <template v-else>Data oferecida ao paciente <span class="font-normal text-ink-muted">(opcional)</span></template>
                </span>
                <input v-model="form.data" type="date" :required="form.status === 'AGENDADO'" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" />
              </label>
              <div v-if="(form.status === 'AGENDADO' || form.status === 'EM_CONTATO') && form.data" class="rounded-md bg-surface-sunken p-2.5 ring-1 ring-line">
                <p class="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-xs font-bold text-ink">
                  Mensagem para o paciente
                  <button
                    type="button"
                    @click="copiar(mensagemPara(i, form.status as StatusItem, form.data), `form-msg-${chaveItem(i)}`)"
                    class="inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 font-bold text-acao hover:bg-acao-suave"
                  >
                    <component :is="copiado === `form-msg-${chaveItem(i)}` ? CheckIcon : ClipboardDocumentIcon" class="h-3.5 w-3.5" aria-hidden="true" />
                    {{ copiado === `form-msg-${chaveItem(i)}` ? 'Copiada' : 'Copiar para o WhatsApp' }}
                  </button>
                </p>
                <p class="mt-1.5 whitespace-pre-line text-xs text-ink text-pretty">{{ mensagemPara(i, form.status as StatusItem, form.data) }}</p>
                <p class="mt-1.5 text-xs text-ink-muted">O AgendaHC não envia mensagens: cole no WhatsApp da Central.</p>
              </div>
              <label class="block">
                <span class="text-xs font-bold text-ink">
                  <template v-if="form.status === 'CANCELADO'">Motivo do cancelamento</template>
                  <template v-else>Observação <span class="font-normal text-ink-muted">(opcional)</span></template>
                </span>
                <textarea v-model="form.observacao" :required="form.status === 'CANCELADO'" rows="2" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" placeholder="Ex.: paciente pediu horário pela manhã"></textarea>
              </label>
              <p v-if="erroForm" class="text-xs font-semibold text-separar-ink" role="alert">{{ erroForm }}</p>
              <div class="flex items-center gap-2">
                <button type="submit" :disabled="salvando || !form.status" class="rounded-md bg-acao px-3 py-1.5 text-sm font-bold text-white hover:bg-acao-hover disabled:bg-paper-disabled disabled:text-ink-muted">
                  {{ salvando ? 'Registrando…' : 'Registrar' }}
                </button>
                <button type="button" @click="aberto = null" class="rounded-md px-3 py-1.5 text-sm font-semibold text-ink-muted hover:text-ink">Cancelar</button>
              </div>
              <p class="text-xs text-ink-muted">A marcação é feita no AGHU. Aqui fica só o registro do resultado.</p>
            </form>
          </li>
        </ul>
      </section>

      <section class="px-5 py-4">
        <h3 class="text-xs font-bold text-ink-muted mb-2">Lista de prioridade</h3>
        <ul v-if="paciente.prioridades.length" class="space-y-1.5 text-sm">
          <li v-for="p in paciente.prioridades" :key="p.id" class="flex items-baseline gap-2">
            <span class="font-bold text-lista-ink">{{ p.area }}</span>
            <span class="text-ink">{{ p.motivo }}</span>
            <span v-if="p.validade" class="text-xs text-ink-muted">· até {{ dataCompleta(p.validade) }}</span>
            <span v-if="p.exemplo" class="text-xs text-ink-muted">· exemplo</span>
          </li>
        </ul>
        <template v-else-if="paciente.prontuario">
          <button
            v-if="!formPrioridade.aberto"
            type="button"
            @click="abrirPrioridade"
            class="inline-flex items-center gap-1.5 rounded-md ring-1 ring-campo bg-surface px-3 py-1.5 text-sm font-semibold text-ink hover:bg-surface-sunken"
          >
            <UserPlusIcon class="h-4 w-4 text-acao" aria-hidden="true" />
            Incluir na lista de prioridade
          </button>
          <form v-else id="form-prioridade" @submit.prevent="incluirPrioridade" class="space-y-2.5">
            <label class="block">
              <span class="text-xs font-bold text-ink">Área responsável</span>
              <select v-model="formPrioridade.area" required class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink">
                <option value="" disabled>Selecione a área</option>
                <option>Nefrologia</option>
                <option>Oncologia</option>
                <option>Cardiologia</option>
                <option value="Outra">Outra…</option>
              </select>
            </label>
            <label v-if="formPrioridade.area === 'Outra'" class="block">
              <span class="text-xs font-bold text-ink">Nome da área</span>
              <input v-model="formPrioridade.areaOutra" required type="text" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" />
            </label>
            <label class="block">
              <span class="text-xs font-bold text-ink">Motivo</span>
              <input v-model="formPrioridade.motivo" required type="text" placeholder="Ex.: paciente em hemodiálise" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink placeholder:text-ink-muted" />
            </label>
            <label class="block">
              <span class="text-xs font-bold text-ink">Vale para</span>
              <select v-model="formPrioridade.valePara" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink">
                <option v-for="u in unidadesDoPaciente" :key="u" :value="u">{{ nomeUnidade(u) }}</option>
                <option value="">Todas as unidades</option>
              </select>
            </label>
            <label class="block">
              <span class="text-xs font-bold text-ink">Válido até <span class="font-normal text-ink-muted">(opcional)</span></span>
              <input v-model="formPrioridade.validade" type="date" :min="hojeIso()" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" />
            </label>
            <p class="text-xs text-ink">
              {{ paciente.nome }} passa à frente de quem não está na lista em
              <strong class="font-bold">{{ formPrioridade.valePara ? nomeUnidade(formPrioridade.valePara) : 'todas as unidades' }}</strong><template v-if="formPrioridade.validade"> até {{ dataCompleta(formPrioridade.validade) }}</template>.
              Dá para desfazer logo após incluir.
            </p>
            <p v-if="erroPrioridade" class="text-xs font-semibold text-separar-ink" role="alert">{{ erroPrioridade }}</p>
            <div class="flex items-center gap-2">
              <button type="submit" :disabled="salvando" class="rounded-md bg-acao px-3 py-1.5 text-sm font-bold text-white hover:bg-acao-hover disabled:bg-paper-disabled">Incluir e reordenar</button>
              <button type="button" @click="formPrioridade.aberto = false" class="rounded-md px-3 py-1.5 text-sm font-semibold text-ink-muted hover:text-ink">Cancelar</button>
            </div>
          </form>
        </template>
        <p v-else class="text-sm text-ink-muted">Sem prontuário no extrato: não é possível incluir na lista.</p>
      </section>

      <section class="px-5 py-4">
        <div class="flex gap-2 text-xs text-ink-muted">
          <InformationCircleIcon class="h-4 w-4 shrink-0 text-ink-muted" aria-hidden="true" />
          <p>Sem dado no extrato do AGHU: {{ paciente.dados_ausentes.join(', ') }}. Esses critérios entram na ordenação quando a TI incluir os campos.</p>
        </div>
      </section>

      <section class="px-5 py-4">
        <h3 class="text-xs font-bold text-ink-muted mb-2">Histórico</h3>
        <ol v-if="paciente.historico.length" class="space-y-2 text-sm">
          <li v-for="(h, n) in paciente.historico" :key="n" class="flex gap-2">
            <span class="tabular text-xs text-ink-muted w-24 shrink-0 pt-0.5">{{ dataHora(h.criado_em) }}</span>
            <span v-if="h.tipo === 'PRIORIDADE'" class="text-ink">
              <strong class="font-bold">Lista de prioridade · {{ h.area }}</strong>
              <template v-if="h.exemplo"> · exemplo</template>
              <template v-else-if="!h.ativo"> · desfeito ou removido</template>
              · {{ h.usuario }}
            </span>
            <span v-else class="text-ink">
              <strong class="font-bold">{{ h.desfaz ? 'Desfeito' : h.status === 'PENDENTE' ? 'Reaberto' : ROTULO_STATUS[h.status as StatusItem] }}</strong>
              · {{ exameDoCodigo(h.codigo_exame ?? '') }} · {{ h.usuario }}<template v-if="h.exemplo"> · exemplo</template>
              <span v-if="h.observacao" class="block text-xs text-ink-muted">“{{ h.observacao }}”</span>
            </span>
          </li>
        </ol>
        <p v-else class="text-sm text-ink-muted text-pretty">Nenhum registro ainda. Cada resultado registrado aparece aqui, com quem registrou e quando.</p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue';
import { XMarkIcon, UserPlusIcon, InformationCircleIcon, ClipboardDocumentIcon, CheckIcon, ChatBubbleLeftEllipsisIcon } from '@heroicons/vue/20/solid';
import { PhoneIcon, PhoneXMarkIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/vue/20/solid';
import api from '../services/api';
import MotivoChip from './MotivoChip.vue';
import StatusTag from './StatusTag.vue';
import AlertaCombinacao from './AlertaCombinacao.vue';
import {
  ROTULO_STATUS, dataCompleta, dataHora, exameCurto, hojeIso, nomeUnidade, primeiroNome,
  type Aba, type Alerta, type ItemFila, type Motivo, type Prioridade, type StatusItem,
} from '../lib/agenda';

type ItemChave = { codigo_solicitacao: string; codigo_exame: string };

interface DetalheResposta {
  chave: string;
  prontuario: string;
  nome: string;
  itens: ItemFila[];
  prioridades: Prioridade[];
  alertas: Alerta[];
  historico: {
    tipo: 'TRATAMENTO' | 'PRIORIDADE';
    codigo_solicitacao?: string;
    codigo_exame?: string;
    status?: string;
    observacao?: string | null;
    area?: string;
    ativo?: boolean;
    exemplo?: boolean;
    desfaz?: boolean;
    usuario: string;
    criado_em: string;
  }[];
  dados_ausentes: string[];
}

const props = withDefaults(
  defineProps<{ chave: string; posicao: number | null; motivo: Motivo; unidade: string | null; prazoRespostaHoras?: number }>(),
  { prazoRespostaHoras: 24 },
);
const emit = defineEmits<{
  (e: 'fechar'): void;
  (e: 'alterado', evento: {
    tipo: 'prioridade' | 'tratamento';
    mensagem: string;
    destino?: Aba;
    desfazerPrioridadeId?: number;
    desfazerTratamento?: { itens: ItemChave[] };
  }): void;
}>();

const paciente = ref<DetalheResposta | null>(null);
const carregando = ref(false);
const salvando = ref(false);
const aberto = ref<string | null>(null);
const erroForm = ref('');
const erroCarga = ref('');
const erroPrioridade = ref('');
const form = reactive<{ status: StatusItem | ''; data: string; observacao: string }>({ status: '', data: '', observacao: '' });
const formPrioridade = reactive({ aberto: false, area: '', areaOutra: '', motivo: '', valePara: '', validade: '' });
const lote = reactive<{ aberto: boolean; status: StatusItem | ''; observacao: string }>({ aberto: false, status: '', observacao: '' });
const erroLote = ref('');

const ativos = computed(() => (paciente.value?.itens ?? []).filter((i) => !finalizado(i.status)));

const DESTINO: Record<StatusItem, Aba> = {
  PENDENTE: 'a_chamar',
  EM_CONTATO: 'em_contato',
  SEM_CONTATO: 'sem_contato',
  AGENDADO: 'finalizados',
  CANCELADO: 'finalizados',
};

function mensagemPara(i: ItemFila, status: StatusItem, dataIso: string | null | undefined) {
  const nome = primeiroNome(paciente.value?.nome ?? '');
  const exame = exameCurto(i.nome_exame);
  const data = dataCompleta(`${dataIso}T12:00:00`);
  if (status === 'EM_CONTATO') {
    return `Olá, ${nome}. Aqui é a Central de Marcação do HC-UFPE.\n`
      + `Temos vaga para o seu exame ${exame} no dia ${data}.\n`
      + `Responda em até ${props.prazoRespostaHoras} horas confirmando se pode comparecer. Sem resposta nesse prazo, a vaga passa para o próximo paciente da fila.`;
  }
  const preparo = i.preparo && !i.preparo.exemplo ? i.preparo.texto : '[preparo a confirmar com a UDI]';
  return `Olá, ${nome}. Aqui é a Central de Marcação do HC-UFPE.\n`
    + `Seu exame ${exame} está marcado para ${data}.\n`
    + `Preparo: ${preparo}\n`
    + 'Leve documento com foto, cartão do SUS e o pedido do exame.';
}

async function abrirLote() {
  lote.aberto = true;
  lote.status = '';
  lote.observacao = '';
  erroLote.value = '';
  await nextTick();
  document.querySelector<HTMLInputElement>('#form-lote input[type=radio]')?.focus();
}

async function registrarLote() {
  if (!lote.status) return;
  if (lote.status === 'CANCELADO' && !lote.observacao.trim()) {
    erroLote.value = 'Informe o motivo do cancelamento.';
    return;
  }
  const itens = ativos.value.map((i) => ({ codigo_solicitacao: i.codigo_solicitacao, codigo_exame: i.codigo_exame }));
  salvando.value = true;
  erroLote.value = '';
  try {
    await api.post('/api/fila/tratamentos/lote', { itens, status: lote.status, observacao: lote.observacao || null });
    const status = lote.status as StatusItem;
    lote.aberto = false;
    await carregar();
    emit('alterado', {
      tipo: 'tratamento',
      mensagem: `${itens.length} exames: ${ROTULO_STATUS[status]}.`,
      destino: DESTINO[status],
      desfazerTratamento: { itens },
    });
  } catch (e: any) {
    erroLote.value = e?.response?.data?.detail ?? 'Não foi possível registrar. Tente de novo.';
  } finally {
    salvando.value = false;
  }
}
const copiado = ref<string | null>(null);

const unidadesDoPaciente = computed(() => {
  const unidades = (paciente.value?.itens ?? []).filter((i) => !finalizado(i.status)).map((i) => i.unidade);
  return [...new Set(unidades)];
});

function chaveDom(i: ItemFila) {
  return `${i.codigo_solicitacao}-${i.codigo_exame}`.replace(/[^A-Za-z0-9_-]/g, '');
}

async function copiar(texto: string, marca: string) {
  try {
    await navigator.clipboard.writeText(texto);
    copiado.value = marca;
    setTimeout(() => {
      if (copiado.value === marca) copiado.value = null;
    }, 1800);
  } catch {
    copiado.value = null;
  }
}

async function abrirPrioridade() {
  formPrioridade.aberto = true;
  formPrioridade.area = '';
  formPrioridade.areaOutra = '';
  formPrioridade.motivo = '';
  formPrioridade.validade = '';
  formPrioridade.valePara = props.unidade && unidadesDoPaciente.value.includes(props.unidade)
    ? props.unidade
    : unidadesDoPaciente.value[0] ?? '';
  erroPrioridade.value = '';
  await nextTick();
  document.querySelector<HTMLElement>('#form-prioridade select')?.focus();
}

const opcoesLote = [
  { valor: 'EM_CONTATO', rotulo: 'Em contato', icone: PhoneIcon },
  { valor: 'SEM_CONTATO', rotulo: 'Sem contato', icone: PhoneXMarkIcon },
  { valor: 'CANCELADO', rotulo: 'Cancelado', icone: XCircleIcon },
] as const;

const opcoesStatus = [
  { valor: 'EM_CONTATO', rotulo: 'Em contato', icone: PhoneIcon },
  { valor: 'SEM_CONTATO', rotulo: 'Sem contato', icone: PhoneXMarkIcon },
  { valor: 'AGENDADO', rotulo: 'Agendado no AGHU', icone: CheckCircleIcon },
  { valor: 'CANCELADO', rotulo: 'Cancelado', icone: XCircleIcon },
] as const;

function chaveItem(i: ItemFila) {
  return `${i.codigo_solicitacao}:${i.codigo_exame}`;
}

function finalizado(status: StatusItem) {
  return status === 'AGENDADO' || status === 'CANCELADO';
}

function exameDoCodigo(codigo: string) {
  const item = paciente.value?.itens.find((i) => i.codigo_exame === codigo);
  return item ? exameCurto(item.nome_exame) : codigo;
}

async function abrirRegistro(i: ItemFila) {
  aberto.value = chaveItem(i);
  form.status = '';
  form.data = '';
  form.observacao = '';
  erroForm.value = '';
  await nextTick();
  document.querySelector<HTMLInputElement>(`#form-${chaveDom(i)} input[type=radio]`)?.focus();
}

async function carregar() {
  carregando.value = true;
  erroCarga.value = '';
  try {
    const { data } = await api.get<DetalheResposta>(`/api/fila/pacientes/${encodeURIComponent(props.chave)}`);
    paciente.value = data;
  } catch (e: any) {
    erroCarga.value = e?.response?.data?.detail ?? 'Verifique a conexão e tente de novo.';
  } finally {
    carregando.value = false;
  }
}

async function registrar(i: ItemFila) {
  if (!form.status) return;
  if (form.status === 'AGENDADO' && !form.data) {
    erroForm.value = 'Informe a data marcada no AGHU.';
    return;
  }
  if (form.status === 'CANCELADO' && !form.observacao.trim()) {
    erroForm.value = 'Informe o motivo do cancelamento.';
    return;
  }
  salvando.value = true;
  erroForm.value = '';
  try {
    await api.post('/api/fila/tratamentos', {
      codigo_solicitacao: i.codigo_solicitacao,
      codigo_exame: i.codigo_exame,
      status: form.status,
      data_agendada: (form.status === 'AGENDADO' || form.status === 'EM_CONTATO') && form.data ? form.data : null,
      observacao: form.observacao || null,
    });
    aberto.value = null;
    await carregar();
    const status = form.status as StatusItem;
    emit('alterado', {
      tipo: 'tratamento',
      mensagem: `${exameCurto(i.nome_exame)}: ${ROTULO_STATUS[status]}.`,
      destino: DESTINO[status],
      desfazerTratamento: { itens: [{ codigo_solicitacao: i.codigo_solicitacao, codigo_exame: i.codigo_exame }] },
    });
    await nextTick();
    document.getElementById(`exame-${chaveDom(i)}`)?.focus();
  } catch (e: any) {
    erroForm.value = e?.response?.data?.detail ?? 'Não foi possível registrar. Tente de novo.';
  } finally {
    salvando.value = false;
  }
}

async function desfazerRegistro(i: ItemFila) {
  salvando.value = true;
  try {
    await api.post('/api/fila/tratamentos/desfazer', {
      itens: [{ codigo_solicitacao: i.codigo_solicitacao, codigo_exame: i.codigo_exame }],
    });
    await carregar();
    const atual = paciente.value?.itens.find((x) => chaveItem(x) === chaveItem(i));
    emit('alterado', {
      tipo: 'tratamento',
      mensagem: `${exameCurto(i.nome_exame)}: registro desfeito.`,
      destino: DESTINO[(atual?.status ?? 'PENDENTE') as StatusItem],
    });
  } catch (e: any) {
    erroCarga.value = e?.response?.data?.detail ?? 'Não foi possível desfazer.';
  } finally {
    salvando.value = false;
  }
}

async function incluirPrioridade() {
  if (!paciente.value) return;
  salvando.value = true;
  erroPrioridade.value = '';
  try {
    const area = formPrioridade.area === 'Outra' ? formPrioridade.areaOutra.trim() : formPrioridade.area;
    const { data } = await api.post<{ id: number }>('/api/regras/prioritarios', {
      prontuario: paciente.value.prontuario,
      area,
      motivo: formPrioridade.motivo,
      unidade: formPrioridade.valePara || null,
      validade: formPrioridade.validade || null,
    });
    formPrioridade.aberto = false;
    await carregar();
    emit('alterado', { tipo: 'prioridade', mensagem: `Incluído na lista de prioridade (${area}).`, desfazerPrioridadeId: data.id });
  } catch (e: any) {
    erroPrioridade.value = e?.response?.data?.detail ?? 'Não foi possível incluir. Tente de novo.';
  } finally {
    salvando.value = false;
  }
}

watch(() => props.chave, () => {
  paciente.value = null;
  aberto.value = null;
  formPrioridade.aberto = false;
  lote.aberto = false;
  carregar();
}, { immediate: true });
</script>
