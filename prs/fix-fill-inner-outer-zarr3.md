**In one sentence:** `fill_inner_outer_labels.py` runs on the zarr version in `vesuvius/uv.lock` (3.2.1) instead of crashing before it processes any slice, and writes the same voxels as main does under zarr 2.

**One real example:** Starting with the public PHercParis4 m7-L2 surface prediction (`PHercParis4/representations/predictions/surfaces/20260411134726-surface-20260413222639-surface-m7-L2-th0.2.zarr`, levels 4 and 5), I ran `fill_inner_outer_labels --skip-outer --workers 1` in single-pass and in two-phase mode under zarr 3.2.1. On main both runs die with `AttributeError: 'Group' object has no attribute 'create_dataset'`. On this branch both complete, and both outputs are voxel-identical to main's output under zarr 2.18.7.

**Before:** `create_output_zarr` opens the output with `zarr.open(mode="w")` and calls `Group.create_dataset`, which zarr 3 removed. Under the locked zarr the script exits 1 before processing any slice, and it leaves an empty zarr v3 group (`zarr.json` only) at the output path.

**After this PR:** The output level is created with `create_level_dataset` (`image_proc/run/zarr_tasks/utils.py`), the helper the zarr_tasks scale, recompress and merge tasks use (merge since #2244), and the output group is opened with `open_zarr_group` (`data/utils.py`). Both work on zarr 2 and zarr 3 and write a zarr v2 store. The rest of the script is unchanged.

**Proof:** same input, same flags, `--skip-outer --workers 1`. Reference = upstream main under zarr 2.18.7 + numcodecs 0.15.2.

| Run | zarr | Exit | Result |
|---|---|---|---|
| main, single-pass (`--compute-level 5 --output-level 5`) | 3.2.1 | 1 | `AttributeError: 'Group' object has no attribute 'create_dataset'` (`fill_inner_outer_labels.py:659`, in `create_output_zarr`) |
| main, two-phase (`--compute-level 5 --output-level 4`) | 3.2.1 | 1 | same error |
| main, single-pass (reference) | 2.18.7 | 0 | 593×256×256, 26,835 voxels = 255 |
| main, two-phase (reference) | 2.18.7 | 0 | 1185×511×511, 210,708 voxels = 255 |
| branch, single-pass | 3.2.1 | 0 | identical to reference (0 differing voxels) |
| branch, two-phase | 3.2.1 | 0 | identical to reference (0 differing voxels) |
| branch, single-pass | 2.18.7 | 0 | identical to reference (0 differing voxels) |
| branch, two-phase | 2.18.7 | 0 | identical to reference (0 differing voxels) |

SHA-1 of the output level bytes: single-pass `92e504ad925c…` and two-phase `ee684809524b…` for the reference and all four branch runs. Every branch output has `.zgroup` = `{"zarr_format": 2}`, no `zarr.json`, and the input's `.zattrs` (`multiscales`) copied over.

**Why / where this is useful:** Anyone who installs `vesuvius` from the lockfile and fills the inner/outer regions of a label or prediction volume can run the script again; today it fails on its first zarr write.

- [ ] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

- Change: `vesuvius/src/vesuvius/scripts/fill_inner_outer_labels.py`, `create_output_zarr` only (2 imports, the two output-group opens, the level creation), and a new test `vesuvius/tests/scripts/test_fill_inner_outer_labels_zarr3.py`.
- Tested: upstream main `d57c28ebe` vs this branch `e5283e277` (one commit on top of `d57c28ebe`), Linux x86_64, 4 CPUs, Python 3.14. zarr 3.2.1 + numcodecs 0.16.5 (the `uv.lock` versions) and zarr 2.18.7 + numcodecs 0.15.2 (the `pyproject.toml` lower bound).
- Other zarr calls in the script, checked under zarr 3.2.1: `input_arr.compressor` still works on a v2 array (it only emits a `ZarrDeprecationWarning`); `attrs.update` works; the workers' and phase 2's `zarr.open(..., mode="r+")` open the v2 output correctly. The `create_dataset` crash was the only failure; both modes complete end to end.
- Data: levels 4 and 5 (plus `.zattrs`/`.zgroup`) of the surface prediction above, downloaded from `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/` into a local `m7.zarr` (11 chunks are absent in the bucket and read as the fill value 0 on both sides).
- Commands (from `vesuvius/` of each checkout, `PYTHONPATH=src`; output removed before each run):

```
python -m vesuvius.scripts.fill_inner_outer_labels m7.zarr out-single.zarr --skip-outer --workers 1 --compute-level 5 --output-level 5
python -m vesuvius.scripts.fill_inner_outer_labels m7.zarr out-two.zarr    --skip-outer --workers 1 --compute-level 5 --output-level 4
```

  Comparison: read the whole output level with zarr and `np.array_equal` against the reference.
- Rerun after a crash on main: the empty `zarr.json` group main leaves behind is converted to v2 by `open_zarr_group` (it does this for empty v3 groups); a branch run over that leftover (`--z-min 0 --z-max 40`, zarr 3.2.1) completed and slices 0–39 match the reference.
- Tests: `PYTHONPATH=src python -m pytest -q tests/scripts/test_fill_inner_outer_labels_zarr3.py` runs the script's `main()` on a small synthetic ring volume in single-pass and two-phase mode and checks the written voxels against `detect_inner_region`/`upscale_mask`, plus that the output is zarr v2 with the input's attrs. Branch: 3 passed under zarr 3.2.1 and under zarr 2.18.7. Main: 3 failed under zarr 3.2.1 (`AttributeError: 'Group' object has no attribute 'create_dataset'`), 3 passed under zarr 2.18.7. `tests/scripts`, `tests/image_proc/test_create_level_dataset.py` and `tests/image_proc/test_merge_task_levels.py`: 22 passed on the branch under both zarr versions.
- On-disk differences from main under zarr 2 (values are identical): chunk keys are nested (`dimension_separator "/"`, which is also what the input uses) instead of zarr 2's default `.`; `fill_value` is 0 (`create_level_dataset` sets it) instead of copied from the input. The input here has fill value 0, so nothing changes for it; an input with a non-zero fill value would differ only in slices outside `--z-min/--z-max` in two-phase mode, which the script never writes. Chunks that hold only zeros are not written (`write_empty_chunks=False`).
- The script now imports from `vesuvius`, so running it by file path needs the package installed or `PYTHONPATH=src` (`python -m vesuvius.scripts.fill_inner_outer_labels` as above).
- Independent of the race fix on `fix/fill-inner-outer-chunk-race-nov` (`12bd34699`, one worker per output z-chunk). Both change `fill_inner_outer_labels.py`, but in different functions (this PR: `create_output_zarr` and the imports; the race fix: new helpers `group_by_output_chunk`, `process_and_write_slices`, `write_slices_with_fill` and the task submission in `main`), and their tests are separate files. `git merge-tree --write-tree e5283e277 12bd34699` merges cleanly with no conflicts; on the merged tree `tests/scripts` passes (18 passed) under zarr 3.2.1 and zarr 2.18.7. The merged code was not run on the real data.
- Same pattern as #2244 (zarr_tasks merge) and #1700 (structure_tensor).

AI-assisted (Claude Code), human-directed.
