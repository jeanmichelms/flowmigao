from django import forms
from .models import Veiculo


class VeiculoForm(forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = ['cliente', 'marca', 'modelo', 'ano', 'placa', 'cor', 'chassi']
        widgets = {
            'cliente': forms.HiddenInput(),
            # Colocando selects da API da FIPE:
            'marca': forms.Select(attrs={'class': 'form-control'}),
            'modelo': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].required = True

        # Os selects são preenchidos pela API da FIPE no navegador. O valor atual (edição ou
        # formulário devolvido com erro) vai como opção selecionada para não se perder.
        for campo in ('marca', 'modelo'):
            valor = self[campo].value()
            self.fields[campo].widget.choices = [(valor, valor)] if valor else [('', '---------')]