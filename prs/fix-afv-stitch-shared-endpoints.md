**In one sentence:** `vesuvius.afv_spline_generator` (the fiber generator VC3D runs) now joins two splines of one fiber whose ends touch. Before, it wrote them as separate fibers, or dropped both as too short, while it joined the same two splines when they were 0.5 voxels apart.

**One real example:** Starting with a 256³ crop of the published PHercParis4 fiber `presence` prediction (level 3, z/y/x origin 4608/1920/1920), I ran the generator's spline fitting, stitching and cleanup with the CLI defaults, using that crop as the fiber probability. On main, 70 fibers (9,731 voxels of polyline) reach the default `--min-length 100`. On this branch, 74 fibers (10,360 voxels, +6.5 %) reach it.

**Before:** `Catalog._compare_pair` (`extend/catalog.py`) proposes a gap join only for end points `.25 <= distance <= GAP_CAP` apart. `fit_portions` (`splines.py`) splits a chain it cannot fit in one spline at half its length, and both halves keep the cut vertex. Their fitted ends are therefore less than 0.25 voxels apart (exactly 0 on a straight chain), so they never become a join candidate. Two collinear pieces sharing an end point stay two fibers, with or without `--extend`. Moving one piece 0.5 voxels away makes them one fiber.

**After this PR:** Below 0.25 voxels the join direction, which was `delta / distance`, comes from the first spline's end-point tangent. All the existing tests still apply: angle ≤ 25° for a candidate; ≤ 12°, mutual tangents within 15° and reliable tips for a strict (accepted) join; plus the ambiguity margin, the obstruction check and the crossing-bridge check. Pieces that meet at an angle are therefore still kept apart. The diff is 2 lines.

**Proof:** same crop, same parameters (`--threshold 60`, `--max-join-angle 45`, `--min-length 100`, one 512-voxel block as the CLI plans for a 256³ zone):

| | splines | same-family end pairs < 0.25 vx | stitched fibers | written fibers (≥ 100 vx) | written length (vx) | longest |
|---|---|---|---|---|---|---|
| main `812d7a893` | 3482 | 438 | 3410 | 70 | 9,731 | 284 |
| branch `60aaa22f7` | 3482 | 438 | 3357 | 74 | 10,360 | 284 |

53 more joins. The total polyline length before cleanup is unchanged (84,088 vs 84,096 vx; the +8 vx are the bridges of the new joins), so nothing is lost or invented: pieces are only connected. On a smaller 128³ crop (origin 4736/2000/2000), the stitched fibers go from 506 to 503 (one block) and from 593 to 591 (8 blocks of 64). Its written fibers are unchanged, because no fiber in that crop reaches 100 voxels.

Regression test `test_splines_meeting_at_a_shared_end_point_become_one_fiber` (two collinear splines, x 10→60 and 60→130, in one block): it fails on main (`assert 2 == 1`) and passes on the branch.

**Why / where this is useful:** Anyone creating an Automated Fiber Volume in VC3D (Fiber Collection Generator), or running `vesuvius.afv_spline_generator`, gets longer fibers wherever the spline fit had to split a curving fiber, instead of fragments that `--min-length` removes.

- [ ] I personally verified that the example and proof above were produced by this PR on the stated data.

## Details

- Change: `vesuvius/src/vesuvius/afv_spline_generator/extend/catalog.py` (2 lines in `_compare_pair`) and one test in `vesuvius/tests/afv_spline_generator/test_stitch.py`.
- The code is used. It is the console script `vesuvius.afv_spline_generator`, and VC3D runs it, through `cli.generate` → `extend.stitch.Stitcher` → `extend.catalog.Catalog`, on every run (with or without `--extend`):
  ```
  $ git grep -n afv_spline_generator upstream/main -- vesuvius/pyproject.toml volume-cartographer/apps/VC3D/FiberCollectionGenerator.hpp vesuvius/README.md
  vesuvius/README.md:30:| `vesuvius.afv_spline_generator` | `afv_spline_generator.cli` | [predicts fibers](docs/afv_spline_generator.md) ...
  vesuvius/pyproject.toml:230:"vesuvius.afv_spline_generator" = "vesuvius.afv_spline_generator.cli:main"
  volume-cartographer/apps/VC3D/FiberCollectionGenerator.hpp:18:inline constexpr auto kModule = "vesuvius.afv_spline_generator";
  $ git grep -n "extend.stitch import\|from .catalog import" upstream/main -- vesuvius/src
  vesuvius/src/vesuvius/afv_spline_generator/cli.py:337:    from .extend.stitch import Stitcher
  vesuvius/src/vesuvius/afv_spline_generator/extend/stitch.py:18:from .catalog import Catalog, point_count
  ```
