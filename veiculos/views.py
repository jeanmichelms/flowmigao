from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from .models import Veiculo
from .forms import VeiculoForm
from clientes.models import Cliente


class VeiculoListView(ListView):
    model = Veiculo
    template_name = 'veiculos/lista.html'
    context_object_name = 'veiculos'


class VeiculoCreateView(CreateView):
    model = Veiculo
    form_class = VeiculoForm
    template_name = 'veiculos/form.html'
    success_url = reverse_lazy('veiculos_lista')

    def get_success_url(self):
        cliente_id = self.request.GET.get('cliente')
        origem = self.request.GET.get('origem')

        if origem == 'cliente_detalhe' and cliente_id and cliente_id.isdigit():
            return reverse_lazy('clientes_detalhe', kwargs={'pk': int(cliente_id)})

        return str(self.success_url)

    def get_initial(self):
        initial = super().get_initial()
        cliente_id = self.request.GET.get('cliente')

        if cliente_id and cliente_id.isdigit():
            try:
                initial['cliente'] = Cliente.objects.get(pk=int(cliente_id))
            except Cliente.DoesNotExist:
                pass

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente_id = self.request.GET.get('cliente')
        origem = self.request.GET.get('origem')
        selected_cliente = None

        if self.request.method == 'GET' and cliente_id and cliente_id.isdigit():
            selected_cliente = Cliente.objects.filter(pk=int(cliente_id)).first()

        context['selected_cliente'] = selected_cliente

        if origem == 'cliente_detalhe' and cliente_id and cliente_id.isdigit():
            context['cancel_url'] = reverse_lazy('clientes_detalhe', kwargs={'pk': int(cliente_id)})
        else:
            context['cancel_url'] = reverse_lazy('veiculos_lista')

        return context


class VeiculoUpdateView(UpdateView):
    model = Veiculo
    form_class = VeiculoForm
    template_name = 'veiculos/form.html'
    success_url = reverse_lazy('veiculos_lista')


class VeiculoDeleteView(DeleteView):
    model = Veiculo
    template_name = 'veiculos/confirmar_exclusao.html'
    success_url = reverse_lazy('veiculos_lista')


class VeiculoDetailView(DetailView):
    model = Veiculo
    template_name = 'veiculos/detalhe.html'
    context_object_name = 'veiculo'


class ClienteBuscaView(View):
    def get(self, request, *args, **kwargs):
        filtro = (request.GET.get('q') or '').strip()
        clientes = Cliente.objects.all()

        if filtro:
            condicao = (
                Q(nome__icontains=filtro)
                | Q(cpf__icontains=filtro)
                | Q(email__icontains=filtro)
                | Q(telefone__icontains=filtro)
            )

            if filtro.isdigit():
                condicao |= Q(id=int(filtro))

            clientes = clientes.filter(condicao)

        clientes = clientes.order_by('nome')[:50]

        resultados = [
            {
                'id': cliente.id,
                'nome': cliente.nome,
                'cpf': cliente.cpf,
                'email': cliente.email,
                'telefone': cliente.telefone or '',
            }
            for cliente in clientes
        ]

        return JsonResponse({'results': resultados})
