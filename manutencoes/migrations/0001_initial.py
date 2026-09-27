from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('veiculos', '0002_alter_veiculo_chassi_optional'),
    ]

    operations = [
        migrations.CreateModel(
            name='Manutencao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descricao', models.CharField(max_length=255)),
                ('data_manutencao', models.DateField()),
                ('quilometragem', models.PositiveIntegerField(blank=True, null=True)),
                ('valor', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('observacoes', models.TextField(blank=True, null=True)),
                ('data_cadastro', models.DateTimeField(auto_now_add=True)),
                ('veiculo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manutencoes', to='veiculos.veiculo')),
            ],
            options={
                'verbose_name': 'Manutenção',
                'verbose_name_plural': 'Manutenções',
                'ordering': ['-data_manutencao', '-id'],
            },
        ),
    ]
