from datetime import date, datetime, timedelta

from src.controllers.fila_controller import (
    CRITERIOS_PADRAO,
    consolidar_tratamentos,
    extrair_prontuarios,
    montar_painel,
    ranquear_fila,
)
from src.routers.fila import _contem

HOJE = date(2026, 11, 6)
REGRAS = {"*": {"unidade": "*", "criterios": CRITERIOS_PADRAO, "espera_limite_dias": 60, "versao": 1}}


def item(prontuario, solicitacao, data, exame="USG AXILA", codigo="USAX", unidade="UDI: ULTRASSONOGRAFIA"):
    return {
        "prontuario": prontuario, "nome": f"PACIENTE {prontuario}", "codigo_solicitacao": solicitacao,
        "data_solicitacao": f"{data}T08:00:00", "unidade": unidade, "codigo_exame": codigo,
        "nome_exame": exame, "solicitante": "",
    }


def ordem(resultado):
    return [g["prontuario"] for g in resultado["grupos"]]


def test_lista_de_prioridade_vem_antes_da_espera():
    itens = [item("1", "10", "2026-08-01"), item("2", "20", "2026-10-30")]
    prioritarios = [{"prontuario": "2", "area": "Nefrologia", "motivo": "Hemodiálise", "unidade": None}]
    r = ranquear_fila(itens, {}, prioritarios, REGRAS, [], HOJE)
    assert ordem(r) == ["2", "1"]
    assert r["grupos"][0]["motivo"]["tipo"] == "LISTA"
    assert r["grupos"][1]["motivo"]["tipo"] == "ESPERA"


def test_sem_criterio_atendido_vale_ordem_de_chegada():
    itens = [item("1", "10", "2026-10-20"), item("2", "20", "2026-10-10")]
    r = ranquear_fila(itens, {}, [], REGRAS, [], HOJE)
    assert ordem(r) == ["2", "1"]
    assert all(g["motivo"]["tipo"] == "CHEGADA" for g in r["grupos"])


def test_agendado_sai_da_fila_e_em_contato_permanece():
    itens = [item("1", "10", "2026-08-01"), item("2", "20", "2026-08-02")]
    status = {("10", "USAX"): {"status": "AGENDADO"}, ("20", "USAX"): {"status": "EM_CONTATO"}}
    r = ranquear_fila(itens, status, [], REGRAS, [], HOJE)
    assert ordem(r) == ["2"]
    assert r["grupos"][0]["itens"][0]["status"] == "EM_CONTATO"


def test_paciente_agrupa_exames_e_detecta_combinacao():
    itens = [
        item("1", "10", "2026-09-01", "BIÓPSIA ORIENTADA POR ECOGRAFIA - MAMA", "USBI4"),
        item("1", "11", "2026-09-01", "ANATOMOPATOLÓGICO - MAMA", "MBIOP"),
    ]
    combinacoes = [{"exame_a": "BIÓPSIA ORIENTADA POR ECOGRAFIA - MAMA", "exame_b": "ANATOMOPATOLÓGICO - MAMA",
                    "tipo": "ORDEM", "orientacao": "Biópsia primeiro."}]
    r = ranquear_fila(itens, {}, [], REGRAS, combinacoes, HOJE)
    assert r["resumo"]["pacientes"] == 1
    assert len(r["grupos"][0]["itens"]) == 2
    assert r["grupos"][0]["alertas"][0]["tipo"] == "ORDEM"


def test_mesma_entrada_gera_mesma_ordem():
    itens = [item(str(n), str(100 + n), f"2026-09-{1 + n % 20:02d}") for n in range(30)]
    assert ordem(ranquear_fila(itens, {}, [], REGRAS, [], HOJE)) == ordem(ranquear_fila(list(reversed(itens)), {}, [], REGRAS, [], HOJE))


def test_filtro_por_unidade_mantem_outros_exames_visiveis():
    itens = [
        item("1", "10", "2026-09-01"),
        item("1", "11", "2026-09-01", "DENSITOMETRIA ÓSSEA", "RXDOS", "UDI: DENSITOMETRIA ÓSSEA"),
    ]
    r = ranquear_fila(itens, {}, [], REGRAS, [], HOJE, unidade="UDI: DENSITOMETRIA ÓSSEA")
    grupo = r["grupos"][0]
    assert [i["na_unidade"] for i in grupo["itens"]] == [True, False]
    assert r["resumo"]["exames"] == 1


def test_api_fila_exige_autenticacao(client):
    assert client.get("/api/fila").status_code == 401


