import imghdr
import re

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


def validate_cpf(value: str) -> None:
    """Validate Brazilian CPF. Accepts '000.000.000-00' or '00000000000'."""
    cpf = re.sub(r'[^0-9]', '', value)

    if len(cpf) != 11:
        raise ValidationError("CPF deve ter 11 dígitos.")

    # Reject all-same sequences
    if cpf == cpf[0] * 11:
        raise ValidationError("CPF inválido.")

    # First check digit
    total = sum(int(cpf[i]) * (10 - i) for i in range(9))
    remainder = (total * 10) % 11
    if remainder == 10:
        remainder = 0
    if remainder != int(cpf[9]):
        raise ValidationError("CPF inválido.")

    # Second check digit
    total = sum(int(cpf[i]) * (11 - i) for i in range(10))
    remainder = (total * 10) % 11
    if remainder == 10:
        remainder = 0
    if remainder != int(cpf[10]):
        raise ValidationError("CPF inválido.")


def validate_cnpj(value: str) -> None:
    """Validate Brazilian CNPJ. Accepts '00.000.000/0000-00' or '00000000000000'."""
    cnpj = re.sub(r'[^0-9]', '', value)

    if len(cnpj) != 14:
        raise ValidationError("CNPJ deve ter 14 dígitos.")

    # Reject all-same sequences
    if cnpj == cnpj[0] * 14:
        raise ValidationError("CNPJ inválido.")

    # First check digit
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(cnpj[i]) * weights1[i] for i in range(12))
    remainder = total % 11
    first_digit = 0 if remainder < 2 else 11 - remainder
    if first_digit != int(cnpj[12]):
        raise ValidationError("CNPJ inválido.")

    # Second check digit
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(cnpj[i]) * weights2[i] for i in range(13))
    remainder = total % 11
    second_digit = 0 if remainder < 2 else 11 - remainder
    if second_digit != int(cnpj[13]):
        raise ValidationError("CNPJ inválido.")


ALLOWED_IMAGE_TYPES = {"jpeg", "png", "webp"}
# Limite do arquivo original enviado pelo usuário (antes de otimização)
# Após otimização o arquivo real no R2 será muito menor
MAX_IMAGE_SIZE_MB = 10


@deconstructible
class ImageFileValidator:
    """Validates that an uploaded file is an allowed image type and within size limits."""

    def __init__(self, max_mb: int = MAX_IMAGE_SIZE_MB, allowed_types: set = ALLOWED_IMAGE_TYPES):
        self.max_mb = max_mb
        self.allowed_types = allowed_types

    def __call__(self, file):
        # Size check
        max_bytes = self.max_mb * 1024 * 1024
        if file.size > max_bytes:
            raise ValidationError(
                f"Image size must be at most {self.max_mb} MB. Uploaded file is {file.size // (1024 * 1024)} MB."
            )

        # MIME type check via magic bytes (not just extension)
        file.seek(0)
        header = file.read(512)
        file.seek(0)
        detected = imghdr.what(None, h=header)
        if detected not in self.allowed_types:
            raise ValidationError(
                f"Unsupported image type '{detected}'. Allowed types: {', '.join(self.allowed_types)}."
            )
