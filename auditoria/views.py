from django.views.generic import ListView

from usuarios.views import SomenteAdministradorMixin

from .forms import FiltroAuditoriaForm
from .models import RegistroAuditoria


class AuditoriaListView(SomenteAdministradorMixin, ListView):
    model = RegistroAuditoria
    template_name = 'auditoria/lista.html'
    context_object_name = 'registros'
    paginate_by = 50

    def get_queryset(self):
        self.filtro = FiltroAuditoriaForm(self.request.GET)
        registros = super().get_queryset().select_related('tipo')
        if self.filtro.is_valid():
            registros = self.filtro.filtrar(registros)
        return registros

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['filtro'] = self.filtro
        contexto['filtrando'] = any(self.request.GET.get(nome) for nome in self.filtro.fields)
        return contexto
