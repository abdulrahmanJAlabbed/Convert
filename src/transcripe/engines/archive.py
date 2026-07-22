"""Archive engine: inspect, extract, and repackage compressed files.

Supports .zip, .tar, .tar.gz/.tgz, .tar.bz2, .tar.xz, .gz, .bz2, .xz, .7z, .rar.
"""
import gzip
import bz2
import lzma
import shutil
import tarfile
import zipfile
from pathlib import Path
from rich.console import Console


TAR_EXTS = {".tar", ".tgz", ".gz", ".bz2", ".xz", ".tbz2", ".txz"}
ARCHIVE_EXTS = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".tbz2",
                ".txz", ".7z", ".rar"}

# Single-file (non-tar) stream compressors.
_STREAM = {".gz": gzip, ".bz2": bz2, ".xz": lzma}


def is_archive(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        return True
    return path.suffix.lower() in ARCHIVE_EXTS


def _is_tar(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
        return True
    # A lone .gz/.bz2/.xz may still wrap a tar; tarfile.is_tarfile decides.
    try:
        return tarfile.is_tarfile(path)
    except Exception:
        return False


def list_contents(path: Path) -> list[tuple[str, int]]:
    """Return [(name, size_bytes), ...] for an archive."""
    ext = path.suffix.lower()
    name = path.name.lower()

    if ext == ".zip" or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            return [(i.filename, i.file_size) for i in z.infolist() if not i.is_dir()]

    if ext == ".7z":
        import py7zr
        with py7zr.SevenZipFile(path, "r") as z:
            return [(n, 0) for n in z.getnames()]

    if ext == ".rar":
        import rarfile
        with rarfile.RarFile(path) as r:
            return [(i.filename, i.file_size) for i in r.infolist() if not i.isdir()]

    if _is_tar(path):
        with tarfile.open(path) as t:
            return [(m.name, m.size) for m in t.getmembers() if m.isfile()]

    # Lone stream compressor (single file inside).
    if ext in _STREAM or name.endswith((".gz", ".bz2", ".xz")):
        return [(path.stem, 0)]

    raise ValueError(f"Unsupported archive type: {path.suffix}")


def extract(path: Path, out_dir: Path | None, console: Console) -> Path:
    """Extract an archive into a folder. Returns the output directory."""
    out_dir = out_dir or (path.parent / f"{path.stem}_extracted")
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    name = path.name.lower()

    with console.status(f"[bold cyan]Extracting {path.name}…[/bold cyan]"):
        if ext == ".zip" or zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                _safe_extract_zip(z, out_dir)
        elif ext == ".7z":
            import py7zr
            with py7zr.SevenZipFile(path, "r") as z:
                _assert_safe_names(z.getnames(), out_dir)
                z.extractall(path=out_dir)
        elif ext == ".rar":
            import rarfile
            with rarfile.RarFile(path) as r:
                _assert_safe_names(r.namelist(), out_dir)
                r.extractall(path=out_dir)
        elif _is_tar(path):
            with tarfile.open(path) as t:
                _safe_extract_tar(t, out_dir)
        elif ext in _STREAM or name.endswith((".gz", ".bz2", ".xz")):
            mod = _STREAM[f".{name.rsplit('.', 1)[-1]}"]
            target = out_dir / path.stem
            with mod.open(path, "rb") as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        else:
            raise ValueError(f"Unsupported archive type: {path.suffix}")

    count = sum(1 for _ in out_dir.rglob("*") if _.is_file())
    console.print(f"[bold green]✓ Extracted {count} file(s) → {out_dir.name}/[/bold green]")
    return out_dir


def _assert_safe_names(names, out_dir: Path) -> None:
    """Reject entries that would escape out_dir (Zip-Slip / path traversal).

    Uses Path.is_relative_to — a plain str.startswith prefix check is bypassable
    (e.g. dest '/x/out' matches '/x/out_evil/f').
    """
    dest = out_dir.resolve()
    for name in names:
        target = (out_dir / name).resolve()
        if not target.is_relative_to(dest):
            raise RuntimeError(f"Unsafe path in archive: {name}")


def _safe_extract_zip(z: zipfile.ZipFile, out_dir: Path) -> None:
    _assert_safe_names((m.filename for m in z.infolist()), out_dir)
    z.extractall(out_dir)


def _safe_extract_tar(t: tarfile.TarFile, out_dir: Path) -> None:
    _assert_safe_names((m.name for m in t.getmembers()), out_dir)
    try:
        t.extractall(out_dir, filter="data")  # Python 3.12+ safe filter
    except TypeError:
        t.extractall(out_dir)


def create(files: list[Path], out_path: Path, console: Console) -> Path:
    """Compress files into an archive chosen by out_path's extension (.zip/.tar.gz/.7z)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ext = out_path.suffix.lower()
    name = out_path.name.lower()

    with console.status(f"[bold cyan]Creating {out_path.name}…[/bold cyan]"):
        if ext == ".zip":
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
                for f in files:
                    z.write(f, arcname=f.name)
        elif ext == ".7z":
            import py7zr
            with py7zr.SevenZipFile(out_path, "w") as z:
                for f in files:
                    z.write(f, arcname=f.name)
        elif name.endswith((".tar.gz", ".tgz")):
            _write_tar(files, out_path, "w:gz")
        elif name.endswith((".tar.bz2", ".tbz2")):
            _write_tar(files, out_path, "w:bz2")
        elif name.endswith((".tar.xz", ".txz")):
            _write_tar(files, out_path, "w:xz")
        elif ext == ".tar":
            _write_tar(files, out_path, "w")
        else:
            raise ValueError(f"Unsupported archive target: {out_path.suffix}")

    size_mb = out_path.stat().st_size / 1_048_576
    console.print(f"[bold green]✓ Archived {len(files)} file(s) → {out_path.name} ({size_mb:.1f} MB)[/bold green]")
    return out_path


def _write_tar(files: list[Path], out_path: Path, mode: str) -> None:
    with tarfile.open(out_path, mode) as t:
        for f in files:
            t.add(f, arcname=f.name)
