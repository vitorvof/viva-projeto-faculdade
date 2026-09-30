# Healix — Sistema de Apoio e Triagem em Prevenção ao Suicídio Assistido por IA
### Protótipo — Fase 1 (simulação interna)

Este é o protótipo do projeto de extensão universitária, correspondente à
**Fase 1** da proposta aprovada: simulação interna completa do fluxo de
triagem, sem contato real com autoridades e sem uso real de localização.

Agora o protótipo é um site completo, não só uma tela de chat:

- `/` — página inicial (institucional, "a vida importa")
- `/sobre` — sobre o projeto, como funciona, em que fase estamos
- `/artigos` — "Importância da vida": o que ajuda no dia a dia, sinais de
  alerta, mitos e verdades
- `/conversar` — o chat com a IA (era a página `/` antes)
- `/painel` — painel da equipe de plantão (não aparece no menu público —
  acesso só por quem tem o link, e exige **login individual**, ver abaixo)
- `/login` — tela de login da equipe de plantão

## ⚠️ Antes de usar com qualquer pessoa real

Este projeto **não deve ser usado com usuários reais** antes de:

1. A lista de frases de alerta máximo (`triage.py` → `IMMEDIATE_TRIGGER_PATTERNS`)
   e os sinais cumulativos (`CUMULATIVE_SIGNALS`) serem revisados, ampliados e
   validados por um(a) psicólogo(a) — a lista atual é apenas um ponto de
   partida ilustrativo.
2. O projeto ser submetido e aprovado por um Comitê de Ética em Pesquisa (CEP).
3. Haver um(a) psicólogo(a) inscrito(a) no CRP responsável pela supervisão
   clínica e pelo atendimento real dos casos escalonados.

Sem esses três pontos, use o protótipo apenas para demonstração, testes
internos da equipe e apresentação acadêmica.

## O que este protótipo faz

- **Chat com IA** (`/`) — o usuário conversa livremente; a cada mensagem, o
  motor de triagem analisa o conteúdo.
- **Camada 1 — Gatilho imediato**: frases de risco iminente (plano, método,
  prazo, despedida) escalonam a conversa instantaneamente.
- **Camada 2 — Pontuação cumulativa**: sinais mais sutis (tristeza,
  isolamento, desesperança...) somam pontos; ao atingir o limiar, também
  escalona.
- **Login individual da equipe de plantão** (`/login`) — cada psicólogo(a)
  tem sua própria conta (e-mail + senha, com hash — nunca em texto puro).
  Depois de 5 tentativas de senha inválidas, o acesso daquela conta fica
  bloqueado por 15 minutos. Ver "Gerenciando a equipe de plantão" abaixo.
- **Camada 3 — Confirmação humana**: nenhuma ação externa é automática. Um
  alerta aparece no **painel da equipe de plantão** (`/painel`), que pode:
  - **Assumir a conversa** — a partir daí, a IA para de responder e o
    psicólogo passa a conversar diretamente com o paciente em tempo real
    (o paciente recebe as mensagens automaticamente, via polling, sem
    precisar atualizar a página);
  - **Resolver sem assumir** — marcar falso positivo, atendimento remoto já
    concluído, encaminhamento, ou confirmação de risco iminente (esta
    última, no protótipo, apenas **registra a decisão** — não liga para o
    SAMU nem usa localização de verdade). Encerrar o atendimento devolve a
    sessão para o acompanhamento normal da IA.
- **Encerrar conversa** (lado do paciente) — botão no cabeçalho do chat que
  encerra a sessão atual e permite iniciar uma conversa nova do zero no
  mesmo navegador (útil para computador compartilhado ou para testar vários
  atendimentos seguidos).
- **CVV (188) e SAMU (192) sempre visíveis** em ambas as telas, independente
  da avaliação da IA.

## Como rodar

```bash
cd app
pip install -r requirements.txt --break-system-packages   # ou num virtualenv
cd backend
python3 database.py     # cria o banco SQLite (app.db)
python3 app.py           # inicia o servidor em http://localhost:5050
```

Abra `http://localhost:5050/` para ver o site (página inicial), e
`http://localhost:5050/painel` em outra aba (painel da equipe de plantão) —
dá pra testar os dois lados ao mesmo tempo. O chat com a IA agora fica em
`http://localhost:5050/conversar`.

Na primeira vez que você roda o app localmente, se nenhuma conta existir
ainda, uma conta de demonstração é criada automaticamente — o terminal
mostra o e-mail e a senha dela (procure pelo aviso `[auth] AVISO:`). Use-a
para entrar em `/login`, ou crie a sua com o utilitário abaixo.

### Gerenciando a equipe de plantão (local)

```bash
cd backend
python3 manage_funcionarios.py listar
python3 manage_funcionarios.py adicionar "Vitor Franco" vitor@exemplo.com minhasenha123
python3 manage_funcionarios.py resetar-senha vitor@exemplo.com outrasenha456
python3 manage_funcionarios.py desativar vitor@exemplo.com   # bloqueia o acesso sem apagar a conta
```

