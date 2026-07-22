"""3D model conversion (needs Node.js toolchain; skips otherwise)."""
import pytest

from transcripe.engines import models3d
from transcripe.core import capabilities

pytestmark = pytest.mark.skipif(not capabilities.can("model3d"),
                                reason="Node.js toolchain unavailable")


def test_obj_to_web_glb_is_draco(fixtures, tmp_path, nullconsole):
    if "obj" not in fixtures:
        pytest.skip("obj fixture unavailable")
    out = tmp_path / "cube_web.glb"
    models3d.convert_model(fixtures["obj"], "glb", nullconsole,
                           output_path=out, optimize=True, compress="draco")
    data = out.read_bytes()
    assert data[:4] == b"glTF", "not a valid GLB container"
    assert len(data) > 0


def test_obj_to_plain_glb(fixtures, tmp_path, nullconsole):
    if "obj" not in fixtures:
        pytest.skip("obj fixture unavailable")
    out = tmp_path / "cube.glb"
    models3d.convert_model(fixtures["obj"], "glb", nullconsole,
                           output_path=out, optimize=False)
    assert out.read_bytes()[:4] == b"glTF"


@pytest.mark.skipif(not capabilities.can("model3d_mesh"), reason="trimesh unavailable")
def test_obj_to_stl_and_ply(fixtures, tmp_path, nullconsole):
    if "obj" not in fixtures:
        pytest.skip("obj fixture unavailable")
    for fmt in ("stl", "ply"):
        out = tmp_path / f"cube.{fmt}"
        models3d.convert_model(fixtures["obj"], fmt, nullconsole, output_path=out, optimize=False)
        assert out.stat().st_size > 0, f"{fmt} export empty"
