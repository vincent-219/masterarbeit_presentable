# Representative surveys on Israel/Palestine

Deutsche Fassung: [README.md](README.md)

`umfragen_israel_palaestina.csv`: values from the published tables (one row per answer category), with source (`url`), field period
and sample size. Checked automatically against the PDF texts (08.10.2026: 0 deviations).

| Source | Waves | Countries | Questions |
|---|---|---|---|
| YouGov EuroTrack (online panel, weighted) | Oct 2023, Nov/Dec 2023, Jun 2024, Oct 2024, May 2025 | GB, FR, DE, DK, ES, IT (SE only 2023) | sympathy, attack on Gaza justified, Israel's conduct |
| Pew Global Attitudes (telephone, random sample) | spring 2025, spring 2026 | FR, DE, GR, HU, IT, NL, PL, ES, SE, GB | opinion of Israel, confidence in Netanyahu |

- `n`: YouGov = unweighted sample size per country and wave; Pew 2025 = sample size according to the methodology PDF.
  Pew 2026: sample size per country not published (empty); about 1,000 is assumed for tests.
- `deff`: design effect according to the Pew 2025 methodology (effective sample size = n / deff). YouGov does not publish design effects.
- Percentages are weighted; sample sizes reconstructed from them are approximations.
- Analysis: `04_umfragen.Rmd`.