- What is real and what is not: the fiber model (`Qualzz20/afv_fiber_9um` on Hugging Face) could not be downloaded in my environment (blocked), and the bucket has no output of it. So the network step (`predict_fibers`) is replaced by a published fiber prediction of a real scroll: `PHercParis4/representations/predictions/fibers/20260411134726-fibers-20260915212757-L1/PHercParis4-20260411134726-las-sd1-7ff0ce6c_presence.ome.zarr/3` from `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/`. I passed it as the vertical channel (horizontal and intersection set to 0). Everything after the network is the generator's own code, unchanged: `extract_splines`, `Stitcher.add_block` with the CLI's block plan and 32-voxel margins, `Stitcher.stitched`, and `clean` with the CLI defaults. The model itself was not run.
- Commands (from `vesuvius/`, `PYTHONPATH=src`, Python 3.12, numpy/scipy/scikit-image current, zarr 3.2.1), run on each checkout:
  ```
  python fetch.py 4608 1920 1920 256 c2.npy   # a[z:z+n, y:y+n, x:x+n] of the level-3 presence array above, saved as .npy
  python real.py c2.npy 512
  ```
  `real.py`:
  ```python
  import sys, tempfile, numpy as np
  from vesuvius.afv_spline_generator.splines import extract_splines, threshold_to_u8
  from vesuvius.afv_spline_generator.extend.stitch import Stitcher
  from vesuvius.afv_spline_generator.cli import zone_blocks, BLOCK_MARGIN, DEFAULT_THRESHOLD, DEFAULT_MAX_JOIN_ANGLE, DEFAULT_MIN_LENGTH
  from vesuvius.afv_spline_generator.cleanup import clean, arclength
  pres = np.load(sys.argv[1]); block = int(sys.argv[2])
  shape_xyz = np.asarray(pres.shape[::-1])
  probs = np.zeros(pres.shape + (3,), np.uint8); probs[..., 0] = pres
  thr = threshold_to_u8(DEFAULT_THRESHOLD)
  blocks = zone_blocks([0, 0, 0], list(shape_xyz), block)
  with tempfile.TemporaryDirectory() as d:
      st = Stitcher(d)
      for i, (o, s) in enumerate(blocks):
          low = np.maximum(np.asarray(o) - BLOCK_MARGIN, 0)
          high = np.minimum(np.asarray(o) + np.asarray(s) + BLOCK_MARGIN, shape_xyz)
          tr = extract_splines(probs[low[2]:high[2], low[1]:high[1], low[0]:high[0]], thr)
          st.add_block(f"block-{i}", low.tolist(), (high - low).tolist(), tr, (np.asarray(o), np.asarray(o) + np.asarray(s)))
      traces = st.stitched(); st.close()
  L = lambda t: arclength(np.asarray(t["points"], float))[-1]
  out = clean(traces, DEFAULT_MAX_JOIN_ANGLE, DEFAULT_MIN_LENGTH)
  print(len(traces), len(out), sum(map(L, out)), max(map(L, out)))
  ```
  (The "end pairs < 0.25 vx" column counts, per block, the same-family spline pairs with an end within 0.25 voxels of the other's end.)
- Why the remaining near-touching pairs are not joined: in the 128³ crop, 54 of the 61 such pairs involve a spline shorter than 16 voxels, which the catalogue never ingests (`point_count < 5`). Of the 7 others, 3 pass the existing gates and are joined on the branch. 2 have an unreliable tip, 1 turns 12–25° and 1 turns more than 25°; those stay apart, as before.
- Tests: `PYTHONPATH=src python -m pytest -q tests/afv_spline_generator` on Python 3.14 with `vc_object_store` built from `../vc_object_store`: branch 56 passed, 1 skipped; main 55 passed, 1 skipped, 1 failed (the new test).
- A join at distance < 0.25 is recorded as a `gap` bridge of that length (0 for coincident ends), as before for longer gaps. `_gap_ranges` drops zero-length bridges (`a != b`), so they are not reported as `inferred_gap_point_ranges`.
- Not changed, seen while testing: on synthetic straight fibers with small `--block-size`, two other things happen. A fiber can be written twice when one block's copy starts 2 voxels earlier than its neighbour's: neither copy is contained in the other, and the overlap leaves less than `MIN_UNIQUE_TAIL`. Also, pieces shorter than `MIN_OVERLAP` that overlap across blocks are not joined. Both are tuning of the overlap rules, not this bug, and are left alone.

AI-assisted, human-directed.
