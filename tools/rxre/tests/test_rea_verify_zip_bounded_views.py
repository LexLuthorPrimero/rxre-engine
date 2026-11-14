#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from rxre.parity import rea_verify_zip_bounded_views as M


def test_unicode_path_field_layout():
    raw = b"legacy.bin"
    field = M.unicode_path_field(raw, b"hidden/")
    assert field[:2] == b"up"  # 0x7075 little endian
    length = int.from_bytes(field[2:4], "little")
    assert length == len(field) - 4
    assert field[4] == 1  # version
    assert int.from_bytes(field[5:9], "little") == zlib_crc32_of(raw)
    assert field[9:] == b"hidden/"


def zlib_crc32_of(raw: bytes) -> int:
    import zlib

    return zlib.crc32(raw) & 0xffffffff


def test_expected_files_conflicting_fields():
    assert M.expected_files(M.fixture_conflict()) == [b"settings.json"]


def test_expected_files_bad_crc_falls_back_to_stored_name():
    assert M.expected_files(M.fixture_bad_final_crc()) == [b"legacy.bin"]


def test_expected_files_utf8_flag_prefers_stored_name():
    assert M.expected_files(M.fixture_utf8_flag()) == ["café.json".encode("utf-8")]


def test_fixture_zip_structures_have_local_and_eocd_records():
    for name, bytes_ in M.FIXTURES.items():
        assert bytes_[:4] == b"PK\x03\x04", name
        assert bytes_.rfind(b"PK\x05\x06") > len(bytes_) - 64, name


def test_all_fixtures_are_distinct_and_nonempty():
    sizes = {name: len(bytes_) for name, bytes_ in M.FIXTURES.items()}
    assert len(set(sizes.values())) >= 2
    assert all(size > 0 for size in sizes.values())
