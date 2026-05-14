# 📚 GUIA COMPLETO: Configurar GitHub Actions + ETL Shopee

> **Para iniciantes**: Explicação passo a passo como se você nunca tivesse usado GitHub Actions antes.

---

## 📋 Sumário do que você vai fazer:

1. ✅ Configurar banco de dados na nuvem (Neon)
2. ✅ Adicionar suas credenciais no GitHub (Secrets)
3. ✅ Rodar o pipeline manualmente para testar
4. ✅ Configurar agendamento automático

**Tempo estimado**: 30 minutos

---

## PASSO 1: Criar Banco de Dados no Neon

### O que é Neon?
Neon é um serviço de banco PostgreSQL na nuvem. É como alugar um computador que guarda seus dados 24h.

### Como criar:

1. **Abra seu navegador** e vá para: https://neon.tech/

2. **Clique em "Sign Up"** (canto superior direito)

3. **Crie sua conta** usando:
   - ✅ Email: `cadu.moraya@gmail.com`
   - ✅ Senha: escolha uma forte

4. **Verifique o email** (pode ir para spam)

5. **Após login**, você verá um painel com "New Project" - **clique nele**

6. **Preencha os dados do projeto**:
   - Project name: `ETL-Shopee` (ou qual nome quiser)
   - Database name: `neondb` (deixe assim mesmo)
   - Clique em **"Create Project"**

7. **Aguarde** alguns segundos até o banco ser criado

8. **Copie a Connection String**:
   - Na página que aparecer, procure por "Connection details"
   - Você verá algo assim:
   ```
   postgresql://neondb_owner:seu_token_gigante@ep-xxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```
   - **Copie TODA essa linha** (Ctrl+C / Cmd+C)
   - Guarde em um bloco de notas, você vai usar daqui a pouco

✅ **Pronto! Seu banco está criado.**

---

## PASSO 2: Adicionar Credenciais no GitHub (Secrets)

### O que são "Secrets"?
Secrets são variáveis secretas que o GitHub guarda. O GitHub Actions consegue usar elas sem exposor publicamente.

### Como adicionar:

1. **Vá para seu repositório GitHub**
   - Link: https://github.com/CarlosMoraya/ETL-Shopee---NovoDash_Deluna

2. **Clique em "Settings"** (aba no topo do repositório)

3. **No menu lateral esquerdo, clique em "Secrets and variables"**
   - Depois em **"Actions"**

4. **Clique em "New repository secret"** (botão verde)

5. **Adicione 3 secrets** (um por um):

### Secret 1: NEON_DATABASE_URL
- **Name**: `NEON_DATABASE_URL`
- **Value**: Cole aquela string que você copiou no Passo 1
  ```
  postgresql://neondb_owner:seu_token_gigante@ep-xxx.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
  ```
- Clique **"Add secret"**

### Secret 2: SHOPEE_EMAIL
- **Name**: `SHOPEE_EMAIL`
- **Value**: Seu email de acesso à Shopee Logistics
  ```
  seu.email@empresa.com
  ```
- Clique **"Add secret"**

### Secret 3: SHOPEE_PWD
- **Name**: `SHOPEE_PWD`
- **Value**: Sua senha de acesso à Shopee Logistics
  ```
  sua_senha_aqui
  ```
- Clique **"Add secret"**

✅ **Agora GitHub Actions tem suas credenciais guardadas de forma segura!**

---

## PASSO 3: Entender os Workflows (Pipelines)

### O que é um Workflow?
Um workflow é um arquivo `.yml` que descreve tarefas que o GitHub pode rodar automaticamente.

### Seus workflows:

Você tem 3 pipelines configurados:

| Pipeline | Frequência | Arquivo | O que faz |
|----------|------------|---------|-----------|
| **Monitoramento** | A cada 15 min | `etl-shopee-monitoramento.yml` | Extrai dados de motoristas |
| **Driver Profile** | Diário (00h) | `etl-shopee-driver-profile.yml` | Perfil dos drivers |
| **PNR** | Diário (00h) | `etl-shopee-pnr.yml` | Dados de PNR |

### Estrutura de um Workflow:

