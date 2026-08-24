"""Tests for APK manifest metadata extraction."""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

from app.services.apk_metadata import extract_apk_metadata


def _string_pool(strings: list[str]) -> bytes:
    offsets: list[int] = []
    payload = bytearray()
    for value in strings:
        raw = value.encode("utf-8")
        offsets.append(len(payload))
        payload.extend(bytes([len(value), len(raw)]))
        payload.extend(raw)
        payload.append(0)
    strings_start = 28 + len(offsets) * 4
    chunk_size = strings_start + len(payload)
    header = struct.pack("<HHIIIIII", 0x0001, 28, chunk_size, len(strings), 0, 0x100, strings_start, 0)
    return header + b"".join(struct.pack("<I", item) for item in offsets) + payload


def _binary_manifest() -> bytes:
    strings = ["manifest", "package", "com.example.demo", "versionName", "1.2.3", "versionCode", "42"]
    indexes = {value: index for index, value in enumerate(strings)}
    pool = _string_pool(strings)
    attributes = b"".join(
        struct.pack(
            "<IIIHBBI",
            0xFFFFFFFF,
            indexes[name],
            indexes[value],
            8,
            0,
            0x03,
            indexes[value],
        )
        for name, value in (
            ("package", "com.example.demo"),
            ("versionName", "1.2.3"),
            ("versionCode", "42"),
        )
    )
    extension = struct.pack("<IIHHHHHH", 0xFFFFFFFF, indexes["manifest"], 20, 20, 3, 0, 0, 0)
    chunk_size = 16 + len(extension) + len(attributes)
    start_element = struct.pack("<HHI", 0x0102, 16, chunk_size) + struct.pack("<II", 1, 0)
    return pool + start_element + extension + attributes


def _wrapped_binary_manifest() -> bytes:
    content = _binary_manifest()
    return struct.pack("<HHI", 0x0003, 8, 8 + len(content)) + content


def _write_apk(path: Path, manifest: bytes) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", manifest)


def test_extract_apk_metadata_reads_binary_android_manifest(tmp_path: Path):
    apk_path = tmp_path / "demo.apk"
    _write_apk(apk_path, _binary_manifest())

    assert extract_apk_metadata(apk_path) == {
        "package_name": "com.example.demo",
        "version_name": "1.2.3",
        "version_code": 42,
    }


def test_extract_apk_metadata_reads_wrapped_binary_android_manifest(tmp_path: Path):
    apk_path = tmp_path / "wrapped-demo.apk"
    _write_apk(apk_path, _wrapped_binary_manifest())

    assert extract_apk_metadata(apk_path) == {
        "package_name": "com.example.demo",
        "version_name": "1.2.3",
        "version_code": 42,
    }


def test_extract_apk_metadata_supports_text_manifest_for_fixtures(tmp_path: Path):
    apk_path = tmp_path / "fixture.apk"
    _write_apk(
        apk_path,
        b'<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
        b'package="com.example.fixture" android:versionName="2.0" android:versionCode="7" />',
    )

    assert extract_apk_metadata(apk_path) == {
        "package_name": "com.example.fixture",
        "version_name": "2.0",
        "version_code": 7,
    }


def test_extract_apk_metadata_returns_empty_for_invalid_apk(tmp_path: Path):
    path = tmp_path / "invalid.apk"
    path.write_bytes(b"not a zip")

    assert extract_apk_metadata(path) == {}
