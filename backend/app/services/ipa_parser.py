"""IPA (iOS Application Archive) Static Metadata Extraction Service (T1.3).

Safely inspects and extracts bundle identifier, version, application name,
and minimum iOS version constraints from Info.plist inside an IPA archive.
"""

from __future__ import annotations

import io
import logging
import plistlib
from typing import Any
import zipfile

logger = logging.getLogger(__name__)


def extract_ipa_metadata(archive_source: str | bytes) -> dict[str, Any]:
    """Safely extract iOS application metadata from an IPA archive path or bytes.

    Extracts:
    - bundle_id: CFBundleIdentifier
    - version_name: CFBundleShortVersionString
    - build_version: CFBundleVersion
    - app_name: CFBundleDisplayName or CFBundleName
    - min_os_version: MinimumOSVersion
    - supported_devices: human-readable device family (iPhone, iPad)
    """
    try:
        if isinstance(archive_source, bytes):
            zip_target: Any = io.BytesIO(archive_source)
        else:
            zip_target = archive_source

        with zipfile.ZipFile(zip_target) as archive:
            plist_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith("Payload/") and name.count("/") == 2 and name.endswith(".app/Info.plist")
            )
            if not plist_names:
                return {}
            with archive.open(plist_names[0]) as plist_file:
                metadata = plistlib.load(plist_file)
    except (
        OSError,
        KeyError,
        zipfile.BadZipFile,
        plistlib.InvalidFileException,
        ValueError,
        TypeError,
    ) as exc:
        logger.debug("Failed to extract IPA metadata: %s", exc)
        return {}

    if not isinstance(metadata, dict):
        return {}

    bundle_id = str(metadata.get("CFBundleIdentifier") or "").strip()
    version_name = str(metadata.get("CFBundleShortVersionString") or "").strip()
    build_version = str(metadata.get("CFBundleVersion") or "").strip()
    app_name = str(metadata.get("CFBundleDisplayName") or metadata.get("CFBundleName") or "").strip()
    min_os = str(metadata.get("MinimumOSVersion") or "").strip()

    # UIDeviceFamily: 1 = iPhone, 2 = iPad
    device_family_raw = metadata.get("UIDeviceFamily") or []
    if isinstance(device_family_raw, int):
        device_family_raw = [device_family_raw]
    supported_devices: list[str] = []
    if 1 in device_family_raw:
        supported_devices.append("iPhone")
    if 2 in device_family_raw:
        supported_devices.append("iPad")

    result: dict[str, Any] = {}
    if bundle_id:
        result["bundle_id"] = bundle_id[:256]
    if version_name:
        result["version_name"] = version_name[:64]
    elif build_version:
        result["version_name"] = build_version[:64]
    if build_version:
        result["build_version"] = build_version[:64]
    if app_name:
        result["app_name"] = app_name[:128]
    if min_os:
        result["min_os_version"] = min_os[:32]
    if supported_devices:
        result["supported_devices"] = supported_devices

    return result
