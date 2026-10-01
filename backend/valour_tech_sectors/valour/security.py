import re


_VITE_ASSET = re.compile(r"^/static/site/assets/.+-[A-Za-z0-9_-]{8,}\.[^/]+$")
_DJANGO_ASSET = re.compile(r"\.[a-f0-9]{12}\.")


def immutable_static_file(path, url):
    """Cache only content-hashed Vite/Django assets for a year, never HTML."""
    return bool(_VITE_ASSET.match(url) or _DJANGO_ASSET.search(url))


def no_client_ip(request):
    """Username-based admin lockouts do not need to retain or trust IP data."""
    return None
