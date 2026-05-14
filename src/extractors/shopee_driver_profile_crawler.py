"""
Extractor: Perfil do Motorista
Fonte: Shopee Logistics - Login via Playwright (navegação real no portal)
Destino: data/raw/shopee_driver_profile/processed_*.csv

Fluxo:
1. Login no portal
2. Navegar para Perfil do Motorista
3. Clicar em "Procurar"
4. Clicar em "Exportar" → "Exportar" (abre painel lateral com tarefa assíncrona)
5. Aguardar processamento e clicar em "Baixar"
6. Tratar com pandas
"""
import asyncio
import os
import zipfile
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

from src.utils import get_logger, DATA_RAW_DIR

logger = get_logger(__name__)

PORTAL_URL = "https://logistics.myagencyservice.com.br/"
DRIVER_PROFILE_URL = "https://logistics.myagencyservice.com.br/#/workforce/driver-profile/list"


async def extract_shopee_driver_profile() -> Path:
    import pandas as pd

    email = os.environ.get("SHOPEE_EMAIL", "")
    senha = os.environ.get("SHOPEE_PWD", "")

    if not email or not senha:
        raise Exception("SHOPEE_EMAIL e SHOPEE_PWD devem estar definidos nos secrets.")

    output_path = DATA_RAW_DIR / "shopee_driver_profile"
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 80)
    logger.info("INICIANDO EXTRAÇÃO: Shopee Perfil do Motorista")
    logger.info("=" * 80)

    async with async_playwright() as p:
        logger.info("Iniciando navegador...")
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            # 1. LOGIN
            logger.info(f"Acessando portal: {PORTAL_URL}")
            await page.goto(PORTAL_URL, wait_until="networkidle", timeout=60_000)

            logger.info("Aguardando formulário de login...")
            await page.locator('input[type="password"]').wait_for(timeout=30_000)

            logger.info("Preenchendo credenciais...")
            await page.locator('input[autocomplete="email"]').fill(email)
            await page.locator('input[type="password"]').fill(senha)

            logger.info("Submetendo login...")
            await page.locator('input[type="password"]').press("Enter")

            logger.info("Aguardando portal carregar após login...")
            try:
                await page.locator('text="Força de trabalho"').wait_for(timeout=30_000)
                logger.info("✅ Login confirmado — menu principal carregado!")
            except Exception:
                screenshot_path = output_path / "login_erro.png"
                await page.screenshot(path=str(screenshot_path))
                raise Exception("Login falhou — credenciais incorretas ou portal travou.")

            # 2. NAVEGAR PARA PERFIL DO MOTORISTA
            logger.info(f"Navegando para: {DRIVER_PROFILE_URL}")
            await page.goto(DRIVER_PROFILE_URL, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(10_000)

            # 3. CLICAR EM "PROCURAR"
            logger.info("Aguardando tabela carregar...")
            await page.wait_for_selector(".ssc-react-pro-table-table", timeout=60_000)
            await page.wait_for_timeout(3_000)

            logger.info("Clicando em 'Procurar'...")
            try:
                botao_procurar = page.locator('button:has-text("Procurar")').first
                await botao_procurar.wait_for(timeout=20_000)
                await botao_procurar.click()
                logger.info("'Procurar' clicado — aguardando dados...")
                await page.wait_for_timeout(10_000)
            except Exception as e:
                logger.warning(f"Botão 'Procurar' não encontrado: {e}")

            # 4. ABRIR DROPDOWN DE EXPORTAR e contar "Baixar" visíveis ANTES de disparar
            logger.info("Clicando em 'Exportar' para abrir dropdown...")
            try:
                botao_exportar = page.locator('button:has-text("Exportar")').first
                await botao_exportar.wait_for(timeout=10_000)
                await botao_exportar.click()
            except Exception:
                botao_exportar = page.locator('button:has-text("Export")').first
                await botao_exportar.wait_for(timeout=10_000)
                await botao_exportar.click()

            await page.wait_for_timeout(2_000)

            # Contar "Baixar" visíveis no popup que pode abrir com o dropdown
            botoes_baixar = page.locator('button:has-text("Baixar"), button:has-text("Download")')
            count_antes = await botoes_baixar.count()
            logger.info(f"Botões 'Baixar' visíveis antes de exportar: {count_antes}")

            # 5. CLICAR NA OPÇÃO "EXPORTAR" DO DROPDOWN
            logger.info("Clicando na opção 'Exportar' do dropdown...")
            opcao = page.locator('text=Exportar').nth(1)
            await opcao.wait_for(timeout=10_000)
            await opcao.click()
            logger.info("Exportação solicitada — aguardando 90s para processamento do servidor...")
            await page.wait_for_timeout(90_000)

            # 6. ABRIR PAINEL "ÚLTIMA TAREFA" via ícone de tarefas no header
            logger.info("Abrindo painel 'Última tarefa' via ícone de tarefas...")
            painel_aberto = False
            for tentativa_painel in range(4):
                try:
                    # Tenta o ícone de tarefas (div com classe icon próximo ao sino)
                    icone = page.locator('div[data-v-13320df0].icon').first
                    await icone.wait_for(timeout=5_000)
                    await icone.click()
                    await page.wait_for_timeout(3_000)
                    await page.screenshot(path=str(output_path / f"painel_tentativa_{tentativa_painel}.png"))
                    painel_aberto = True
                    logger.info(f"✅ Painel aberto (tentativa {tentativa_painel + 1})")
                    break
                except Exception as e:
                    logger.warning(f"Tentativa {tentativa_painel + 1} — ícone não encontrado: {e}")
                    await page.wait_for_timeout(30_000)

            if not painel_aberto:
                await page.screenshot(path=str(output_path / "erro_painel.png"))
                raise Exception("Não foi possível abrir o painel 'Última tarefa'.")

            # 7. LOCALIZAR TAREFA DO DRIVER PROFILE (filtrar por nome contendo "br_driver" ou "driver")
            # O painel lista TODAS as tarefas históricas — precisamos achar a do driver profile,
            # não a do PNR ou outras. O arquivo gerado tem nome com "br_driver".
            logger.info("Procurando tarefa do driver profile no painel...")
            palavras_chave = ["br_driver", "driver_profile", "driver-profile"]
            botao_baixar = None
            encontrado = False

            for tentativa in range(8):
                # Para cada palavra-chave, procura uma linha do painel que a contenha
                # e tenha um botão Baixar visível
                for palavra in palavras_chave:
                    candidato = page.locator(
                        f'*:has-text("{palavra}")'
                    ).locator(
                        'button:has-text("Baixar"), button:has-text("Download")'
                    ).first
                    try:
                        await candidato.wait_for(timeout=5_000, state="visible")
                        botao_baixar = candidato
                        encontrado = True
                        logger.info(f"✅ Tarefa encontrada (palavra-chave: '{palavra}', tentativa {tentativa + 1})!")
                        break
                    except Exception:
                        continue

                if encontrado:
                    break

                elapsed_extra = (tentativa + 1) * 30
                logger.info(f"Tarefa do driver profile não pronta — aguardando 30s ({elapsed_extra}s extra)...")
                await page.screenshot(path=str(output_path / f"aguardando_driver_{elapsed_extra}s.png"))
                # Reabre o painel para atualizar status
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(2_000)
                try:
                    icone = page.locator('div[data-v-13320df0].icon').first
                    await icone.wait_for(timeout=5_000)
                    await icone.click()
                    await page.wait_for_timeout(3_000)
                except Exception as e:
                    logger.warning(f"Erro ao reabrir painel: {e}")

            if not encontrado:
                await page.screenshot(path=str(output_path / "erro_sem_baixar.png"))
                raise Exception(
                    "Timeout: tarefa do driver profile (br_driver) não apareceu após 240s adicionais."
                )

            # 8. DOWNLOAD — clica no botão "Baixar" do driver profile
            caminho_arquivo = None
            logger.info("Clicando em 'Baixar' da tarefa do driver profile...")
            async with page.expect_download(timeout=120_000) as download_info:
                await botao_baixar.click()

            download = await download_info.value
            nome_baixado = download.suggested_filename.lower()
            logger.info(f"Nome do arquivo baixado: {download.suggested_filename}")

            if not any(p in nome_baixado for p in ["br_driver", "driver_profile", "driver-profile"]):
                raise Exception(
                    f"Arquivo baixado não é do driver profile! Nome: {download.suggested_filename}"
                )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho_arquivo = output_path / f"shopee_driver_profile_{timestamp}_{download.suggested_filename}"
            await download.save_as(str(caminho_arquivo))
            logger.info(f"✅ Arquivo baixado: {caminho_arquivo}")

        finally:
            await browser.close()

    # 8. PROCESSAR COM PANDAS
    logger.info("Processando arquivo...")
    sufixo = Path(caminho_arquivo).suffix.lower()

    if sufixo == ".zip":
        with zipfile.ZipFile(caminho_arquivo, 'r') as zip_ref:
            arquivos = zip_ref.namelist()
            logger.info(f"Arquivos no ZIP: {arquivos}")

            csv_files = sorted([f for f in arquivos if f.lower().endswith('.csv')])
            excel_files = [f for f in arquivos if f.lower().endswith(('.xlsx', '.xls'))]

            if csv_files:
                logger.info(f"Lendo {len(csv_files)} CSV(s) do ZIP...")
                dfs = []
                for csv_file in csv_files:
                    with zip_ref.open(csv_file) as f:
                        dfs.append(pd.read_csv(f))
                df = pd.concat(dfs, ignore_index=True)
            elif excel_files:
                arquivo_excel = excel_files[0]
                logger.info(f"Extraindo {arquivo_excel} do ZIP...")
                with zip_ref.open(arquivo_excel) as f:
                    df = pd.read_excel(f)
            else:
                raise Exception(f"Nenhum arquivo CSV/Excel no ZIP. Arquivos: {arquivos}")
    elif sufixo == ".csv":
        df = pd.read_csv(caminho_arquivo)
    else:
        df = pd.read_excel(caminho_arquivo)

    logger.info(f"Linhas brutas: {len(df)} | Colunas: {len(df.columns)}")

    # Normalizar colunas
    df.columns = (
        df.columns
        .str.replace("（", "(").str.replace("）", ")")
        .str.replace("'", "").str.replace('"', "")
        .str.strip().str.lower().str.replace(" ", "_")
        .str.replace("(#)", "_qtd", regex=False)
        .str.replace("(%)", "_perc", regex=False)
        .str.replace("(", "").str.replace(")", "")
        .str.replace("-", "_")
        .str.replace(r"[^a-z0-9_]", "", regex=True)
        .str.replace("__", "_").str.strip("_")
    )

    df["extracted_at"] = datetime.now()

    logger.info(f"Colunas normalizadas: {list(df.columns)}")
    logger.info(f"Total Motoristas: {len(df)}")

    processed_file = output_path / f"processed_{timestamp}.csv"
    df.to_csv(processed_file, index=False)
    logger.info(f"Dados processados salvos: {processed_file}")

    return processed_file


async def run():
    try:
        arquivo = await extract_shopee_driver_profile()
        logger.info(f"✅ Extração concluída: {arquivo}")
        return str(arquivo)
    except Exception as e:
        logger.error(f"❌ Falha na extração: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run())
