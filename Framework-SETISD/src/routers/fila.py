import os
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.auth import auth_handler
from ..controllers import fila_controller as fila
from ..dependencies import get_solicitacao_provider
from ..helpers.audit_helper import registrar_auditoria
from ..models.agenda import TratamentoSolicitacao
from ..providers.interfaces.solicitacao_provider_interface import SolicitacaoProviderInterface
from ..resources.database import get_app_db_session

STRATEGY = os.getenv("SOLICITACAO_PROVIDER_TYPE", "csv")

router = APIRouter(
    prefix="/api/fila",
    tags=["Fila de marcação"],
    dependencies=[Depends(auth_handler.decode_token)],
)


class NovoTratamento(BaseModel):
    codigo_solicitacao: str
    codigo_exame: str
    status: str
    data_agendada: Optional[date] = None
    observacao: Optional[str] = None


class ItemDaFila(BaseModel):
    codigo_solicitacao: str
    codigo_exame: str


class TratamentoEmLote(BaseModel):
    itens: List[ItemDaFila] = Field(min_length=1, max_length=50)
    status: str
    observacao: Optional[str] = None


class Desfazer(BaseModel):
    itens: List[ItemDaFila] = Field(min_length=1, max_length=50)


def _usuario(payload: dict) -> str:
    return payload.get("sub") or payload.get("username") or "desconhecido"


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _contem(grupo, termo: str) -> bool:
    termo = termo.strip().lower()
    return (
        termo in grupo["nome"].lower()
        or termo in grupo["prontuario"]
        or any(termo in i["codigo_solicitacao"] for i in grupo["itens"])
    )


