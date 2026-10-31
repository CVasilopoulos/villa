# Triage: open ScrollPrize/villa issues created on or after 2026-10-08 (checked 2026-10-31). No new fix branch this run: every code-fixable issue already has a PR, a posted branch or a stated claim.

Skipped as already triaged (not ours): #2058, #2078, #2092, #2243.

| # | Title | Verdict | Reason |
|---|---|---|---|
| 2391 | lasagna Offset configs: offset.json keeps the surface on its start winding, and offset_snap.json does not parse | skip | Reporter offers to send the PR (comma + pred_dt); weight retuning is a maintainer/research call |
| 2371 | download_required_zarr_chunks: wrong tifxyz place at volume_scale > 0 | skip | Open PR #2379 by the reporter |
| 2370 | ink/ bucket: HF65 canvases do not line up with the tifxyz beside them | skip | Data-only (published bucket alignment) |
| 2369 | ink/man5/MAN5_outer_3: label zarrs 59 px smaller than the segment grid | skip | Data-only |
| 2346 | Rendering parameters for the 65-slice PHercParis4 HF volumes | skip | Question / data provenance, no code fix |
| 2320 | vc_object_ingest refuses the published fiber annotations (no target_uuid) | skip | Reporter has draft PR #2321 |
| 2312 | PHercParis4: request a 1B transform or bridge to the 2.4 um scan | skip | Data request |
| 2310 | PHercParis4: request targeted CT ROI and manual continuity records | skip | Data request |
| 2299 | vesuvius: locked wandb 0.28 can't find a W&B Forge login | skip | Lock bump left to maintainers by reporter; docs workaround in #2298; needs a W&B account |
| 2294 | render_ink.py memory / caches | skip | Reporter has a tested patch; stantheman0128 has branch fix-2294 and will open the PR |
| 2279 | tifxyz meta.json has no isometry numbers | skip | Open PR #2352 |
| 2277 | Ink loading slows under CPU quota (Numba pools) | skip | Draft PR #2311 (and closed #2357) |
| 2264 | Fiber evaluation: reference line drawn by beam tracer | skip | Research/evaluation; related PRs #2265, #2377 |
| 2246 | Linear surface interpolation keeps the normal constant per cell | skip | Open PR #2247 |
| 2239 | One umbilicus JSON, two different scroll centers | skip | Draft PR #2242 |
| 2222 | Saving a segment in VC3D deletes its subfolders | skip | Draft PR #2223; GUI |
| 2167 | PHerc0139: w036 lies inside w034 | skip | Data/annotation |
| 2153 | Linux AppImage: CLI tools fail on headless servers | skip | Docs PR #2259 merged; packaging |
| 2144 | surfaces/kaggle labels: 6 holes are pockets between merged sheets | skip | Data/labels; related PR #2147 |
| 2135 | vesuvius.zarr_tasks pyramid levels one voxel short | skip | Draft PR #2136 by reporter |
| 2125 | Proposal: Bacterial Apatite Triage (XRF screening) | skip | Research proposal |
| 2119 | vc_render_tifxyz: uint8 output truncated, not rounded | skip | Draft PR #2122 |
| 2107 | ink/ label bucket: level 2 holds only 17 of 65 depth slices | skip | Data-only; code-side PRs #2256, #2303 open |
| 2106 | metadata.json: z_direction_is_top_to_bottom null on 13 volumes | skip | Catalog data |
| 2105 | spiral-fitting README: PHerc0826 example says CW | skip | PR #2111 closed by maintainer with orientation unverified against the scan; needs scan check, not a doc edit |
| 2104 | vc_grow_seg_from_seed with x/y/z limits stops growing | skip | Draft PR #2389 plus open #2278 |
| 2080 | vc_grow_seg_from_seed without normal_grid_path ignores the volume | skip | Draft PR #2081 |
| 2072 | sheet tracer: area_cm2 uses the checkpoint's 9.6 um | skip | Open PR #2073 |
| 2049 | VC3D releases are deleted on promotion | skip | Open PR #2351; CI/release process |
| 2029 | spiral-fitting: umbilicus loss and transform use two centres | skip | Draft PR #2030 |
