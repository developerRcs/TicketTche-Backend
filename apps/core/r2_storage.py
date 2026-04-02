from storages.backends.s3boto3 import S3Boto3Storage


class R2MediaStorage(S3Boto3Storage):
    """Storage para arquivos de mídia enviados pelos usuários (avatars, logos, eventos, qrcodes)."""

    location = ""
    file_overwrite = False
    default_acl = None
    querystring_auth = False
