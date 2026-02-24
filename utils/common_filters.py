def validate_file_extension(value):
    import os
    from django.core.exceptions import ValidationError

    allowed_extensions = [".xlsx", ".xls", ".csv", ".pdf", ".jpeg", ".jpg", ".png"]
    ext = os.path.splitext(value.name)[1].lower()

    if ext not in allowed_extensions:
        raise ValidationError(
            f'File type not supported. Allowed types: {", ".join(allowed_extensions)}'
        )
