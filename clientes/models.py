from django.db import models


class Cliente(models.Model):
    nome = models.CharField(max_length=150)
    cpf = models.CharField(max_length=14, unique=True)
    email = models.EmailField(unique=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)

    # Desmembrando o endereço para facilitar o uso da API ViaCEP
    cep = models.CharField(max_length=9, blank=True, null=True) 
    endereco = models.CharField(max_length=255, blank=True, null=True) # Pode ser usado como 'Rua/Avenida'
    numero = models.CharField(max_length=10, blank=True, null=True) 
    bairro = models.CharField(max_length=100, blank=True, null=True) 
    cidade = models.CharField(max_length=100, blank=True, null=True) 
    estado = models.CharField(max_length=2, blank=True, null=True)

    
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return f'{self.nome} - {self.cpf}'