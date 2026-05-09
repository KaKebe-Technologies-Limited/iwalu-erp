from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('outlets', '0001_initial'),
        ('cafe', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='menuorder',
            name='outlet',
            field=models.ForeignKey(
                default=1,
                help_text='Outlet where this order was placed',
                on_delete=django.db.models.deletion.PROTECT,
                to='outlets.outlet',
            ),
            preserve_default=False,
        ),
    ]
