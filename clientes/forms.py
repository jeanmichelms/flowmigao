from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # ATUALIZE PARA ESTA LINHA ABAIXO:
        fields = ['nome', 'cpf', 'email', 'telefone', 'cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado']