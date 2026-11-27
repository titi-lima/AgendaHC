import json
import os
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.auth import auth_handler
from ..controllers import fila_controller as fila
from ..dependencies import get_solicitacao_provider
from ..helpers.audit_helper import registrar_auditoria
from ..models.agenda import PacientePrioritario, PreparoExame, RegraPrioridade, VagasExame
from ..models.audit_log import AuditLog
from ..providers.interfaces.solicitacao_provider_interface import SolicitacaoProviderInterface
from ..resources.database import get_app_db_session

STRATEGY = os.getenv("SOLICITACAO_PROVIDER_TYPE", "csv")

router = APIRouter(
    prefix="/api",
    tags=["Regras e painel"],
    dependencies=[Depends(auth_handler.decode_token)],
)


class AtualizarRegra(BaseModel):
    unidade: str
    criterios: List[str]
    espera_limite_dias: int = Field(ge=1, le=365)


class NovaRegraExame(BaseModel):
    codigo_exame: str
    criterios: List[str]
    espera_limite_dias: int = Field(ge=1, le=365)


class PrioritariosEmLote(BaseModel):
    prontuarios: str = Field(min_length=1, max_length=20000)
    area: str
    motivo: str
    unidade: Optional[str] = None
    validade: Optional[date] = None


class AtualizarVagas(BaseModel):
    codigo_exame: str
    vagas: Optional[int] = Field(default=None, ge=0, le=9999)


class AtualizarPreparo(BaseModel):
    codigo_exame: str
    texto: str = Field(max_length=2000)


ACOES_DE_GOVERNANCA = (
    "ALTERAR_REGRA_PRIORIDADE", "CRIAR_REGRA_EXAME", "REMOVER_REGRA_EXAME",
    "INCLUIR_PACIENTE_PRIORITARIO", "REMOVER_PACIENTE_PRIORITARIO",
    "ALTERAR_VAGAS_EXAME", "ALTERAR_PREPARO_EXAME",
)


class NovoPrioritario(BaseModel):
    prontuario: str
    area: str
    motivo: str
    unidade: Optional[str] = None
    validade: Optional[date] = None


def _usuario(payload: dict) -> str:
    return payload.get("sub") or payload.get("username") or "desconhecido"


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _validar_criterios(criterios: List[str]) -> None:
    invalidos = [c for c in criterios if c not in fila.CRITERIOS_VALIDOS]
    if invalidos or len(set(criterios)) != len(criterios) or not criterios:
        raise HTTPException(status_code=400, detail="Critérios inválidos ou repetidos.")


def _catalogo_de_exames(itens) -> dict:
    catalogo = {}
    for i in itens:
        catalogo.setdefault(i["codigo_exame"], {"codigo": i["codigo_exame"], "nome": i["nome_exame"], "unidade": i["unidade"]})
    return catalogo


def _json(valor: Optional[str]):
    if not valor:
        return None
    try:
        return json.loads(valor)
    except ValueError:
        return valor


