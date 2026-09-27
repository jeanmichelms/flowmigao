from datetime import date, datetime, time

from django.db.models import ProtectedError, Q, Count, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from clientes.models import Cliente
from veiculos.models import Veiculo
from .forms import ManutencaoForm, add_months, PecaForm, PecaUsadaForm
from .models import Manutencao, Peca, PecaUsada


class ManutencaoListView(ListView):
    model = Manutencao
    template_name = 'manutencoes/lista.html'
    context_object_name = 'manutencoes'


class ManutencaoCreateView(CreateView):
    model = Manutencao
    form_class = ManutencaoForm
    template_name = 'manutencoes/form.html'
    success_url = reverse_lazy('manutencoes_lista')

    def get_success_url(self):
        veiculo_id = self.request.GET.get('veiculo')
        origem = self.request.GET.get('origem')

        if origem == 'veiculo_detalhe' and veiculo_id and veiculo_id.isdigit():
            return reverse('veiculos_detalhe', kwargs={'pk': int(veiculo_id)})

        return str(self.success_url)

    def get_initial(self):
        initial = super().get_initial()
        hoje = date.today()
        initial.setdefault('data_manutencao', hoje)
        initial.setdefault('data_proxima_manutencao', add_months(hoje, 6))

        veiculo_id = self.request.GET.get('veiculo')
        if veiculo_id and veiculo_id.isdigit():
            try:
                initial['veiculo'] = Veiculo.objects.select_related('cliente').get(pk=int(veiculo_id))
            except Veiculo.DoesNotExist:
                pass

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        veiculo_id = self.request.GET.get('veiculo')
        selected_veiculo = None

        if self.request.method == 'GET' and veiculo_id and veiculo_id.isdigit():
            selected_veiculo = Veiculo.objects.select_related('cliente').filter(pk=int(veiculo_id)).first()

        context['selected_veiculo'] = selected_veiculo
        context['cancel_url'] = (
            reverse('veiculos_detalhe', kwargs={'pk': int(veiculo_id)})
            if self.request.GET.get('origem') == 'veiculo_detalhe' and veiculo_id and veiculo_id.isdigit()
            else reverse('manutencoes_lista')
        )
        return context


