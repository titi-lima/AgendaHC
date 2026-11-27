from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agenda import (
    CombinacaoExames,
    PacientePrioritario,
    PreparoExame,
    RegraPrioridade,
    TratamentoSolicitacao,
    VagasExame,
)

CRITERIOS_VALIDOS = ("LISTA_PRIORIDADE", "ESPERA_LIMITE", "ORDEM_CHEGADA")
CRITERIOS_PADRAO = ["LISTA_PRIORIDADE", "ESPERA_LIMITE", "ORDEM_CHEGADA"]
STATUS_VALIDOS = ("EM_CONTATO", "SEM_CONTATO", "AGENDADO", "CANCELADO", "PENDENTE")
STATUS_QUE_SAEM_DA_FILA = ("AGENDADO", "CANCELADO")
STATUS_DE_CONTATO = ("EM_CONTATO", "SEM_CONTATO")
STATUS_EM_LOTE = ("EM_CONTATO", "SEM_CONTATO", "CANCELADO", "PENDENTE")
PRAZO_RESPOSTA_HORAS = 24
ABAS = ("a_chamar", "em_contato", "sem_contato", "finalizados")
REGRA_GERAL = "*"
PREFIXO_REGRA_EXAME = "EXAME:"

Chave = Tuple[str, str]


def chave_item(item: Dict[str, Any]) -> Chave:
    return (item["codigo_solicitacao"], item["codigo_exame"])


def chave_paciente(item: Dict[str, Any]) -> str:
    return item["prontuario"] or f"sem-prontuario:{item['codigo_solicitacao']}"


def chave_regra_exame(codigo_exame: str) -> str:
    return f"{PREFIXO_REGRA_EXAME}{codigo_exame}"


def eh_regra_de_exame(chave: str) -> bool:
    return chave.startswith(PREFIXO_REGRA_EXAME)


def agora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def dias_de_espera(data_iso: str, hoje: date) -> int:
    try:
        return max((hoje - datetime.fromisoformat(data_iso).date()).days, 0)
    except ValueError:
        return 0