### Testes automatizados

```bash
cd backend
python3 test_triage.py
# ou, se tiver pytest instalado: pytest test_triage.py -v
```

## Como colocar no ar (link público, para demonstração)

Isso publica o app num endereço `https://algumacoisa.onrender.com` acessível
de qualquer navegador, sem precisar do seu computador ligado. **Só faça isso
para demonstração controlada** (professores, banca, um grupo pequeno e
conhecido) — não anuncie o link publicamente nem use com pessoas reais em
crise (ver aviso no topo deste arquivo).

### 1. Prepare as contas da equipe de plantão (obrigatório antes de publicar)

O acesso ao `/painel` agora exige login individual (e-mail + senha por
funcionário), em vez de uma senha única compartilhada. **Nunca coloque
e-mails e senhas reais da equipe no código** — este repositório é público.
As contas são criadas a partir da variável de ambiente `FUNCIONARIOS_SEED`,
configurada só no Render (passo 4), no formato:

```
Nome Completo:email:senha;Nome Completo 2:email2:senha2
```

Exemplo com a equipe do projeto (troque pelos e-mails e senhas reais na hora
de configurar no Render — isto aqui é só ilustrativo):

```
Vitor Franco:vitor.franco@exemplo.com:senhaForte1;Vitor Bertok:vitor.bertok@exemplo.com:senhaForte2;Vitor Nunes:vitor.nunes@exemplo.com:senhaForte3;Thiago:thiago@exemplo.com:senhaForte4;Fabio:fabio@exemplo.com:senhaForte5
```

Se você esquecer de configurar essa variável, o app cria uma única conta de
demonstração automaticamente (e avisa no log) — funciona para testar, mas
substitua por contas reais antes de divulgar o link.

### 2. Sobe o código pro GitHub (via GitHub Desktop, sem usar terminal)

1. Abre o GitHub Desktop → **File → New Repository**. Escolhe a pasta `app`
   deste projeto (ou a pasta `healix-app` inteira) como local do repositório.
2. Clica em **Publish repository**. Pode deixar como privado.
3. Confirma que os arquivos `gemini_key.txt`, `anthropic_key.txt` e `app.db`
   **não aparecem** na lista de arquivos a enviar — se aparecerem, NÃO
   publique ainda; me avise antes.

### 3. Cria o serviço no Render

1. Acessa [render.com](https://render.com) e cria uma conta (dá pra entrar
   com a conta do GitHub).
2. **New → Web Service** → conecta o repositório que você acabou de publicar.
3. Preenche:
   - **Root Directory**: `app`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd backend && gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type**: Free

### 4. Configura as variáveis de ambiente no Render

Na aba **Environment** do serviço, adiciona:

- `GEMINI_API_KEY` = sua chave do Google AI Studio (a mesma que vai no
  `gemini_key.txt` localmente — no Render, use a variável de ambiente em vez
  do arquivo)
- `FUNCIONARIOS_SEED` = as contas reais da equipe de plantão, no formato do
  passo 1
- `SECRET_KEY` = qualquer texto longo e aleatório (ex.: gerado com
  `python3 -c "import secrets; print(secrets.token_hex(32))"`) — mantém as
  sessões de login válidas entre reinicializações do serviço

Salva — o Render faz o deploy automaticamente. Depois de alguns minutos, o
link aparece no topo da página do serviço.

### Limitações importantes do plano gratuito do Render

- O serviço "dorme" depois de 15 minutos sem uso — a primeira pessoa a abrir
  o link depois disso espera uns 30-60 segundos pra ele acordar.
- **O banco de dados (conversas, alertas e também as contas da equipe) é
  apagado toda vez que o serviço reinicia ou dorme e acorda de novo.** Para
  uma demonstração ao vivo (mostrar o chat e, na sequência, o painel) isso
  não é problema — as contas de `FUNCIONARIOS_SEED` são recriadas
  automaticamente a cada reinicialização — mas não dá pra contar com o
  histórico de atendimentos continuar disponível se a demonstração for
  interrompida por muito tempo. A migração para um banco de dados persistente
  (ex.: PostgreSQL) resolve isso e é o próximo passo do projeto (Fase 5).

## Estrutura do projeto

```
app/
├── backend/
│   ├── app.py                   # servidor Flask, rotas da API
│   ├── auth.py                  # login da equipe: hash de senha, seed, bloqueio
│   ├── manage_funcionarios.py   # CLI para gerenciar contas localmente
│   ├── triage.py                 # motor de triagem (Camadas 1 e 2)
│   ├── ai_provider.py            # geração das respostas da IA (simulado ou real)
│   ├── database.py               # esquema e conexão SQLite
│   ├── test_triage.py             # testes automatizados do motor de triagem
│   └── app.db                     # banco de dados (criado ao rodar database.py)
├── frontend/
│   ├── templates/
│   │   ├── chat.html       # tela do usuário
│   │   ├── login.html      # login da equipe de plantão
│   │   └── painel.html     # painel da equipe de plantão
│   └── static/
│       ├── style.css
│       ├── chat.js
│       └── painel.js
└── requirements.txt
```

