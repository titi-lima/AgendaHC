export type TipoMotivo = 'LISTA' | 'ESPERA' | 'CHEGADA' | 'FINAL';
export type TipoCombinacao = 'SEPARAR' | 'ORDEM' | 'AGRUPAR' | 'DUPLICIDADE';
export type Aba = 'a_chamar' | 'em_contato' | 'sem_contato' | 'finalizados';
export type StatusItem = 'PENDENTE' | 'EM_CONTATO' | 'SEM_CONTATO' | 'AGENDADO' | 'CANCELADO';

export interface Motivo {
  tipo: TipoMotivo;
  rotulo: string;
  detalhe: string;
}

export interface Alerta {
  tipo: TipoCombinacao;
  orientacao: string;
  exames: string[];
  solicitacoes?: string[];
  exemplo?: boolean;
}

export interface StatusInfo {
  status: StatusItem;
  data_agendada: string | null;
  observacao: string | null;
  usuario: string;
  criado_em: string;
  tentativas?: number;
  horas?: number | null;
  prazo_vencido?: boolean;
  exemplo?: boolean;
}

export interface Preparo {
  texto: string;
  exemplo: boolean;
  atualizado_por?: string;
  atualizado_em?: string | null;
}

export interface ItemFila {
  codigo_solicitacao: string;
  codigo_exame: string;
  nome_exame: string;
  unidade: string;
  data_solicitacao: string;
  espera_dias: number;
  status: StatusItem;
  status_info: StatusInfo | null;
  na_unidade?: boolean;
  solicitante?: string;
  quantidade?: number;
  preparo?: Preparo | null;
  vagas?: number | null;
}

export interface Prioridade {
  id?: number;
  prontuario: string;
  area: string;
  motivo: string;
  unidade: string | null;
  validade?: string | null;
  exemplo?: boolean;
  nome?: string | null;
  criado_por?: string;
  criado_em?: string | null;
}

export interface GrupoFila {
  chave: string;
  prontuario: string;
  nome: string;
  sem_prontuario: boolean;
  posicao: number | null;
  motivo: Motivo;
  prioridade: Prioridade | null;
  espera_dias: number;
  aba: Aba;
  contato: StatusInfo | null;
  tentativas: number;
  registrado_em?: string;
  itens: ItemFila[];
  alertas: Alerta[];
}

export interface Regra {
  unidade: string;
  criterios: string[];
  espera_limite_dias: number;
  versao: number;
  exemplo?: boolean;
  atualizado_por?: string;
  atualizado_em?: string | null;
}

export const ROTULO_CRITERIO: Record<string, string> = {
  LISTA_PRIORIDADE: 'Lista de prioridade',
  ESPERA_LIMITE: 'Espera acima do limite da unidade',
  ORDEM_CHEGADA: 'Ordem de chegada',
};

export const ROTULO_STATUS: Record<StatusItem, string> = {
  PENDENTE: 'Pendente',
  EM_CONTATO: 'Em contato',
  SEM_CONTATO: 'Sem contato',
  AGENDADO: 'Agendado no AGHU',
  CANCELADO: 'Cancelado',
};

export const ROTULO_COMBINACAO: Record<TipoCombinacao, string> = {
  SEPARAR: 'Não no mesmo dia',
  ORDEM: 'Ordem obrigatória',
  AGRUPAR: 'Agendar junto',
  DUPLICIDADE: 'Pedido repetido',
};

export const ROTULO_ABA: Record<Aba, string> = {
  a_chamar: 'A chamar',
  em_contato: 'Em contato',
  sem_contato: 'Sem contato',
  finalizados: 'Finalizados hoje',
};

export function primeiroNome(nome: string): string {
  const primeiro = nome.trim().split(/\s+/)[0] ?? '';
  return primeiro.charAt(0) + primeiro.slice(1).toLowerCase();
}

function celulaCsv(valor: string | number | null | undefined): string {
  const texto = valor === null || valor === undefined ? '' : String(valor);
  return /[";\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
}

export function baixarCsv(nomeArquivo: string, linhas: (string | number | null | undefined)[][]) {
  const conteudo = '\ufeff' + linhas.map((l) => l.map(celulaCsv).join(';')).join('\r\n');
  const url = URL.createObjectURL(new Blob([conteudo], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = nomeArquivo;
  link.click();
  URL.revokeObjectURL(url);
}

export function hojeIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const CORRECOES_AGHU: [RegExp, string][] = [
  [/RESSON[ÂA]NIA\b/g, 'RESSONÂNCIA'],
  [/RENALCOM\b/g, 'RENAL COM'],
  [/MIOCARCARDICA\b/g, 'MIOCÁRDICA'],
  [/ABDOMEINFERIOR\b/g, 'ABDOME INFERIOR'],
  [/TOMOGRADIA\b/g, 'TOMOGRAFIA'],
  [/\bRESSONANCIA\b/g, 'RESSONÂNCIA'],
  [/\bMAGNETICA\b/g, 'MAGNÉTICA'],
  [/\bMIOCARDIO\b/g, 'MIOCÁRDIO'],
  [/\bTORAX\b/g, 'TÓRAX'],
  [/\bSEDACAO\b/g, 'SEDAÇÃO'],
  [/\bESOFAGICO\b/g, 'ESOFÁGICO'],
  [/\bLIQUIDO\b/g, 'LÍQUIDO'],
  [/\bLINFATICAS\b/g, 'LINFÁTICAS'],
  [/\bREGIAO\b/g, 'REGIÃO'],
  [/\bPROSTATA\b/g, 'PRÓSTATA'],
  [/-\s{2,}/g, '- '],
];

function corrigirAghu(texto: string): string {
  return CORRECOES_AGHU.reduce((t, [padrao, correto]) => t.replace(padrao, correto), texto.toUpperCase());
}

export function nomeUnidade(unidade: string | null | undefined): string {
  if (!unidade || unidade === '*') return 'Todas as unidades';
  return corrigirAghu(unidade.replace(/^UDI:\s*/, '')).toLowerCase().replace(/(^|\s)\S/g, (l) => l.toUpperCase());
}

function paraData(iso: string): Date {
  return new Date(/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T12:00:00` : iso);
}

export function dataCurta(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = paraData(iso);
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

export function dataCompleta(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = paraData(iso);
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function exameCurto(nome: string): string {
  const corrigido = corrigirAghu(nome);
  return corrigido.charAt(0) + corrigido.slice(1).toLowerCase();
}

export function horaCurta(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  if (d.toDateString() === new Date().toDateString()) return `hoje ${hora}`;
  return `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${hora}`;
}
