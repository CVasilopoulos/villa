**In one sentence:** `tifs_to_ome_zarr.py` runs on the zarr version in `vesuvius/uv.lock` (3.2.1) instead of crashing before it writes level 0, and writes the same voxels as main does under zarr 2.

**One real example:** I exported 64 real CT slices (384×384, uint8) from the public PHercParis4 45.532 µm volume to TIFF and ran `tifs_to_ome_zarr --num-levels 4 --workers 4` on them under zarr 3.2.1. On main it dies with `AttributeError: 'Group' object has no attribute 'create_dataset'`. On this branch it completes, and all four levels are voxel-identical to main's output under zarr 2.18.7.

**Before:** `convert_tifs_to_ome_zarr` opens the output with `zarr.open(mode="w")` and calls `Group.create_dataset` for level 0 (l. 709); `generate_pyramid_levels` calls it again for every pyramid level (l. 555). zarr 3 removed `create_dataset`, so under the locked zarr the script exits 1 before writing level 0 and leaves an empty zarr v3 group (`zarr.json` only) at the output path.

**After this PR:** Level 0 and the pyramid levels are created with `create_zarr_array` and the output group is opened with `open_zarr_group` (both in `vesuvius/data/utils.py`, used by `structure_tensor` since #1700). Both work on zarr 2 and zarr 3 and write a zarr v2 store with the same array metadata main writes under zarr 2. Nothing else in the script changes.

**Proof:** same 64 TIFFs, same flags (`--num-levels 4 --workers 4`, default chunks `64,256,256`), fresh copy of the TIFFs for every run. Reference = upstream main under zarr 2.18.7 + numcodecs 0.15.2.

| Run | zarr | Exit | Result |
|---|---|---|---|
| main | 3.2.1 | 1 | `AttributeError: 'Group' object has no attribute 'create_dataset'` (`tifs_to_ome_zarr.py:709`, in `convert_tifs_to_ome_zarr`); output dir holds only `zarr.json` (66 bytes) |
| main (reference) | 2.18.7 | 0 | levels 64×384×384, 32×192×192, 16×96×96, 8×48×48; level 0 has 9,194,644 non-zero voxels, sum 802,366,303 |
| branch | 3.2.1 | 0 | identical to reference at all 4 levels (0 differing voxels) |
| branch | 2.18.7 | 0 | identical to reference at all 4 levels (0 differing voxels) |

SHA-1 of the decoded level arrays, identical for the reference and both branch runs: level 0 `2335a8dd7cb2…`, 1 `556d94b80701…`, 2 `e4a9da094c6d…`, 3 `2c2fad9f34f4…`. Every branch output has `.zgroup` = `{"zarr_format": 2}`, no `zarr.json`, the same `.zattrs` (`multiscales`) as the reference, and a blosc/zstd compressor on every level.

**Why / where this is useful:** Anyone who installs `vesuvius` from the lockfile and turns a TIFF stack into an OME-Zarr can run the script again; today it fails on its first zarr write.

- [ ] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

- Change: `vesuvius/src/vesuvius/scripts/tifs_to_ome_zarr.py` only (1 import, the output-group open, the two `create_dataset` calls), and a new test `vesuvius/tests/scripts/test_tifs_to_ome_zarr_zarr3.py`.
- Tested: upstream main `d57c28ebe` vs this branch `85fa6027b` (one commit on top of `d57c28ebe`), Linux x86_64, 4 CPUs, Python 3.14. zarr 3.2.1 + numcodecs 0.16.5 (the `uv.lock` versions) and zarr 2.18.7 + numcodecs 0.15.2 (the `pyproject.toml` lower bound).
- Data: `PHercParis4/volumes/20260310170716-45.532um-11.0m-74keV-masked.zarr`, level 0 (4071×2264×2264 uint8, 128³ chunks, uncompressed), crop z 2000:2064, y 1000:1384, x 900:1284, read from the 32 chunks `0/15..16/7..10/7..10` downloaded from `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/`. Each z slice was written as one untiled uint8 TIFF (`02000.tif` … `02063.tif`, 9.3 MB in total; min 0, max 255, mean 85.0). The script converts untiled TIFFs to tiled ones in place, so every run got a fresh copy.
- Commands (from `vesuvius/` of each checkout, `PYTHONPATH=src`):

```
python -m vesuvius.scripts.tifs_to_ome_zarr tifs/ out.zarr --num-levels 4 --workers 4
```

  Comparison: read each level with zarr and `np.count_nonzero(a != b)` against the reference, plus `.zarray`, `.zattrs` and `.zgroup`.
- Other zarr calls in the script, checked under zarr 3.2.1: the level-0 tile writes from the thread pool, `generate_pyramid_levels`' `zarr.open(mode="r+")` and its `root[...]` reads, and `downsample_chunk`'s reads in the process pool all work on the v2 store. The l. 555 pyramid call was the second crash site (hidden behind l. 709 on main); with both replaced the run completes with 1 and with 4 workers.
- On-disk differences from main under zarr 2: none in the decoded values or the chunk file names. Under zarr 3 the `.zarray` files carry an explicit `"dimension_separator": "."` (zarr 2 leaves the key out; `.` is its default) and each level directory gets an empty `.zattrs` (`{}`). Under zarr 2 the branch writes the same metadata as main. The compressed chunk bytes are not compared: two main runs under zarr 2 on the same TIFFs already produce different bytes for the same chunks (blosc), with identical decoded values.
- Why `create_zarr_array` and not `create_level_dataset`: `create_level_dataset` hard-codes `dimension_separator="/"`, `fill_value=0` and `write_empty_chunks=False`, which would change the chunk layout this script has always written (`.` keys, all-zero chunks of level 0 written). `create_zarr_array` is the `create_dataset` replacement that keeps zarr 2's layout on both majors.
- Tests: `PYTHONPATH=src python -m pytest -q tests/scripts/test_tifs_to_ome_zarr_zarr3.py` converts an 8×40×48 TIFF stack with 1 and 2 workers and checks levels 0–2 against the strided stack, the v2 group and the compressor. Branch: 2 passed under zarr 3.2.1 and under zarr 2.18.7. Main: 2 failed under zarr 3.2.1 (`AttributeError: 'Group' object has no attribute 'create_dataset'`, `tifs_to_ome_zarr.py:709`), 2 passed under zarr 2.18.7. `tests/scripts`: 11 passed on the branch under both zarr versions. `tests/structure_tensor/test_zarr3_compat.py` (covers `create_zarr_array`/`open_zarr_group`): 10 passed under 3.2.1, 7 passed + 3 skipped under 2.18.7; its other 2 tests fail with `ModuleNotFoundError` (`dask`, `torch` are not installed in my test environment), the same on main.
- The script now imports from `vesuvius`, so running it by file path needs the package installed or `PYTHONPATH=src` (`python -m vesuvius.scripts.tifs_to_ome_zarr` as above).
- Earlier work: #1467 (jaideepsaipadhi, closed without merging) changed these two calls as part of a repo-wide zarr 2/3 compatibility layer (`vesuvius.zarr_compat`), which main does not have; this PR uses the helpers that were merged instead.
- Independent of the other zarr 3 script fixes (`labels_to_zarr`, `extract_sparse_ome_zarr`, `fill_inner_outer_labels`): different files; `git merge-tree --write-tree` merges this branch cleanly with each of them.

AI-assisted, human-directed.
