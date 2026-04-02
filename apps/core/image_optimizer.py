"""
Image optimization pipeline — comprime e redimensiona imagens antes de salvar no R2.

Estratégia por tipo:
  avatar      → 400×400 px  (crop centralizado)  WebP q=82  ~15–30 KB
  logo        → 800×800 px  (fit, sem crop)       WebP q=85  ~30–60 KB
  event cover → 1280×720 px (16:9 crop)           WebP q=85  ~80–150 KB
  qr_code     → 420×420 px  (sem crop)            PNG        ~10–18 KB

Com esses limites, 10 GB aguentam ~40 000 eventos completos com folga.
"""

import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

# (max_width, max_height, crop, format, quality)
PROFILES = {
    "avatar":       (400,  400,  True,  "WEBP", 82),
    "logo":         (800,  800,  False, "WEBP", 85),
    "event_cover":  (1280, 720,  True,  "WEBP", 85),
    "qr_code":      (420,  420,  False, "PNG",  None),
}


def optimize_image(field_file, profile: str) -> None:
    """
    Processa a imagem do ImageField in-memory e substitui pelo resultado otimizado.
    Deve ser chamado no save() do model, antes de enviar ao storage.

    Uso:
        optimize_image(self.avatar, "avatar")
    """
    if not field_file:
        return

    max_w, max_h, do_crop, fmt, quality = PROFILES[profile]

    try:
        field_file.open("rb")
        img = Image.open(field_file).convert("RGB" if fmt != "PNG" else "RGBA")

        # Remove metadados EXIF (privacidade + tamanho)
        img = ImageOps.exif_transpose(img)

        if do_crop:
            img = _crop_to_ratio(img, max_w, max_h)
        else:
            img.thumbnail((max_w, max_h), Image.LANCZOS)

        buffer = io.BytesIO()
        save_kwargs = {"format": fmt}
        if quality is not None:
            save_kwargs["quality"] = quality
        if fmt == "WEBP":
            save_kwargs["method"] = 6  # melhor compressão (mais lento, OK para upload)

        img.save(buffer, **save_kwargs)
        buffer.seek(0)

        ext = "webp" if fmt == "WEBP" else "png"
        # Use only the filename portion (no directory prefix) so that Django's
        # upload_to doesn't double-prepend the folder on field_file.save().
        full_name = field_file.name.rsplit(".", 1)[0]
        file_basename = full_name.split("/")[-1]
        new_name = f"{file_basename}.{ext}"

        field_file.save(new_name, ContentFile(buffer.read()), save=False)

    except Exception:
        # Nunca quebrar o save por falha de otimização — usa imagem original
        pass
    finally:
        try:
            field_file.close()
        except Exception:
            pass


def _crop_to_ratio(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Redimensiona mantendo proporção e depois faz crop centralizado."""
    target_ratio = target_w / target_h
    src_ratio = img.width / img.height

    if src_ratio > target_ratio:
        # imagem mais larga — ajusta pela altura
        new_h = min(img.height, target_h)
        new_w = round(new_h * src_ratio)
    else:
        # imagem mais alta — ajusta pela largura
        new_w = min(img.width, target_w)
        new_h = round(new_w / src_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    return ImageOps.fit(img, (min(new_w, target_w), min(new_h, target_h)), Image.LANCZOS)
