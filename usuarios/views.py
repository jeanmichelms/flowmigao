from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import AlterarSenhaForm, LoginForm, UsuarioCriarForm, UsuarioEditarForm
from .regras import eh_administrador, motivo_para_nao_excluir

User = get_user_model()


class EntrarView(LoginView):
    template_name = 'usuarios/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class AlterarSenhaView(SuccessMessageMixin, PasswordChangeView):
    template_name = 'usuarios/alterar_senha.html'
    form_class = AlterarSenhaForm
    success_url = reverse_lazy('home')
    success_message = 'Senha alterada com sucesso.'


class SomenteAdministradorMixin(UserPassesTestMixin):
    """Usuário comum logado recebe 403; quem não está logado já foi mandado para o login."""

    def test_func(self):
        return eh_administrador(self.request.user)


class UsuarioListView(SomenteAdministradorMixin, ListView):
    model = User
    template_name = 'usuarios/lista.html'
    context_object_name = 'usuarios'
    ordering = ['username']


class UsuarioCreateView(SomenteAdministradorMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = UsuarioCriarForm
    template_name = 'usuarios/form.html'
    success_url = reverse_lazy('usuarios_lista')
    success_message = 'Usuário "%(username)s" cadastrado com sucesso.'


class UsuarioUpdateView(SomenteAdministradorMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UsuarioEditarForm
    template_name = 'usuarios/form.html'
    success_url = reverse_lazy('usuarios_lista')
    success_message = 'Usuário "%(username)s" atualizado com sucesso.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['editando_a_si_mesmo'] = self.object.pk == self.request.user.pk
        return kwargs

    def form_valid(self, form):
        resposta = super().form_valid(form)
        if form.senha_alterada and self.object.pk == self.request.user.pk:
            # Sem isso, trocar a própria senha encerraria a sessão atual
            update_session_auth_hash(self.request, self.object)
        return resposta


class UsuarioDeleteView(SomenteAdministradorMixin, DeleteView):
    model = User
    template_name = 'usuarios/confirmar_exclusao.html'
    success_url = reverse_lazy('usuarios_lista')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['motivo_bloqueio'] = motivo_para_nao_excluir(self.object, self.request.user)
        return contexto

    def form_valid(self, form):
        motivo = motivo_para_nao_excluir(self.object, self.request.user)
        if motivo:
            messages.error(self.request, motivo)
            return redirect('usuarios_lista')
        messages.success(self.request, f'Usuário "{self.object.username}" excluído com sucesso.')
        return super().form_valid(form)
