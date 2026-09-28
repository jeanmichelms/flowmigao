from django.views.generic import ListView

from usuarios.views import SomenteAdministradorMixin

from .forms import FiltroAuditoriaForm, FiltroLoginForm
from .models import RegistroAuditoria, TentativaLogin


class ListaFiltradaMixin(SomenteAdministradorMixin):
    """Lista só para administradores, com filtros enviados por GET e 50 itens por página."""

    filtro_class = None
    paginate_by = 50

    def get_queryset(self):
        self.filtro = self.filtro_class(self.request.GET)
        itens = super().get_queryset()
        if self.filtro.is_valid():
            itens = self.filtro.filtrar(itens)
        return itens

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['filtro'] = self.filtro
        contexto['filtrando'] = any(self.request.GET.get(nome) for nome in self.filtro.fields)
        return contexto


class AuditoriaListView(ListaFiltradaMixin, ListView):
    queryset = RegistroAuditoria.objects.select_related('tipo')
    filtro_class = FiltroAuditoriaForm
    template_name = 'auditoria/lista.html'
    context_object_name = 'registros'


class TentativaLoginListView(ListaFiltradaMixin, ListView):
    model = TentativaLogin
    filtro_class = FiltroLoginForm
    template_name = 'auditoria/logins.html'
    context_object_name = 'tentativas'
