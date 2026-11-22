# Protocol questions for owner review

These notes do not change the v0.2.1 scorer or reference values.

- **Fixed in data v0.2.2:** magnetovolume mapping designs formerly carried signs on non-magnetic species. Use the corrected inputs; historical energy-mapping runs require recomputation. Exchange-readout scores are unaffected.
- **Exchange interpretation:** the reference J values come from a shell-truncated energy fit. An analytic bare pair readout and a fit of the model energy using that same truncation need not agree. to be provided: Choose and document the intended comparability requirement.
- **Accuracy dynamic range:** earlier review found normalised RMS errors around 3–4 for J and volume slopes, suppressing their accuracy components. to be provided: Decide whether any future protocol should change this scale; retain current scores unchanged.
- **Hull boundary:** hull-side classification can change within about 1 meV/atom of zero. to be provided: Decide whether a future release needs a tolerance; the current split remains strictly >0 versus ≤0.
- **Seed amplitudes:** model-chosen amplitudes must be recorded. to be provided: Ratify how optional seed tables are standardised and versioned across future submissions.
- **Uncomputed states:** a model may prefer a magnetic state that the reference calculations never evaluated. to be provided: Define future reference expansion and adjudication; the present experimental-match gate remains unchanged.
