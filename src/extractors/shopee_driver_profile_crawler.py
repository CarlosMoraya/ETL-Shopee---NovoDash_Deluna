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

            # Estratégia 1: localizar item EXATO 'Export'/'Exportar' DENTRO de .el-dropdown-menu visível
            # (NÃO usar [role="menuitem"] genérico — casa nav lateral e dispara navegação errada)
            logger.info("Tentativa 1: Localizando item 'Export' do dropdown via JS (escopado)...")
            try:
                # Aguardar o dropdown realmente abrir — Shopee usa .ssc-dropdown-menu (custom),
                # não Element UI. Também aceitar .el-dropdown-menu como fallback.
                await page.wait_for_selector(
                    '.ssc-dropdown-menu, .el-dropdown-menu, [class*="dropdown-menu"]',
                    timeout=5_000,
                    state="visible",
                )
            except Exception as e:
                logger.warning(f"Dropdown não ficou visível em 5s: {e} — tentando re-clicar o botão Export...")
                try:
                    await botao_exportar.click()
                    await page.wait_for_timeout(800)
                except Exception:
                    pass

            await page.screenshot(path=str(output_path / "dropdown_aberto.png"))

            try:
                result = await page.evaluate("""
                    () => {
                        // Buscar dentro de QUALQUER dropdown-menu visível (Shopee usa .ssc-dropdown-menu)
                        const menus = Array.from(document.querySelectorAll(
                            '.ssc-dropdown-menu, .el-dropdown-menu, [class*="dropdown-menu"]'
                        )).filter(m => {
                            const s = window.getComputedStyle(m);
                            return s.display !== 'none' && s.visibility !== 'hidden';
                        });
                        for (const menu of menus) {
                            // Buscar TODOS os clicáveis dentro do menu, não só li
                            const items = Array.from(menu.querySelectorAll(
                                'li, .ssc-dropdown-menu-item, [class*="dropdown-menu-item"], '
                                + '.el-dropdown-menu__item, [role="menuitem"], div, span, a'
                            )).filter(el => {
                                // Apenas elementos folha com texto curto (evita pegar o menu inteiro)
                                const txt = (el.textContent || '').trim();
                                return txt.length > 0 && txt.length < 60 && el.children.length <= 2;
                            });
                            // Procurar item com texto EXATO "Export" / "Exportar"
                            // (NÃO "Export History" / "Histórico de exportação")
                            const alvo = items.find(it => {
                                const txt = (it.textContent || '').trim().toLowerCase();
                                return txt === 'export' || txt === 'exportar';
                            });
                            if (alvo) {
                                alvo.click();
                                return { success: true, text: alvo.textContent.trim() };
                            }
                            // Fallback: primeiro item que NÃO contenha "history"/"histórico"
                            const naoHist = items.find(it => {
                                const txt = (it.textContent || '').trim().toLowerCase();
                                return txt && !txt.includes('hist') && (txt.includes('export') || txt.includes('exportar'));
                            });
                            if (naoHist) {
                                naoHist.click();
                                return { success: true, text: naoHist.textContent.trim() };
                            }
                        }
                        return { success: false, reason: 'Nenhum item Export encontrado em dropdown VISÍVEL' };
                    }
                """)
                if result.get('success'):
                    logger.info(f"✅ Item de dropdown clicado via JS: '{result.get('text')}'")
                    export_sucesso = True
                else:
                    logger.warning(f"JS falhou: {result.get('reason')}")
            except Exception as e:
                logger.warning(f"Estratégia 1 (JS escopado) falhou: {e}")

            # Estratégia 2: teclado (ArrowDown + Enter) — só se dropdown estiver aberto
            if not export_sucesso:
                logger.info("Tentativa 2: Teclado (ArrowDown + Enter)...")
                try:
                    await botao_exportar.click()
                    await page.wait_for_timeout(800)
                    await page.keyboard.press("ArrowDown")
                    await page.wait_for_timeout(200)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(1_000)
                    export_sucesso = True
                    logger.info("✅ ArrowDown + Enter executado!")
                except Exception as e:
                    logger.warning(f"Teclado falhou: {e}")

            # Estratégia 3: coordenadas relativas ao botão (clique abaixo do Export)
            if not export_sucesso:
                logger.info("Tentativa 3: Click por coordenadas abaixo do botão...")
                try:
                    await botao_exportar.click()
                    await page.wait_for_timeout(800)
                    coords = await page.evaluate("""
                        () => {
                            const buttons = Array.from(document.querySelectorAll('button'));
                            const btn = buttons.find(b => {
                                const t = (b.textContent || '').trim().toLowerCase();
                                return t === 'exportar' || t === 'export';
                            });
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
                        logger.warning("Botão Export não encontrado via JS")
                except Exception as e:
                    logger.warning(f"Coordenadas falharam: {e}")

            if not export_sucesso:
                await page.screenshot(path=str(output_path / "erro_exportar.png"))
                raise Exception("Não foi possível acionar a exportação via dropdown")

            await page.screenshot(path=str(output_path / "pos_export_click.png"))

            logger.info("Exportação solicitada — aguardando 90s para processamento do servidor...")
            await page.wait_for_timeout(90_000)

            # 6. NAVEGAR PARA A PÁGINA DEDICADA "Export Task Center"
            # Muito mais determinístico que tentar abrir popover "Latest Task"
            export_center_url = "https://logistics.myagencyservice.com.br/#/taskCenter/exportTaskCenter"
            logger.info(f"Navegando para Export Task Center: {export_center_url}")
            await page.goto(export_center_url, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(5_000)
            await page.screenshot(path=str(output_path / "export_task_center.png"))

            # 7. POLLING — recarregar e procurar tarefa com timestamp >= hora_antes_export
            # E botão "Baixar"/"Download". Validar pelo nome do arquivo.
            logger.info(
                f"Procurando tarefa com horário >= {hora_antes_export.strftime('%Y-%m-%d %H:%M:%S')} "
                f"e botão Baixar disponível..."
            )
            caminho_arquivo = None
            encontrado = False

            for tentativa in range(12):
                await page.wait_for_timeout(2_000)

                # Coletar TODAS as linhas com botão Baixar/Download e tentar extrair timestamp
                tarefas_info = await page.evaluate("""
                    () => {
                        const tarefas = [];
                        // SSC table rows ou Element UI rows
                        const rows = document.querySelectorAll(
                            'tr, .ssc-table-row, [class*="table-row"], [class*="task-row"]'
                        );
                        rows.forEach((row, idx) => {
                            const text = row.textContent || '';
                            const timeMatch = text.match(/\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}/);
                            const horario = timeMatch ? timeMatch[0] : 'desconhecido';
                            const buttons = row.querySelectorAll('button, a, span[class*="btn"]');
                            let temBaixar = false;
                            buttons.forEach(btn => {
                                const t = (btn.textContent || '').trim();
                                if (t === 'Baixar' || t === 'Download') {
                                    temBaixar = true;
                                }
                            });
                            if (temBaixar) {
                                tarefas.push({ idx, horario, snippet: text.substring(0, 150) });
                            }
                        });
                        return tarefas;
                    }
                """)

                logger.info(f"Tentativa {tentativa + 1}: {len(tarefas_info)} linhas com botão Baixar")

                # Filtrar tarefas com timestamp >= hora_antes_export
                # (margem de -60s para tolerar dessincronia de timezone)
                limite = hora_antes_export.replace(microsecond=0)
                candidatas = []
                for t in tarefas_info:
                    h = t['horario']
                    if h == 'desconhecido':
                        continue
                    try:
                        dt = datetime.strptime(h, '%Y-%m-%d %H:%M:%S')
                        if dt >= limite:
                            candidatas.append((dt, t))
                    except Exception:
                        continue

                if candidatas:
                    candidatas.sort(key=lambda x: x[0], reverse=True)
                    logger.info(f"   {len(candidatas)} candidatas posteriores ao export — tentando mais recente")
                    for _, alvo in candidatas:
                        logger.info(f"   Tentando linha idx={alvo['idx']} horário={alvo['horario']}")
                        try:
                            async with page.expect_download(timeout=60_000) as download_info:
                                click_result = await page.evaluate(
                                    """
                                    (idx) => {
                                        const rows = document.querySelectorAll(
                                            'tr, .ssc-table-row, [class*="table-row"], [class*="task-row"]'
                                        );
                                        const row = rows[idx];
                                        if (!row) return { success: false, reason: 'linha não existe' };
                                        const buttons = row.querySelectorAll('button, a, span[class*="btn"]');
                                        for (const btn of buttons) {
                                            const t = (btn.textContent || '').trim();
                                            if (t === 'Baixar' || t === 'Download') {
                                                btn.click();
                                                return { success: true };
                                            }
                                        }
                                        return { success: false, reason: 'botão não encontrado' };
                                    }
                                    """,
                                    alvo['idx'],
                                )
                            if not click_result.get('success'):
                                logger.warning(f"   Click falhou: {click_result.get('reason')}")
                                continue

                            download = await download_info.value
                            nome_baixado = download.suggested_filename.lower()
                            logger.info(f"   Arquivo baixado: {download.suggested_filename}")

                            if "driver" not in nome_baixado:
                                logger.warning(
                                    f"   ⚠️ Arquivo não é driver profile ({nome_baixado}) — pulando"
                                )
                                continue

                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            caminho_arquivo = (
                                output_path
                                / f"shopee_driver_profile_{timestamp}_{download.suggested_filename}"
                            )
                            await download.save_as(str(caminho_arquivo))
                            logger.info(f"✅ Arquivo salvo: {caminho_arquivo}")
                            encontrado = True
                            break
                        except Exception as e:
                            logger.warning(f"   Erro no download desta linha: {e}")
                            continue

                    if encontrado:
                        break

                # Nenhuma candidata válida ainda — recarregar e tentar de novo
                elapsed = (tentativa + 1) * 20
                logger.info(f"Aguardando 20s antes de recarregar a página ({elapsed}s decorridos)...")
                await page.screenshot(path=str(output_path / f"export_center_t{tentativa}.png"))
                await page.wait_for_timeout(20_000)
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30_000)
                    await page.wait_for_timeout(3_000)
                except Exception as e:
                    logger.warning(f"Reload falhou: {e}")

            if not encontrado:
                await page.screenshot(path=str(output_path / "erro_export_center.png"))
                raise Exception(
                    f"Timeout: nenhuma tarefa driver profile pronta para download em "
                    f"/taskCenter/exportTaskCenter após ~4 min (esperando timestamp >= "
                    f"{hora_antes_export.strftime('%Y-%m-%d %H:%M:%S')}). "
                    f"Export pode não ter sido disparado ou está demorando demais."
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
