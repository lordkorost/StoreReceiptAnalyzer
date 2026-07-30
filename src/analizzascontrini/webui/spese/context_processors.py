from datetime import timedelta
from pathlib import Path
from packaging.version import Version
from django.utils import timezone
from django.conf import settings

import requests

from .models import VersionCheck

# VERSION is located in the project root.
VERSION_FILE = Path(settings.BASE_DIR).parent.parent.parent / "VERSION"

def get_current_version():
    """
    Returns the installed version by reading the VERSION file.
    """
    try:
        return VERSION_FILE.read_text().strip()
    except Exception:
        return None

def check_update_available(version_check):
    """
    Compare the installed version with the one found on GitHub.
    """
    current_version = get_current_version()

    if not current_version or not version_check.latest_version:
        return False

    try:
        return Version(version_check.latest_version) > Version(current_version)
    except Exception:
        return False

def version_context(request):

    version_check, _ = VersionCheck.objects.get_or_create(id=1)
    now = timezone.now()

    # Check GitHub at most once every 24 hours
    if (
        version_check.last_check is None
        or now - version_check.last_check > timedelta(hours=24)
    ):
        try:
            response = requests.get(
                "https://raw.githubusercontent.com/lordkorost/StoreReceiptAnalyzer/main/VERSION",
                timeout=3,
            )

            if response.status_code == 200:
                latest_version = response.text.strip()

                version_check.latest_version = latest_version
                version_check.update_url = (
                    "https://github.com/lordkorost/StoreReceiptAnalyzer"
                )

            version_check.last_check = now
            version_check.save()

        except Exception:
            # Never block the site if GitHub is unreachable
            version_check.last_check = now
            version_check.save()

    return {
        "app_version": get_current_version(),
        "latest_version": version_check.latest_version,
        "update_available": check_update_available(version_check),
        "update_url": version_check.update_url,
    }