**In one sentence:** `labels_to_zarr.py` runs on the zarr version in `vesuvius/uv.lock` (3.2.1), including `--expand`, instead of crashing before it writes any label, and writes the same voxels as main does under zarr 2.

**One real example:** Starting with the published tifxyz mesh of PHercParis4 segment `20260602225659-5753_0` on the 45.532 µm volume and an ink label made from that segment's published ink prediction, I ran `labels_to_zarr --label-value 255 --padding 0 --expand 2 --num-workers 4` with the volume's shape under zarr 3.2.1. On main it dies with `AttributeError: 'Group' object has no attribute 'create_dataset'`. With only that call fixed it dies later, in the `--expand` step, with `AttributeError: 'LocalStore' object has no attribute 'keys'`. On this branch it completes, and all 6 levels are voxel-identical to main's output under zarr 2.18.7.

**Before:** `main` opens the output with `zarr.open_group(mode="w")` and calls `Group.create_dataset` for level 0 (l. 1850), and `generate_pyramid_levels` calls it for every pyramid level (l. 1668); zarr 3 removed `create_dataset`, so under the locked zarr the script exits 1 before writing any label and leaves an empty zarr v3 group (`zarr.json` only). Behind that, `get_initialized_chunk_indices` (used by `--expand` and `--padding-expansion`) lists chunks with `zarr_array.store.keys()`, which zarr 3 stores do not have.

