import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def migrate_imported_models(apps, schema_editor):
    """
    Best-effort forward migration:
    Each REGISTERED ImportedModel row becomes a LogicalModel + ModelVersion.
    Rows without mlflow_name or mlflow_version are skipped.
    """
    ImportedModel = apps.get_model('registry', 'ImportedModel')
    LogicalModel = apps.get_model('registry', 'LogicalModel')
    ModelVersion = apps.get_model('registry', 'ModelVersion')

    for old in ImportedModel.objects.filter(status='REGISTERED'):
        if not old.mlflow_name or not old.mlflow_version:
            # Not enough info to reconstruct — skip
            continue

        # Derive a best-effort model_type from the file format
        model_type_map = {'pkl': 'sklearn', 'pt': 'pytorch', 'onnx': 'onnx'}
        model_type = model_type_map.get(old.file_format, 'Unknown')

        # Get or create the LogicalModel
        logical_model, _ = LogicalModel.objects.get_or_create(
            name=old.mlflow_name,
            defaults={
                'model_type': model_type,
                'mlflow_name': old.mlflow_name,
            },
        )

        # Avoid duplicate version records
        if ModelVersion.objects.filter(
            logical_model=logical_model,
            version_number=old.mlflow_version
        ).exists():
            continue

        ModelVersion.objects.create(
            logical_model=logical_model,
            version_number=old.mlflow_version,
            architecture='',
            accuracy=0.0,
            priority=None,
            is_deployable=False,
            remarks='Migrated from ImportedModel',
            deployment_points=[],
            original_filename=old.original_filename,
            file_format=old.file_format,
            file_size=old.file_size,
            run_id=old.run_id or '',
            status='REGISTERED',
        )


class Migration(migrations.Migration):
    """
    Migration 0003: Replace ImportedModel with LogicalModel + ModelVersion.

    Best-effort data migration strategy:
    - Each existing ImportedModel row that has a registered mlflow_name and version
      is converted into a LogicalModel + ModelVersion pair.
    - Rows with status != 'REGISTERED' or missing mlflow data are skipped.
    - The ImportedModel table is then dropped.
    """

    dependencies = [
        ('registry', '0002_alter_importedmodel_status'),
    ]

    operations = [
        # Step 1: Create LogicalModel table
        migrations.CreateModel(
            name='LogicalModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('model_type', models.CharField(max_length=100)),
                ('mlflow_name', models.CharField(max_length=255, unique=True)),
            ],
            options={'abstract': False},
        ),

        # Step 2: Create ModelVersion table
        migrations.CreateModel(
            name='ModelVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('version_number', models.IntegerField()),
                ('architecture', models.CharField(blank=True, max_length=100)),
                ('accuracy', models.FloatField(
                    default=0.0,
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(100),
                    ]
                )),
                ('priority', models.IntegerField(blank=True, null=True)),
                ('is_deployable', models.BooleanField(default=False)),
                ('remarks', models.TextField(blank=True)),
                ('deployment_points', models.JSONField(default=list)),
                ('original_filename', models.CharField(max_length=255)),
                ('file_format', models.CharField(max_length=20)),
                ('file_size', models.PositiveBigIntegerField()),
                ('run_id', models.CharField(max_length=255)),
                ('status', models.CharField(default='PENDING', max_length=50)),
                ('logical_model', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versions',
                    to='registry.logicalmodel',
                )),
            ],
            options={'abstract': False},
        ),

        # Step 3: Best-effort migrate ImportedModel rows → LogicalModel + ModelVersion
        migrations.RunPython(
            code=migrate_imported_models,
            reverse_code=migrations.RunPython.noop,
        ),

        # Step 4: Drop the old ImportedModel table
        migrations.DeleteModel(name='ImportedModel'),
    ]