```
1. ⬜ Checkout do código (baixa o projeto)
   ↓
2. ⬜ Setup Python (instala Python 3.11)
   ↓
3. ⬜ Instalar dependências (pip install -r requirements.txt)
   ↓
4. ⬜ Instalar browsers (Playwright para web scraping)
   ↓
5. ⬜ Rodar Pipeline ETL (executa o script Python)
   ↓
6. ⬜ Upload de artifacts (se deu erro, salva logs)
```

---

## PASSO 4: Rodar Manualmente (Teste)

### Como testar antes de agendamento automático:

1. **Vá para seu repositório GitHub**
   - https://github.com/CarlosMoraya/ETL-Shopee---NovoDash_Deluna

2. **Clique na aba "Actions"** (ao lado de "Code", "Issues", etc)

3. **No lado esquerdo, clique em "ETL Shopee - Monitoramento (15 min)"**

4. **Você verá um botão azul com seta: "Run workflow"**
   - Clique nele
   - Selecione a branch `main` (padrão)
   - Clique em "Run workflow" de novo

5. **Aguarde**: Você verá uma linha amarela aparecendo com um "●" pulsando
   - Isso significa que está rodando
   - Pode levar 2-5 minutos

6. **Acompanhe os logs**:
   - Clique na linha do workflow em execução
   - Veja cada step sendo executado em tempo real
   - Procure por erros em vermelho

### Se der sucesso ✅
Você verá na tela:
```
✓ Checkout do código
✓ Setup Python
✓ Instalar dependências
✓ Instalar browsers do Playwright
✓ Rodar Pipeline ETL
```

### Se der erro ❌
Procure pelo step com problemas (em vermelho) e:
- Leia a mensagem de erro
- Verifique se as Secrets foram adicionadas corretamente
- Verifique se email/senha Shopee estão corretos

---

## PASSO 5: Entender o Agendamento

### Cron Expressions (Horários)

Cada workflow tem um horário para rodar. Isso é definido com uma expressão **cron**.

**Formato**: `minuto hora dia_mês mês dia_semana`

### Exemplos:

| Expressão | Significado |
|-----------|-----------|
| `*/15 0-2,9-23 * * *` | A cada 15 min, de 00h a 02h59 e de 09h a 23h59 (Monitoramento) |
| `0 3 * * *` | Todos os dias às 03h UTC (= 00h BRT) |
| `0 9 * * 1` | Toda segunda-feira às 09h UTC |

### Fusos Horários:
- **BRT** (Brasil) = **UTC - 3**
- Então: 03h UTC = 00h BRT

### Seus horários atuais:

**Monitoramento (15 em 15 min)**:
- Cron: `*/15 0-2,9-23 * * *`
- Significa: Roda de 15 em 15 min, das 00h às 02h59 UTC e 09h às 23h59 UTC
- Em Brasília: 21h a 23h59 (anterior) + 06h a 20h59 (atual)

**Driver Profile** (Diário):
- Cron: `0 3 * * *`
- Significa: Todos os dias às 03h UTC
- Em Brasília: Todos os dias às 00h (meia-noite)

**PNR** (Diário):
- Cron: `0 3 * * *`
- Significa: Todos os dias às 03h UTC
- Em Brasília: Todos os dias às 00h (meia-noite)

---

## PASSO 6: Acompanhar Execuções

### Dashboard de Execuções:

1. **Vá para Actions** (no GitHub)

2. **Você verá uma lista com todos os runs** (execuções)
   - Verde ✅ = sucesso
   - Vermelho ❌ = erro
   - Amarelo ⏳ = em andamento

3. **Para ver detalhes**:
   - Clique no workflow
   - Clique no job específico
   - Expanda cada "step" para ver logs

### Entender os Logs:

```
⏱️ 2026-05-13 21:30:15 UTC - Checkout do código
   → git checkout main
   → ✓ Código baixado

⏱️ 2026-05-13 21:30:25 UTC - Setup Python
   → Python 3.11.5
   → ✓ Python pronto

⏱️ 2026-05-13 21:30:30 UTC - Instalar dependências
   → pip install --no-cache-dir -r requirements.txt
   → Downloading playwright-1.49.1
   → ✓ Dependências instaladas

⏱️ 2026-05-13 21:30:45 UTC - Rodar Pipeline ETL
   → python -m src.pipelines.shopee_monitoramento_pipeline
   → Conectando ao Neon...
   → Extraindo dados...
   → Transformando dados...
   → Carregando no banco...
   → ✓ 25 registros inseridos
```

