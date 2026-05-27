from pathlib import Path

import pytest

from acquisition.manifest import ManifestEntry, load_manifest


def write_manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(body)
    return path


def test_load_manifest_parses_entries(tmp_path):
    path = write_manifest(tmp_path, """
- key: usgs
  title: "USGS Argentine Lithium Geodatabase"
  doi: "10.5066/P9RLUH4F"
  url: "https://example.com/usgs.gdb.zip"
  version: "1.0"
  license: "Public domain (USGS)"
  sha256: ""
  size_bytes: 0
  clip_to_puna: false
  notes: "control set"
""")
    entries = load_manifest(path)
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, ManifestEntry)
    assert e.key == "usgs"
    assert e.clip_to_puna is False
    assert e.sha256 == ""
    assert e.size_bytes == 0


def test_load_manifest_requires_key(tmp_path):
    path = write_manifest(tmp_path, """
- title: "no key"
  url: "https://x"
  version: "1"
  license: "x"
  clip_to_puna: false
""")
    with pytest.raises(ValueError, match="key"):
        load_manifest(path)


def test_load_manifest_requires_url(tmp_path):
    path = write_manifest(tmp_path, """
- key: usgs
  title: t
  version: "1"
  license: x
  clip_to_puna: false
""")
    with pytest.raises(ValueError, match="url"):
        load_manifest(path)


def test_load_manifest_rejects_unknown_field(tmp_path):
    path = write_manifest(tmp_path, """
- key: usgs
  title: t
  url: "https://x"
  version: "1"
  license: x
  clip_to_puna: false
  bogus_field: hello
""")
    with pytest.raises(ValueError, match="bogus_field"):
        load_manifest(path)


def test_compute_sha256_known_value(tmp_path):
    from acquisition.manifest import compute_sha256

    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    # sha256("hello world") = b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
    assert compute_sha256(f) == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_verify_sha256_matches(tmp_path):
    from acquisition.manifest import compute_sha256, verify_sha256

    f = tmp_path / "x.bin"
    f.write_bytes(b"data")
    sha = compute_sha256(f)
    verify_sha256(f, sha)  # no raise


def test_verify_sha256_mismatch_raises(tmp_path):
    from acquisition.manifest import IntegrityError, verify_sha256

    f = tmp_path / "x.bin"
    f.write_bytes(b"data")
    with pytest.raises(IntegrityError, match="SHA256"):
        verify_sha256(f, "0" * 64)
