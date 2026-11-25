# Historical hull reference audit (data v0.2.3)

Analysis only: no reference data, cohorts or scores changed.

## Source and checks

The original [MP archive](https://api.figshare.com/v2/file/download/40344436) was
retrieved from the file pinned by the [Matbench Discovery data manifest](https://github.com/janosh/matbench-discovery/blob/main/matbench_discovery/data-files.yml).
It contains 154,718 entries. Its decompressed SHA256 exactly matches the
benchmark `01_refined_structures_191/mp_hull/summary.json`:

`f196b04bfa9d2337503726d23025b652033909610281cbef9752b514bc2f4563`.

The persisted gzip is 179,351,659 bytes; MD5 `76fc748db6b175bb80de4c276d27c235`.
All 19 exact-composition entries for these nine materials were examined. Their
raw energies, corrections and corrected energies reproduce the delivered
`mp_hull/mp_reference_entries.json` values within 1e-9 eV/atom. All nine stored
hull distances reconstruct arithmetically. The exported structures and J-static
design geometries match at ltol=0.02, stol=0.02, angle_tol=1 degree without volume
scaling, including supercells. No mixed-geometry arithmetic error was found.

Other source files, relative to the extracted benchmark dataset root:

- `01_refined_structures_191/mp_hull/results.json` (decompositions and distances).
- `01_refined_structures_191/mp_hull/compatibility_audit.json` (benchmark entries and corrections).
- `01_refined_structures_191/<material>/energy_reference.json`, `reference.json`, `INCAR` and `CONTCAR`.
- `targets/ground_state.json` and `targets/hull.json`.

StructureMatcher uses ltol=0.2, stol=0.3, angle_tol=5 degrees, primitive-cell
reduction, isotropic scale normalization and supercell matching. A second check
uses 0.05, 0.1 and 2 degrees. A geometric match is a relaxed structural variant,
not identity of the magnetic state or proof of the same polymorph. Space groups
(symprec=0.01 A), volumes and both match results are reported below. RMS distances
are normalized by the average free length per atom.

The benchmark is VASP/PBE, with the declared legacy POTCAR set and MP2020
Advanced corrections (`strict_anions=no_check`, symbols checked, hashes unchecked).
For every available same-composition MP entry, the POTCAR titles and U values
match the benchmark. This supports a common **declared** VASP/PBE energy zero;
absolute POTCAR byte identity cannot be established from a combined benchmark
SHA256 and the individual MP POTCAR hashes. Corrections are applied exactly once.

The measured pattern is mixed signs on the benchmark magnetic elements versus
parallel dominant MP moments. Here dominant means abs(moment) >= max(0.1 muB,
10% of that element-set maximum), excluding small induced anion moments. This is
a diagnostic description of the supplied collinear cells, not a magnetic ground-state
determination. Energy lowering due to the AFM-like state is an **inference**:
relaxation and numerical settings also differ, so causality needs matched DFT runs.

## Nine outliers

| ID | Material | Hull (meV/atom) | Raw / corrected benchmark (eV/atom) | MP hull (eV/atom) | C (eV/cell) | Assessment |
|---|---|---:|---|---:|---:|---|
| 028 | Co3O4 | -70.551626 | -6.150903305 / -7.245474733 | -7.174923107 | -15.324000 | plausible |
| 082 | KFeS2 | -87.988970 | -5.305495351 / -5.556995351 | -5.469006381 | -2.012000 | plausible |
| 083 | KMnAs | -85.847128 | -5.365380455 / -5.365380455 | -5.279533327 | 0.000000 | plausible |
| 093 | LaMnAsO | -65.881994 | -7.368438830 / -7.957188830 | -7.891306836 | -4.710000 | suspect |
| 129 | NaMnAs | -117.097685 | -5.469284545 / -5.469284545 | -5.352186860 | 0.000000 | plausible |
| 144 | RbFeS2 | -94.196029 | -5.282392884 / -5.533892884 | -5.439696855 | -2.012000 | plausible |
| 145 | RbFeSe2 | -89.599768 | -4.860924113 / -5.096924112 | -5.007324345 | -1.888000 | plausible |
| 146 | RbMnAs | -61.717717 | -5.277646478 / -5.277646478 | -5.215928761 | 0.000000 | plausible |
| 183 | MnTe | -57.251612 | -6.302303738 / -6.513303738 | -6.456052127 | -0.844000 | plausible |

### 028 Co3O4

Benchmark source: `01_refined_structures_191/028_Co3O4/energy_reference.json` and `reference.json`.
Structure: Fd-3m (No. 227), 9.681056 A^3/atom; MAGNDATA 0.463. Magnetic-element moments in source order (muB): Co:-2.642, Co:+0.000, Co:+0.000, Co:+0.000, Co:+0.000, Co:+2.642.
POTCAR set: `['PAW_PBE Co 06Sep2000', 'PAW_PBE O 08Apr2002']`.
Combined benchmark POTCAR SHA256: `35def855ec44beaf8a5ab2d4f98ae2ba563d05275b4e7002569bbb36cdd4336c`.
U values (eV): `{'Co': 3.32, 'O': 0}`; GGA+U.
MP2020 corrections: MP2020 anion correction (oxide): -5.496000 eV/cell; MP2020 GGA/GGA+U mixing correction (Co): -9.828000 eV/cell.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-1271793-GGA+U | C2/m (12) / 10.339288 | True / True | 0.0304967 / 0.0425356 | -6.080351679 / -7.174923107 | -1.094571429 | -70.551626 |
| mp-18748-GGA+U | I4_1md (109) / 10.585361 | True / True | 0.0216497 / 0.0287713 | -6.069871747 / -7.164443176 | -1.094571429 | -81.031558 |
| mp-1271940-GGA+U | Imma (74) / 10.481586 | True / False | 0.0217085 / 0.0297383 | -5.990453578 / -7.085025006 | -1.094571429 | -160.449727 |
| mp-1271784-GGA+U | Imma (74) / 10.481586 | True / False | 0.0217085 / 0.0297383 | -6.049969968 / -7.144541396 | -1.094571429 | -100.933337 |

**mp-1271793-GGA+U**: parallel dominant moments (FM-like); magnetic-element moments (muB): Co:+0.101, Co:+0.108, Co:+0.107, Co:+2.639, Co:+2.639, Co:+0.089.
POTCAR: PAW_PBE Co 06Sep2000 [b169bca4e137294d2ab3df8cbdd09083], PAW_PBE O 08Apr2002 [7a25bc5b9a5393f46600a4939d357982]. U (eV): `{'Co': 3.32, 'O': 0.0}`. POTCAR titles match: True; U match: True. Run type: GGA+U.

**mp-18748-GGA+U**: parallel dominant moments (FM-like); magnetic-element moments (muB): Co:+2.646, Co:+0.102, Co:+0.102, Co:+2.647, Co:+0.102, Co:+0.102.
POTCAR: PAW_PBE Co 06Sep2000 [b169bca4e137294d2ab3df8cbdd09083], PAW_PBE O 08Apr2002 [7a25bc5b9a5393f46600a4939d357982]. U (eV): `{'Co': 3.32, 'O': 0.0}`. POTCAR titles match: True; U match: True. Run type: GGA+U.

**mp-1271940-GGA+U**: parallel dominant moments (FM-like); magnetic-element moments (muB): Co:+3.113, Co:+3.113, Co:+2.722, Co:+2.722, Co:+2.086, Co:+2.086.
POTCAR: PAW_PBE Co 06Sep2000 [b169bca4e137294d2ab3df8cbdd09083], PAW_PBE O 08Apr2002 [7a25bc5b9a5393f46600a4939d357982]. U (eV): `{'Co': 3.32, 'O': 0.0}`. POTCAR titles match: True; U match: True. Run type: GGA+U.

**mp-1271784-GGA+U**: parallel dominant moments (FM-like); magnetic-element moments (muB): Co:+2.648, Co:+2.648, Co:+0.111, Co:+0.111, Co:+0.100, Co:+0.100.
POTCAR: PAW_PBE Co 06Sep2000 [b169bca4e137294d2ab3df8cbdd09083], PAW_PBE O 08Apr2002 [7a25bc5b9a5393f46600a4939d357982]. U (eV): `{'Co': 3.32, 'O': 0.0}`. POTCAR titles match: True; U match: True. Run type: GGA+U.

Hull decomposition: `[{'mp_entry_id': 'mp-1271793-GGA+U', 'formula': 'Co3O4', 'atomic_fraction': 1.0, 'energy_per_atom_eV': -7.174923107142857}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

### 082 KFeS2

Benchmark source: `01_refined_structures_191/082_KFeS2/energy_reference.json` and `reference.json`.
Structure: C2/c (No. 15), 25.169769 A^3/atom; MAGNDATA 0.633. Magnetic-element moments in source order (muB): Fe:-2.771, Fe:+2.771.
POTCAR set: `['PAW_PBE K_sv 06Sep2000', 'PAW_PBE Fe_pv 06Sep2000', 'PAW_PBE S 17Jan2003']`.
Combined benchmark POTCAR SHA256: `d461c6768df2b188e295dcc1d3a9a056aad29c7604860f33df973a8abceab68e`.
U values (eV): `{}`; GGA.
MP2020 corrections: MP2020 anion correction (S): -2.012000 eV/cell.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-3827-GGA | C2/c (15) / 24.627965 | True / True | 0.0132936 / 0.0167516 | -5.213417190 / -5.464917190 | -0.251500000 | -92.078161 |

**mp-3827-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Fe:+2.061, Fe:+2.061.
POTCAR: PAW_PBE K_sv 06Sep2000 [3e84f86d37f203a4fb01de36af57e430], PAW_PBE Fe_pv 06Sep2000 [5963411539032ec3298fa675a32c5e64], PAW_PBE S 17Jan2003 [d368db6899d8839859bbee4811a42a88]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

Hull decomposition: `[{'mp_entry_id': 'mp-1204678-GGA', 'formula': 'K7(FeS2)5', 'atomic_fraction': 0.7857142857142856, 'energy_per_atom_eV': -5.207167434772727}, {'mp_entry_id': 'mp-1522-GGA', 'formula': 'FeS2', 'atomic_fraction': 0.2142857142857144, 'energy_per_atom_eV': -6.429082515}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

### 083 KMnAs

Benchmark source: `01_refined_structures_191/083_KMnAs/energy_reference.json` and `reference.json`.
Structure: P4/nmm (No. 129), 24.519388 A^3/atom; MAGNDATA 1.553. Magnetic-element moments in source order (muB): Mn:-3.684, Mn:+3.684, Mn:-3.684, Mn:+3.684.
POTCAR set: `['PAW_PBE K_sv 06Sep2000', 'PAW_PBE Mn_pv 07Sep2000', 'PAW_PBE As 06Sep2000']`.
Combined benchmark POTCAR SHA256: `ad017b37a5e556e8ffeceb60cd0ddf6061e2787a95bd9b74ff7f0082edbe9b10`.
U values (eV): `{}`; GGA.
MP2020 corrections: none.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-21847-GGA | P4/nmm (129) / 25.403481 | True / True | 0.00916902 / 0.0152828 | -5.224840987 / -5.224840987 | 0.000000000 | -140.539468 |

**mp-21847-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.669, Mn:+3.669.
POTCAR: PAW_PBE K_sv 06Sep2000 [3e84f86d37f203a4fb01de36af57e430], PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE As 06Sep2000 [8005364db225a254e52cba350bedd032]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

Hull decomposition: `[{'mp_entry_id': 'mp-35-GGA', 'formula': 'Mn', 'atomic_fraction': 0.33333333333333337, 'energy_per_atom_eV': -9.162015292068965}, {'mp_entry_id': 'mp-713-GGA', 'formula': 'KAs', 'atomic_fraction': 0.6666666666666667, 'energy_per_atom_eV': -3.338292345}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

### 093 LaMnAsO

Benchmark source: `01_refined_structures_191/093_LaMnAsO/energy_reference.json` and `reference.json`.
Structure: P4/nmm (No. 129), 20.141672 A^3/atom; MAGNDATA 0.619. Magnetic-element moments in source order (muB): Mn:-4.376, Mn:+4.376.
POTCAR set: `['PAW_PBE La 06Sep2000', 'PAW_PBE Mn_pv 07Sep2000', 'PAW_PBE As 06Sep2000', 'PAW_PBE O 08Apr2002']`.
Combined benchmark POTCAR SHA256: `85454f050a43b0995f3b7d927a28de9041bcbcbc35fdb3653a4d008b8d73652b`.
U values (eV): `{'La': 0, 'Mn': 3.9, 'As': 0, 'O': 0}`; GGA+U.
MP2020 corrections: MP2020 anion correction (oxide): -1.374000 eV/cell; MP2020 GGA/GGA+U mixing correction (Mn): -3.336000 eV/cell.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| None in this historical snapshot | n/a | n/a | n/a | n/a | n/a | n/a |

Hull decomposition: `[{'mp_entry_id': 'mp-22240-GGA', 'formula': 'MnAs', 'atomic_fraction': 0.3333333333333335, 'energy_per_atom_eV': -7.181139465}, {'mp_entry_id': 'mp-708-GGA', 'formula': 'LaAs', 'atomic_fraction': 0.16666666666666652, 'energy_per_atom_eV': -6.361248085}, {'mp_entry_id': 'mp-2292-GGA', 'formula': 'La2O3', 'atomic_fraction': 0.4166666666666667, 'energy_per_atom_eV': -8.81732254125}, {'mp_entry_id': 'mp-35-GGA', 'formula': 'Mn', 'atomic_fraction': 0.08333333333333326, 'energy_per_atom_eV': -9.162015292068965}]`.

**Conclusion: suspect.** No exact-composition LaMnAsO entry exists among the 154,718 historical source entries, so no MP polymorph or same-structure energy is available. A missing stable AFM phase is plausible, but the 65.882 meV/atom advantage over the decomposition hull remains unresolved without a matched calculation. No arithmetic error is established.

### 129 NaMnAs

Benchmark source: `01_refined_structures_191/129_NaMnAs/energy_reference.json` and `reference.json`.
Structure: P4/nmm (No. 129), 20.067800 A^3/atom; MAGNDATA 0.629. Magnetic-element moments in source order (muB): Mn:-3.520, Mn:+3.520.
POTCAR set: `['PAW_PBE Na_pv 05Jan2001', 'PAW_PBE Mn_pv 07Sep2000', 'PAW_PBE As 06Sep2000']`.
Combined benchmark POTCAR SHA256: `e1d168216f2a8ac2b46d10415ba4c2001a3f587bbc864d582844719aabf9fd62`.
U values (eV): `{}`; GGA.
MP2020 corrections: none.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-20612-GGA | P4/nmm (129) / 19.932508 | True / True | 0.00777722 / 0.0108836 | -5.325392533 / -5.325392533 | 0.000000000 | -143.892012 |

**mp-20612-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.268, Mn:+3.268.
POTCAR: PAW_PBE Na_pv 05Jan2001 [c71d0ed99a871c91fccae9347860d8ba], PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE As 06Sep2000 [8005364db225a254e52cba350bedd032]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

Hull decomposition: `[{'mp_entry_id': 'mp-655-GGA', 'formula': 'Na3As', 'atomic_fraction': 0.4444444444444444, 'energy_per_atom_eV': -2.5707771466666665}, {'mp_entry_id': 'mp-22240-GGA', 'formula': 'MnAs', 'atomic_fraction': 0.4444444444444443, 'energy_per_atom_eV': -7.181139465}, {'mp_entry_id': 'mp-35-GGA', 'formula': 'Mn', 'atomic_fraction': 0.11111111111111116, 'energy_per_atom_eV': -9.162015292068965}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

### 144 RbFeS2

Benchmark source: `01_refined_structures_191/144_RbFeS2/energy_reference.json` and `reference.json`.
Structure: C2/c (No. 15), 27.513118 A^3/atom; MAGNDATA 0.636. Magnetic-element moments in source order (muB): Fe:-2.797, Fe:+2.797.
POTCAR set: `['PAW_PBE Rb_sv 06Sep2000', 'PAW_PBE Fe_pv 06Sep2000', 'PAW_PBE S 17Jan2003']`.
Combined benchmark POTCAR SHA256: `055722b14d8ca19db4dfef0fbab9f56cd49a860a6509b1cead4ac7f526add932`.
U values (eV): `{}`; GGA.
MP2020 corrections: MP2020 anion correction (S): -2.012000 eV/cell.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-5372-GGA | C2/c (15) / 27.000558 | True / True | 0.0162236 / 0.0220827 | -5.188196855 / -5.439696855 | -0.251500000 | -94.196029 |
| mp-1078517-GGA | Immm (71) / 26.794514 | False / False | n/a | -5.185428341 / -5.436928341 | -0.251500000 | -96.964543 |

**mp-5372-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Fe:+2.084, Fe:+2.084.
POTCAR: PAW_PBE Rb_sv 06Sep2000 [aadc1665275b2ae1eed0dcf93c95f9ce], PAW_PBE Fe_pv 06Sep2000 [5963411539032ec3298fa675a32c5e64], PAW_PBE S 17Jan2003 [d368db6899d8839859bbee4811a42a88]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-1078517-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Fe:+2.050, Fe:+2.050.
POTCAR: PAW_PBE Rb_sv 06Sep2000 [aadc1665275b2ae1eed0dcf93c95f9ce], PAW_PBE Fe_pv 06Sep2000 [5963411539032ec3298fa675a32c5e64], PAW_PBE S 17Jan2003 [d368db6899d8839859bbee4811a42a88]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

Hull decomposition: `[{'mp_entry_id': 'mp-5372-GGA', 'formula': 'RbFeS2', 'atomic_fraction': 1.0, 'energy_per_atom_eV': -5.439696855}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

### 145 RbFeSe2

Benchmark source: `01_refined_structures_191/145_RbFeSe2/energy_reference.json` and `reference.json`.
Structure: C2/c (No. 15), 30.434927 A^3/atom; MAGNDATA 0.638. Magnetic-element moments in source order (muB): Fe:-2.954, Fe:+2.954.
POTCAR set: `['PAW_PBE Rb_sv 06Sep2000', 'PAW_PBE Fe_pv 06Sep2000', 'PAW_PBE Se 06Sep2000']`.
Combined benchmark POTCAR SHA256: `58ccab94f17bced139b7f4ac62828000c3b1907623a5d79eb0c322c4d5cfd709`.
U values (eV): `{}`; GGA.
MP2020 corrections: MP2020 anion correction (Se): -1.888000 eV/cell.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-7086-GGA | C2/c (15) / 30.106295 | True / True | 0.00613943 / 0.00860888 | -4.771324345 / -5.007324345 | -0.236000000 | -89.599768 |

**mp-7086-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Fe:+2.488, Fe:+2.488.
POTCAR: PAW_PBE Rb_sv 06Sep2000 [aadc1665275b2ae1eed0dcf93c95f9ce], PAW_PBE Fe_pv 06Sep2000 [5963411539032ec3298fa675a32c5e64], PAW_PBE Se 06Sep2000 [67a8804ede9f1112726e3d136978ef19]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

Hull decomposition: `[{'mp_entry_id': 'mp-7086-GGA', 'formula': 'RbFeSe2', 'atomic_fraction': 1.0, 'energy_per_atom_eV': -5.007324345}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

### 146 RbMnAs

Benchmark source: `01_refined_structures_191/146_RbMnAs/energy_reference.json` and `reference.json`.
Structure: P4/nmm (No. 129), 27.539310 A^3/atom; MAGNDATA 1.543. Magnetic-element moments in source order (muB): Mn:-3.705, Mn:+3.705, Mn:-3.705, Mn:+3.705.
POTCAR set: `['PAW_PBE Rb_sv 06Sep2000', 'PAW_PBE Mn_pv 07Sep2000', 'PAW_PBE As 06Sep2000']`.
Combined benchmark POTCAR SHA256: `3752ac8996e9e520c2a0e66803735c26b12106fdb9e0a510d84599fa993d3981`.
U values (eV): `{}`; GGA.
MP2020 corrections: none.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-987178-GGA | P4/nmm (129) / 32.733794 | True / False | 0.101582 / 0.127227 | -5.176329082 / -5.176329082 | 0.000000000 | -101.317397 |
| mp-20242-GGA | P4/nmm (129) / 28.167831 | True / False | 0.022081 / 0.0334994 | -5.136451072 / -5.136451072 | 0.000000000 | -141.195407 |

**mp-987178-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.238, Mn:+3.236.
POTCAR: PAW_PBE Rb_sv 06Sep2000 [aadc1665275b2ae1eed0dcf93c95f9ce], PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE As 06Sep2000 [8005364db225a254e52cba350bedd032]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-20242-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.938, Mn:+3.938.
POTCAR: PAW_PBE Rb_sv 06Sep2000 [aadc1665275b2ae1eed0dcf93c95f9ce], PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE As 06Sep2000 [8005364db225a254e52cba350bedd032]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

Hull decomposition: `[{'mp_entry_id': 'mp-35-GGA', 'formula': 'Mn', 'atomic_fraction': 0.33333333333333337, 'energy_per_atom_eV': -9.162015292068965}, {'mp_entry_id': 'mp-10802-GGA', 'formula': 'RbAs', 'atomic_fraction': 0.6666666666666667, 'energy_per_atom_eV': -3.242885495625}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

### 183 MnTe

Benchmark source: `01_refined_structures_191/183_MnTe/energy_reference.json` and `reference.json`.
Structure: P6_3/mmc (No. 194), 23.482407 A^3/atom; MAGNDATA 0.800. Magnetic-element moments in source order (muB): Mn:-3.969, Mn:+3.969.
POTCAR set: `['PAW_PBE Mn_pv 07Sep2000', 'PAW_PBE Te 08Apr2002']`.
Combined benchmark POTCAR SHA256: `4f45fadf0c3499e9a799dbcafecf503fbda78b18a0111c0c48d961d1c9e5ef82`.
U values (eV): `{}`; GGA.
MP2020 corrections: MP2020 anion correction (Te): -0.844000 eV/cell.

MP entries of this exact reduced composition (all 19 are included across the table):

| MP entry | Structure / volume (A^3/atom) | Geometric / tighter match | Normalized RMS / max | Raw / corrected (eV/atom) | C (eV/atom) | Benchmark minus MP (meV/atom) |
|---|---|---|---|---|---:|---:|
| mp-1172860-GGA | Imma (74) / 26.254350 | False / False | n/a | -5.467470132 / -5.678470133 | -0.211000000 | -834.833606 |
| mp-672389-GGA | P2_1/m (11) / 25.638997 | False / False | n/a | -6.151487643 / -6.362487643 | -0.211000000 | -150.816096 |
| mp-1079443-GGA | Pnma (62) / 25.419181 | False / False | n/a | -6.053413284 / -6.264413284 | -0.211000000 | -248.890455 |
| mp-1406-GGA | Fm-3m (225) / 24.012055 | False / False | n/a | -6.189266780 / -6.400266780 | -0.211000000 | -113.036958 |
| mp-404-GGA | P6_3/mmc (194) / 22.926354 | True / False | 5.98657e-07 / 8.46629e-07 | -6.234819630 / -6.445819630 | -0.211000000 | -67.484108 |
| mp-1080073-GGA | Pnma (62) / 22.461108 | True / False | 0.000776728 / 0.00109846 | -6.232569835 / -6.443569835 | -0.211000000 | -69.733903 |
| mp-1009222-GGA | F-43m (216) / 32.697119 | False / False | n/a | -6.207895210 / -6.418895210 | -0.211000000 | -94.408528 |

**mp-1172860-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.921, Mn:+3.921, Mn:+3.921, Mn:+3.921, Mn:+3.921, Mn:+3.921, Mn:+3.921, Mn:+3.921.
POTCAR: PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE Te 08Apr2002 [72719856e22fb1d3032df6f96d98a0f2]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-672389-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.763, Mn:+3.290, Mn:+3.290, Mn:+3.763.
POTCAR: PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE Te 08Apr2002 [72719856e22fb1d3032df6f96d98a0f2]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-1079443-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+4.176, Mn:+4.176, Mn:+4.176, Mn:+4.175.
POTCAR: PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE Te 08Apr2002 [72719856e22fb1d3032df6f96d98a0f2]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-1406-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+4.143.
POTCAR: PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE Te 08Apr2002 [72719856e22fb1d3032df6f96d98a0f2]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-404-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.782, Mn:+3.783.
POTCAR: PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE Te 08Apr2002 [72719856e22fb1d3032df6f96d98a0f2]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-1080073-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+3.781, Mn:+3.751, Mn:+3.777, Mn:+3.751.
POTCAR: PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE Te 08Apr2002 [72719856e22fb1d3032df6f96d98a0f2]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

**mp-1009222-GGA**: parallel dominant moments (FM-like); magnetic-element moments (muB): Mn:+4.346.
POTCAR: PAW_PBE Mn_pv 07Sep2000 [fa52f891f234d49bb4cb5ea96aae8f98], PAW_PBE Te 08Apr2002 [72719856e22fb1d3032df6f96d98a0f2]. U (eV): `{}`. POTCAR titles match: True; U match: True. Run type: GGA.

Hull decomposition: `[{'mp_entry_id': 'mp-21893-GGA', 'formula': 'MnTe2', 'atomic_fraction': 0.75, 'energy_per_atom_eV': -5.554064405000001}, {'mp_entry_id': 'mp-35-GGA', 'formula': 'Mn', 'atomic_fraction': 0.25, 'energy_per_atom_eV': -9.162015292068965}]`.

**Conclusion: plausible.** Geometrically matching MP entries exist on the same declared U/POTCAR-symbol recipe. The benchmark is lower in energy, so a different relaxed magnetic state or numerical setup is a plausible explanation. This is an inference, not proof of magnetic origin; exact POTCAR hashes and complete electronic settings remain unverified.

## Near-hull references

57 references are within +/-1 meV/atom; 21 within +/-0.1 meV/atom. Values come
from `mp_hull/results.json` and agree with `targets/hull.json`. The final column
identifies all 21 members of the narrower band.

| ID | Material | Hull distance (meV/atom) | Within 0.1 |
|---|---|---:|---|
| 001 | AlFe2B2 | -0.595925000 |  |
| 005 | BaFe2As2 | 0.876775750 |  |
| 006 | BaMn2As2 | 0.474669333 |  |
| 011 | Ba2NiWO6 | -0.158677300 |  |
| 013 | BaMnO3 | -0.062155556 | yes |
| 014 | BaNa2V2CoO8 | -0.198728185 |  |
| 015 | BaNi2As2O8 | 0.859595000 |  |
| 016 | BaNi2P2O8 | 0.132242885 |  |
| 017 | CaCo2P2 | 0.842052750 |  |
| 018 | CaFe2As2 | 0.984525250 |  |
| 027 | CoRh2O4 | -0.078240952 | yes |
| 029 | CoBiO3 | -0.087636250 | yes |
| 030 | CoBr2 | 0.278711667 |  |
| 032 | CoF2 | -0.043904444 | yes |
| 038 | Cr2O3 | 0.076191500 | yes |
| 039 | Cr2TeO6 | 0.001532500 | yes |
| 040 | Cr2WO6 | 0.003541944 | yes |
| 043 | CrCl3 | 0.875857187 |  |
| 056 | CsNiF3 | 0.370564833 |  |
| 059 | CuO | 0.213317500 |  |
| 060 | EuO | 0.144380000 |  |
| 064 | Fe2O3 | -0.034318500 | yes |
| 065 | Fe2TeO6 | -0.071332500 | yes |
| 070 | FeF2 | -0.176064722 |  |
| 073 | FeHO2 | 0.018263906 | yes |
| 074 | FeI2 | -0.643921667 |  |
| 091 | LaCrO3 | 0.485850000 |  |
| 101 | LiCrGe2O6 | -0.095402125 | yes |
| 105 | LiMnPO4 | -0.032119107 | yes |
| 112 | Mn3GaC | -0.252918000 |  |
| 120 | MnF2 | 0.183825833 |  |
| 122 | MnO | -0.064040417 | yes |
| 123 | MnPS3 | 0.691735667 |  |
| 125 | MnS | 0.800362500 |  |
| 128 | MnWO4 | 0.172370937 |  |
| 134 | Nb3VS6 | -0.238781625 |  |
| 135 | Ni3TeO6 | 0.389819500 |  |
| 138 | NiO | 0.669546000 |  |
| 140 | NiSO4 | 0.164234167 |  |
| 141 | NiWO4 | -0.510630208 |  |
| 156 | SrRu2O6 | 0.004073611 | yes |
| 158 | Sr2CoTeO6 | -0.405892083 |  |
| 161 | Sr2MnTeO6 | 0.189698833 |  |
| 162 | Sr2NiTeO6 | -0.830118250 |  |
| 163 | Sr2NiWO6 | -0.019900250 | yes |
| 168 | TiMnO3 | -0.174757000 |  |
| 169 | TiNiO3 | -0.129886000 |  |
| 173 | V2WO6 | 0.010118889 | yes |
| 174 | VClO | -0.512893333 |  |
| 179 | YVO3 | -0.040404000 | yes |
| 184 | Ca2NiOsO6 | -0.024074375 | yes |
| 187 | NaFeSi2O6 | 0.386587375 |  |
| 189 | Ba2CoGe2O7 | 0.032780937 | yes |
| 191 | CaIrO3 | -0.284325000 |  |
| 201 | LiFePO4 | -0.051916786 | yes |
| 215 | Ta2Mn4O9 | 0.156088333 |  |
| 218 | YCrO3 | 0.028821000 | yes |

## Limits and follow-up

Eight negative distances are plausible on a compatible declared energy scale
with explicit structural and magnetic-state comparisons. This does not establish
that the full energy difference is magnetic. LaMnAsO is **suspect/unresolved**,
because no exact-composition MP entry exists in this snapshot; a missing stable
AFM phase is possible. No proven data error was identified and no data were edited.
Exact per-element benchmark POTCAR hashes, matched k-point/electronic settings,
and controlled AFM/FM calculations would be needed for a causal attribution.
Current MP website records cannot replace the pinned historical snapshot.
