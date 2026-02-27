import os
import ssl

import certifi
from django.core.mail.backends.smtp import EmailBackend


class CertifiSMTPEmailBackend(EmailBackend):
    """
    SMTP backend that uses certifi's CA bundle to avoid Windows/Python certificate
    store issues on some environments (notably Windows + newer Python builds).

    If you are behind an antivirus/proxy doing TLS inspection, the certificate
    presented to Python may be replaced by a local CA that is not RFC-compliant,
    causing CERTIFICATE_VERIFY_FAILED. In that case you can *temporarily* disable
    verification by setting:

        EMAIL_SKIP_SSL_VERIFY=1

    This is NOT recommended for production.
    """

    def __init__(self, *args, **kwargs):
        skip_verify = os.getenv("EMAIL_SKIP_SSL_VERIFY", "").strip() in {"1", "true", "True", "yes", "YES"}
        if skip_verify:
            ctx = ssl._create_unverified_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        else:
            ctx = ssl.create_default_context(cafile=certifi.where())

        kwargs["ssl_context"] = ctx
        super().__init__(*args, **kwargs)
