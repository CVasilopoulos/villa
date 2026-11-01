**In one sentence:** `extract_sparse_ome_zarr.py` runs on the zarr version in `vesuvius/uv.lock` (3.2.1) instead of crashing before it copies any chunk, and writes the same voxels as main does under zarr 2.

**One real example:** Starting with the public PHercParis4 45.532 µm volume and the published tifxyz mesh of segment `20260602225659-5753_0` on that volume, I ran `extract_sparse_ome_zarr --margin 64 --num-levels 6 --workers 4` under zarr 3.2.1. On main it dies with `AttributeError: 'Group' object has no attribute 'create_dataset'`. On this branch it copies 550 chunks over 6 levels, and the output is voxel-identical to main's output under zarr 2.18.7, with the same chunk files.

**Before:** `extract_sparse_ome_zarr` opens the output with `zarr.open(mode="w")` and calls `Group.create_dataset` for every level (l. 431). zarr 3 removed `create_dataset`, so under the locked zarr the script exits 1 right after computing the chunk list and leaves an empty zarr v3 group (`zarr.json` only) at the output path.

**After this PR:** The output levels are created with `create_zarr_array` and the output group is opened with `open_zarr_group` (both in `vesuvius/data/utils.py`, used by `structure_tensor` since #1700). Both work on zarr 2 and zarr 3 and write a zarr v2 store with the same array metadata main writes under zarr 2. Nothing else in the script changes.

**Proof:** same source, same segment, same flags. Reference = upstream main under zarr 2.18.7 + numcodecs 0.15.2.

| Run | zarr | Exit | Result |
|---|---|---|---|
| main | 3.2.1 | 1 | `AttributeError: 'Group' object has no attribute 'create_dataset'` (`extract_sparse_ome_zarr.py:431`); output dir holds only `zarr.json` |
| main (reference) | 2.18.7 | 0 | 550 chunks copied (416 / 92 / 26 / 13 / 2 / 1 on levels 0–5), 1.15 GB; level 0 has 803,974,094 non-zero voxels |
| branch | 3.2.1 | 0 | identical to reference at all 6 levels (0 differing voxels, same chunk file set) |
| branch | 2.18.7 | 0 | identical to reference at all 6 levels (0 differing voxels, same chunk file set) |
| branch, source = bucket URL | 3.2.1 | 0 | identical to reference at all 6 levels (0 differing voxels, same chunk file set) |

The source is uncompressed (`compressor: null`, which the script copies), so the chunk files can be compared directly: every chunk file of both branch runs is byte-identical to the reference (`diff -rq` reports only metadata files). `chunks.json` is byte-identical to the reference for both local-source branch runs. Every branch output has `.zgroup` = `{"zarr_format": 2}`, no `zarr.json`, and the same `.zattrs` (`multiscales`) as the reference.

**Why / where this is useful:** Anyone who installs `vesuvius` from the lockfile and cuts a sparse working copy of a volume around their segments can run the script again; today it fails on its first zarr write.

- [ ] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

- Change: `vesuvius/src/vesuvius/scripts/extract_sparse_ome_zarr.py` only (1 import, the output-group open, the `create_dataset` call), and a new test `vesuvius/tests/scripts/test_extract_sparse_ome_zarr_zarr3.py`.
- Tested: upstream main `d57c28ebe` vs this branch `bc3864660` (one commit on top of `d57c28ebe`), Linux x86_64, 4 CPUs, Python 3.14. zarr 3.2.1 + numcodecs 0.16.5 (the `uv.lock` versions) and zarr 2.18.7 + numcodecs 0.15.2 (the `pyproject.toml` lower bound).
- Data, all from `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/`:
  - segment: `PHercParis4/segments/20260602225659-5753_0/mesh/20260602225659-on-20260310170716-45.532um.tifxyz/` (`meta.json`, `x.tif`, `y.tif`, `z.tif`; 212×43 grid, 6,265 valid points), unchanged.
  - source: `PHercParis4/volumes/20260310170716-45.532um-11.0m-74keV-masked.zarr` (level 0 4071×2264×2264 uint8, 128³ chunks, uncompressed). For the local runs I mirrored `.zgroup`, `.zattrs`, every level's `.zarray` and exactly the chunks the script selects for this segment (433 / 92 / 26 / 13 / 2 / 1 on levels 0–5, computed with the script's own `compute_relevant_chunks`/`compute_chunks_for_level`); 17 of the 433 level-0 chunks do not exist in the bucket and read as fill value 0, which the script skips as empty on both sides. The fifth run reads the bucket URL directly (the script's fsspec path) instead of the mirror.
- Commands (from `vesuvius/` of each checkout, `PYTHONPATH=src`):

```
python -m vesuvius.scripts.extract_sparse_ome_zarr vol45-mirror.zarr out.zarr --tifxyz segs/ --margin 64 --num-levels 6 --workers 4
python -m vesuvius.scripts.extract_sparse_ome_zarr https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHercParis4/volumes/20260310170716-45.532um-11.0m-74keV-masked.zarr out.zarr --tifxyz segs/ --margin 64 --num-levels 6 --workers 4
```

  Comparison: chunk-wise (level 0 is 20 GB dense), over the union of chunk files written by either run, `np.count_nonzero(a != b)`; regions with no chunk file in either store read as the fill value in both. Plus `.zarray`, `.zattrs`, `.zgroup`, `chunks.json` and `diff -rq` of the chunk files.
- Other zarr calls in the script, checked under zarr 3.2.1: `src_arr.compressor` (l. 402) still works on a v2 source (it emits a `ZarrDeprecationWarning`); `open_zarr_read` works for a local path and for the https URL (fsspec mapper); `copy_chunk_worker`'s `zarr.open(mode="r+")` writes into the v2 output from the process pool. `copy_chunk_worker` logs and swallows any exception, so a failure there would show up only as missing chunks: none of the branch runs logged `Failed to copy`, and all copied 550 chunks.
- On-disk differences from main under zarr 2: none in the values or the chunk files. Under zarr 3 the `.zarray` files carry an explicit `"dimension_separator": "."` (zarr 2 leaves the key out; `.` is its default) and each level directory gets an empty `.zattrs` (`{}`). Under zarr 2 the branch writes the same metadata as main.
- Why `create_zarr_array` and not `create_level_dataset`: `create_level_dataset` hard-codes `dimension_separator="/"`, which would change the chunk layout this script has always written; `create_zarr_array` is the `create_dataset` replacement that keeps zarr 2's layout on both majors and takes the same `fill_value=0`, `write_empty_chunks=False` the script already passes.
- Tests: `PYTHONPATH=src python -m pytest -q tests/scripts/test_extract_sparse_ome_zarr_zarr3.py` extracts the chunks around a small tifxyz plane from a two-level synthetic source with 1 and 2 workers and checks the copied and the untouched regions of both levels, `chunks.json`, the v2 group and the compressor. Branch: 2 passed under zarr 3.2.1 and under zarr 2.18.7. Main: 2 failed under zarr 3.2.1 (`AttributeError: 'Group' object has no attribute 'create_dataset'`, `extract_sparse_ome_zarr.py:431`), 2 passed under zarr 2.18.7. `tests/scripts`: 11 passed on the branch under both zarr versions. `tests/structure_tensor/test_zarr3_compat.py` (covers `create_zarr_array`/`open_zarr_group`): 10 passed under 3.2.1, 7 passed + 3 skipped under 2.18.7; its other 2 tests fail with `ModuleNotFoundError` (`dask`, `torch` are not installed in my test environment), the same on main.
- Earlier work: #1467 (jaideepsaipadhi, closed without merging) changed this call as part of a repo-wide zarr 2/3 compatibility layer (`vesuvius.zarr_compat`), which main does not have; this PR uses the helpers that were merged instead.
- Independent of the other zarr 3 script fixes (`tifs_to_ome_zarr`, `labels_to_zarr`, `fill_inner_outer_labels`): different files; `git merge-tree --write-tree` merges this branch cleanly with each of them.

AI-assisted, human-directed.