def test_api_fila_retorna_grupos(client):
    token = client.post("/api/login", data={"username": "admin", "password": "admin"}).json()["access_token"]
    resposta = client.get("/api/fila", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["resumo"]["pacientes"] == len(corpo["grupos"])
    assert all(g["motivo"]["rotulo"] for g in corpo["grupos"])


def test_espera_igual_ao_limite_nao_conta_como_acima():
    itens = [item("1", "10", "2026-09-07"), item("2", "20", "2026-09-06")]
    r = ranquear_fila(itens, {}, [], REGRAS, [], HOJE)
    motivos = {g["prontuario"]: g["motivo"]["tipo"] for g in r["grupos"]}
    assert motivos == {"1": "CHEGADA", "2": "ESPERA"}


def test_itens_repetidos_viram_um_com_quantidade():
    itens = [item("1", "10", "2026-09-01"), item("1", "10", "2026-09-01")]
    r = ranquear_fila(itens, {}, [], REGRAS, [], HOJE)
    assert len(r["grupos"][0]["itens"]) == 1
    assert r["grupos"][0]["itens"][0]["quantidade"] == 2


AGORA = datetime(2026, 11, 6, 15, 0, 0)


def tratamento(solicitacao, status, horas_atras, codigo="USAX", desfaz=False):
    return {
        "codigo_solicitacao": solicitacao, "codigo_exame": codigo, "status": status,
        "criado_em": (AGORA - timedelta(hours=horas_atras)).isoformat(), "desfaz": desfaz,
    }


def test_desfazer_volta_ao_estado_anterior_e_nao_conta_tentativa():
    status = consolidar_tratamentos([
        tratamento("10", "EM_CONTATO", 30),
        tratamento("10", "SEM_CONTATO", 5),
        tratamento("10", "PENDENTE", 1, desfaz=True),
    ])
    assert status[("10", "USAX")]["status"] == "EM_CONTATO"
    assert status[("10", "USAX")]["tentativas"] == 1


def test_abas_separam_em_contato_com_prazo_de_24h_e_mantem_posicao():
    itens = [item("1", "10", "2026-08-01"), item("2", "20", "2026-08-02"), item("3", "30", "2026-08-03")]
    status = consolidar_tratamentos([tratamento("10", "EM_CONTATO", 25), tratamento("30", "SEM_CONTATO", 2)])
    r = ranquear_fila(itens, status, [], REGRAS, [], HOJE, aba="em_contato", agora=AGORA)
    assert ordem(r) == ["1"]
    assert r["grupos"][0]["posicao"] == 1
    assert r["grupos"][0]["contato"]["prazo_vencido"] is True
    assert r["resumo"]["abas"] == {"a_chamar": 1, "em_contato": 1, "sem_contato": 1, "finalizados": 0, "prazo_vencido": 1}
    a_chamar = ranquear_fila(itens, status, [], REGRAS, [], HOJE, aba="a_chamar", agora=AGORA)
    assert [(g["prontuario"], g["posicao"]) for g in a_chamar["grupos"]] == [("2", 2)]


def test_paciente_com_um_exame_em_contato_fica_na_aba_em_contato():
    itens = [item("1", "10", "2026-08-01"), item("1", "11", "2026-08-01", "MAMOGRAFIA BILATERAL", "RXMM1")]
    status = consolidar_tratamentos([tratamento("10", "EM_CONTATO", 1)])
    r = ranquear_fila(itens, status, [], REGRAS, [], HOJE, agora=AGORA)
    assert r["grupos"][0]["aba"] == "em_contato"


def test_filtro_por_exame_usa_regra_propria_do_exame():
    regras = {**REGRAS, "EXAME:USAX": {"unidade": "EXAME:USAX", "criterios": ["ORDEM_CHEGADA"], "espera_limite_dias": 30, "versao": 1}}
    itens = [item("1", "10", "2026-10-30"), item("2", "20", "2026-08-01", "MAMOGRAFIA BILATERAL", "RXMM1")]
    prioritarios = [{"prontuario": "1", "area": "Oncologia", "motivo": "Suspeita", "unidade": None}]
    r = ranquear_fila(itens, {}, prioritarios, regras, [], HOJE, exame="USAX")
    assert r["regra"]["unidade"] == "EXAME:USAX"
    assert ordem(r) == ["1"]
    assert r["grupos"][0]["motivo"]["tipo"] == "CHEGADA"
    assert {e["codigo"] for e in r["exames_unidade"]} == {"USAX", "RXMM1"}


def test_mesmo_exame_em_duas_solicitacoes_gera_alerta_de_duplicidade():
    itens = [item("1", "10", "2026-09-01"), item("1", "11", "2026-09-02")]
    r = ranquear_fila(itens, {}, [], REGRAS, [], HOJE)
    alertas = r["grupos"][0]["alertas"]
    assert [a["tipo"] for a in alertas] == ["DUPLICIDADE"]
    assert alertas[0]["solicitacoes"] == ["10", "11"]
    assert r["resumo"]["com_alerta"] == 1


def test_busca_encontra_numero_da_solicitacao():
    grupo = {"nome": "PACIENTE", "prontuario": "123", "itens": [{"codigo_solicitacao": "9000011"}]}
    assert _contem(grupo, "9000011")
    assert not _contem(grupo, "777")


def test_lista_colada_de_prontuarios_separa_validos_e_invalidos():
    validos, invalidos = extrair_prontuarios("12345678, 23456789\n12345678; abc 12")
    assert validos == ["12345678", "23456789"]
    assert invalidos == ["abc", "12"]


def test_painel_compara_espera_da_lista_com_os_demais():
    itens = [item("1", "10", "2026-10-30"), item("2", "20", "2026-08-01")]
    prioritarios = [{"prontuario": "1", "area": "Nefrologia", "motivo": "Hemodiálise", "unidade": None}]
    p = montar_painel(itens, {}, REGRAS, HOJE, prioritarios, agora=AGORA)
    assert p["prioridade"]["lista"] == {"pacientes": 1, "exames": 1, "espera_mediana": 7}
    assert p["prioridade"]["demais"]["espera_mediana"] == 97


def test_api_novos_endpoints_respondem(client):
    token = client.post("/api/login", data={"username": "admin", "password": "admin"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    fila_resp = client.get("/api/fila?aba=a_chamar", headers=h).json()
    assert set(fila_resp["resumo"]["abas"]) >= {"a_chamar", "em_contato", "sem_contato", "finalizados"}
    assert client.get("/api/fila?aba=invalida", headers=h).status_code == 400
    assert client.get("/api/regras/auditoria", headers=h).status_code == 200
    assert "prioridade" in client.get("/api/painel", headers=h).json()
