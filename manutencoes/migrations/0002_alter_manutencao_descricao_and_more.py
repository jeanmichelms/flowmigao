from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manutencoes', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='manutencao',
            name='descricao',
            field=models.TextField(),
        ),
        migrations.AddField(
            model_name='manutencao',
            name='data_proxima_manutencao',
            field=models.DateField(blank=True, null=True),
        ),
    ]
