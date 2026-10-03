# PHYS-TIRE-04 solver-timing accuracy audit

Generated UTC: 2026-10-01T17:01:51.965718+00:00

Read-only audit of the 12 existing trial JSON and 12 JSONL.gz traces. No simulation was run. Each trace contains 720 ticks and four wheel records per tick. Timing arrays are intentionally excluded from repeated-run equality because wall time is the measured variable; full decoded trace bytes and all other trial JSON metadata were compared.

## A/B source paths and deterministic inputs

A loads modules from `B:\AI agent\暑期计算机程序设计\CoastalDrive\docs\evidence\PHYS-TIRE-04\mechanical-rigid\baseline-source` (archived baseline tree); B loads from `B:\AI agent\暑期计算机程序设计\CoastalDrive` (live project tree). Each variant resolves 183 source files. Each run's before/after SHA maps match; A and B differ in 77 source-file hashes. Exact module map and source-manifest digests are in `accuracy-audit.json`.

A/B use the same full per-case vehicle configuration, input configuration, initial snapshot, and every per-tick command. For each case, A repetitions 0/3 and B repetitions 1/2 have byte-identical decompressed traces and identical non-timing JSON metadata. The recorded command order is A, B, B, A. Full configs, input configs, and initial snapshots are retained in the JSON audit.

## Accuracy metrics

| Case | Variant | max recorded |force_residual| (N) | strict grip excess count | max excess (N) | minimum signed road dissipation (J/tick/wheel) | location | endpoint work proxy `.001*|patch speed|*dt` (J) |
|---|---:|---:|---:|---:|---:|---|---:|
| acceleration | A | 0.000963758327703 | 0 | 0 | -1.16293319066e-06 | tick 12, wheel 2 | 2.8840268248475907e-12 |
| acceleration | B | 0.000963762454646 | 0 | 0 | -1.16300556598e-06 | tick 12, wheel 2 | 2.8840301342345133e-12 |
| constant-turn | A | 0.000934359418597 | 0 | 0 | 5.19129207994e-06 | tick 1, wheel 0 | 3.503175778205052e-09 |
| constant-turn | B | 0.000934234134712 | 0 | 0 | 5.19133723097e-06 | tick 1, wheel 0 | 3.5032285289288706e-09 |
| asphalt-brake | A | 0.000992279403941 | 6 | 7.73070496507e-11 | -2.83422173287e-10 | tick 375, wheel 0 | 6.600082398810379e-16 |
| asphalt-brake | B | 0.000994765633014 | 4 | 8.77662387211e-11 | -6.63727879025e-09 | tick 461, wheel 1 | 3.954916811580028e-14 |

The stored `force_residual` is the coupled solver’s `max(force_error, brake_error)`, not a separately recorded pure force-equation residual. Grip was checked against force-phase `force_grip` using strict `hypot(fx,fy) > force_grip`; no tolerance was added. Tiny strict exceedances are preserved as measured.

The negative road minima are retained as signed values. `force_patch_kappa/alpha` and longitudinal speed permit reconstructing the final saved patch-slip speed because the source defines `denominator=max(abs(vx), slip_speed)`, `patch_x=kappa*denominator`, and `patch_y=-denominator*tan(alpha)`. The requested `.001 N * patch_speed * dt` value is reported as an endpoint proxy using body `dt`; a substep proxy is also stored per minimum row.

The per-tick `road_dissipation` field sums signed per-substep `sub_dt * dot(force, patch)` over two substeps. Since the raw rows store only the final substep patch speed and residual, an exact aggregate residual-work bound over both substeps cannot be calculated from these files alone. That aggregate-bound field is therefore left unknown in `accuracy-audit.json`; no negative value is clamped and no acceptance threshold is relaxed.

Repeat identity excludes only per-run wall-time values and the trajectory filename. It includes full configuration, initialization, before/after source hashes, final state, and the exact decompressed JSONL contents. The 0-byte adjacent `.log` files do not provide additional diagnostics.

## Full-substep work audit

The later [full-substep recording](residual-work-v2/summary.json) records all 34,560 wheel-substeps of these six trials and reproduces every timed-trace row exactly. The [gate-bound audit](residual-work-v2/gate-bound-audit.json) uses the original 0.001 N force gate: rolling work error is bounded by `h epsilon |patch|`; the static projection additionally permits `h epsilon D/(Kh+b)`. Every substep and macro sum stays within that bound, with no negative-work clamp. A tighter bound based on the actual recorded residual has four near-machine-precision exceptions, retained in the raw audit. This does not change the earlier CSV-only limitation or claim that actual-residual bounds pass strictly.

These timing and work trials use the original Box representation. They isolate the optimizer, not the later production Hull migration.
