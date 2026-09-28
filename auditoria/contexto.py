"""Guarda a requisição em andamento para os sinais saberem quem fez a alteração.

Os sinais do Django (post_save, post_delete...) não recebem a requisição. O middleware coloca a
requisição numa ContextVar, que é separada por thread/requisição, e os sinais leem dali.
Fora de uma requisição (serviço de aviso de revisão, shell, migrate) não há usuário: fica "Sistema".
"""
from contextvars import ContextVar

_requisicao_atual = ContextVar('auditoria_requisicao_atual', default=None)


def usuario_atual():
    usuario = getattr(_requisicao_atual.get(), 'user', None)
    if usuario is not None and usuario.is_authenticated:
        return usuario
    return None


class UsuarioAtualMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Guarda a requisição (e não o usuário) para enxergar o usuário atualizado depois do login
        token = _requisicao_atual.set(request)
        try:
            return self.get_response(request)
        finally:
            _requisicao_atual.reset(token)
