# flowmigao
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