---

## PASSO 7: Verificar Dados no Banco

### Conectar ao Neon e ver os dados:

1. **Vá para https://neon.tech**

2. **Login com sua conta**

3. **Clique no seu projeto (ETL-Shopee)**

4. **Clique em "SQL Editor"** (ao lado)

5. **Execute esta query para ver os dados**:
```sql
SELECT * FROM shopee_monitoramento 
ORDER BY extracted_at DESC 
LIMIT 10;
```

6. **Clique em "Run"** (Ctrl+Enter)

7. Você verá os dados que o ETL inseriu! 🎉

---

## 🚨 Troubleshooting (Resolvendo Problemas)

### Problema: "Secret not found"
**Solução**: Verifique se as Secrets foram adicionadas corretamente:
- Vá em Settings → Secrets and variables → Actions
- Confira se todas as 3 secrets estão lá
- Se faltar alguma, adicione novamente

### Problema: "Connection refused"
**Solução**: Verifique a Connection String:
- Pode estar incorreta ou expirada
- Copie novamente da página do Neon

### Problema: "Playwright timeout"
**Solução**: Shopee pode estar lento ou bloqueando
- Tente rodar manualmente depois
- Verifique se email/senha estão corretos
- Pode estar pedindo 2FA (autenticação dupla)

### Problema: "Table does not exist"
**Solução**: A tabela ainda não foi criada
- Na primeira execução, o código cria a tabela
- Verifique nos logs se o erro é em "CREATE TABLE" ou "INSERT"

### Problema: "Syntax error in yml"
**Solução**: O arquivo workflow tem erro de formatação
- YAML é sensível a espaçamento
- Use espaços, NÃO tabs
- Valide em https://www.yamllint.com/

---

## 📊 Estrutura dos Dados

### Tabela: `shopee_monitoramento`

| Coluna | Tipo | Exemplo |
|--------|------|---------|
| `driver_id` | VARCHAR | `12345` |
| `driver_name` | VARCHAR | `João Silva` |
| `assigned` | INTEGER | `50` |
| `handed_over` | INTEGER | `45` |
| `delivered_qtd` | INTEGER | `40` |
| `on_hold` | INTEGER | `5` |
| `delivering_qtd` | INTEGER | `10` |
| `extracted_at` | TIMESTAMP | `2026-05-13 21:35:00` |

---

## ✅ Checklist Final

- [ ] Criei conta no Neon
- [ ] Copiei a Connection String
- [ ] Adicionei NEON_DATABASE_URL no GitHub Secrets
- [ ] Adicionei SHOPEE_EMAIL no GitHub Secrets
- [ ] Adicionei SHOPEE_PWD no GitHub Secrets
- [ ] Rodei um workflow manualmente e passou ✅
- [ ] Verifiquei os dados no banco do Neon
- [ ] Entendi o agendamento (cron)
- [ ] Tenho um lugar seguro para guardar as credenciais

---

## 📞 Resumo Rápido do Que Acontece

```
┌─────────────────────────────────────────────────────────────┐
│  A cada 15 minutos (ou quando você dispara manualmente):    │
├─────────────────────────────────────────────────────────────┤
│ 1. GitHub Actions baixa seu código                          │
│ 2. Instala Python e dependências                            │
│ 3. Instala Playwright (navegador automatizado)              │
│ 4. Seu script Python faz login na Shopee                    │
│ 5. Extrai dados de motoristas                               │
│ 6. Transforma e limpa os dados                              │
│ 7. Insere no banco Neon                                     │
│ 8. Se deu erro, salva screenshots em artifacts              │
│ 9. Workflow termina                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎓 Próximos Passos

Agora que você entende como funciona:

1. **Adicione alertas**: Configure notificações quando algo falhar
2. **Adicione mais pipelines**: Implemente outras telas do Shopee
3. **Crie dashboards**: Visualize os dados em ferramentas como Metabase
4. **Configure backups**: Exporte dados periodicamente

---

**Dúvidas?** Consulte:
- [Documentação GitHub Actions](https://docs.github.com/pt/actions)
- [Documentação Neon](https://neon.tech/docs/)
- [Documentação Playwright](https://playwright.dev/python/)
