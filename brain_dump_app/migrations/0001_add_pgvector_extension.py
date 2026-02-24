from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):
    """
    Migration to enable the pgvector extension in PostgreSQL.
    This is required before using VectorField.
    """

    dependencies = []

    operations = [
        VectorExtension(),
    ]