**After this PR:** Level 0 and the pyramid levels are created with `create_zarr_array` and the output group is opened with `open_zarr_group` (both in `vesuvius/data/utils.py`, used by `structure_tensor` since #1700). Both work on zarr 2 and zarr 3 and write a zarr v2 store with the same array metadata main writes under zarr 2, including a non-zero `fill_value` from `--remap-json`. `get_initialized_chunk_indices` keeps `store.keys()` where the store has it (zarr 2) and otherwise lists the array's directory with the zarr 3 store's `list_dir`. Nothing else in the script changes.

**Proof:** same inputs, same flags (`--label-suffix _inklabels --label-value 255 --shape 4071 2264 2264 --chunks 128 128 128 --padding 0 --expand 2 --num-workers 4`, default 6 levels), fresh copy of the inputs for every run. Reference = upstream main under zarr 2.18.7 + numcodecs 0.15.2.

| Run | zarr | Exit | Result |
|---|---|---|---|
| main | 3.2.1 | 1 | `AttributeError: 'Group' object has no attribute 'create_dataset'` (`labels_to_zarr.py:1850`, in `main`); output dir holds only `zarr.json` |
| main + only the `create_dataset` changes | 3.2.1 | 1 | `AttributeError: 'LocalStore' object has no attribute 'keys'` (`get_initialized_chunk_indices`, called from `expand_labels_in_zarr`) |
| main (reference) | 2.18.7 | 0 | 162 / 56 / 17 / 9 / 2 / 1 chunk files on levels 0–5; level 0 has 1,406,360 voxels = 255; expansion found 162 initialized chunks and processed 729 |
| branch | 3.2.1 | 0 | identical to reference at all 6 levels (0 differing voxels, same chunk file set); expansion found 162 initialized chunks and processed 729 |
| branch | 2.18.7 | 0 | identical to reference at all 6 levels (0 differing voxels, same chunk file set) |

SHA-1 of the decoded written chunks, identical for the reference and both branch runs: level 0 `a97079b983e9…`, level 1 `b1ef23016677…`. Every branch output has `.zgroup` = `{"zarr_format": 2}`, no `zarr.json`, the same `.zattrs` (`multiscales`) as the reference, and `fill_value` 0 on every level.

**Why / where this is useful:** Anyone who installs `vesuvius` from the lockfile and turns 2D ink or surface labels on tifxyz segments into a 3D label volume can run the script again; today it fails on its first zarr write, and with `--expand` it would fail again after writing the labels.

- [ ] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

- Change: `vesuvius/src/vesuvius/scripts/labels_to_zarr.py` only (1 import, the output-group open, the two `create_dataset` calls, the store listing in `get_initialized_chunk_indices`), and a new test `vesuvius/tests/scripts/test_labels_to_zarr_zarr3.py`.
- Tested: upstream main `d57c28ebe` vs this branch `74daa32e8` (one commit on top of `d57c28ebe`), Linux x86_64, 4 CPUs, Python 3.14. zarr 3.2.1 + numcodecs 0.16.5 (the `uv.lock` versions) and zarr 2.18.7 + numcodecs 0.15.2 (the `pyproject.toml` lower bound).
- Data, from `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/`:
  - segment: `PHercParis4/segments/20260602225659-5753_0/mesh/20260602225659-on-20260310170716-45.532um.tifxyz/` (`meta.json`, `x.tif`, `y.tif`, `z.tif`; 212×43 stored, 4240×860 at full resolution), unchanged.
  - label: `PHercParis4/segments/20260602225659-5753_0/ink-detection/PHercParis4-20260602225659-2.4um-0.22m-78keV-volume-20260411134726-20260417190342-new_canon_autoresearch_recipe-tile256-stride128.tif` (80240×16160 uint8, values 0–247). This is a model prediction, not a hand-made label, and it is on the 2.4 µm mesh's grid. I resized it to the 45.532 µm mesh's full-resolution grid (4240×860, `cv2.INTER_NEAREST`) and set pixels ≥128 to 255 and the rest to 0 (280,415 of 3,646,400 pixels are 255), saved as `20260602225659_inklabels.tif` in the tifxyz folder. I resized it beforehand because the script only resizes labels that are smaller than the surface; a larger one is cropped.
  - `--shape` is the shape of level 0 of `PHercParis4/volumes/20260310170716-45.532um-11.0m-74keV-masked.zarr` (4071×2264×2264).
- Commands (from `vesuvius/` of each checkout, `PYTHONPATH=src`):

```
python -m vesuvius.scripts.labels_to_zarr segs/ --label-suffix _inklabels --label-value 255 --output out.zarr \
    --shape 4071 2264 2264 --chunks 128 128 128 --padding 0 --expand 2 --num-workers 4
```

  Comparison: chunk-wise (level 0 is 20 GB dense), over the union of chunk files written by either run, `np.count_nonzero(a != b)`; regions with no chunk file in either store read as the fill value in both. Plus `.zarray`, `.zattrs` and `.zgroup`.
- Other zarr calls in the script, checked under zarr 3.2.1: the workers' `zarr.open(mode="r+")` writes, `expand_chunk_worker`, `generate_pyramid_levels`' `zarr.open(mode="r+")`, its `fill_value` reads and the downsampling workers all work on the v2 store. `get_initialized_chunk_indices` was the only other failure. `chunks_written.json` and `metadata.json` are written without zarr.
- On-disk differences from main under zarr 2: none in the decoded values or the chunk file names. Under zarr 3 the `.zarray` files carry an explicit `"dimension_separator": "."` (zarr 2 leaves the key out; `.` is its default) and each level directory gets an empty `.zattrs` (`{}`). Under zarr 2 the branch writes the same metadata as main. The compressed chunk bytes are not compared: two main runs under zarr 2 on the same inputs already differ in 85 of 247 chunk files (blosc), with identical decoded values.
- Why `create_zarr_array` and not `create_level_dataset`: `create_level_dataset` hard-codes `fill_value=0` and `dimension_separator="/"`. This script uses the `--remap-json` mapping of 0 as the fill value (the second test covers fill value 2), and `get_initialized_chunk_indices` parses `.`-separated chunk keys, so both would break. `create_zarr_array` is the `create_dataset` replacement that keeps zarr 2's layout on both majors and takes the script's `fill_value` and `write_empty_chunks=False` as they are.
- The zarr 3 listing uses `zarr.core.sync.collect_aiterator` with `store.list_dir(...)`, checked on zarr 3.2.1 only. The level-0 array is opened at its own path, so the listing covers just its chunk keys, as `keys()` does on zarr 2.
- Tests: `PYTHONPATH=src python -m pytest -q tests/scripts/test_labels_to_zarr_zarr3.py` runs the script's `main()` on a 24×24 tifxyz plane with a 4×4 ink label (a) with `--expand 1`, checking level 0 against an EDT dilation of the labelled voxels and level 1 against its stride-2 sample, and (b) with a remap `{"0": 2, "255": 1}`, checking the values and `fill_value` 2 on both levels. Branch: 2 passed under zarr 3.2.1 and under zarr 2.18.7. Main: 2 failed under zarr 3.2.1 (`AttributeError: 'Group' object has no attribute 'create_dataset'`, `labels_to_zarr.py:1850`), 2 passed under zarr 2.18.7. With the `create_dataset` changes but without the listing change, (a) fails under zarr 3.2.1 with `AttributeError: 'LocalStore' object has no attribute 'keys'`. `tests/scripts`: 11 passed on the branch under both zarr versions. `tests/structure_tensor/test_zarr3_compat.py` (covers `create_zarr_array`/`open_zarr_group`): 10 passed under 3.2.1, 7 passed + 3 skipped under 2.18.7; its other 2 tests fail with `ModuleNotFoundError` (`dask`, `torch` are not installed in my test environment), the same on main.
- Every run, main under zarr 2 included, ends with a `resource_tracker` "leaked semaphore objects" warning; it is not from this change.
- Earlier work: #1200 (NanokodasKarolis, closed without merging) fixed these zarr 3 failures together with chunked-expansion fixes; its `get_initialized_chunk_indices` also listed zarr 3 stores through `collect_aiterator`, and its array creation used `create_array(..., zarr_format=2)`, which zarr 2 does not have. #1467 (jaideepsaipadhi, closed without merging) changed the `create_dataset` calls as part of a repo-wide compatibility layer (`vesuvius.zarr_compat`) that main does not have. This PR is the zarr 3 part only, on the helpers that were merged.
- Independent of the other zarr 3 script fixes (`tifs_to_ome_zarr`, `extract_sparse_ome_zarr`, `fill_inner_outer_labels`): different files; `git merge-tree --write-tree` merges this branch cleanly with each of them.

AI-assisted, human-directed.
