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
   python manage.py createsuperuser
   python manage.py runserver
   ```

Acesse http://localhost:8000 (dashboard em `/manutencoes/dashboard/`, admin em `/admin/`).

## Testes

Os testes automatizados usam o framework de testes do Django e cobrem:

| App | O que é testado |
|---|---|
| `clientes` | validação do formulário (CPF/e-mail únicos, e-mail inválido), cadastro, edição, detalhe e exclusão |
| `veiculos` | cadastro (inclusive a partir do cliente), placa repetida, marca/modelo da FIPE preservados, busca de clientes do modal |
| `manutencoes` | cadastro/edição/exclusão, cálculo de datas, peças usadas e custo total, painel gerencial, busca de veículos e aviso de revisão por e-mail |
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
| Antes de subir | `python manage.py migrate` cria/atualiza as tabelas no MySQL |
| Execução | `gunicorn` serve o site; o WhiteNoise entrega CSS/JS compactados |
| Healthcheck | o Railway só coloca a versão nova no ar se `/saude/` responder (o app e o banco) |

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

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

4. Na aba **Settings → Networking**, clique em **Generate Domain** para ganhar um endereço `*.up.railway.app`.
   O domínio é liberado automaticamente no Django (`ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`).
5. Para criar o usuário do `/admin/`, use a [CLI do Railway](https://docs.railway.com/guides/cli):

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
