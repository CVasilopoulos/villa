"""extract_sparse_ome_zarr runs end to end on every zarr the package accepts (pyproject: zarr>=2.18.7,<4).

extract_sparse_ome_zarr called Group.create_dataset, which zarr 3 removed, so the script crashed
under zarr 3 before copying any chunk. It now creates the output levels through create_zarr_array.
"""
import json

import numpy as np
import pytest
import zarr
from numcodecs import Blosc

from vesuvius.data.utils import create_zarr_array, open_zarr_group
from vesuvius.scripts import extract_sparse_ome_zarr as esz
from vesuvius.tifxyz import Tifxyz, write_tifxyz


def _write_source(path):
    rng = np.random.default_rng(0)
    root = open_zarr_group(str(path), mode="w")
    levels = {"0": rng.integers(1, 256, size=(64, 64, 64), dtype=np.uint8)}
    levels["1"] = levels["0"][::2, ::2, ::2].copy()
    for name, data in levels.items():
        create_zarr_array(root, name, data=data, chunks=(16, 16, 16), compressor=Blosc(cname="zstd", clevel=1))
    return levels


def _write_plane(folder, z):
    yy, xx = np.mgrid[4:28, 4:28].astype(np.float32)
    surface = Tifxyz(_x=xx, _y=yy, _z=np.full_like(xx, z), uuid="plane", _mask=np.ones(xx.shape, dtype=bool))
    write_tifxyz(folder / "plane", surface)


@pytest.mark.parametrize("workers", [1, 2])
def test_copies_only_the_chunks_near_the_surface(tmp_path, workers):
    levels = _write_source(tmp_path / "src.zarr")
    _write_plane(tmp_path / "surfaces", z=20)
    out = tmp_path / "out.zarr"

    esz.extract_sparse_ome_zarr(str(tmp_path / "src.zarr"), out, tmp_path / "surfaces",
                                margin_voxels=4, num_levels=2, num_workers=workers)

    expected0 = np.zeros_like(levels["0"])
    expected0[16:32, 0:32, 0:32] = levels["0"][16:32, 0:32, 0:32]
    expected1 = np.zeros_like(levels["1"])
    expected1[0:16, 0:16, 0:16] = levels["1"][0:16, 0:16, 0:16]
    np.testing.assert_array_equal(zarr.open(str(out / "0"), mode="r")[...], expected0)
    np.testing.assert_array_equal(zarr.open(str(out / "1"), mode="r")[...], expected1)
    manifest = json.loads((out / "chunks.json").read_text())
    assert manifest["total_copied"] == 5
    assert sorted(map(tuple, manifest["chunks_by_level"]["0"])) == [(1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1)]
    assert json.loads((out / ".zgroup").read_text())["zarr_format"] == 2
    assert not (out / "zarr.json").exists()
    assert json.loads((out / "0" / ".zarray").read_text())["compressor"]["id"] == "blosc"
