from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manutencoes', '0003_alter_manutencao_quilometragem_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='manutencao',
            name='email_aviso_revisao_enviado',
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
