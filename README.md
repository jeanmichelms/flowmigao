# flowmigao

[![Testes](https://github.com/jeanmichelms/flowmigao/actions/workflows/testes.yml/badge.svg)](https://github.com/jeanmichelms/flowmigao/actions/workflows/testes.yml)

Controle de Manutenções Automotivas e Histórico de Revisões

## Como rodar (MySQL)

Pré-requisitos: Python 3.12+ e MySQL 8.

1. Crie o banco e o usuário no MySQL (como root):

   ```sql
   CREATE DATABASE flowmigao CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'flowmigao'@'localhost' IDENTIFIED BY 'sua-senha';
   GRANT ALL PRIVILEGES ON flowmigao.* TO 'flowmigao'@'localhost';
   GRANT ALL PRIVILEGES ON test_flowmigao.* TO 'flowmigao'@'localhost';
   ```

2. Copie `.env.example` para `.env` e preencha `DB_PASSWORD` (e demais variáveis, se necessário).
   Para usar SQLite em vez de MySQL, defina `DB_ENGINE=sqlite` no `.env`.

3. Instale as dependências e crie as tabelas:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver
   ```

Acesse http://localhost:8000. A primeira tela é o **login** (dashboard em `/manutencoes/dashboard/`, admin em `/admin/`).

## Usuários e login

Todas as páginas exigem login, exceto a própria tela de login e o healthcheck `/saude/`.

- **Primeiro acesso:** se a tabela de usuários estiver vazia, o `migrate` cria um administrador. O usuário e a
  senha vêm de `DJANGO_ADMIN_USUARIO` (padrão `admin`) e `DJANGO_ADMIN_SENHA`; sem senha definida, uma senha
  aleatória é gerada e mostrada no console do `migrate`. Troque-a em **Alterar senha** depois de entrar.
  Bancos que já têm usuários (por exemplo, criados com `createsuperuser`) não são alterados.
- **Perfis:** o **administrador** acessa a tela **Usuários** (cadastrar, editar, desativar, trocar senha e excluir).
  O **usuário comum** usa o restante do sistema, mas não vê o menu Usuários e recebe "Acesso negado" se tentar abrir a tela.
- **Regras:** ninguém pode excluir o próprio usuário, e o administrador também não pode remover o próprio perfil
  de administrador nem se desativar. A tabela de usuários nunca fica vazia: a exclusão do último usuário é
  desfeita, mesmo pelo `/admin/` ou pelo shell.
- Qualquer usuário pode trocar a própria senha em **Alterar senha**, no topo da página.

## Auditoria

Toda inclusão, alteração e exclusão de clientes, veículos, manutenções, peças, peças usadas e usuários
fica registrada com o usuário, a data/hora e os campos que mudaram (valor anterior e novo). O registro
é feito automaticamente pelos sinais do Django (app `auditoria`), então vale para todas as telas e
também para o `/admin/`.

- **Tela Auditoria** (só administradores): lista com filtros por tipo de registro, ação, usuário, período e texto.
- **Telas de detalhe** de cliente, veículo e manutenção mostram quem cadastrou e quem fez a última alteração;
  o administrador tem um link para o histórico completo daquele registro.
- Alterações feitas fora de uma tela, como o aviso de revisão por e-mail marcando o envio, aparecem como **Sistema**.
- Senhas nunca são gravadas: aparece só "Senha: (alterada)". Logins bem-sucedidos não geram registro.
- Se um usuário for excluído, os registros dele continuam mostrando o nome.
- Cada requisição roda numa transação única (`ATOMIC_REQUESTS`): se a auditoria falhar, a alteração também é
  desfeita, então nenhuma mudança feita pelas telas fica sem registro.
- Registros cadastrados antes desta funcionalidade não têm histórico de inclusão.
- **Logins malsucedidos** (aba na tela Auditoria): cada tentativa que falha, na tela de login do sistema ou do
  `/admin/`, grava a data/hora, o usuário digitado, o motivo (senha incorreta, usuário não cadastrado ou
  desativado), o IP e o navegador. A senha digitada nunca é gravada. No Railway, o IP vem do cabeçalho
  `X-Forwarded-For` (o último endereço, que é o acrescentado pelo proxy).

## Testes

Os testes automatizados usam o framework de testes do Django e cobrem:

| App | O que é testado |
|---|---|
| `clientes` | validação do formulário (CPF/e-mail únicos, e-mail inválido), cadastro, edição, detalhe e exclusão |
| `veiculos` | cadastro (inclusive a partir do cliente), placa repetida, marca/modelo da FIPE preservados, busca de clientes do modal |
| `manutencoes` | cadastro/edição/exclusão, cálculo de datas, peças usadas e custo total, painel gerencial, busca de veículos e aviso de revisão por e-mail |
| `usuarios` | login/logout, páginas protegidas, acesso só para administradores, cadastro/edição/exclusão, não excluir a si mesmo, nunca ficar sem usuários e administrador inicial |
| `auditoria` | inclusão/alteração/exclusão registradas com usuário e campos alterados, exclusão em cascata, senha oculta, alterações do sistema, tela com filtros e paginação, resumo nas telas de detalhe, transação por requisição, logins malsucedidos (motivo, IP, senha nunca gravada, tela e filtros) |
| `flowmigao` | acessibilidade: estrutura das páginas, títulos, tabelas, erros ligados aos campos, modais e barra de fonte/contraste |

Para rodar localmente:

```bash
pip install -r requirements-dev.txt
python manage.py test
```

Com relatório de cobertura (mostra as linhas não testadas):

```bash
coverage run manage.py test
coverage report
```

### Integração contínua (GitHub Actions)

O workflow [`.github/workflows/testes.yml`](.github/workflows/testes.yml) roda **somente em pull
requests**: quando o PR é aberto, a cada novo commit enviado ao branch do PR e quando o PR é reaberto.
Commits em branches sem PR aberto não disparam os testes, mas é possível rodá-los manualmente em
**Actions → Testes → Run workflow**, escolhendo o branch. Se um commit novo chegar enquanto a execução
anterior ainda roda, a antiga é cancelada. Os testes rodam em dois bancos: **MySQL 8** e **SQLite**. Ele também
verifica a configuração do Django e se há migrações pendentes. O resumo da cobertura aparece na
página da execução, e o relatório HTML completo fica disponível para download (artefato `cobertura-html`).

## Deploy na nuvem (Railway)

O projeto já vem configurado para o [Railway](https://railway.com) pelo arquivo [`railway.json`](railway.json):

| Etapa | O que acontece |
|---|---|
| Build | o Railpack instala o Python 3.12 (`.python-version`) e as dependências, e roda `collectstatic` (que não depende da `DJANGO_SECRET_KEY`: se ela ainda não existir, o build usa uma provisória) |
| Início | `python manage.py migrate` cria/atualiza as tabelas no MySQL e, em seguida, o `gunicorn` sobe o site; o WhiteNoise entrega CSS/JS compactados |
| Healthcheck | o Railway só coloca a versão nova no ar se `/saude/` responder: app no ar, banco conectado e nenhuma migração pendente |

No Railway, `DEBUG` fica desligado automaticamente e o site passa a exigir HTTPS.

### Passo a passo

1. Em [railway.com](https://railway.com), crie um projeto com **Deploy from GitHub repo** e escolha este repositório.
2. No mesmo projeto, adicione um banco: **+ Create → Database → MySQL**.
3. No serviço do site, aba **Variables**, crie:

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | `${{MySQL.MYSQL_URL}}` (referência ao banco; use o nome do serviço do banco, se for diferente de `MySQL`) |
   | `DJANGO_SECRET_KEY` | uma chave longa e aleatória, gerada com o comando abaixo |
   | `BREVO_API_KEY` | chave de API do Brevo (veja "E-mail pelo Brevo" abaixo) |
   | `DEFAULT_FROM_EMAIL` | remetente verificado no Brevo, ex.: `FlowMigao <seu-email@gmail.com>` |
   | `DJANGO_ADMIN_SENHA` | senha do primeiro administrador (usuário `admin` ou o de `DJANGO_ADMIN_USUARIO`), usada só se o banco não tiver nenhum usuário |

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

4. Na aba **Settings → Networking**, clique em **Generate Domain** para ganhar um endereço `*.up.railway.app`.
   O domínio é liberado automaticamente no Django (`ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`).
5. No primeiro deploy, o `migrate` cria o administrador inicial (veja "Usuários e login"). Se `DJANGO_ADMIN_SENHA`
   não estiver definida, a senha gerada aparece na aba **Deploy Logs**. Para criar outros administradores pela
   linha de comando, use a [CLI do Railway](https://docs.railway.com/guides/cli):

   ```bash
   railway ssh
   python manage.py createsuperuser
   ```

Cada novo commit no branch escolhido no Railway gera um deploy automático.

### E-mail pelo Brevo

O aviso de revisão é enviado pela API HTTPS do [Brevo](https://www.brevo.com) (plano gratuito: 300 e-mails
por dia). SMTP não funciona no Railway: ele bloqueia essas conexões nos planos Free, Trial e Hobby
([documentação](https://docs.railway.com/networking/outbound-networking)).

1. Crie uma conta gratuita no Brevo.
2. Cadastre e confirme o **remetente** (o e-mail que aparecerá como "De:"). Use esse endereço em `DEFAULT_FROM_EMAIL`.
3. Gere uma **chave de API** (menu *SMTP & API → API Keys*) e coloque em `BREVO_API_KEY`.
4. Em *Settings → Security → Authorized IPs*, **desative o bloqueio de IPs desconhecidos**. O IP de saída do
   Railway muda, e após 30 dias o Brevo passaria a recusar os envios
   ([documentação](https://help.brevo.com/hc/en-us/articles/5740111683858)).
5. Teste o envio pelo próprio Railway:

   ```bash
   railway ssh
   python manage.py sendtestemail seu-email@exemplo.com
   ```

Sem domínio próprio, os e-mails podem cair na caixa de spam. Localmente, sem `BREVO_API_KEY`, o sistema usa SMTP
(variáveis `EMAIL_*` do `.env`).
