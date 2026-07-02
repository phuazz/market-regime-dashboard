# VERIFICATION.md — data-provider series verification log

Every data-provider series ID is verified against two independent sources
before first use (project CLAUDE.md, "Data integrity"). Each entry records
what was checked, the values compared, and the URLs, so the check can be
repeated. A mismatch blocks the series from shipping until resolved.

Verification standard: (1) confirm the series resolves to the intended
concept via provider metadata where accessible; (2) match the latest values
for identical reference dates against the originating agency or a second
independent publisher; (3) record both URLs and the check date here, and
carry `source_url` plus `secondary_source_url` in the JSON for every data
point.

---

## T10Y3M — 10-Year Treasury Constant Maturity Minus 3-Month Treasury Constant Maturity

- **Verified:** 2026-07-02
- **Provider:** FRED (Federal Reserve Bank of St. Louis), keyless `fredgraph.csv` endpoint
- **Primary URL:** https://fred.stlouisfed.org/series/T10Y3M
- **Secondary (originating agency):** US Treasury daily par yield curve rates —
  https://home.treasury.gov/resource-center/data-chart-center/interest-rates
- **Value checks** (FRED pull and Treasury CSV pull, both 2026-07-02):

  | Date | FRED `T10Y3M` | Treasury 10 Yr | Treasury 3 Mo | Treasury 10Y − 3M | Match |
  |---|---|---|---|---|---|
  | 2026-06-29 | 0.51 | 4.38 | 3.87 | 0.51 | yes |
  | 2026-06-30 | 0.57 | 4.44 | 3.87 | 0.57 | yes |
  | 2026-07-01 | 0.63 | 4.48 | 3.85 | 0.63 | yes |

- **Internal consistency:** FRED component series agree — `DGS10` − `DGS3MO`
  = 4.44 − 3.87 = 0.57 on 2026-06-30, equal to `T10Y3M` on the same date.
- **History sanity check:** sustained-inversion episodes detected in the full
  series (1982–2026) match the historical record — 2000-07-19 → 2001-01-19,
  2006-07-19 → 2007-05-29, and 2022-10-25 → 2024-12-12.
- **Notes:** the FRED HTML series page returned HTTP 403 to automated
  fetching on 2026-07-02, so the page-title check could not be captured in
  this log. Identification therefore rests on the numeric match against the
  originating agency across three consecutive sessions plus internal
  consistency with the component series `DGS10` and `DGS3MO`, which is the
  substantive test. `DGS10` and `DGS3MO` are used for verification arithmetic
  only and do not feed the dashboard.

---

## Pending verification (phase 2 and later — do not use before logging here)

`SAHMREALTIME` (vs `SAHMCURRENT`), `BAMLH0A0HYM2`, `UNRATE`, `PAYEMS`,
`UEMP27OV`, `CCSA`, the ISM proxy (S&P Global US Manufacturing PMI headline;
fallback regional Fed survey candidates `GACDISA066MSFRBNY` and
`GACDFSA066MSFRBPHI`, both unconfirmed from-memory IDs), the Conference Board
LEI headline and its public-component proxy inputs, Shiller CAPE
(multpl.com vs the Shiller Yale dataset), `NFCI` / `ANFCI`, `DRTSCILM`,
`UMCSENT`, `CPIAUCSL`, `USREC`, AAII survey values, the NAAIM Exposure
Index, and all price feeds (`^GSPC`, RPV/RPG) with their second feeds.