@router.get("")
async def obter_fila(
    unidade: Optional[str] = None,
    exame: Optional[str] = None,
    aba: Optional[str] = None,
    busca: Optional[str] = None,
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    if aba is not None and aba not in fila.ABAS:
        raise HTTPException(status_code=400, detail=f"Aba inválida: {aba}")
    hoje = date.today()
    itens = await provider.listar_itens_solicitados()
    ctx = await fila.carregar_contexto(db, hoje)
    resultado = fila.ranquear_fila(
        itens, ctx["status_atual"], ctx["prioritarios"], ctx["regras"], ctx["combinacoes"], hoje,
        unidade=unidade, exame=exame, aba=aba,
    )
    grupos = resultado["grupos"]
    if busca:
        grupos = [g for g in grupos if _contem(g, busca)]
    vagas = await fila.carregar_vagas(db)
    return {
        "fonte": provider.descricao_fonte(),
        "gerado_em": datetime.now().isoformat(timespec="minutes"),
        "unidade": unidade,
        "exame": exame,
        "aba": aba,
        "regra": resultado["regra"],
        "regra_do_exame": bool(exame) and fila.eh_regra_de_exame(resultado["regra"]["unidade"]),
        "resumo": resultado["resumo"],
        "unidades": fila.resumo_unidades(itens, ctx["status_atual"]),
        "exames": [{**e, "vagas": (vagas.get(e["codigo"]) or {}).get("vagas")} for e in resultado["exames_unidade"]],
        "vagas": vagas.get(exame) if exame else None,
        "prazo_resposta_horas": fila.PRAZO_RESPOSTA_HORAS,
        "total_exames": len(itens),
        "grupos": grupos,
    }


@router.get("/pacientes/{chave}")
async def obter_paciente(
    chave: str,
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    hoje = date.today()
    agora = fila.agora_utc()
    itens = fila.agrupar_repetidos(
        [i for i in await provider.listar_itens_solicitados() if fila.chave_paciente(i) == chave]
    )
    if not itens:
        raise HTTPException(status_code=404, detail="Paciente não encontrado na fila")
    ctx = await fila.carregar_contexto(db, hoje)
    preparos = await fila.carregar_preparos(db)
    vagas = await fila.carregar_vagas(db)
    todos = []
    for item in sorted(itens, key=lambda i: i["data_solicitacao"]):
        st = ctx["status_atual"].get(fila.chave_item(item))
        todos.append({
            **{k: v for k, v in item.items() if k not in ("prontuario", "nome")},
            "espera_dias": fila.dias_de_espera(item["data_solicitacao"], hoje),
            "status": st["status"] if st else "PENDENTE",
            "status_info": fila.info_status(st, agora),
            "preparo": preparos.get(item["codigo_exame"]),
            "vagas": (vagas.get(item["codigo_exame"]) or {}).get("vagas"),
        })
    prontuario = itens[0]["prontuario"]
    ativos = [i for i in todos if i["status"] not in fila.STATUS_QUE_SAEM_DA_FILA]
    return {
        "chave": chave,
        "prontuario": prontuario,
        "nome": itens[0]["nome"],
        "itens": todos,
        "prioridades": [p for p in ctx["prioritarios"] if prontuario and p["prontuario"] == prontuario],
        "alertas": fila.alertas_do_paciente(ativos, ctx["combinacoes"]),
        "historico": await fila.historico_do_paciente(db, prontuario or chave),
        "prazo_resposta_horas": fila.PRAZO_RESPOSTA_HORAS,
        "dados_ausentes": ["data de retorno", "município", "telefone"],
    }


async def _itens_do_aghu(provider: SolicitacaoProviderInterface, chaves: List[ItemDaFila]):
    por_chave = {fila.chave_item(i): i for i in await provider.listar_itens_solicitados()}
    encontrados = []
    for c in chaves:
        item = por_chave.get((c.codigo_solicitacao, c.codigo_exame))
        if item is None:
            raise HTTPException(
                status_code=404,
                detail=f"Solicitação {c.codigo_solicitacao} ({c.codigo_exame}) não encontrada no AGHU",
            )
        encontrados.append(item)
    return encontrados


def _novo_tratamento(item, status_novo, usuario, data_agendada=None, observacao=None, desfaz=False):
    return TratamentoSolicitacao(
        codigo_solicitacao=item["codigo_solicitacao"],
        codigo_exame=item["codigo_exame"],
        prontuario=item["prontuario"] or fila.chave_paciente(item),
        status=status_novo,
        data_agendada=data_agendada,
        observacao=(observacao or "").strip() or None,
        usuario=usuario,
        desfaz=desfaz,
    )


@router.post("/tratamentos", status_code=status.HTTP_201_CREATED)
async def registrar_tratamento(
    corpo: NovoTratamento,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    if corpo.status not in fila.STATUS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Status inválido: {corpo.status}")
    if corpo.status == "AGENDADO" and not corpo.data_agendada:
        raise HTTPException(status_code=400, detail="Informe a data agendada no AGHU.")
    if corpo.status == "CANCELADO" and not (corpo.observacao or "").strip():
        raise HTTPException(status_code=400, detail="Informe o motivo do cancelamento.")
    (item,) = await _itens_do_aghu(provider, [ItemDaFila(**corpo.model_dump(include={"codigo_solicitacao", "codigo_exame"}))])

    nome_usuario = _usuario(usuario)
    anterior = (await fila.carregar_contexto(db, date.today()))["status_atual"].get(fila.chave_item(item))
    db.add(_novo_tratamento(item, corpo.status, nome_usuario, corpo.data_agendada, corpo.observacao))
    await db.commit()
    await registrar_auditoria(
        db=db,
        usuario=nome_usuario,
        categoria="NEGOCIO_CLINICO",
        acao="REGISTRAR_TRATAMENTO_SOLICITACAO",
        recurso=f"solicitacao:{corpo.codigo_solicitacao}:{corpo.codigo_exame}",
        dados_anteriores=anterior,
        dados_novos=corpo.model_dump(mode="json"),
        ip_origem=_ip(request),
    )
    return {"ok": True}


@router.post("/tratamentos/lote", status_code=status.HTTP_201_CREATED)
async def registrar_tratamento_em_lote(
    corpo: TratamentoEmLote,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    if corpo.status not in fila.STATUS_EM_LOTE:
        raise HTTPException(
            status_code=400,
            detail="Em lote só vale para Em contato, Sem contato, Cancelado ou Pendente. Agendamento é por exame.",
        )
    if corpo.status == "CANCELADO" and not (corpo.observacao or "").strip():
        raise HTTPException(status_code=400, detail="Informe o motivo do cancelamento.")
    itens = await _itens_do_aghu(provider, corpo.itens)
    nome_usuario = _usuario(usuario)
    status_atual = (await fila.carregar_contexto(db, date.today()))["status_atual"]
    for item in itens:
        db.add(_novo_tratamento(item, corpo.status, nome_usuario, observacao=corpo.observacao))
    await db.commit()
    for item in itens:
        await registrar_auditoria(
            db=db,
            usuario=nome_usuario,
            categoria="NEGOCIO_CLINICO",
            acao="REGISTRAR_TRATAMENTO_SOLICITACAO",
            recurso=f"solicitacao:{item['codigo_solicitacao']}:{item['codigo_exame']}",
            dados_anteriores=status_atual.get(fila.chave_item(item)),
            dados_novos={"status": corpo.status, "observacao": corpo.observacao, "em_lote": len(itens)},
            ip_origem=_ip(request),
        )
    return {"ok": True, "registrados": len(itens)}


@router.post("/tratamentos/desfazer")
async def desfazer_tratamento(
    corpo: Desfazer,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    itens = await _itens_do_aghu(provider, corpo.itens)
    nome_usuario = _usuario(usuario)
    tratamentos = await fila.carregar_tratamentos(db)
    antes = fila.consolidar_tratamentos(tratamentos)
    sem_registro = [i for i in itens if fila.chave_item(i) not in antes]
    if sem_registro:
        raise HTTPException(status_code=409, detail="Não há registro para desfazer nesse exame.")
    desfeitos = [{"desfaz": True, "codigo_solicitacao": i["codigo_solicitacao"], "codigo_exame": i["codigo_exame"]} for i in itens]
    depois = fila.consolidar_tratamentos(tratamentos + desfeitos)
    for item in itens:
        chave = fila.chave_item(item)
        restaurado = depois.get(chave, {}).get("status", "PENDENTE")
        db.add(_novo_tratamento(
            item, restaurado, nome_usuario, observacao=f"Desfeito: {antes[chave]['status']}", desfaz=True,
        ))
    await db.commit()
    for item in itens:
        chave = fila.chave_item(item)
        await registrar_auditoria(
            db=db,
            usuario=nome_usuario,
            categoria="NEGOCIO_CLINICO",
            acao="DESFAZER_TRATAMENTO_SOLICITACAO",
            recurso=f"solicitacao:{item['codigo_solicitacao']}:{item['codigo_exame']}",
            dados_anteriores=antes[chave],
            dados_novos=depois.get(chave) or {"status": "PENDENTE"},
            ip_origem=_ip(request),
        )
    return {"ok": True, "desfeitos": len(itens)}
