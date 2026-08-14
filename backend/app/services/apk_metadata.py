"""Read package metadata from an APK without requiring Android build tools."""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree


_MAX_MANIFEST_SIZE = 4 * 1024 * 1024
_NO_STRING = 0xFFFFFFFF
_TYPE_STRING = 0x03
_TYPE_INT_DEC = 0x10
_TYPE_INT_HEX = 0x11


def extract_apk_metadata(path: str | Path) -> dict[str, str | int]:
    """Return package/version metadata, or an empty mapping for unreadable APKs.

    Android packages normally contain a binary ``AndroidManifest.xml``.  A
    small parser is kept here so uploads work on Windows hosts without an
    ``aapt``/Android SDK installation.  Metadata is best-effort: a malformed
    or protected APK must not prevent the file itself from being uploaded.
    """

    try:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo("AndroidManifest.xml")
            if info.file_size > _MAX_MANIFEST_SIZE:
                return {}
            manifest = archive.read(info)
    except (OSError, KeyError, RuntimeError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return {}

    try:
        if manifest.lstrip().startswith(b"<"):
            return _parse_text_manifest(manifest)
        return _parse_binary_manifest(manifest)
    except (IndexError, LookupError, struct.error, UnicodeDecodeError, ValueError, ElementTree.ParseError):
        return {}


def _parse_text_manifest(manifest: bytes) -> dict[str, str | int]:
    root = ElementTree.fromstring(manifest)
    values: dict[str, str | int] = {}
    if root.attrib.get("package"):
        values["package_name"] = root.attrib["package"]
    for key, value in root.attrib.items():
        if key.endswith("versionName") and value:
            values["version_name"] = value
        elif key.endswith("versionCode") and value:
            parsed = _parse_int(value)
            if parsed is not None:
                values["version_code"] = parsed
    return values


def _parse_binary_manifest(manifest: bytes) -> dict[str, str | int]:
    strings: list[str] = []
    values: dict[str, str | int] = {}
    offset = 0

    while offset + 8 <= len(manifest):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", manifest, offset)
        if chunk_size < header_size or offset + chunk_size > len(manifest):
            break
        if chunk_type == 0x001C:
            strings = _parse_string_pool(manifest, offset, header_size, chunk_size)
        elif chunk_type == 0x0102 and strings:
            values.update(_parse_start_element(manifest, offset, header_size, chunk_size, strings))
            if values.get("package_name"):
                break
        offset += chunk_size

    return values


def _parse_string_pool(data: bytes, offset: int, header_size: int, chunk_size: int) -> list[str]:
    if header_size < 28 or chunk_size < header_size:
        return []
    string_count, style_count, flags, strings_start, _styles_start = struct.unpack_from(
        "<IIIII", data, offset + 8
    )
    offsets_start = offset + header_size
    strings_base = offset + strings_start
    is_utf8 = bool(flags & 0x100)
    strings: list[str] = []

    for index in range(string_count):
        string_offset = struct.unpack_from("<I", data, offsets_start + index * 4)[0]
        cursor = strings_base + string_offset
        if cursor >= offset + chunk_size:
            strings.append("")
            continue
        if is_utf8:
            _utf16_length, cursor = _read_utf8_length(data, cursor)
            byte_length, cursor = _read_utf8_length(data, cursor)
            raw = data[cursor : cursor + byte_length]
            strings.append(raw.decode("utf-8", errors="replace"))
        else:
            char_length, cursor = _read_utf16_length(data, cursor)
            raw = data[cursor : cursor + char_length * 2]
            strings.append(raw.decode("utf-16le", errors="replace"))
    return strings


def _read_utf8_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    if first & 0x80:
        return ((first & 0x7F) << 8) | data[offset + 1], offset + 2
    return first, offset + 1


def _read_utf16_length(data: bytes, offset: int) -> tuple[int, int]:
    first = struct.unpack_from("<H", data, offset)[0]
    if first & 0x8000:
        second = struct.unpack_from("<H", data, offset + 2)[0]
        return ((first & 0x7FFF) << 16) | second, offset + 4
    return first, offset + 2


def _parse_start_element(
    data: bytes,
    offset: int,
    header_size: int,
    chunk_size: int,
    strings: list[str],
) -> dict[str, str | int]:
    if header_size < 16 or offset + header_size + 20 > offset + chunk_size:
        return {}
    extension = offset + header_size
    _namespace, name_index = struct.unpack_from("<II", data, extension)
    if _string(strings, name_index) != "manifest":
        return {}
    attribute_start, attribute_size, attribute_count = struct.unpack_from("<HHH", data, extension + 8)
    if attribute_size < 20:
        return {}
    attributes_start = extension + attribute_start
    values: dict[str, str | int] = {}

    for index in range(attribute_count):
        attribute = attributes_start + index * attribute_size
        if attribute + 20 > offset + chunk_size:
            break
        _namespace, name_index, raw_value = struct.unpack_from("<III", data, attribute)
        value_size, _reserved, data_type, typed_value = struct.unpack_from("<HBBI", data, attribute + 12)
        if value_size < 8:
            continue
        name = _string(strings, name_index)
        value = _attribute_value(strings, raw_value, data_type, typed_value)
        if name == "package" and isinstance(value, str) and value:
            values["package_name"] = value
        elif name == "versionName" and isinstance(value, str) and value:
            values["version_name"] = value
        elif name == "versionCode":
            parsed = value if isinstance(value, int) else _parse_int(value)
            if parsed is not None:
                values["version_code"] = parsed
    return values


def _attribute_value(strings: list[str], raw_value: int, data_type: int, typed_value: int) -> str | int | None:
    if raw_value != _NO_STRING:
        raw = _string(strings, raw_value)
        if raw:
            return raw
    if data_type == _TYPE_STRING:
        return _string(strings, typed_value)
    if data_type in {_TYPE_INT_DEC, _TYPE_INT_HEX}:
        return typed_value
    return None


def _string(strings: list[str], index: int) -> str:
    if index == _NO_STRING or index < 0 or index >= len(strings):
        return ""
    return strings[index]


def _parse_int(value: str | int | None) -> int | None:
    if isinstance(value, int):
        return value
    if not value:
        return None
    try:
        return int(value, 0)
    except ValueError:
        try:
            return int(value)
        except ValueError:
            return None