def horas_desde(iso_utc: Optional[str], agora: datetime) -> Optional[int]:
    if not iso_utc:
        return None
    try:
        momento = datetime.fromisoformat(iso_utc).replace(tzinfo=None)
    except ValueError:
        return None
    return max(int((agora - momento).total_seconds() // 3600), 0)


def data_local(iso_utc: Optional[str]) -> Optional[date]:
    if not iso_utc:
        return None
    try:
        return datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc).astimezone().date()
    except ValueError:
        return None


def regra_da_unidade(
    regras: Dict[str, Dict[str, Any]], unidade: Optional[str], exame: Optional[str] = None
) -> Dict[str, Any]:
    if exame and chave_regra_exame(exame) in regras:
        return regras[chave_regra_exame(exame)]
    regra = regras.get(unidade or REGRA_GERAL) or regras.get(REGRA_GERAL)
    return regra or {"unidade": REGRA_GERAL, "criterios": CRITERIOS_PADRAO, "espera_limite_dias": 60, "versao": 0}


def prioridade_do_paciente(
    prontuario: str, unidade: Optional[str], prioritarios: Iterable[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    for p in prioritarios:
        if p["prontuario"] == prontuario and (not p.get("unidade") or not unidade or p["unidade"] == unidade):
            return p
    return None


def _chave_ordenacao(item, regra, prioritario) -> Tuple[tuple, Dict[str, Any]]:
    valores = []
    motivo = None
    for criterio in list(regra["criterios"]) + ["ORDEM_CHEGADA"]:
        if criterio == "LISTA_PRIORIDADE":
            atende = prioritario is not None
            valores.append(0 if atende else 1)
            if atende and motivo is None:
                motivo = {
                    "tipo": "LISTA",
                    "rotulo": f"Lista da {prioritario['area']}",
                    "detalhe": prioritario["motivo"] + (" (lista de exemplo)" if prioritario.get("exemplo") else ""),
                }
        elif criterio == "ESPERA_LIMITE":
            atende = item["espera_dias"] > regra["espera_limite_dias"]
            valores.append(0 if atende else 1)
            if atende and motivo is None:
                motivo = {
                    "tipo": "ESPERA",
                    "rotulo": f"Espera > {regra['espera_limite_dias']} dias",
                    "detalhe": f"Aguarda há {item['espera_dias']} dias",
                }
        elif criterio == "ORDEM_CHEGADA":
            valores.append(item["data_solicitacao"])
    valores.append(item["codigo_solicitacao"])
    if motivo is None:
        motivo = {
            "tipo": "CHEGADA",
            "rotulo": "Ordem de chegada",
            "detalhe": f"Solicitado há {item['espera_dias']} dias",
        }
    return tuple(valores), motivo


def detectar_combinacoes(nomes_exames: Iterable[str], combinacoes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    presentes = set(nomes_exames)
    alertas = []
    for c in combinacoes:
        if c["exame_a"] in presentes and c["exame_b"] in presentes:
            alertas.append({
                "tipo": c["tipo"],
                "orientacao": c["orientacao"],
                "exames": [c["exame_a"], c["exame_b"]],
                "exemplo": c.get("exemplo", False),
            })
    return alertas


def detectar_duplicidades(itens: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    por_exame: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in itens:
        por_exame[item["codigo_exame"]].append(item)
    alertas = []
    for lista in por_exame.values():
        solicitacoes = sorted({i["codigo_solicitacao"] for i in lista})
        if len(solicitacoes) > 1:
            alertas.append({
                "tipo": "DUPLICIDADE",
                "orientacao": (
                    f"Mesmo exame em {len(solicitacoes)} solicitações ({', '.join(solicitacoes)}). "
                    "Confirme com o solicitante se são pedidos distintos antes de marcar os dois."
                ),
                "exames": [lista[0]["nome_exame"]],
                "solicitacoes": solicitacoes,
                "exemplo": False,
            })
    return alertas


def alertas_do_paciente(itens_ativos: List[Dict[str, Any]], combinacoes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return detectar_duplicidades(itens_ativos) + detectar_combinacoes(
        (i["nome_exame"] for i in itens_ativos), combinacoes
    )


def agrupar_repetidos(itens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unicos: Dict[Chave, Dict[str, Any]] = {}
    for item in itens:
        chave = chave_item(item)
        if chave in unicos:
            unicos[chave]["quantidade"] += 1
        else:
            unicos[chave] = {**item, "quantidade": 1}
    return list(unicos.values())


def consolidar_tratamentos(tratamentos: Iterable[Dict[str, Any]]) -> Dict[Chave, Dict[str, Any]]:
    pilhas: Dict[Chave, List[Dict[str, Any]]] = defaultdict(list)
    for t in tratamentos:
        chave = (t["codigo_solicitacao"], t["codigo_exame"])
        if t.get("desfaz"):
            if pilhas[chave]:
                pilhas[chave].pop()
        else:
            pilhas[chave].append(t)
    status_atual: Dict[Chave, Dict[str, Any]] = {}
    for chave, pilha in pilhas.items():
        if not pilha:
            continue
        topo = pilha[-1]
        status_atual[chave] = {
            "status": topo["status"],
            "data_agendada": topo.get("data_agendada"),
            "observacao": topo.get("observacao"),
            "usuario": topo.get("usuario"),
            "criado_em": topo.get("criado_em"),
            "exemplo": topo.get("exemplo", False),
            "tentativas": sum(1 for t in pilha if t["status"] in STATUS_DE_CONTATO),
        }
    return status_atual


def info_status(st: Optional[Dict[str, Any]], agora: datetime) -> Optional[Dict[str, Any]]:
    if not st:
        return None
    horas = horas_desde(st.get("criado_em"), agora)
    return {
        **st,
        "tentativas": st.get("tentativas", 0),
        "horas": horas,
        "prazo_vencido": st["status"] == "EM_CONTATO" and horas is not None and horas >= PRAZO_RESPOSTA_HORAS,
    }


def aba_do_paciente(itens_no_escopo: List[Dict[str, Any]]) -> str:
    status = {i["status"] for i in itens_no_escopo}
    if "EM_CONTATO" in status:
        return "em_contato"
    if "SEM_CONTATO" in status:
        return "sem_contato"
    return "a_chamar"


def _sem_dados_do_paciente(item: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in item.items() if k not in ("prontuario", "nome")}


def ranquear_fila(
    itens: List[Dict[str, Any]],
    status_atual: Dict[Chave, Dict[str, Any]],
    prioritarios: List[Dict[str, Any]],
    regras: Dict[str, Dict[str, Any]],
    combinacoes: List[Dict[str, Any]],
    hoje: date,
    unidade: Optional[str] = None,
    exame: Optional[str] = None,
    aba: Optional[str] = None,
    agora: Optional[datetime] = None,
) -> Dict[str, Any]:
    agora = agora or agora_utc()
    regra = regra_da_unidade(regras, unidade, exame)
    ativos_por_paciente: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    finais_por_paciente: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    exames_da_unidade: Dict[str, Dict[str, Any]] = {}
    for bruto in agrupar_repetidos(itens):
        st = status_atual.get(chave_item(bruto))
        item = dict(bruto)
        item["espera_dias"] = dias_de_espera(item["data_solicitacao"], hoje)
        item["status"] = st["status"] if st else "PENDENTE"
        item["status_info"] = info_status(st, agora)
        na_unidade = unidade is None or item["unidade"] == unidade
        item["na_unidade"] = na_unidade and (exame is None or item["codigo_exame"] == exame)
        if item["status"] in STATUS_QUE_SAEM_DA_FILA:
            finais_por_paciente[chave_paciente(item)].append(item)
            continue
        ativos_por_paciente[chave_paciente(item)].append(item)
        if na_unidade:
            e = exames_da_unidade.setdefault(
                item["codigo_exame"], {"codigo": item["codigo_exame"], "nome": item["nome_exame"], "pendentes": 0}
            )
            e["pendentes"] += 1

    grupos = []
    for chave, lista in ativos_por_paciente.items():
        no_escopo = [i for i in lista if i["na_unidade"]]
        if not no_escopo:
            continue
        prontuario = lista[0]["prontuario"]
        prioritario = prioridade_do_paciente(prontuario, unidade, prioritarios) if prontuario else None
        avaliados = [(*_chave_ordenacao(i, regra, prioritario), i) for i in no_escopo]
        avaliados.sort(key=lambda t: t[0])
        melhor_chave, motivo, _ = avaliados[0]
        ordenados = [t[2] for t in avaliados] + sorted(
            (i for i in lista if not i["na_unidade"]), key=lambda i: i["data_solicitacao"]
        )
        contatos = [i["status_info"] for i in no_escopo if i["status"] in STATUS_DE_CONTATO and i["status_info"]]
        grupos.append({
            "chave": chave,
            "prontuario": prontuario,
            "nome": lista[0]["nome"],
            "sem_prontuario": not prontuario,
            "motivo": motivo,
            "prioridade": prioritario,
            "espera_dias": max(i["espera_dias"] for i in no_escopo),
            "aba": aba_do_paciente(no_escopo),
            "contato": max(contatos, key=lambda c: c["horas"] if c["horas"] is not None else 0) if contatos else None,
            "tentativas": max((i["status_info"] or {}).get("tentativas", 0) for i in no_escopo),
            "itens": [_sem_dados_do_paciente(i) for i in ordenados],
            "alertas": alertas_do_paciente(lista, combinacoes),
            "_ordem": melhor_chave,
        })

    grupos.sort(key=lambda g: g["_ordem"])
    for posicao, g in enumerate(grupos, start=1):
        g["posicao"] = posicao
        del g["_ordem"]

    finalizados = []
    for chave, lista in finais_por_paciente.items():
        hoje_no_escopo = [
            i for i in lista
            if i["na_unidade"] and data_local((i["status_info"] or {}).get("criado_em")) == hoje
        ]
        if not hoje_no_escopo:
            continue
        hoje_no_escopo.sort(key=lambda i: i["status_info"]["criado_em"], reverse=True)
        ultimo = hoje_no_escopo[0]
        finalizados.append({
            "chave": chave,
            "prontuario": ultimo["prontuario"],
            "nome": ultimo["nome"],
            "sem_prontuario": not ultimo["prontuario"],
            "motivo": {"tipo": "FINAL", "rotulo": "Finalizado hoje", "detalhe": "Resultado registrado hoje"},
            "prioridade": None,
            "espera_dias": max(i["espera_dias"] for i in hoje_no_escopo),
            "aba": "finalizados",
            "contato": None,
            "tentativas": max(i["status_info"].get("tentativas", 0) for i in hoje_no_escopo),
            "itens": [_sem_dados_do_paciente(i) for i in hoje_no_escopo],
            "alertas": [],
            "posicao": None,
            "registrado_em": ultimo["status_info"]["criado_em"],
        })
    finalizados.sort(key=lambda g: g["registrado_em"], reverse=True)

    contagem_abas = Counter(g["aba"] for g in grupos)
    abas = {a: contagem_abas.get(a, 0) for a in ABAS[:3]}
    abas["finalizados"] = len(finalizados)
    abas["prazo_vencido"] = sum(1 for g in grupos if g["contato"] and g["contato"]["prazo_vencido"])

    esperas = [i["espera_dias"] for g in grupos for i in g["itens"] if i["na_unidade"]]
    resumo = {
        "pacientes": len(grupos),
        "exames": len(esperas),
        "prioritarios": sum(1 for g in grupos if g["motivo"]["tipo"] == "LISTA"),
        "com_alerta": sum(1 for g in grupos if any(a["tipo"] != "AGRUPAR" for a in g["alertas"])),
        "espera_mediana": int(median(esperas)) if esperas else 0,
        "espera_maxima": max(esperas) if esperas else 0,
        "abas": abas,
    }

    if aba == "finalizados":
        visiveis = finalizados
    elif aba == "em_contato":
        visiveis = sorted(
            (g for g in grupos if g["aba"] == aba),
            key=lambda g: -((g["contato"] or {}).get("horas") or 0),
        )
    elif aba in ABAS:
        visiveis = [g for g in grupos if g["aba"] == aba]
    else:
        visiveis = grupos

    return {
        "regra": regra,
        "grupos": visiveis,
        "resumo": resumo,
        "exames_unidade": sorted(exames_da_unidade.values(), key=lambda e: (-e["pendentes"], e["nome"])),
    }


def resumo_unidades(itens, status_atual) -> List[Dict[str, Any]]:
    contagem: Dict[str, Dict[str, Any]] = {}
    for item in agrupar_repetidos(itens):
        st = status_atual.get(chave_item(item))
        if st and st["status"] in STATUS_QUE_SAEM_DA_FILA:
            continue
        u = contagem.setdefault(item["unidade"], {"unidade": item["unidade"], "exames": 0, "pacientes": set()})
        u["exames"] += 1
        u["pacientes"].add(chave_paciente(item))
    return sorted(
        ({"unidade": u["unidade"], "exames": u["exames"], "pacientes": len(u["pacientes"])} for u in contagem.values()),
        key=lambda u: -u["exames"],
    )


def _resumo_grupo(pacientes: set, esperas: List[int]) -> Dict[str, Any]:
    return {
        "pacientes": len(pacientes),
        "exames": len(esperas),
        "espera_mediana": int(median(esperas)) if esperas else 0,
    }


def montar_painel(
    itens, status_atual, regras, hoje: date, prioritarios: Iterable[Dict[str, Any]] = (), agora: Optional[datetime] = None
) -> Dict[str, Any]:
    agora = agora or agora_utc()
    prioritarios = list(prioritarios)
    por_unidade: Dict[str, Dict[str, Any]] = {}
    lista = {"pacientes": set(), "esperas": []}
    demais = {"pacientes": set(), "esperas": []}
    contato = {"em_contato": 0, "prazo_vencido": 0, "sem_contato": 0}
    for item in agrupar_repetidos(itens):
        u = por_unidade.setdefault(item["unidade"], {
            "unidade": item["unidade"], "pendentes": 0, "esperas": [], "faixas": [0, 0, 0, 0], "tratados": 0,
            "exames": defaultdict(int),
        })
        st = status_atual.get(chave_item(item))
        if st and st["status"] in STATUS_QUE_SAEM_DA_FILA:
            u["tratados"] += 1
            continue
        espera = dias_de_espera(item["data_solicitacao"], hoje)
        u["pendentes"] += 1
        u["esperas"].append(espera)
        u["faixas"][0 if espera <= 30 else 1 if espera <= 60 else 2 if espera <= 90 else 3] += 1
        u["exames"][item["nome_exame"]] += 1
        alvo = lista if item["prontuario"] and prioridade_do_paciente(
            item["prontuario"], item["unidade"], prioritarios
        ) else demais
        alvo["pacientes"].add(chave_paciente(item))
        alvo["esperas"].append(espera)
        if st and st["status"] == "EM_CONTATO":
            contato["em_contato"] += 1
            if (info_status(st, agora) or {}).get("prazo_vencido"):
                contato["prazo_vencido"] += 1
        elif st and st["status"] == "SEM_CONTATO":
            contato["sem_contato"] += 1

    unidades = []
    for u in sorted(por_unidade.values(), key=lambda u: -u["pendentes"]):
        esperas = u.pop("esperas")
        exames = u.pop("exames")
        u["espera_mediana"] = int(median(esperas)) if esperas else 0
        u["espera_maxima"] = max(esperas) if esperas else 0
        u["limite"] = regra_da_unidade(regras, u["unidade"])["espera_limite_dias"]
        u["acima_limite"] = sum(1 for e in esperas if e > u["limite"])
        u["principais_exames"] = sorted(
            ({"exame": k, "pendentes": v} for k, v in exames.items()), key=lambda e: -e["pendentes"]
        )[:3]
        unidades.append(u)

    return {
        "unidades": unidades,
        "totais": {
            "pendentes": sum(u["pendentes"] for u in unidades),
            "tratados": sum(u["tratados"] for u in unidades),
            "acima_limite": sum(u["acima_limite"] for u in unidades),
            "faixas": [sum(u["faixas"][i] for u in unidades) for i in range(4)],
        },
        "prioridade": {
            "lista": _resumo_grupo(lista["pacientes"], lista["esperas"]),
            "demais": _resumo_grupo(demais["pacientes"], demais["esperas"]),
        },
        "contato": contato,
        "status": dict(Counter(s["status"] for s in status_atual.values() if s["status"] != "PENDENTE")),
    }


def _tratamento_para_dict(t: TratamentoSolicitacao) -> Dict[str, Any]:
    return {
        "codigo_solicitacao": t.codigo_solicitacao,
        "codigo_exame": t.codigo_exame,
        "status": t.status,
        "data_agendada": t.data_agendada.isoformat() if t.data_agendada else None,
        "observacao": t.observacao,
        "usuario": t.usuario,
        "criado_em": t.criado_em.replace(tzinfo=None).isoformat(),
        "desfaz": bool(t.desfaz),
        "exemplo": bool(t.exemplo),
    }


async def carregar_tratamentos(session: AsyncSession) -> List[Dict[str, Any]]:
    return [
        _tratamento_para_dict(t)
        for t in (await session.execute(
            select(TratamentoSolicitacao).order_by(TratamentoSolicitacao.criado_em, TratamentoSolicitacao.id)
        )).scalars().all()
    ]


async def carregar_contexto(session: AsyncSession, hoje: date) -> Dict[str, Any]:
    status_atual = consolidar_tratamentos(await carregar_tratamentos(session))

    prioritarios = [
        {
            "id": p.id, "prontuario": p.prontuario, "area": p.area, "motivo": p.motivo, "unidade": p.unidade,
            "validade": p.validade.isoformat() if p.validade else None, "exemplo": p.exemplo,
            "criado_por": p.criado_por, "criado_em": p.criado_em.isoformat() if p.criado_em else None,
        }
        for p in (await session.execute(
            select(PacientePrioritario).where(PacientePrioritario.ativo.is_(True)).order_by(PacientePrioritario.id)
        )).scalars().all()
        if p.validade is None or p.validade >= hoje
    ]

    regras = {
        r.unidade: {
            "unidade": r.unidade, "criterios": r.criterios, "espera_limite_dias": r.espera_limite_dias,
            "versao": r.versao, "exemplo": r.exemplo, "atualizado_por": r.atualizado_por,
            "atualizado_em": r.atualizado_em.isoformat() if r.atualizado_em else None,
        }
        for r in (await session.execute(select(RegraPrioridade))).scalars().all()
    }

    combinacoes = [
        {"id": c.id, "exame_a": c.exame_a, "exame_b": c.exame_b, "tipo": c.tipo, "orientacao": c.orientacao,
         "exemplo": c.exemplo}
        for c in (await session.execute(
            select(CombinacaoExames).where(CombinacaoExames.ativo.is_(True)).order_by(CombinacaoExames.id)
        )).scalars().all()
    ]

    return {"status_atual": status_atual, "prioritarios": prioritarios, "regras": regras, "combinacoes": combinacoes}


async def carregar_vagas(session: AsyncSession) -> Dict[str, Dict[str, Any]]:
    return {
        v.codigo_exame: {
            "vagas": v.vagas, "atualizado_por": v.atualizado_por,
            "atualizado_em": v.atualizado_em.replace(tzinfo=None).isoformat() if v.atualizado_em else None,
        }
        for v in (await session.execute(select(VagasExame))).scalars().all()
    }


async def carregar_preparos(session: AsyncSession) -> Dict[str, Dict[str, Any]]:
    return {
        p.codigo_exame: {
            "texto": p.texto, "exemplo": p.exemplo, "atualizado_por": p.atualizado_por,
            "atualizado_em": p.atualizado_em.replace(tzinfo=None).isoformat() if p.atualizado_em else None,
        }
        for p in (await session.execute(select(PreparoExame))).scalars().all()
    }


async def historico_do_paciente(session: AsyncSession, prontuario: str) -> List[Dict[str, Any]]:
    tratamentos = (await session.execute(
        select(TratamentoSolicitacao).where(TratamentoSolicitacao.prontuario == prontuario)
    )).scalars().all()
    inclusoes = (await session.execute(
        select(PacientePrioritario).where(PacientePrioritario.prontuario == prontuario)
    )).scalars().all()
    eventos = [{"tipo": "TRATAMENTO", **_tratamento_para_dict(t)} for t in tratamentos] + [
        {
            "tipo": "PRIORIDADE", "area": p.area, "motivo": p.motivo, "ativo": p.ativo, "exemplo": p.exemplo,
            "usuario": p.criado_por, "criado_em": p.criado_em.replace(tzinfo=None).isoformat(),
        }
        for p in inclusoes
    ]
    return sorted(eventos, key=lambda e: e["criado_em"], reverse=True)


def extrair_prontuarios(texto: str) -> Tuple[List[str], List[str]]:
    validos, invalidos, vistos = [], [], set()
    for bruto in texto.replace(";", "\n").replace(",", "\n").split():
        token = bruto.strip()
        if not token:
            continue
        if not token.isdigit() or not 4 <= len(token) <= 12:
            invalidos.append(token)
            continue
        if token not in vistos:
            vistos.add(token)
            validos.append(token)
    return validos, invalidos


COMBINACOES_EXEMPLO = [
    ("CINTILOGRAFIA DO MIOCARDIO EM REPOUSO", "CINTILOGRAFIA DO MIOCARDIO COM DIPIRIDAMOL", "AGRUPAR",
     "Repouso e estresse fazem parte do mesmo protocolo: agendar em sequência."),
    ("CINTILOGRAFIA RENAL COM DMSA", "CINTILOGRAFIA RENALCOM DTPA", "SEPARAR",
     "Radiofármacos diferentes: não agendar no mesmo dia."),
    ("BIÓPSIA ORIENTADA POR ECOGRAFIA - MAMA", "ANATOMOPATOLÓGICO - MAMA", "ORDEM",
     "O anatomopatológico depende do material da biópsia: biópsia primeiro."),
    ("DENSITOMETRIA ÓSSEA", "CINTILOGRAFIA DO ESQUELETO", "SEPARAR",
     "Radiofármaco interfere na densitometria: densitometria antes ou com intervalo."),
    ("AUDIOMETRIA TONAL LIMIAR (VIA AÉREA/VIA ÓSSEA)", "IMITANCIOMETRIA", "AGRUPAR",
     "Bateria audiológica: agendar no mesmo atendimento."),
    ("AUDIOMETRIA TONAL LIMIAR (VIA AÉREA/VIA ÓSSEA)", "LOGOAUDIOMETRIA", "AGRUPAR",
     "Bateria audiológica: agendar no mesmo atendimento."),
]

PREPAROS_EXEMPLO = {
    "RXMM1": "Não usar desodorante, talco ou creme nas mamas e axilas no dia do exame. Trazer mamografias anteriores.",
    "RXDOS": "Não tomar suplemento de cálcio nas 24 horas anteriores. Vir com roupa sem metal. "
             "Avisar se fez exame com contraste ou medicina nuclear nos últimos 7 dias.",
    "USAX": "Sem preparo especial. Não usar desodorante no dia. Trazer exames de imagem anteriores.",
    "USBI4": "Informar uso de anticoagulante ou AAS. Vir com acompanhante. Trazer exames de imagem anteriores.",
    "CESQ": "Beber bastante água após a injeção do radiofármaco. O exame tem duas etapas no mesmo dia "
            "(injeção e imagens cerca de 3 horas depois).",
    "CRDMS": "Beber bastante água antes do exame. O exame tem duas etapas no mesmo dia (injeção e imagens horas depois).",
    "CRDTP": "Beber 2 copos de água 30 minutos antes do exame. Trazer exames de função renal recentes.",
    "CMREP": "Jejum de 4 horas. Não consumir café, chá, refrigerante de cola ou chocolate nas 24 horas anteriores.",
    "CMDIP": "Jejum de 4 horas. Não consumir café, chá, refrigerante de cola ou chocolate nas 24 horas anteriores. "
             "Medicamentos de uso contínuo conforme orientação do médico solicitante.",
    "ATL": "Evitar ruído intenso (som alto, fones de ouvido) nas 14 horas anteriores. Vir sem gripe ou dor de ouvido.",
    "LOG": "Evitar ruído intenso (som alto, fones de ouvido) nas 14 horas anteriores.",
    "IMT": "Vir sem gripe ou dor de ouvido. Sem outro preparo.",
    "CTIR": "Suspender hormônio tireoidiano e evitar alimentos ricos em iodo conforme orientação do médico solicitante.",
}

TRATAMENTOS_EXEMPLO = [
    ("EM_CONTATO", 2, "Exemplo: mensagem enviada com a data oferecida, aguardando resposta"),
    ("EM_CONTATO", 6, "Exemplo: mensagem enviada com a data oferecida, aguardando resposta"),
    ("EM_CONTATO", 27, "Exemplo: mensagem enviada com a data oferecida, sem resposta"),
    ("EM_CONTATO", 31, "Exemplo: mensagem enviada com a data oferecida, sem resposta"),
    ("SEM_CONTATO", 26, "Exemplo: telefone do cadastro não atende"),
    ("SEM_CONTATO", 50, "Exemplo: número inexistente"),
    ("SEM_CONTATO", 75, "Exemplo: telefone do cadastro não atende"),
    ("AGENDADO", 1, "Exemplo: paciente confirmou a data"),
    ("AGENDADO", 2, "Exemplo: paciente confirmou a data"),
    ("AGENDADO", 3, "Exemplo: paciente confirmou a data"),
    ("CANCELADO", 3, "Exemplo: paciente já fez o exame em outro serviço"),
]

UNIDADES_DOS_EXEMPLOS = ("UDI: MAMOGRAFIA", "UDI: DENSITOMETRIA ÓSSEA", "UDI: ULTRASSONOGRAFIA")


def escolher_pacientes_para_exemplo(
    itens: List[Dict[str, Any]], reservados: set, quantidade: int
) -> List[Dict[str, Any]]:
    por_paciente: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in agrupar_repetidos(itens):
        if item["prontuario"]:
            por_paciente[item["prontuario"]].append(item)
    candidatos = sorted(
        (lista[0] for prontuario, lista in por_paciente.items()
         if len(lista) == 1 and prontuario not in reservados and lista[0]["unidade"] in UNIDADES_DOS_EXEMPLOS),
        key=lambda i: (i["data_solicitacao"], i["codigo_solicitacao"]),
    )
    passo = max(len(candidatos) // (quantidade + 1), 1)
    return candidatos[passo // 2::passo][:quantidade]


async def semear_dados_exemplo(
    session: AsyncSession, itens: List[Dict[str, Any]], agora: Optional[datetime] = None
) -> None:
    agora = agora or datetime.now(timezone.utc)
    if (await session.execute(select(func.count()).select_from(RegraPrioridade))).scalar_one() == 0:
        session.add(RegraPrioridade(
            unidade=REGRA_GERAL, criterios=CRITERIOS_PADRAO, espera_limite_dias=60, versao=1, exemplo=True,
            atualizado_por="sistema",
        ))
        for unidade in sorted({i["unidade"] for i in itens}):
            session.add(RegraPrioridade(
                unidade=unidade, criterios=CRITERIOS_PADRAO, espera_limite_dias=60, versao=1, exemplo=True,
                atualizado_por="sistema",
            ))

    if (await session.execute(select(func.count()).select_from(CombinacaoExames))).scalar_one() == 0:
        for a, b, tipo, orientacao in COMBINACOES_EXEMPLO:
            session.add(CombinacaoExames(exame_a=a, exame_b=b, tipo=tipo, orientacao=orientacao, exemplo=True))

    if (await session.execute(select(func.count()).select_from(PreparoExame))).scalar_one() == 0:
        codigos = {i["codigo_exame"] for i in itens}
        for codigo, texto in PREPAROS_EXEMPLO.items():
            if codigo in codigos:
                session.add(PreparoExame(codigo_exame=codigo, texto=texto, exemplo=True, atualizado_por="sistema"))

    if (await session.execute(select(func.count()).select_from(PacientePrioritario))).scalar_one() == 0:
        def escolher(codigos: Tuple[str, ...], quantidade: int) -> List[Dict[str, Any]]:
            vistos, escolhidos = set(), []
            for item in sorted(itens, key=lambda i: (i["data_solicitacao"], i["codigo_solicitacao"]), reverse=True):
                if item["codigo_exame"] in codigos and item["prontuario"] and item["prontuario"] not in vistos:
                    vistos.add(item["prontuario"])
                    escolhidos.append(item)
                if len(escolhidos) == quantidade:
                    break
            return escolhidos

        for item in escolher(("CRDMS", "CRDTP"), 3):
            session.add(PacientePrioritario(
                prontuario=item["prontuario"], area="Nefrologia", motivo="Paciente em hemodiálise",
                unidade=item["unidade"], exemplo=True, criado_por="sistema",
            ))
        for item in escolher(("USBI4", "MBIOP"), 3):
            session.add(PacientePrioritario(
                prontuario=item["prontuario"], area="Oncologia", motivo="Suspeita oncológica",
                unidade=item["unidade"], exemplo=True, criado_por="sistema",
            ))
        await session.flush()

    if (await session.execute(select(func.count()).select_from(TratamentoSolicitacao))).scalar_one() == 0:
        reservados = {
            p for p in (await session.execute(select(PacientePrioritario.prontuario))).scalars().all()
        }
        escolhidos = escolher_pacientes_para_exemplo(itens, reservados, len(TRATAMENTOS_EXEMPLO))
        for item, (status, horas, observacao) in zip(escolhidos, TRATAMENTOS_EXEMPLO):
            momento = agora - timedelta(hours=horas)
            base = dict(
                codigo_solicitacao=item["codigo_solicitacao"], codigo_exame=item["codigo_exame"],
                prontuario=item["prontuario"], usuario="sistema", exemplo=True,
            )
            if status == "SEM_CONTATO":
                session.add(TratamentoSolicitacao(
                    **base, status="EM_CONTATO", observacao="Exemplo: primeira tentativa, sem resposta",
                    criado_em=momento - timedelta(hours=48),
                ))
            session.add(TratamentoSolicitacao(
                **base, status=status, observacao=observacao, criado_em=momento,
                data_agendada=(momento + timedelta(days=9 + horas)).date() if status == "AGENDADO" else None,
            ))

    await session.commit()
