"""Cria o primeiro administrador quando a tabela de usuários está vazia.

Sem nenhum usuário ninguém conseguiria passar da tela de login. Usuário e senha vêm de
DJANGO_ADMIN_USUARIO / DJANGO_ADMIN_SENHA / DJANGO_ADMIN_EMAIL; sem senha definida, uma senha
aleatória é gerada e mostrada no console (no Railway, na aba "Logs" do deploy).
"""
import os
import secrets

from django.contrib.auth.hashers import make_password
from django.db import migrations


def criar_administrador_inicial(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    if User.objects.exists():
        return

    usuario = os.getenv('DJANGO_ADMIN_USUARIO') or 'admin'
    senha = os.getenv('DJANGO_ADMIN_SENHA')
    if not senha:
        senha = secrets.token_urlsafe(12)
        print(
            f'\n  Administrador inicial criado: usuário "{usuario}", senha "{senha}". '
            'Troque a senha no primeiro acesso.'
        )

    User.objects.create(
        username=usuario,
        email=os.getenv('DJANGO_ADMIN_EMAIL', ''),
        password=make_password(senha),
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(criar_administrador_inicial, migrations.RunPython.noop),
    ]
