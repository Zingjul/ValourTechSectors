from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check Supabase upload, signed download, and bucket privacy using a temporary PDF, then delete it."

    def handle(self, *args, **options):
        if not settings.SUPABASE_URL or not settings.SUPABASE_STORAGE_BUCKET:
            raise CommandError("Configure Supabase Storage first; this check does not support local media storage.")
        name = f"deployment-checks/{uuid4().hex}.pdf"
        content = b"%PDF-1.4\n% ValourTech storage permission probe\n%%EOF\n"
        saved_name = None
        cleanup_failed = False
        try:
            saved_name = default_storage.save(name, ContentFile(content))
            signed_url = default_storage.url(saved_name)
            parsed = urlparse(signed_url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != urlparse(settings.SUPABASE_URL).netloc
                or not parse_qs(parsed.query).get("X-Amz-Signature")
            ):
                raise CommandError("Storage did not return an HTTPS signed URL for the configured project.")
            with urlopen(signed_url, timeout=15) as response:
                if response.read(len(content) + 1) != content:
                    raise CommandError("The signed download did not return the uploaded content.")
            public_url = (
                f"{settings.SUPABASE_URL}/storage/v1/object/public/"
                f"{quote(settings.SUPABASE_STORAGE_BUCKET, safe='')}/{quote(saved_name, safe='/')}"
            )
            try:
                with urlopen(public_url, timeout=15):
                    pass
            except HTTPError as error:
                if error.code not in {400, 401, 403, 404}:
                    raise CommandError("Could not verify bucket privacy; the public endpoint returned an unexpected status.") from None
            else:
                raise CommandError("The bucket is publicly readable. Make it PRIVATE before publishing any course files.")
        except (BotoCoreError, ClientError, URLError, OSError):
            # These exceptions can embed signed URLs or credentials. Do not print them.
            raise CommandError("Storage verification failed. Check the bucket, S3 credentials, region, and network access in Render.") from None
        finally:
            if saved_name:
                try:
                    default_storage.delete(saved_name)
                except (BotoCoreError, ClientError, OSError):
                    cleanup_failed = True
                    self.stderr.write(f"Could not delete the temporary probe. Remove {saved_name} from the bucket manually.")
        if cleanup_failed:
            raise CommandError("Storage read/write checks passed, but deletion failed. Fix S3 delete permissions and remove the temporary probe.")
        self.stdout.write(self.style.SUCCESS("Storage verified: upload and signed download work; the object is not publicly readable."))