## Como plugar uma IA conversacional real depois

Por padrão, o app usa um motor **simulado** de respostas (regras de escuta
ativa) — por isso a conversa fica repetitiva e só faz perguntas genéricas.
Pra ter uma conversa de verdade, que entende o contexto e responde aos
detalhes específicos que a pessoa conta, é preciso plugar um modelo de
linguagem real. Duas opções:

### Opção gratuita — Gemini (Google AI Studio)

1. Acesse [aistudio.google.com](https://aistudio.google.com), faça login com
   uma conta Google.
2. Na barra lateral, clique em **"Get API key"** → **"Create API key"**.
3. Copie a chave gerada (começa com `AIzaSy...`). Não precisa de cartão de
   crédito para o plano gratuito (exceto contas da UE/Reino Unido/Suíça).
4. Configure a chave usando **uma** das duas formas abaixo (a primeira é a
   mais simples e à prova de erro de terminal):

   **Opção A — direto no código (recomendado):** abra `backend/ai_provider.py`
   em um editor de texto, procure a linha bem no topo do arquivo:
   ```python
   GEMINI_API_KEY_HARDCODED = ""
   ```
   e cole a chave entre as aspas:
   ```python
   GEMINI_API_KEY_HARDCODED = "AIzaSy...sua_chave_de_verdade..."
   ```
   Salve o arquivo. Pronto — não precisa de mais nenhum passo.

   **Opção B — arquivo separado:** dentro da pasta `backend`, crie um arquivo
   chamado **`gemini_key.txt`** e cole a chave dentro dele, sozinha, sem aspas
   e sem espaços:
   ```bash
   echo "cole_sua_chave_aqui" > gemini_key.txt
   ```
   (troque `cole_sua_chave_aqui` pela chave de verdade).
5. Rode o app normalmente — `python3 app.py`. Assim que o servidor subir,
   olhe a primeira linha impressa no terminal: ela diz se a IA real foi
   detectada (`Modo ativo: IA REAL via Gemini...`) ou se caiu no motor
   simulado, e por quê. Se uma chamada real falhar durante a conversa, o
   motivo exato do erro também aparece no terminal (e a conversa cai
   automaticamente para o motor simulado, sem travar).

**Nunca compartilhe o conteúdo da chave nem cole a chave em conversas, prints
ou mensagens** — se isso acontecer, revogue a chave em
[aistudio.google.com](https://aistudio.google.com) e gere uma nova
imediatamente. Se for usar a Opção A e este projeto for compartilhado ou
publicado (inclusive em um repositório Git), lembre de apagar a chave do
código antes, ou usar a Opção B com um `.gitignore`.

### Opção paga — Anthropic (Claude)

1. Instale a biblioteca: `pip3 install anthropic`
2. Crie um arquivo `anthropic_key.txt` dentro de `backend` com sua chave
   (mesmo processo do Gemini acima) — requer conta com créditos na
   Anthropic Console.
3. Rode o app normalmente.

Se houver uma chave da Anthropic configurada, ela tem prioridade sobre a do
Gemini. Se nenhuma das duas estiver configurada, o app usa o motor
simulado. Qualquer erro na chamada à API real (chave inválida, sem conexão,
etc.) cai automaticamente para o motor simulado, sem travar a conversa.
Nenhuma outra parte do sistema precisa ser alterada — a troca é transparente
para o resto do app.

Os arquivos `gemini_key.txt` e `anthropic_key.txt` guardam informação
sensível — não os envie para ninguém nem os inclua caso este projeto seja
publicado em um repositório Git (adicione-os a um `.gitignore`).

## Principais limitações conhecidas (protótipo)

- A lista de gatilhos e pesos é ilustrativa e precisa de validação clínica
  antes de qualquer uso real (ver aviso no topo).
- O "acionamento do SAMU" no painel é apenas um registro da decisão humana —
  não há integração real com serviços de emergência nem captura de
  localização. Isso corresponde à Fase 4 da proposta, que exige parceria
  formal e aprovação de CEP antes de ser implementada.
- O login da equipe já existe, mas ainda não há um cadastro visual (tela) de
  novos funcionários — contas são criadas via `FUNCIONARIOS_SEED` (produção)
  ou `manage_funcionarios.py` (local). Uma tela de administração de contas
  fica para uma fase futura.
- O banco de dados ainda é SQLite local, que não é persistente no plano
  gratuito do Render (ver limitações acima) — a migração para um banco
  persistente é o próximo passo (Fase 5).
- O site (incluindo o chat, o login e o painel da equipe) já é responsivo em
  celular e tablet — testado em telas de 375px de largura.
- O motor de linguagem natural (sem API real) é baseado em regras simples,
  não em compreensão profunda de contexto — serve para demonstração da
  arquitetura, não para avaliação clínica de fato.
