from django.db import models
from django.forms.models import model_to_dict
import uuid


class BaseTimestampModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    # for debugging in shell!
    @property
    def to_dict(self):
        return model_to_dict(self)

    class Meta:
        abstract = True
