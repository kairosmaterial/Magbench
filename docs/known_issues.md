# Protocol questions for owner review

Reference values remain unchanged; resolved scoring items identify their protocol version.

- **Fixed in data v0.2.2:** magnetovolume mapping designs formerly carried signs on non-magnetic species. Use the corrected inputs; historical energy-mapping runs require recomputation. Exchange-readout scores are unaffected.
- **Exchange interpretation:** the reference J values come from a shell-truncated energy fit. An analytic bare pair readout and a fit of the model energy using that same truncation need not agree. to be provided: Choose and document the intended comparability requirement.
- **Addressed in v0.3 — accuracy dynamic range:** J accuracy now uses relative scale 0.5 and floor 0.5 meV. The sign term is unchanged. Volume-slope accuracy retains its original scale and remains an open diagnostic question.
- **Addressed in v0.3 — hull boundary:** the side term is credited when sides agree or both absolute energies are at most 1 meV/atom; the continuous term is unchanged.
- **Seed amplitudes:** model-chosen amplitudes must be recorded. to be provided: Ratify how optional seed tables are standardised and versioned across future submissions.
- **Uncomputed states:** a model may prefer a magnetic state that the reference calculations never evaluated. to be provided: Define future reference expansion and adjudication; the present experimental-match gate remains unchanged.
