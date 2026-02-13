from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("operational", "0012_aiconversation_aidocumentchunk_aimessage_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="aiconversation",
            index=models.Index(fields=["company", "created_at"], name="idx_aiconv_ct"),
        ),
        migrations.AddIndex(
            model_name="aimessage",
            index=models.Index(fields=["company", "created_at"], name="idx_aimsg_ct"),
        ),
        migrations.AddIndex(
            model_name="aisuggestion",
            index=models.Index(fields=["company", "created_at"], name="idx_aisug_ct"),
        ),
    ]
