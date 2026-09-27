# flowmigao

[![Testes](https://github.com/jeanmichelms/flowmigao/actions/workflows/testes.yml/badge.svg?branch=dev)](https://github.com/jeanmichelms/flowmigao/actions/workflows/testes.yml)

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

O workflow [`.github/workflows/testes.yml`](.github/workflows/testes.yml) roda a cada `push` e
`pull request` nos branches `main` e `dev`, em dois bancos: **MySQL 8** e **SQLite**. Ele também
verifica a configuração do Django e se há migrações pendentes. O resumo da cobertura aparece na
página da execução, e o relatório HTML completo fica disponível para download (artefato `cobertura-html`).
