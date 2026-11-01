"""tifs_to_ome_zarr runs end to end on every zarr the package accepts (pyproject: zarr>=2.18.7,<4).

convert_tifs_to_ome_zarr and generate_pyramid_levels called Group.create_dataset, which zarr 3
removed, so the script crashed under zarr 3 before writing level 0. They now create levels through
create_zarr_array.
"""
import json

import numpy as np
import pytest
import tifffile
import zarr

from vesuvius.scripts import tifs_to_ome_zarr as t2z


def _write_tiffs(folder, volume):
    folder.mkdir()
    for z, plane in enumerate(volume):
        tifffile.imwrite(folder / f"{z:03d}.tif", plane, tile=(16, 16))


@pytest.mark.parametrize("workers", [1, 2])
def test_writes_level_0_and_strided_pyramid_levels(tmp_path, workers):
    rng = np.random.default_rng(0)
    volume = rng.integers(1, 256, size=(8, 40, 48), dtype=np.uint8)
    _write_tiffs(tmp_path / "tifs", volume)
    out = tmp_path / "out.zarr"

    t2z.convert_tifs_to_ome_zarr(tmp_path / "tifs", out, num_levels=3, chunk_shape=(4, 16, 16), num_workers=workers)

    np.testing.assert_array_equal(zarr.open(str(out / "0"), mode="r")[...], volume)
    np.testing.assert_array_equal(zarr.open(str(out / "1"), mode="r")[...], volume[::2, ::2, ::2])
    np.testing.assert_array_equal(zarr.open(str(out / "2"), mode="r")[...], volume[::4, ::4, ::4])
    assert json.loads((out / ".zgroup").read_text())["zarr_format"] == 2
    assert not (out / "zarr.json").exists()
    for level in ("0", "1", "2"):
        meta = json.loads((out / level / ".zarray").read_text())
        assert meta["zarr_format"] == 2
        assert meta["compressor"]["id"] == "blosc"
    assert [d["path"] for d in json.loads((out / ".zattrs").read_text())["multiscales"][0]["datasets"]] == ["0", "1", "2"]
