from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from flowmigao.paginacao import ListaComBuscaMixin
from .models import Cliente
from .forms import ClienteForm


class ClienteListView(ListaComBuscaMixin, ListView):
    model = Cliente
    template_name = 'clientes/lista.html'
    context_object_name = 'clientes'
    campos_busca = ['nome', 'cpf', 'email', 'telefone', 'cidade']
    campos_busca_numericos = ['id']
    rotulo_itens = 'clientes'
    ajuda_busca = 'Nome, CPF, e-mail, telefone ou cidade.'


class ClienteCreateView(CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/form.html'
    success_url = reverse_lazy('clientes_lista')


class ClienteUpdateView(UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/form.html'
    success_url = reverse_lazy('clientes_lista')


class ClienteDeleteView(DeleteView):
    model = Cliente
    template_name = 'clientes/confirmar_exclusao.html'
    success_url = reverse_lazy('clientes_lista')


class ClienteDetailView(DetailView):
    model = Cliente
    template_name = 'clientes/detalhe.html'
    context_object_name = 'cliente'