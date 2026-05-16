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

            # 4. ABRIR DROPDOWN DE EXPORTAR
            logger.info("Clicando em 'Exportar' para abrir dropdown...")
            botao_exportar = page.locator('button:has-text("Exportar"), button:has-text("Export")').first
            await botao_exportar.wait_for(timeout=10_000)
            await botao_exportar.click()

            hora_antes_export = datetime.now()
            logger.info(f"🕐 Horário do clique em Exportar: {hora_antes_export.strftime('%Y-%m-%d %H:%M:%S')}")

            await page.wait_for_timeout(1_000)
            await page.screenshot(path=str(output_path / "dropdown_aberto.png"))

            export_sucesso = False

            # Estratégia 1: locator Playwright nativo
            logger.info("Tentativa 1: Localizando item do dropdown via Playwright...")
            for sel in [
                '.el-dropdown-menu__item:first-child',
                '.el-dropdown-menu li:first-child',
                'li.el-dropdown-menu__item',
                '[role="menuitem"]',
            ]:
                item = page.locator(sel).first
                cnt = await item.count()
                if cnt > 0:
                    txt = await item.inner_text()
                    logger.info(f"Item encontrado via '{sel}': '{txt}' — clicando...")
                    try:
                        await item.click(timeout=2_000)
                    except Exception:
                        await item.click(force=True)
                    logger.info("✅ Item de dropdown clicado!")
                    export_sucesso = True
                    break

            # Estratégia 2: teclado (ArrowDown + Enter)
            if not export_sucesso:
                logger.info("Tentativa 2: Teclado (ArrowDown + Enter)...")
                try:
                    await botao_exportar.click()
                    await page.wait_for_timeout(400)
                    await page.keyboard.press("ArrowDown")
                    await page.wait_for_timeout(200)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(1_000)
                    export_sucesso = True
                    logger.info("✅ ArrowDown + Enter executado!")
                except Exception as e:
                    logger.warning(f"Teclado falhou: {e}")

            # Estratégia 3: JavaScript no menu dropdown
            if not export_sucesso:
                logger.info("Tentativa 3: JavaScript no menu dropdown...")
                try:
                    await botao_exportar.click()
                    await page.wait_for_timeout(500)
                    result = await page.evaluate("""
                        () => {
                            const menus = document.querySelectorAll(
                                '.el-dropdown-menu, [class*="dropdown-menu"]'
                            );
                            for (const menu of menus) {
                                const items = menu.querySelectorAll('li, .el-dropdown-menu__item');
                                for (const item of items) {
                                    const txt = item.textContent.trim();
                                    if (txt && !txt.toLowerCase().includes('hist')) {
                                        item.click();
                                        return { success: true, text: txt };
                                    }
                                }
                                if (items.length > 0) {
                                    items[0].click();
                                    return { success: true, text: items[0].textContent.trim() };
                                }
                            }
                            return { success: false, reason: 'Nenhum menu dropdown encontrado no DOM' };
                        }
                    """)
                    if result.get('success'):
                        logger.info(f"✅ JS dropdown: '{result.get('text')}'")
                        export_sucesso = True
                    else:
                        logger.warning(f"JS: {result.get('reason')}")
                except Exception as e:
                    logger.warning(f"JavaScript falhou: {e}")

            # Estratégia 4: coordenadas relativas ao botão
            if not export_sucesso:
                logger.info("Tentativa 4: Click por coordenadas abaixo do botão...")
                try:
                    await botao_exportar.click()
                    await page.wait_for_timeout(500)
                    coords = await page.evaluate("""
                        () => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const btn = buttons.find(b => b.textContent.trim() === 'Exportar' || b.textContent.trim() === 'Export');
                            if (!btn) return null;
                            const rect = btn.getBoundingClientRect();
                            return { x: rect.left + rect.width / 2, y: rect.bottom + 20 };
                        }
                    """)
                    if coords:
                        logger.info(f"Clicando em ({coords['x']:.0f}, {coords['y']:.0f})...")
                        await page.mouse.click(coords['x'], coords['y'])
                        export_sucesso = True
                        logger.info("✅ Click por coordenadas!")
                    else:
                        logger.warning("Botão Exportar não encontrado via JS")
                except Exception as e:
                    logger.warning(f"Coordenadas falharam: {e}")

            if not export_sucesso:
                await page.screenshot(path=str(output_path / "erro_exportar.png"))
                raise Exception("Não foi possível acionar a exportação via dropdown")

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

            # 7. AGUARDAR NOVA TAREFA — buscar tarefa com timestamp >= hora_antes_export
            logger.info(
                f"Aguardando NOVA tarefa de Spx Driver com horário >= "
                f"{hora_antes_export.strftime('%Y-%m-%d %H:%M:%S')}..."
            )
            caminho_arquivo = None
            encontrado = False

            for tentativa in range(10):
                tarefas_info = await page.evaluate("""
                    () => {
                        const tarefas = [];
                        document.querySelectorAll('tr, .el-scrollbar__view > div, [class*="task"], [class*="item"]').forEach(el => {
                            const text = el.textContent || '';
                            if (text.includes('Spx Driver') || text.includes('spx_driver')) {
                                const timeMatch = text.match(/\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}/);
                                const horario = timeMatch ? timeMatch[0] : 'desconhecido';
                                const buttons = el.querySelectorAll('button, a');
                                buttons.forEach(btn => {
                                    if (btn.textContent.includes('Baixar') || btn.textContent.includes('Download')) {
                                        tarefas.push({ horario, text: text.substring(0, 200) });
                                    }
                                });
                            }
                        });
                        return tarefas;
                    }
                """)

                logger.info(f"Tentativa {tentativa + 1}: {len(tarefas_info)} tarefas Spx Driver com botão Baixar")

                tarefa_valida = None
                if tarefas_info:
                    tarefa_mais_recente = max(tarefas_info, key=lambda x: x['horario'])
                    horario_str = tarefa_mais_recente['horario']
                    logger.info(f"   Mais recente: {horario_str}")
                    if horario_str != 'desconhecido':
                        try:
                            hora_tarefa_dt = datetime.strptime(horario_str, '%Y-%m-%d %H:%M:%S')
                            if hora_tarefa_dt >= hora_antes_export:
                                tarefa_valida = tarefa_mais_recente
                                logger.info(
                                    f"✅ Tarefa {horario_str} é posterior à exportação — baixando!"
                                )
                            else:
                                logger.info(
                                    f"   Tarefa {horario_str} ainda é anterior à exportação "
                                    f"({hora_antes_export.strftime('%Y-%m-%d %H:%M:%S')})"
                                )
                        except Exception as e:
                            logger.warning(f"   Erro ao parsear horário: {e}")

                if tarefa_valida:
                    async with page.expect_download(timeout=120_000) as download_info:
                        click_result = await page.evaluate("""
                            () => {
                                const elementos = document.querySelectorAll('tr, .el-scrollbar__view > div, [class*="task"], [class*="item"]');
                                let melhor = null;
                                let melhorHorario = '';
                                elementos.forEach(el => {
                                    const text = el.textContent || '';
                                    if (text.includes('Spx Driver') || text.includes('spx_driver')) {
                                        const timeMatch = text.match(/\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}/);
                                        const horario = timeMatch ? timeMatch[0] : '';
                                        if (horario > melhorHorario) {
                                            melhorHorario = horario;
                                            melhor = el;
                                        }
                                    }
                                });
                                if (!melhor) return { success: false };
                                const buttons = melhor.querySelectorAll('button, a');
                                for (const btn of buttons) {
                                    if (btn.textContent.includes('Baixar') || btn.textContent.includes('Download')) {
                                        btn.click();
                                        return { success: true, horario: melhorHorario };
                                    }
                                }
                                return { success: false };
                            }
                        """)

                    if not click_result.get('success'):
                        logger.warning("⚠️ Encontrou tarefa válida mas não conseguiu clicar — re-tentando...")
                    else:
                        logger.info(f"✅ Botão 'Baixar' clicado na tarefa {click_result.get('horario')}!")
                        download = await download_info.value
                        nome_baixado = download.suggested_filename.lower()
                        logger.info(f"Nome do arquivo baixado: {download.suggested_filename}")

                        if "driver" not in nome_baixado:
                            raise Exception(
                                f"Arquivo baixado não é do driver profile (não contém 'driver')! "
                                f"Nome: {download.suggested_filename}"
                            )

                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        caminho_arquivo = output_path / f"shopee_driver_profile_{timestamp}_{download.suggested_filename}"
                        await download.save_as(str(caminho_arquivo))
                        logger.info(f"✅ Arquivo baixado: {caminho_arquivo}")
                        encontrado = True
                        break

                elapsed_extra = (tentativa + 1) * 30
                logger.info(f"Nenhuma nova tarefa ainda — aguardando 30s ({elapsed_extra}s extra)...")
                await page.screenshot(path=str(output_path / f"aguardando_nova_tarefa_{elapsed_extra}s.png"))
                await page.wait_for_timeout(30_000)

            if not encontrado:
                await page.screenshot(path=str(output_path / "erro_sem_nova_tarefa.png"))
                raise Exception(
                    f"Timeout: nenhuma nova tarefa de export Spx Driver apareceu após 300s "
                    f"(esperando horário >= {hora_antes_export.strftime('%Y-%m-%d %H:%M:%S')}). "
                    f"Export pode não ter sido disparado."
                )

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
