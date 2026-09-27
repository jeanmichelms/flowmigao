from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manutencoes', '0002_alter_manutencao_descricao_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='manutencao',
            name='quilometragem',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name='manutencao',
            name='valor',
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
    ]