@router.get("/regras")
async def listar_regras(
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    ctx = await fila.carregar_contexto(db, date.today())
    itens = await provider.listar_itens_solicitados()
    nomes = {i["prontuario"]: i["nome"] for i in itens if i["prontuario"]}
    catalogo = _catalogo_de_exames(itens)
    preparos = await fila.carregar_preparos(db)
    vagas = await fila.carregar_vagas(db)
    regras_unidade = [r for r in ctx["regras"].values() if not fila.eh_regra_de_exame(r["unidade"])]
    regras_exame = []
    for r in ctx["regras"].values():
        if fila.eh_regra_de_exame(r["unidade"]):
            codigo = r["unidade"][len(fila.PREFIXO_REGRA_EXAME):]
            regras_exame.append({**r, "codigo_exame": codigo, "exame": catalogo.get(codigo)})
    return {
        "criterios_disponiveis": list(fila.CRITERIOS_VALIDOS),
        "regras": sorted(regras_unidade, key=lambda r: (r["unidade"] != fila.REGRA_GERAL, r["unidade"])),
        "regras_exame": sorted(regras_exame, key=lambda r: r["codigo_exame"]),
        "prioritarios": [{**p, "nome": nomes.get(p["prontuario"])} for p in ctx["prioritarios"]],
        "combinacoes": ctx["combinacoes"],
        "exames": [
            {**e, "preparo": preparos.get(e["codigo"]), "vagas": (vagas.get(e["codigo"]) or {}).get("vagas")}
            for e in sorted(catalogo.values(), key=lambda e: (e["unidade"], e["nome"]))
        ],
    }


@router.put("/regras")
async def atualizar_regra(
    corpo: AtualizarRegra,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    db: AsyncSession = Depends(get_app_db_session),
):
    _validar_criterios(corpo.criterios)
    regra = (await db.execute(select(RegraPrioridade).where(RegraPrioridade.unidade == corpo.unidade))).scalar_one_or_none()
    if regra is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada para a unidade")
    anterior = {"criterios": regra.criterios, "espera_limite_dias": regra.espera_limite_dias, "versao": regra.versao}
    regra.criterios = corpo.criterios
    regra.espera_limite_dias = corpo.espera_limite_dias
    regra.versao = regra.versao + 1
    regra.exemplo = False
    regra.atualizado_por = _usuario(usuario)
    await db.commit()
    await registrar_auditoria(
        db=db, usuario=_usuario(usuario), categoria="CONFIGURACAO", acao="ALTERAR_REGRA_PRIORIDADE",
        recurso=f"regra:{corpo.unidade}", dados_anteriores=anterior,
        dados_novos={"criterios": regra.criterios, "espera_limite_dias": regra.espera_limite_dias, "versao": regra.versao},
        ip_origem=_ip(request),
    )
    return {"ok": True, "versao": regra.versao}


@router.post("/regras/exame", status_code=201)
async def criar_regra_exame(
    corpo: NovaRegraExame,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    _validar_criterios(corpo.criterios)
    if corpo.codigo_exame not in _catalogo_de_exames(await provider.listar_itens_solicitados()):
        raise HTTPException(status_code=404, detail="Exame não encontrado no extrato do AGHU")
    chave = fila.chave_regra_exame(corpo.codigo_exame)
    if (await db.execute(select(RegraPrioridade).where(RegraPrioridade.unidade == chave))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Esse exame já tem regra própria. Edite a existente.")
    regra = RegraPrioridade(
        unidade=chave, criterios=corpo.criterios, espera_limite_dias=corpo.espera_limite_dias, versao=1,
        exemplo=False, atualizado_por=_usuario(usuario),
    )
    db.add(regra)
    await db.commit()
    await registrar_auditoria(
        db=db, usuario=_usuario(usuario), categoria="CONFIGURACAO", acao="CRIAR_REGRA_EXAME",
        recurso=f"regra:{chave}", dados_novos=corpo.model_dump(mode="json"), ip_origem=_ip(request),
    )
    return {"ok": True, "unidade": chave}


@router.delete("/regras/exame/{codigo_exame}")
async def remover_regra_exame(
    codigo_exame: str,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    db: AsyncSession = Depends(get_app_db_session),
):
    chave = fila.chave_regra_exame(codigo_exame)
    regra = (await db.execute(select(RegraPrioridade).where(RegraPrioridade.unidade == chave))).scalar_one_or_none()
    if regra is None:
        raise HTTPException(status_code=404, detail="Regra do exame não encontrada")
    anterior = {"criterios": regra.criterios, "espera_limite_dias": regra.espera_limite_dias, "versao": regra.versao}
    await db.delete(regra)
    await db.commit()
    await registrar_auditoria(
        db=db, usuario=_usuario(usuario), categoria="CONFIGURACAO", acao="REMOVER_REGRA_EXAME",
        recurso=f"regra:{chave}", dados_anteriores=anterior, ip_origem=_ip(request),
    )
    return {"ok": True}


@router.post("/regras/prioritarios/lote", status_code=201)
async def incluir_prioritarios_em_lote(
    corpo: PrioritariosEmLote,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    if not corpo.area.strip() or not corpo.motivo.strip():
        raise HTTPException(status_code=400, detail="Área e motivo são obrigatórios.")
    validos, invalidos = fila.extrair_prontuarios(corpo.prontuarios)
    if not validos:
        raise HTTPException(status_code=400, detail="Nenhum prontuário válido na lista.")
    ctx = await fila.carregar_contexto(db, date.today())
    ja_na_lista = {
        p["prontuario"] for p in ctx["prioritarios"]
        if not p.get("unidade") or not corpo.unidade or p["unidade"] == corpo.unidade
    }
    itens = await provider.listar_itens_solicitados()
    com_pendencia = {
        i["prontuario"] for i in itens
        if i["prontuario"] and ctx["status_atual"].get(fila.chave_item(i), {}).get("status") not in fila.STATUS_QUE_SAEM_DA_FILA
        and (not corpo.unidade or i["unidade"] == corpo.unidade)
    }
    incluidos, repetidos = [], []
    for prontuario in validos:
        if prontuario in ja_na_lista:
            repetidos.append(prontuario)
            continue
        db.add(PacientePrioritario(
            prontuario=prontuario, area=corpo.area.strip(), motivo=corpo.motivo.strip(), unidade=corpo.unidade,
            validade=corpo.validade, criado_por=_usuario(usuario),
        ))
        incluidos.append(prontuario)
    await db.commit()
    for prontuario in incluidos:
        await registrar_auditoria(
            db=db, usuario=_usuario(usuario), categoria="NEGOCIO_CLINICO", acao="INCLUIR_PACIENTE_PRIORITARIO",
            recurso=f"prontuario:{prontuario}",
            dados_novos={**corpo.model_dump(mode="json", exclude={"prontuarios"}), "prontuario": prontuario, "em_lote": True},
            ip_origem=_ip(request),
        )
    return {
        "ok": True,
        "incluidos": incluidos,
        "ja_na_lista": repetidos,
        "sem_solicitacao": [p for p in incluidos if p not in com_pendencia],
        "invalidos": invalidos,
    }


@router.post("/regras/prioritarios", status_code=201)
async def incluir_prioritario(
    corpo: NovoPrioritario,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    db: AsyncSession = Depends(get_app_db_session),
):
    if not corpo.prontuario.strip() or not corpo.area.strip() or not corpo.motivo.strip():
        raise HTTPException(status_code=400, detail="Prontuário, área e motivo são obrigatórios.")
    novo = PacientePrioritario(
        prontuario=corpo.prontuario.strip(), area=corpo.area.strip(), motivo=corpo.motivo.strip(),
        unidade=corpo.unidade, validade=corpo.validade, criado_por=_usuario(usuario),
    )
    db.add(novo)
    await db.commit()
    await registrar_auditoria(
        db=db, usuario=_usuario(usuario), categoria="NEGOCIO_CLINICO", acao="INCLUIR_PACIENTE_PRIORITARIO",
        recurso=f"prontuario:{novo.prontuario}", dados_novos=corpo.model_dump(mode="json"), ip_origem=_ip(request),
    )
    return {"ok": True, "id": novo.id}


@router.delete("/regras/prioritarios/{prioritario_id}")
async def remover_prioritario(
    prioritario_id: int,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    db: AsyncSession = Depends(get_app_db_session),
):
    registro = await db.get(PacientePrioritario, prioritario_id)
    if registro is None or not registro.ativo:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    registro.ativo = False
    await db.commit()
    await registrar_auditoria(
        db=db, usuario=_usuario(usuario), categoria="NEGOCIO_CLINICO", acao="REMOVER_PACIENTE_PRIORITARIO",
        recurso=f"prontuario:{registro.prontuario}", dados_anteriores={"area": registro.area, "ativo": True},
        dados_novos={"ativo": False}, ip_origem=_ip(request),
    )
    return {"ok": True}


@router.put("/vagas")
async def atualizar_vagas(
    corpo: AtualizarVagas,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    db: AsyncSession = Depends(get_app_db_session),
):
    registro = (await db.execute(select(VagasExame).where(VagasExame.codigo_exame == corpo.codigo_exame))).scalar_one_or_none()
    anterior = {"vagas": registro.vagas} if registro else None
    if corpo.vagas is None:
        if registro:
            await db.delete(registro)
    elif registro:
        registro.vagas = corpo.vagas
        registro.atualizado_por = _usuario(usuario)
    else:
        db.add(VagasExame(codigo_exame=corpo.codigo_exame, vagas=corpo.vagas, atualizado_por=_usuario(usuario)))
    await db.commit()
    await registrar_auditoria(
        db=db, usuario=_usuario(usuario), categoria="CONFIGURACAO", acao="ALTERAR_VAGAS_EXAME",
        recurso=f"exame:{corpo.codigo_exame}", dados_anteriores=anterior, dados_novos={"vagas": corpo.vagas},
        ip_origem=_ip(request),
    )
    return {"ok": True}


@router.put("/preparos")
async def atualizar_preparo(
    corpo: AtualizarPreparo,
    request: Request,
    usuario: dict = Depends(auth_handler.decode_token),
    db: AsyncSession = Depends(get_app_db_session),
):
    texto = corpo.texto.strip()
    registro = (await db.execute(select(PreparoExame).where(PreparoExame.codigo_exame == corpo.codigo_exame))).scalar_one_or_none()
    anterior = {"texto": registro.texto, "exemplo": registro.exemplo} if registro else None
    if not texto:
        if registro:
            await db.delete(registro)
    elif registro:
        registro.texto = texto
        registro.exemplo = False
        registro.atualizado_por = _usuario(usuario)
    else:
        db.add(PreparoExame(codigo_exame=corpo.codigo_exame, texto=texto, exemplo=False, atualizado_por=_usuario(usuario)))
    await db.commit()
    await registrar_auditoria(
        db=db, usuario=_usuario(usuario), categoria="CONFIGURACAO", acao="ALTERAR_PREPARO_EXAME",
        recurso=f"exame:{corpo.codigo_exame}", dados_anteriores=anterior, dados_novos={"texto": texto or None},
        ip_origem=_ip(request),
    )
    return {"ok": True}


@router.get("/regras/auditoria")
async def listar_auditoria_de_regras(limite: int = 30, db: AsyncSession = Depends(get_app_db_session)):
    registros = (await db.execute(
        select(AuditLog).where(AuditLog.acao.in_(ACOES_DE_GOVERNANCA))
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(min(max(limite, 1), 200))
    )).scalars().all()
    return [
        {
            "id": r.id, "quando": r.created_at.replace(tzinfo=None).isoformat(), "usuario": r.usuario,
            "acao": r.acao, "recurso": r.recurso,
            "antes": _json(r.dados_anteriores), "depois": _json(r.dados_novos),
        }
        for r in registros
    ]


@router.get("/painel")
async def obter_painel(
    provider: SolicitacaoProviderInterface = Depends(get_solicitacao_provider(STRATEGY)),
    db: AsyncSession = Depends(get_app_db_session),
):
    hoje = date.today()
    itens = await provider.listar_itens_solicitados()
    ctx = await fila.carregar_contexto(db, hoje)
    painel = fila.montar_painel(itens, ctx["status_atual"], ctx["regras"], hoje, ctx["prioritarios"])
    painel["fonte"] = provider.descricao_fonte()
    return painel