class ManutencaoUpdateView(UpdateView):
    model = Manutencao
    form_class = ManutencaoForm
    template_name = 'manutencoes/form.html'
    success_url = reverse_lazy('manutencoes_lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse('manutencoes_lista')
        return context


class ManutencaoDeleteView(DeleteView):
    model = Manutencao
    template_name = 'manutencoes/confirmar_exclusao.html'
    success_url = reverse_lazy('manutencoes_lista')


class ManutencaoDetailView(DetailView):
    model = Manutencao
    template_name = 'manutencoes/detalhe.html'
    context_object_name = 'manutencao'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Envia o formulário vazio para a tela
        context['form_peca'] = PecaUsadaForm()
        # Envia a lista de peças que já foram cadastradas nesta manutenção
        context['pecas_usadas'] = self.object.pecas_usadas.select_related('peca')
        context['total_pecas'] = context['pecas_usadas'].aggregate(total=Sum('valor_total_custo'))['total'] or 0
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() # Pega a manutenção que estamos visualizando
        form_peca = PecaUsadaForm(request.POST)
        
        if form_peca.is_valid():
            nova_peca = form_peca.save(commit=False)
            nova_peca.manutencao = self.object # Amarra a peça à manutenção correta
            nova_peca.save()
            # Recarrega a página atual para mostrar a peça nova na lista
            return redirect('manutencoes_detalhe', pk=self.object.pk) 
            
        # Se der erro de validação, recarrega a página mostrando o erro
        context = self.get_context_data(object=self.object)
        context['form_peca'] = form_peca
        return self.render_to_response(context)


class PecaUsadaRemoverView(View):
    http_method_names = ['post']

    def post(self, request, pk):
        peca_usada = get_object_or_404(PecaUsada, pk=pk)
        manutencao_id = peca_usada.manutencao_id
        peca_usada.delete()
        return redirect('manutencoes_detalhe', pk=manutencao_id)


class PecaListView(ListView):
    model = Peca
    template_name = 'pecas/lista.html'
    context_object_name = 'pecas'


class PecaCreateView(CreateView):
    model = Peca
    form_class = PecaForm
    template_name = 'pecas/form.html'
    success_url = reverse_lazy('pecas_lista')

    def _manutencao_origem(self):
        manutencao_id = self.request.GET.get('manutencao')
        if manutencao_id and manutencao_id.isdigit():
            return int(manutencao_id)
        return None

    def get_success_url(self):
        # Cadastro aberto a partir de uma manutenção: volta para ela já com a peça pronta para uso
        manutencao_id = self._manutencao_origem()
        if manutencao_id:
            return reverse('manutencoes_detalhe', kwargs={'pk': manutencao_id})
        return str(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        manutencao_id = self._manutencao_origem()
        context['cancel_url'] = (
            reverse('manutencoes_detalhe', kwargs={'pk': manutencao_id})
            if manutencao_id
            else reverse('pecas_lista')
        )
        return context


class PecaUpdateView(UpdateView):
    model = Peca
    form_class = PecaForm
    template_name = 'pecas/form.html'
    success_url = reverse_lazy('pecas_lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse('pecas_lista')
        return context


class PecaDeleteView(DeleteView):
    model = Peca
    template_name = 'pecas/confirmar_exclusao.html'
    success_url = reverse_lazy('pecas_lista')

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            # PecaUsada usa on_delete=PROTECT: peça já usada em manutenção não pode ser excluída
            context = self.get_context_data(erro_protegida=True)
            return self.render_to_response(context)


class VeiculoBuscaView(View):
    def get(self, request, *args, **kwargs):
        filtro = (request.GET.get('q') or '').strip()
        veiculos = Veiculo.objects.select_related('cliente').all()

        if filtro:
            condicao = (
                Q(cliente__nome__icontains=filtro)
                | Q(cliente__cpf__icontains=filtro)
                | Q(marca__icontains=filtro)
                | Q(modelo__icontains=filtro)
                | Q(placa__icontains=filtro)
            )

            if filtro.isdigit():
                condicao |= Q(ano=int(filtro))

            veiculos = veiculos.filter(condicao)

        veiculos = veiculos.order_by('cliente__nome', 'marca', 'modelo', 'placa')[:50]

        resultados = [
            {
                'id': veiculo.id,
                'cliente_nome': veiculo.cliente.nome,
                'cliente_cpf': veiculo.cliente.cpf,
                'marca': veiculo.marca,
                'modelo': veiculo.modelo,
                'ano': veiculo.ano,
                'placa': veiculo.placa,
            }
            for veiculo in veiculos
        ]

        return JsonResponse({'results': resultados})



def dashboard_gerencial(request):
    hoje = timezone.localdate()

    # 1. Número de clientes novos no mês atual
    # Filtra por intervalo (e não por __year/__month) porque no MySQL essas lookups
    # em DateTimeField usam CONVERT_TZ, que retorna NULL sem as tabelas de fuso carregadas.
    inicio_mes = timezone.make_aware(datetime(hoje.year, hoje.month, 1))
    inicio_proximo_mes = timezone.make_aware(datetime.combine(add_months(inicio_mes.date(), 1), time.min))
    clientes_mes = Cliente.objects.filter(
        data_cadastro__gte=inicio_mes,
        data_cadastro__lt=inicio_proximo_mes,
    ).count()

    # 2. Histórico de serviços por mês (Separa preventivas e corretivas)
    historico_servicos = Manutencao.objects.annotate(
        mes=TruncMonth('data_manutencao')
    ).values('mes').annotate(
        total_servicos=Count('id'),
        preventivas=Count('id', filter=Q(tipo='PREVENTIVA')),
        corretivas=Count('id', filter=Q(tipo='CORRETIVA'))
    ).order_by('-mes')

    # 3. Gasto com peças no mês atual
    gasto_pecas_mes = PecaUsada.objects.filter(
        manutencao__data_manutencao__year=hoje.year,
        manutencao__data_manutencao__month=hoje.month
    ).aggregate(total=Sum('valor_total_custo'))['total'] or 0.00

    context = {
        'clientes_mes': clientes_mes,
        'historico_servicos': historico_servicos,
        'gasto_pecas_mes': gasto_pecas_mes,
    }
    return render(request, 'manutencoes/dashboard.html', context)
