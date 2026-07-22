"""Archive extraction and text-encoding / corruption handling."""
import pytest

from transcripe.engines import archive
from transcripe.core import text_utils, capabilities


def test_zip_create_list_extract(fixtures, tmp_path, nullconsole):
    out = tmp_path / "b.zip"
    archive.create([fixtures["csv"], fixtures["json"]], out, nullconsole)
    names = {n for n, _ in archive.list_contents(out)}
    assert {"sample.csv", "sample.json"} <= names
    dest = archive.extract(out, tmp_path / "ex", nullconsole)
    assert (dest / "sample.csv").read_text().startswith("name,score")


def test_targz_roundtrip(fixtures, tmp_path, nullconsole):
    out = tmp_path / "b.tar.gz"
    archive.create([fixtures["csv"]], out, nullconsole)
    dest = archive.extract(out, tmp_path / "ex", nullconsole)
    assert (dest / "sample.csv").exists()


@pytest.mark.skipif(not capabilities.can("archive_7z"), reason="py7zr missing")
def test_7z_roundtrip(fixtures, tmp_path, nullconsole):
    out = tmp_path / "b.7z"
    archive.create([fixtures["json"]], out, nullconsole)
    dest = archive.extract(out, tmp_path / "ex", nullconsole)
    assert (dest / "sample.json").exists()


def test_zip_slip_protection(tmp_path, nullconsole):
    import zipfile
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../escape.txt", "pwned")
    with pytest.raises(RuntimeError):
        archive.extract(evil, tmp_path / "out", nullconsole)


def test_is_archive_detection(tmp_path):
    for name in ("a.zip", "a.tar.gz", "a.tgz", "a.7z", "a.rar", "a.tar.bz2"):
        assert archive.is_archive(tmp_path / name), name
    assert not archive.is_archive(tmp_path / "a.txt")


def test_encoding_detection_and_repair(fixtures, tmp_path, nullconsole):
    if "latin1" not in fixtures:
        pytest.skip("latin1 fixture unavailable")
    text, enc = text_utils.read_text_safe(fixtures["latin1"])
    assert "Café" in text and "résumé" in text
    out = tmp_path / "fixed.txt"
    text_utils.reencode_to_utf8(fixtures["latin1"], nullconsole, output_path=out)
    assert out.read_text(encoding="utf-8").startswith("Café")


def test_corruption_flags_binary_but_not_text():
    binary = "".join(chr(b) for b in range(256))
    assert text_utils.looks_corrupt(binary)[0] is True
    assert text_utils.looks_corrupt("A normal, readable sentence.")[0] is False
    assert text_utils.looks_corrupt("")[0] is True  # empty
    assert text_utils.looks_corrupt("He\ufffd\ufffd\ufffdlo\ufffd\ufffd")[0] is True
