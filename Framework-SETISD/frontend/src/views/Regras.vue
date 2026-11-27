<template>
  <div class="px-6 py-5 max-w-[1280px] space-y-6">
    <div v-if="erro && !dados" class="rounded-md border border-separar-bg bg-surface p-4 text-sm" role="alert">
      <p class="font-bold text-separar-ink">Não foi possível carregar as regras.</p>
      <p class="mt-1 text-ink-muted">{{ erro }}</p>
      <button type="button" @click="carregar()" class="mt-3 rounded-md bg-acao px-3 py-1.5 text-sm font-bold text-white hover:bg-acao-hover">Tentar de novo</button>
    </div>

    <div v-else-if="carregando && !dados" class="space-y-3">
      <div v-for="n in 5" :key="n" class="h-12 rounded bg-line/70 animate-pulse"></div>
    </div>

    <template v-else-if="dados">
      <nav aria-label="Seções" class="flex flex-wrap gap-x-4 gap-y-1 text-sm font-semibold">
        <a v-for="s in SECOES" :key="s.id" :href="`#${s.id}`" class="text-acao underline decoration-line-strong underline-offset-4 hover:decoration-acao">{{ s.rotulo }}</a>
      </nav>

      <section id="sec-criterios" class="rounded-lg bg-surface ring-1 ring-line overflow-hidden scroll-mt-4">
        <div class="px-5 pt-4 pb-3 border-b border-line">
          <h2 class="text-base font-extrabold text-ink">Ordem dos critérios por unidade e por exame</h2>
          <p class="text-xs text-ink-muted mt-0.5">
            A fila aplica os critérios de cima para baixo. Um exame pode ter regra própria (RN-03); ela vale quando a fila é filtrada por esse exame.
            Cada alteração gera uma nova versão e fica no histórico abaixo.
          </p>
        </div>
        <div class="grid md:grid-cols-[17rem_1fr]">
          <div class="border-r border-line bg-surface-sunken py-2 max-h-[30rem] overflow-y-auto">
            <p class="px-4 pt-1 pb-1 text-xs font-bold text-ink-muted">Unidades</p>
            <ul>
              <li v-for="r in dados.regras" :key="r.unidade">
                <button
                  type="button"
                  @click="trocarRegra(r)"
                  :aria-current="edicao?.unidade === r.unidade ? 'true' : undefined"
                  :class="edicao?.unidade === r.unidade ? 'bg-surface text-ink font-bold ring-1 ring-line' : 'text-ink-muted hover:text-ink'"
                  class="w-full flex items-baseline justify-between gap-2 px-4 py-2 text-left text-sm"
                >
                  <span class="truncate">{{ nomeDaRegra(r) }}</span>
                  <span class="tabular text-xs shrink-0">v{{ r.versao }}</span>
                </button>
              </li>
            </ul>
            <p class="px-4 pt-3 pb-1 text-xs font-bold text-ink-muted border-t border-line mt-2">Exames com regra própria</p>
            <ul>
              <li v-for="r in dados.regras_exame" :key="r.unidade">
                <button
                  type="button"
                  @click="trocarRegra(r)"
                  :aria-current="edicao?.unidade === r.unidade ? 'true' : undefined"
                  :class="edicao?.unidade === r.unidade ? 'bg-surface text-ink font-bold ring-1 ring-line' : 'text-ink-muted hover:text-ink'"
                  class="w-full flex items-baseline justify-between gap-2 px-4 py-2 text-left text-sm"
                >
                  <span class="truncate">{{ nomeDaRegra(r) }}</span>
                  <span class="tabular text-xs shrink-0">v{{ r.versao }}</span>
                </button>
              </li>
              <li v-if="!dados.regras_exame.length" class="px-4 py-1 text-xs text-ink-muted">Nenhuma ainda.</li>
            </ul>
            <form @submit.prevent="criarRegraExame" class="px-4 pt-2 pb-2 space-y-1.5">
              <label class="block">
                <span class="sr-only">Exame para criar regra própria</span>
                <select v-model="novaRegraExame" class="block w-full rounded-md border border-campo bg-surface px-2 py-1.5 text-xs text-ink">
                  <option value="">Criar regra para um exame…</option>
                  <option v-for="e in examesSemRegra" :key="e.codigo" :value="e.codigo">{{ exameCurto(e.nome) }} · {{ nomeUnidade(e.unidade) }}</option>
                </select>
              </label>
              <button v-if="novaRegraExame" type="submit" :disabled="salvando" class="rounded-md bg-acao px-2.5 py-1 text-xs font-bold text-white hover:bg-acao-hover disabled:opacity-60">
                Criar a partir da regra da unidade
              </button>
            </form>
          </div>

          <form v-if="edicao" @submit.prevent="salvar" class="p-5 space-y-4">
            <div class="flex flex-wrap items-baseline gap-x-3">
              <h3 class="text-sm font-extrabold text-ink">{{ edicao.unidade === '*' ? 'Regra padrão' : nomeDaRegra(edicao) }}</h3>
              <span class="text-xs text-ink-muted">
                versão {{ edicao.versao }}
                <template v-if="edicao.exemplo"> · regra de exemplo, a validar com a Central</template>
                <template v-else> · alterada por {{ edicao.atualizado_por }}</template>
              </span>
            </div>
            <p v-if="ehRegraDeExame(edicao.unidade)" class="text-xs text-ink-muted max-w-lg">
              Vale na fila filtrada por este exame. Sem filtro, a fila usa a regra da unidade.
            </p>

            <ol class="space-y-1.5 max-w-lg">
              <li v-for="(c, i) in edicao.criterios" :key="c" class="flex items-center gap-3 rounded-md bg-surface ring-1 ring-line px-3 py-2">
                <span class="tabular w-5 text-sm font-extrabold text-ink">{{ i + 1 }}</span>
                <span class="flex-1 text-sm font-semibold text-ink">
                  {{ c === 'ESPERA_LIMITE' ? `Espera > ${edicao.espera_limite_dias} dias` : ROTULO_CRITERIO[c] }}
                </span>
                <button type="button" @click="mover(i, -1)" :disabled="i === 0" class="rounded p-1 text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed" :aria-label="`Subir ${ROTULO_CRITERIO[c]}`">
                  <ChevronUpIcon class="h-4 w-4" />
                </button>
                <button type="button" @click="mover(i, 1)" :disabled="i === edicao.criterios.length - 1" class="rounded p-1 text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed" :aria-label="`Descer ${ROTULO_CRITERIO[c]}`">
                  <ChevronDownIcon class="h-4 w-4" />
                </button>
              </li>
            </ol>

            <label class="flex items-center gap-3 text-sm text-ink">
              <span class="font-semibold">Limite de espera</span>
              <input v-model.number="edicao.espera_limite_dias" type="number" min="1" max="365" class="tabular w-20 rounded-md border border-campo bg-surface px-2 py-1.5 text-sm" />
              <span class="text-ink-muted">dias</span>
            </label>

            <p class="text-xs text-ink-muted max-w-lg">
              Data de retorno e distância do município entram como critérios quando o extrato do AGHU trouxer esses campos.
            </p>

            <div class="flex flex-wrap items-center gap-3">
              <button type="submit" :disabled="salvando || !alterada" class="rounded-md bg-acao px-4 py-2 text-sm font-bold text-white hover:bg-acao-hover disabled:bg-paper-disabled disabled:text-ink-muted">
                {{ salvando ? 'Salvando…' : 'Salvar nova versão' }}
              </button>
              <button v-if="alterada" type="button" @click="desfazer" class="text-sm font-semibold text-ink-muted hover:text-ink">Desfazer</button>
              <router-link
                v-if="ehRegraDeExame(edicao.unidade)"
                :to="{ path: '/fila', query: { unidade: exameDaRegra(edicao)?.unidade, exame: codigoDaRegra(edicao) } }"
                class="text-sm font-semibold text-acao underline underline-offset-2"
              >
                Ver a fila deste exame
              </router-link>
              <button
                v-if="ehRegraDeExame(edicao.unidade)"
                type="button"
                @click="removerRegraExame"
                class="ml-auto inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-ink-muted hover:bg-separar-bg hover:text-separar-ink"
              >
                <TrashIcon class="h-3.5 w-3.5" aria-hidden="true" /> Voltar a usar a regra da unidade
              </button>
            </div>
          </form>
        </div>
      </section>

      <section id="sec-lista" class="rounded-lg bg-surface ring-1 ring-line overflow-hidden scroll-mt-4">
        <div class="px-5 pt-4 pb-3 flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h2 class="text-base font-extrabold text-ink">Lista de prioridade</h2>
            <p class="text-xs text-ink-muted mt-0.5">Mantida pelas áreas solicitantes, com validade. Substitui as listas avulsas enviadas à Central.</p>
          </div>
          <button
            v-if="!lote.aberto"
            type="button"
            @click="abrirLote"
            class="inline-flex items-center gap-1.5 rounded-md ring-1 ring-campo bg-surface px-3 py-1.5 text-sm font-semibold text-ink hover:bg-surface-sunken"
          >
            <UserPlusIcon class="h-4 w-4 text-acao" aria-hidden="true" />
            Incluir pacientes
          </button>
        </div>

        <form v-if="lote.aberto" id="form-lote-prioridade" @submit.prevent="incluirLote" class="mx-5 mb-4 grid gap-3 rounded-md bg-surface-sunken p-4 ring-1 ring-line md:grid-cols-[1fr_1fr]">
          <label class="block md:row-span-3">
            <span class="text-xs font-bold text-ink">Prontuários</span>
            <span class="block text-xs text-ink-muted">Um por linha, ou cole a lista enviada pela área (vírgula, ponto e vírgula ou espaço).</span>
            <textarea v-model="lote.prontuarios" required rows="7" class="tabular mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" placeholder="Um prontuário por linha"></textarea>
            <span class="mt-1 block text-xs text-ink-muted">{{ contagemColada }}</span>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-xs font-bold text-ink">Área responsável</span>
              <input v-model="lote.area" required list="areas-conhecidas" type="text" placeholder="Ex.: Nefrologia" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" />
              <datalist id="areas-conhecidas">
                <option>Nefrologia</option>
                <option>Oncologia</option>
                <option>Cardiologia</option>
              </datalist>
            </label>
            <label class="block">
              <span class="text-xs font-bold text-ink">Motivo</span>
              <input v-model="lote.motivo" required type="text" placeholder="Ex.: paciente em hemodiálise" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" />
            </label>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <label class="block">
              <span class="text-xs font-bold text-ink">Vale para</span>
              <select v-model="lote.unidade" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink">
                <option value="">Todas as unidades</option>
                <option v-for="r in dados.regras.filter((x) => x.unidade !== '*')" :key="r.unidade" :value="r.unidade">{{ nomeUnidade(r.unidade) }}</option>
              </select>
            </label>
            <label class="block">
              <span class="text-xs font-bold text-ink">Válido até</span>
              <input v-model="lote.validade" type="date" :min="hojeIso()" class="mt-1 block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink" />
            </label>
          </div>
          <div class="flex flex-wrap items-center gap-2 self-end">
            <button type="submit" :disabled="salvando" class="rounded-md bg-acao px-3 py-1.5 text-sm font-bold text-white hover:bg-acao-hover disabled:opacity-60">Incluir na lista</button>
            <button type="button" @click="lote.aberto = false" class="rounded-md px-3 py-1.5 text-sm font-semibold text-ink-muted hover:text-ink">Fechar</button>
            <span v-if="!lote.validade" class="text-xs text-ink-muted">Sem validade, a inclusão vale até alguém remover.</span>
          </div>
          <div v-if="resultadoLote" class="md:col-span-2 rounded-md bg-surface p-3 text-sm ring-1 ring-line" role="status">
            <p class="font-bold text-ink">{{ resultadoLote.incluidos.length }} {{ resultadoLote.incluidos.length === 1 ? 'paciente incluído' : 'pacientes incluídos' }}.</p>
            <ul class="mt-1 space-y-0.5 text-xs text-ink-muted">
              <li v-if="resultadoLote.ja_na_lista.length">Já estavam na lista: <span class="tabular">{{ resultadoLote.ja_na_lista.join(', ') }}</span></li>
              <li v-if="resultadoLote.sem_solicitacao.length">Sem solicitação pendente no AGHU agora (entram na fila quando tiverem): <span class="tabular">{{ resultadoLote.sem_solicitacao.join(', ') }}</span></li>
              <li v-if="resultadoLote.invalidos.length" class="text-separar-ink">Ignorados por não parecerem prontuário: {{ resultadoLote.invalidos.join(', ') }}</li>
            </ul>
          </div>
        </form>

        <table class="w-full text-sm">
          <thead class="text-left text-xs font-bold text-ink-muted border-y border-line bg-surface-sunken whitespace-nowrap">
            <tr>
              <th scope="col" class="pl-5 pr-2 py-2">Paciente</th>
              <th scope="col" class="px-2 py-2">Área</th>
              <th scope="col" class="px-2 py-2">Motivo</th>
              <th scope="col" class="px-2 py-2">Vale para</th>
              <th scope="col" class="px-2 py-2">Validade</th>
              <th scope="col" class="px-2 py-2">Incluído por</th>
              <th scope="col" class="pl-2 pr-5 py-2"><span class="sr-only">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in dados.prioritarios" :key="p.id" class="border-b border-line last:border-0">
              <td class="pl-5 pr-2 py-2.5">
                <p class="font-semibold text-ink">{{ p.nome ?? 'Sem solicitação no extrato atual' }}</p>
                <p class="tabular text-xs text-ink-muted">Pront. {{ p.prontuario }}</p>
              </td>
              <td class="px-2 py-2.5 font-bold text-lista-ink">{{ p.area }}</td>
              <td class="px-2 py-2.5 text-ink">{{ p.motivo }}</td>
              <td class="px-2 py-2.5 text-ink-muted">{{ p.unidade ? nomeUnidade(p.unidade) : 'Todas as unidades' }}</td>
              <td class="tabular px-2 py-2.5" :class="venceEmBreve(p.validade) ? 'font-bold text-espera-ink' : 'text-ink-muted'">
                {{ p.validade ? `até ${dataCompleta(`${p.validade}T12:00:00`)}` : 'sem prazo' }}
              </td>
              <td class="px-2 py-2.5 text-ink-muted">
                <template v-if="p.exemplo">Exemplo</template>
                <template v-else>{{ p.criado_por }} · {{ dataHora(p.criado_em) }}</template>
              </td>
              <td class="pl-2 pr-5 py-2.5 text-right whitespace-nowrap">
                <span v-if="confirmando === p.id" class="inline-flex items-center gap-1">
                  <span class="text-xs text-ink">Remover da lista?</span>
                  <button type="button" @click="remover(p)" :disabled="removendo" class="rounded bg-separar-ink px-2 py-1 text-xs font-bold text-white hover:opacity-90 disabled:opacity-60">Confirmar</button>
                  <button type="button" @click="confirmando = null" class="rounded px-2 py-1 text-xs font-semibold text-ink-muted hover:text-ink">Cancelar</button>
                </span>
                <button v-else type="button" @click="confirmando = p.id ?? null" :aria-label="`Remover ${p.nome ?? 'prontuário ' + p.prontuario} da lista de prioridade`" class="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold text-ink-muted hover:bg-separar-bg hover:text-separar-ink">
                  <TrashIcon class="h-3.5 w-3.5" aria-hidden="true" /> Remover
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section id="sec-preparo" class="rounded-lg bg-surface ring-1 ring-line overflow-hidden scroll-mt-4">
        <div class="px-5 pt-4 pb-3 flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h2 class="text-base font-extrabold text-ink">Preparo por exame</h2>
            <p class="text-xs text-ink-muted mt-0.5">
              O marcador vê o preparo no detalhe do paciente e na mensagem para o WhatsApp (RF020).
              Os textos de exemplo não entram na mensagem até a UDI revisar e salvar.
            </p>
          </div>
          <label class="flex items-center gap-2 text-xs font-bold text-ink-muted">
            Adicionar para
            <select v-model="novoPreparo" @change="editarPreparo(novoPreparo)" class="rounded-md border border-campo bg-surface px-2 py-1.5 text-xs text-ink">
              <option value="">escolha um exame…</option>
              <option v-for="e in dados.exames.filter((x) => !x.preparo)" :key="e.codigo" :value="e.codigo">{{ exameCurto(e.nome) }}</option>
            </select>
          </label>
        </div>
        <table class="w-full text-sm">
          <thead class="text-left text-xs font-bold text-ink-muted border-y border-line bg-surface-sunken whitespace-nowrap">
            <tr>
              <th scope="col" class="pl-5 pr-2 py-2 w-[16rem]">Exame</th>
              <th scope="col" class="px-2 py-2">Orientação ao paciente</th>
              <th scope="col" class="pl-2 pr-5 py-2 w-[9rem]"><span class="sr-only">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in examesComPreparo" :key="e.codigo" class="border-b border-line last:border-0 align-top">
              <td class="pl-5 pr-2 py-2.5">
                <p class="font-semibold text-ink">{{ exameCurto(e.nome) }}</p>
                <p class="text-xs text-ink-muted">{{ nomeUnidade(e.unidade) }}</p>
              </td>
              <td class="px-2 py-2.5">
                <form v-if="editandoPreparo === e.codigo" @submit.prevent="salvarPreparo(e.codigo)" class="space-y-2">
                  <textarea v-model="textoPreparo" rows="3" :aria-label="`Preparo de ${exameCurto(e.nome)}`" class="block w-full rounded-md border border-campo bg-surface px-2.5 py-1.5 text-sm text-ink"></textarea>
                  <div class="flex items-center gap-2">
                    <button type="submit" :disabled="salvando" class="rounded-md bg-acao px-3 py-1 text-xs font-bold text-white hover:bg-acao-hover disabled:opacity-60">Salvar como revisado</button>
                    <button type="button" @click="editandoPreparo = null" class="text-xs font-semibold text-ink-muted hover:text-ink">Cancelar</button>
                    <span class="text-xs text-ink-muted">Deixe vazio para remover.</span>
                  </div>
                </form>
                <template v-else>
                  <p class="text-ink text-pretty">{{ e.preparo?.texto }}</p>
                  <p class="mt-0.5 text-xs text-ink-muted">
                    <template v-if="e.preparo?.exemplo">Texto de exemplo, a validar com a UDI</template>
                    <template v-else>Revisado por {{ e.preparo?.atualizado_por }} · {{ dataHora(e.preparo?.atualizado_em) }}</template>
                  </p>
                </template>
              </td>
              <td class="pl-2 pr-5 py-2.5 text-right">
                <button v-if="editandoPreparo !== e.codigo" type="button" @click="editarPreparo(e.codigo)" class="text-xs font-bold text-acao underline underline-offset-2 hover:text-acao-hover">Editar</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section id="sec-combinacoes" class="rounded-lg bg-surface ring-1 ring-line overflow-hidden scroll-mt-4">
        <div class="px-5 pt-4 pb-3">
          <h2 class="text-base font-extrabold text-ink">Combinações de exames</h2>
          <p class="text-xs text-ink-muted mt-0.5">Regras de exemplo montadas a partir dos pares mais frequentes no extrato. A UDI precisa validar cada uma.</p>
        </div>
        <table class="w-full text-sm">
          <thead class="text-left text-xs font-bold text-ink-muted border-y border-line bg-surface-sunken whitespace-nowrap">
            <tr>
              <th scope="col" class="pl-5 pr-2 py-2">Exames</th>
              <th scope="col" class="px-2 py-2">Tipo</th>
              <th scope="col" class="pl-2 pr-5 py-2">Orientação ao marcador</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in dados.combinacoes" :key="c.id" class="border-b border-line last:border-0 align-top">
              <td class="pl-5 pr-2 py-2.5 text-ink">{{ exameCurto(c.exame_a) }} <span class="text-ink-muted">+</span> {{ exameCurto(c.exame_b) }}</td>
              <td class="px-2 py-2.5"><AlertaCombinacao :alerta="{ tipo: c.tipo, orientacao: c.orientacao, exames: [c.exame_a, c.exame_b] }" /></td>
              <td class="pl-2 pr-5 py-2.5 text-ink">{{ c.orientacao }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section id="sec-historico" class="rounded-lg bg-surface ring-1 ring-line overflow-hidden scroll-mt-4">
        <div class="px-5 pt-4 pb-3">
          <h2 class="text-base font-extrabold text-ink">Histórico de alterações</h2>
          <p class="text-xs text-ink-muted mt-0.5">Regras, lista de prioridade, vagas e preparo. Vem da trilha de auditoria, que não pode ser editada.</p>
        </div>
        <table v-if="auditoria.length" class="w-full text-sm">
          <thead class="text-left text-xs font-bold text-ink-muted border-y border-line bg-surface-sunken whitespace-nowrap">
            <tr>
              <th scope="col" class="pl-5 pr-2 py-2 w-[8rem]">Quando</th>
              <th scope="col" class="px-2 py-2 w-[9rem]">Quem</th>
              <th scope="col" class="px-2 py-2 w-[13rem]">O quê</th>
              <th scope="col" class="pl-2 pr-5 py-2">Detalhe</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in auditoria" :key="a.id" class="border-b border-line last:border-0 align-top">
              <td class="tabular pl-5 pr-2 py-2 text-ink-muted">{{ dataHora(a.quando) }}</td>
              <td class="px-2 py-2 text-ink">{{ a.usuario }}</td>
              <td class="px-2 py-2 font-semibold text-ink">{{ ROTULO_ACAO[a.acao] ?? a.acao }}</td>
              <td class="pl-2 pr-5 py-2 text-ink-muted">{{ descreverAuditoria(a) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="px-5 pb-4 text-sm text-ink-muted">Nenhuma alteração registrada ainda. As regras, listas e preparos atuais são os de exemplo.</p>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useToast } from 'vue-toastification';
import { ChevronUpIcon, ChevronDownIcon, TrashIcon, UserPlusIcon } from '@heroicons/vue/20/solid';
import api from '../services/api';
import AlertaCombinacao from '../components/AlertaCombinacao.vue';
import {
  ROTULO_CRITERIO, dataCompleta, dataHora, exameCurto, hojeIso, nomeUnidade,
  type Preparo, type Prioridade, type Regra, type TipoCombinacao,
} from '../lib/agenda';

interface ExameCatalogo {
  codigo: string;
  nome: string;
  unidade: string;
  preparo: Preparo | null;
  vagas: number | null;
}

interface RegraExame extends Regra {
  codigo_exame: string;
  exame: { codigo: string; nome: string; unidade: string } | null;
}

interface RespostaRegras {
  criterios_disponiveis: string[];
  regras: Regra[];
  regras_exame: RegraExame[];
  prioritarios: Prioridade[];
  combinacoes: { id: number; exame_a: string; exame_b: string; tipo: TipoCombinacao; orientacao: string; exemplo: boolean }[];
  exames: ExameCatalogo[];
}

interface RegistroAuditoria {
  id: number;
  quando: string;
  usuario: string;
  acao: string;
  recurso: string;
  antes: Record<string, any> | null;
  depois: Record<string, any> | null;
}

interface ResultadoLote {
  incluidos: string[];
  ja_na_lista: string[];
  sem_solicitacao: string[];
  invalidos: string[];
}

const SECOES = [
  { id: 'sec-criterios', rotulo: 'Critérios' },
  { id: 'sec-lista', rotulo: 'Lista de prioridade' },
  { id: 'sec-preparo', rotulo: 'Preparo' },
  { id: 'sec-combinacoes', rotulo: 'Combinações' },
  { id: 'sec-historico', rotulo: 'Histórico' },
];

const ROTULO_ACAO: Record<string, string> = {
  ALTERAR_REGRA_PRIORIDADE: 'Regra alterada',
  CRIAR_REGRA_EXAME: 'Regra de exame criada',
  REMOVER_REGRA_EXAME: 'Regra de exame removida',
  INCLUIR_PACIENTE_PRIORITARIO: 'Incluído na lista',
  REMOVER_PACIENTE_PRIORITARIO: 'Removido da lista',
  ALTERAR_VAGAS_EXAME: 'Vagas alteradas',
  ALTERAR_PREPARO_EXAME: 'Preparo alterado',
};

const toast = useToast();
const dados = ref<RespostaRegras | null>(null);
const auditoria = ref<RegistroAuditoria[]>([]);
const carregando = ref(false);
const salvando = ref(false);
const edicao = ref<Regra | null>(null);
const original = ref<Regra | null>(null);
const novaRegraExame = ref('');
const novoPreparo = ref('');
const editandoPreparo = ref<string | null>(null);
const textoPreparo = ref('');
const lote = reactive({ aberto: false, prontuarios: '', area: '', motivo: '', unidade: '', validade: '' });
const resultadoLote = ref<ResultadoLote | null>(null);

const alterada = computed(() =>
  !!edicao.value && !!original.value &&
  (edicao.value.criterios.join() !== original.value.criterios.join() ||
    edicao.value.espera_limite_dias !== original.value.espera_limite_dias),
);

const examesPorCodigo = computed(() => new Map((dados.value?.exames ?? []).map((e) => [e.codigo, e])));

const examesSemRegra = computed(() => {
  const comRegra = new Set((dados.value?.regras_exame ?? []).map((r) => r.codigo_exame));
  return (dados.value?.exames ?? []).filter((e) => !comRegra.has(e.codigo));
});

const examesComPreparo = computed(() =>
  (dados.value?.exames ?? []).filter((e) => e.preparo || e.codigo === editandoPreparo.value),
);

const contagemColada = computed(() => {
  const tokens = lote.prontuarios.split(/[\s,;]+/).filter(Boolean);
  const unicos = new Set(tokens.filter((t) => /^\d{4,12}$/.test(t)));
  if (!tokens.length) return '';
  return `${unicos.size} ${unicos.size === 1 ? 'prontuário reconhecido' : 'prontuários reconhecidos'}`;
});

const erro = ref('');
const confirmando = ref<number | null>(null);
const removendo = ref(false);

function ehRegraDeExame(unidade: string) {
  return unidade.startsWith('EXAME:');
}

function codigoDaRegra(r: Regra) {
  return r.unidade.slice('EXAME:'.length);
}

function exameDaRegra(r: Regra) {
  return examesPorCodigo.value.get(codigoDaRegra(r));
}

function nomeDaRegra(r: Regra) {
  if (r.unidade === '*') return 'Padrão (todas)';
  if (ehRegraDeExame(r.unidade)) {
    const exame = exameDaRegra(r);
    return exame ? exameCurto(exame.nome) : codigoDaRegra(r);
  }
  return nomeUnidade(r.unidade);
}

function nomeDoRecurso(recurso: string) {
  const [tipo, ...resto] = recurso.split(':');
  const valor = resto.join(':');
  if (tipo === 'exame') return exameCurto(examesPorCodigo.value.get(valor)?.nome ?? valor);
  if (tipo === 'regra') return nomeDaRegra({ unidade: valor } as Regra);
  if (tipo === 'prontuario') return `Pront. ${valor}`;
  return recurso;
}

function descreverAuditoria(a: RegistroAuditoria) {
  const alvo = nomeDoRecurso(a.recurso);
  const antes = a.antes ?? {};
  const depois = a.depois ?? {};
  switch (a.acao) {
    case 'ALTERAR_REGRA_PRIORIDADE': {
      const ordem = (lista?: string[]) => (lista ?? []).map((c) => ROTULO_CRITERIO[c] ?? c).join(' › ');
      const mudouOrdem = (antes.criterios ?? []).join() !== (depois.criterios ?? []).join();
      const mudouLimite = antes.espera_limite_dias !== depois.espera_limite_dias;
      const partes = [`${alvo} v${antes.versao} → v${depois.versao}`];
      if (mudouOrdem) partes.push(`ordem: ${ordem(depois.criterios)}`);
      if (mudouLimite) partes.push(`limite ${antes.espera_limite_dias} → ${depois.espera_limite_dias} dias`);
      return partes.join(' · ');
    }
    case 'INCLUIR_PACIENTE_PRIORITARIO':
      return `${alvo} · ${depois.area}${depois.validade ? ` até ${dataCompleta(`${depois.validade}T12:00:00`)}` : ''}${depois.em_lote ? ' · lista colada' : ''}`;
    case 'REMOVER_PACIENTE_PRIORITARIO':
      return `${alvo} · ${antes.area ?? ''}`;
    case 'ALTERAR_VAGAS_EXAME':
      return `${alvo}: ${antes.vagas ?? '—'} → ${depois.vagas ?? '—'}`;
    case 'ALTERAR_PREPARO_EXAME':
      return depois.texto ? `${alvo}: texto revisado` : `${alvo}: preparo removido`;
    default:
      return alvo;
  }
}

function venceEmBreve(validade: string | null | undefined) {
  if (!validade) return false;
  const dias = (new Date(`${validade}T12:00:00`).getTime() - Date.now()) / 86400000;
  return dias <= 7;
}

function trocarRegra(r: Regra) {
  if (alterada.value && !window.confirm('Descartar as alterações não salvas desta regra?')) return;
  escolher(r);
}

function escolher(r: Regra) {
  original.value = r;
  edicao.value = { ...r, criterios: [...r.criterios] };
}

function desfazer() {
  if (original.value) escolher(original.value);
}

function mover(i: number, delta: number) {
  if (!edicao.value) return;
  const lista = edicao.value.criterios;
  const j = i + delta;
  [lista[i], lista[j]] = [lista[j], lista[i]];
}

async function carregarAuditoria() {
  try {
    auditoria.value = (await api.get<RegistroAuditoria[]>('/api/regras/auditoria')).data;
  } catch {
    auditoria.value = [];
  }
}

async function carregar(manterUnidade?: string) {
  carregando.value = true;
  erro.value = '';
  try {
    dados.value = (await api.get<RespostaRegras>('/api/regras')).data;
    const todas = [...dados.value.regras, ...dados.value.regras_exame];
    const alvo = todas.find((r) => r.unidade === manterUnidade) ?? dados.value.regras[0];
    if (alvo) escolher(alvo);
    await carregarAuditoria();
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? 'Verifique a conexão com o servidor e tente de novo.';
  } finally {
    carregando.value = false;
  }
}

async function salvar() {
  if (!edicao.value) return;
  salvando.value = true;
  try {
    const { data } = await api.put('/api/regras', {
      unidade: edicao.value.unidade,
      criterios: edicao.value.criterios,
      espera_limite_dias: edicao.value.espera_limite_dias,
    });
    toast.success(`Regra salva como versão ${data.versao}. A fila já usa a nova ordem.`);
    await carregar(edicao.value.unidade);
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível salvar a regra.');
  } finally {
    salvando.value = false;
  }
}

async function criarRegraExame() {
  const exame = examesPorCodigo.value.get(novaRegraExame.value);
  if (!exame || !dados.value) return;
  const base = dados.value.regras.find((r) => r.unidade === exame.unidade) ?? dados.value.regras[0];
  salvando.value = true;
  try {
    const { data } = await api.post<{ unidade: string }>('/api/regras/exame', {
      codigo_exame: exame.codigo,
      criterios: base?.criterios ?? ['LISTA_PRIORIDADE', 'ESPERA_LIMITE', 'ORDEM_CHEGADA'],
      espera_limite_dias: base?.espera_limite_dias ?? 60,
    });
    toast.success(`${exameCurto(exame.nome)} agora tem regra própria. Ajuste a ordem e salve.`);
    novaRegraExame.value = '';
    await carregar(data.unidade);
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível criar a regra.');
  } finally {
    salvando.value = false;
  }
}

async function removerRegraExame() {
  if (!edicao.value || !ehRegraDeExame(edicao.value.unidade)) return;
  const nome = nomeDaRegra(edicao.value);
  if (!window.confirm(`Remover a regra própria de ${nome}? A fila desse exame volta a usar a regra da unidade.`)) return;
  try {
    await api.delete(`/api/regras/exame/${encodeURIComponent(codigoDaRegra(edicao.value))}`);
    toast.success(`${nome} voltou a usar a regra da unidade.`);
    await carregar();
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível remover a regra.');
  }
}

function abrirLote() {
  lote.aberto = true;
  resultadoLote.value = null;
}

async function incluirLote() {
  salvando.value = true;
  try {
    const { data } = await api.post<ResultadoLote>('/api/regras/prioritarios/lote', {
      prontuarios: lote.prontuarios,
      area: lote.area,
      motivo: lote.motivo,
      unidade: lote.unidade || null,
      validade: lote.validade || null,
    });
    resultadoLote.value = data;
    if (data.incluidos.length) lote.prontuarios = '';
    toast.success(`${data.incluidos.length} incluídos na lista de prioridade.`);
    await carregar(edicao.value?.unidade);
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível incluir. Confira a lista e tente de novo.');
  } finally {
    salvando.value = false;
  }
}

function editarPreparo(codigo: string) {
  if (!codigo) return;
  editandoPreparo.value = codigo;
  textoPreparo.value = examesPorCodigo.value.get(codigo)?.preparo?.texto ?? '';
  novoPreparo.value = '';
}

async function salvarPreparo(codigo: string) {
  salvando.value = true;
  try {
    await api.put('/api/preparos', { codigo_exame: codigo, texto: textoPreparo.value });
    editandoPreparo.value = null;
    toast.success('Preparo salvo. Já aparece para o marcador e na mensagem ao paciente.');
    await carregar(edicao.value?.unidade);
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível salvar o preparo.');
  } finally {
    salvando.value = false;
  }
}

async function remover(p: Prioridade) {
  removendo.value = true;
  try {
    await api.delete(`/api/regras/prioritarios/${p.id}`);
    toast.success(`${p.nome ?? `Prontuário ${p.prontuario}`} saiu da lista de prioridade.`);
    confirmando.value = null;
    await carregar(edicao.value?.unidade);
  } catch (e: any) {
    toast.error(e?.response?.data?.detail ?? 'Não foi possível remover. Tente de novo.');
  } finally {
    removendo.value = false;
  }
}

onMounted(() => carregar());
</script>
