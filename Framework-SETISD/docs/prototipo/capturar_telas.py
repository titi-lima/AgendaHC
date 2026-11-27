import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "screenshots"
SAIDA.mkdir(parents=True, exist_ok=True)


def captura(pagina, nome):
    pagina.wait_for_timeout(700)
    pagina.screenshot(path=str(SAIDA / f"{nome}.png"))
    print("salvo", nome)


with sync_playwright() as p:
    navegador = p.chromium.launch(channel="chrome", headless=True)
    contexto = navegador.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, locale="pt-BR")
    pagina = contexto.new_page()
    pagina.goto(f"{BASE}/login")
    pagina.fill("input[type=text]", "admin")
    pagina.fill("input[type=password]", "admin")
    pagina.click("button[type=submit]")
    pagina.wait_for_url("**/fila")
    pagina.wait_for_selector("tbody tr[data-chave]")
    captura(pagina, "01-fila")

    pagina.get_by_role("button", name="Medicina Nuclear").click()
    pagina.wait_for_timeout(900)
    linhas = pagina.locator("tbody tr[data-chave]")
    alvo = next((linhas.nth(i) for i in range(linhas.count()) if linhas.nth(i).get_by_text("Não no mesmo dia").count()), linhas.first)
    alvo.click()
    pagina.wait_for_selector("text=Exames do paciente")
    captura(pagina, "02-detalhe-combinacao")

    linhas = pagina.locator("tbody tr[data-chave]")
    escolhido = next(
        linhas.nth(i) for i in range(linhas.count())
        if i > 8 and "renal" in linhas.nth(i).inner_text().lower() and "Lista ·" not in linhas.nth(i).inner_text()
    )
    escolhido.click()
    pagina.wait_for_selector("text=Incluir na lista de prioridade")
    pagina.get_by_role("button", name="Incluir na lista de prioridade").click()
    pagina.locator("#form-prioridade select").first.select_option(label="Nefrologia")
    pagina.fill("input[placeholder^='Ex.: paciente em']", "Paciente em hemodiálise")
    captura(pagina, "03a-incluir-prioridade")
    pagina.get_by_role("button", name="Incluir e reordenar").click()
    pagina.wait_for_selector("text=Subiu de")
    pagina.wait_for_timeout(900)
    captura(pagina, "03-reordenacao-prioridade")
    pagina.get_by_role("button", name="Desfazer").click()
    pagina.wait_for_selector("text=Inclusão desfeita")
    print("desfazer ok:", pagina.get_by_text("Inclusão desfeita").first.inner_text())
    pagina.wait_for_timeout(600)

    pagina.get_by_role("button", name="Registrar resultado").first.click()
    pagina.locator("label", has_text="Agendado no AGHU").click()
    pagina.fill("input[type=date]", "2026-12-04")
    pagina.fill("textarea", "Paciente confirmou por telefone")
    captura(pagina, "04-registrar-resultado")
    pagina.get_by_role("button", name="Registrar", exact=True).click()
    pagina.wait_for_timeout(1500)
    captura(pagina, "05-apos-registro")
    pagina.get_by_role("button", name="Desfazer").click()
    pagina.wait_for_selector("text=Registro desfeito")
    print("desfazer registro ok:", pagina.get_by_text("Registro desfeito").first.inner_text())
    pagina.wait_for_timeout(600)

    pagina.goto(f"{BASE}/painel")
    pagina.wait_for_selector("text=Demanda por unidade")
    captura(pagina, "06-painel")

    pagina.goto(f"{BASE}/regras")
    pagina.wait_for_selector("text=Ordem dos critérios por unidade")
    captura(pagina, "07-regras")
    pagina.locator("main").evaluate("el => el.scrollTo(0, el.scrollHeight)")
    captura(pagina, "08-regras-listas")

    pagina.set_viewport_size({"width": 1366, "height": 768})
    pagina.goto(f"{BASE}/fila")
    pagina.wait_for_selector("tbody tr[data-chave]")
    pagina.locator("tbody tr[data-chave]").nth(2).click()
    pagina.wait_for_selector("text=Exames do paciente")
    pagina.get_by_role("button", name="Registrar resultado").first.click()
    pagina.get_by_text("Em contato", exact=True).click()
    pagina.get_by_role("button", name="Registrar", exact=True).click()
    pagina.wait_for_timeout(1500)
    captura(pagina, "09-compacto-1366")

    navegador.close()
