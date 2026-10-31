# zarr 3 survey: `vesuvius/src/vesuvius/scripts/` and `vesuvius/src/vesuvius/*.py`

Upstream main `d57c28ebe`, zarr 3.2.1 + numcodecs 0.16.5 (`uv.lock`) vs zarr 2.18.7 + numcodecs 0.15.2 (control), Python 3.14, Linux x86_64.

Searched for APIs that zarr 3.2.1 no longer has (checked with `hasattr` on 3.2.1): `Group.create_dataset`, `Group.require_dataset`, `Group.array`, `Group.visititems`, `Array.chunk_store`, `zarr.DirectoryStore`/`NestedDirectoryStore`/`FSStore`/`LRUStoreCache`/`N5Store`, `zarr.convenience`/`hierarchy`/`creation`, synchronizers. Only `create_dataset` occurs in these files.

Synthetic inputs (made by a scratch script, not committed): 8 TIFFs of 32×32 uint8; one 16×16 tifxyz plane in a 32³ volume (+ a 16×16 `_inklabels.png` of 255); a zarr v2 source with levels 0 (32³) and 1 (16³). Every crashing script ran to completion on the same input under zarr 2.18.7.

| File | Call site | Crashes under zarr 3.2.1? (how verified) | Existing PR/issue | Separate PR? |
|---|---|---|---|---|
| `scripts/fill_inner_outer_labels.py` | `create_output_zarr`: `output_store.create_dataset` (l. 659) | Yes, `AttributeError: 'Group' object has no attribute 'create_dataset'` (ran on real m7-L2 data, both modes) | none open; fixed on fork branch `fix/fill-inner-outer-zarr3` | Yes (drafted: `prs/fix-fill-inner-outer-zarr3.md`) |
| `scripts/tifs_to_ome_zarr.py` | `convert_tifs_to_ome_zarr`: `root.create_dataset` (l. 709, level 0); `generate_pyramid_levels`: `root.create_dataset` (l. 555) | Yes, same AttributeError at l. 709 before level 0 is written (ran `tifs_to_ome_zarr tifs out.zarr --num-levels 2 --chunk-size 16 --workers 1`; zarr 2: exit 0). l. 555 is not reached; by reading it fails the same way. `zarr.open(mode="w")` (l. 706) would also create a v3 group | none found (searched `tifs_to_ome_zarr` in PRs and issues; #1682/#1670 only matched on generic words) | Yes; small, same `create_level_dataset` pattern for both call sites |
| `scripts/labels_to_zarr.py` | `main`: `root.create_dataset` (l. 1850, level 0); `generate_pyramid_levels`: `root.create_dataset` (l. 1668) | Yes, same AttributeError at l. 1850 before any label is written (ran `labels_to_zarr segs_l --label-suffix _inklabels --label-value 255 --output out.zarr --shape 32 32 32 --chunks 16 16 16 --num-workers 1 --num-levels 2 --padding 0`; zarr 2: exit 0) | #1200 (closed, not merged, NanokodasKarolis) bundled a zarr 3 fix with an EDT expansion fix, using `create_array` + `zarr_format=2`, which does not exist on zarr 2. No open PR or issue | Yes; check with the #1200 author's claim first (closed, so not a live duplicate) |
| `scripts/extract_sparse_ome_zarr.py` | `extract_sparse_ome_zarr`: `root.create_dataset` (l. 431) | Yes, same AttributeError at l. 431 (ran `extract_sparse_ome_zarr src.zarr out.zarr --tifxyz segs --num-levels 2 --workers 1`; zarr 2: exit 0, 9 chunks). Also `src_arr.compressor` (l. 402) only warns on 3.2.1 | none found | Yes, small |
| `label_zarr.py` | `create_v2_array`: `group.create_dataset` (l. 141) | No: guarded by `_ZARR_V3`, uses `create_array` on zarr 3. Verified: `create_label_group` + `create_v2_array` wrote and read back an 8³ array (zarr_format 2) under 3.2.1 | n/a | No |
| `surface_preflight.py` | `zarr.open(store, mode="r")` (l. 189) | No removed API (by reading) | n/a | No |
| `scripts/build_chunk_occupancy.py`, `crop_tif_stack.py`, `detect_holes.py`, `fix_holes.py`, `hole_viewer.py`; `__init__.py`, `_version.py`, `tifxyz_canvas.py` | no zarr calls (zarr only through `data/zarr_chunk_index`, outside this survey's scope) | No (by reading) | n/a | No |

Notes
- Only the first crash per script was observed at runtime; later call sites (pyramid levels in `tifs_to_ome_zarr` and `labels_to_zarr`) are by reading.
- Open-PR limit: each new PR counts against the 3 open non-draft PRs for users without write access; `tifs_to_ome_zarr`, `labels_to_zarr` and `extract_sparse_ome_zarr` could also go in one PR ("scripts: create zarr levels through create_level_dataset"), but maintainers prefer small ones.
