from django.contrib.auth import get_user_model


def entrar(client, username='operador', administrador=False):
    """Cria um usuário e faz login com ele no client de testes (todas as páginas exigem login)."""
    # Sem senha: o force_login não precisa dela e o teste fica mais rápido (sem calcular o hash)
    usuario = get_user_model().objects.create_user(username, is_superuser=administrador, is_staff=administrador)
    client.force_login(usuario)
    return usuario
