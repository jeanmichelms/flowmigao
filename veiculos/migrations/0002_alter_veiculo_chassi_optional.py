from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('veiculos', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='veiculo',
            name='chassi',
            field=models.CharField(max_length=30, unique=True, blank=True, null=True),
        ),
    ]
