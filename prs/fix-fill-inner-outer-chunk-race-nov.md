Replaces #2109, which the idle bot closed.

**In one sentence:** `fill_inner_outer_labels.py` gives the same output with `--workers 4` as with `--workers 1`, instead of silently dropping whole filled slices when several workers write into the same output chunk.

**One real example:** Starting with the public PHercParis4 m7-L2 surface prediction (`PHercParis4/representations/predictions/surfaces/20260411134726-surface-20260413222639-surface-m7-L2-th0.2.zarr`, levels 4 and 5), I ran the script with `--skip-outer --workers 4` three times on main and three times on this branch, in single-pass and in two-phase mode, and compared every run voxel for voxel with a `--workers 1` run of main. All six branch runs match it exactly; every main run lost 51 to 73 slices.

**Before:** Both modes write one z-slice per task, but the output array copies the input's chunk shape (192×192×192 here), so neighbouring slices of one chunk are written at the same time by different processes (single-pass) or threads (two-phase). Each slice write reads, modifies and rewrites the whole chunk, so writers overwrite each other's slices. The run exits 0 and still prints the full `Filled N pixels` total, and the lost slices change from run to run.

**After this PR:** Slices are grouped by the output z-chunk they write to (taking the compute-to-output upscale into account) and each group is written in order by one worker. The per-slice computation is unchanged.

**Proof:** differing slices, nonempty slices and nonzero voxels of each output against the `--workers 1` reference from main (same input, same flags):

Single-pass, `--compute-level 5 --output-level 5`, output shape 593×256×256. Reference: 174 nonempty slices, 26,835 nonzero voxels.

| Run (`--workers 4`) | Differing slices | Nonempty slices | Nonzero voxels |
|---|---:|---:|---:|
| main 1 | 51 | 124 | 11,463 (−15,372) |
| main 2 | 61 | 113 | 19,662 (−7,173) |
| main 3 | 63 | 111 | 11,664 (−15,171) |
| branch 1 | 0 | 174 | 26,835 |
| branch 2 | 0 | 174 | 26,835 |
| branch 3 | 0 | 174 | 26,835 |

Two-phase, `--compute-level 5 --output-level 4`, output shape 1185×511×511. Reference: 347 nonempty slices, 210,708 nonzero voxels.

| Run (`--workers 4`) | Differing slices | Nonempty slices | Nonzero voxels |
|---|---:|---:|---:|
| main 1 | 73 | 275 | 149,624 (−61,084) |
| main 2 | 57 | 292 | 158,876 (−51,832) |
| main 3 | 65 | 288 | 140,132 (−70,576) |
| branch 1 | 0 | 347 | 210,708 |
| branch 2 | 0 | 347 | 210,708 |
| branch 3 | 0 | 347 | 210,708 |

Every main run above still printed `Complete! Filled 26,835 pixels` (single-pass) or `Complete! Filled 210,708 pixels` (two-phase), the same as the reference.

**Why / where this is useful:** Anyone filling the inner/outer regions of a label or prediction volume with the default worker count (all CPUs) gets an output with missing slices and no warning. With this change the output no longer depends on `--workers` or timing.

- [ ] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

- Change: `vesuvius/src/vesuvius/scripts/fill_inner_outer_labels.py` (`group_by_output_chunk`, plus one task per group in both modes) and a new test `vesuvius/tests/scripts/test_fill_inner_outer_labels.py`.
- Tested: upstream main `d57c28ebe` vs this branch `12bd346` (one commit on top of `d57c28ebe`), Linux x86_64, 4 CPUs, Python 3.14, zarr 2.18.7, numcodecs 0.15.2.
- `--skip-outer` is used because the outer fill subsamples points with `np.random.choice`, so it is not deterministic even with one worker. The inner fill is deterministic, so any difference from the reference comes from the writes.
- Data: levels 4 and 5 (plus `.zattrs`/`.zgroup`) of the surface prediction above, downloaded from `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/` into a local `m7.zarr`.
- Commands (from `vesuvius/` of each checkout; one run at a time; output removed before each run):

```
# reference, upstream main, one worker
python src/vesuvius/scripts/fill_inner_outer_labels.py m7.zarr ref-single.zarr --skip-outer --compute-level 5 --output-level 5 --workers 1
python src/vesuvius/scripts/fill_inner_outer_labels.py m7.zarr ref-two.zarr    --skip-outer --compute-level 5 --output-level 4 --workers 1
# three times each on main and on this branch
python src/vesuvius/scripts/fill_inner_outer_labels.py m7.zarr out-single-$i.zarr --skip-outer --compute-level 5 --output-level 5 --workers 4
python src/vesuvius/scripts/fill_inner_outer_labels.py m7.zarr out-two-$i.zarr    --skip-outer --compute-level 5 --output-level 4 --workers 4
```

  Comparison: read the whole output level with zarr; a slice "differs" if any voxel in it differs from the reference; "nonempty" means any nonzero voxel in the slice.
- Tests: `PYTHONPATH=src python -m pytest -q tests/scripts/test_fill_inner_outer_labels.py`: 6 passed on the branch; on main the module fails to import (`cannot import name 'group_by_output_chunk'`). The tests check that no output chunk is written by two groups for aligned, unaligned and upscaled slice ranges. The race itself depends on timing, so the real-data runs above are the main proof.
- Trade-off: a z range spanning k output chunks runs at most k tasks at once, so a small `--z-min/--z-max` window gets less parallelism.
- Not part of this PR: with the zarr version in `vesuvius/uv.lock` (3.2.1) the script fails on both main and this branch before any slice is processed (`AttributeError: 'Group' object has no attribute 'create_dataset'` in `create_output_zarr`), so these runs used zarr 2.18.7, which `pyproject.toml` allows.

AI-assisted (Claude Code), human-directed.
