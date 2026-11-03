# Third-party data and services

Every API and dataset TarangYukti uses, with its licence, attribution and use (spec §11).
Added as each milestone starts using a source.

## Data sources (Milestone 2)

| Source | Endpoint | Licence / terms | Attribution | Used for |
|---|---|---|---|---|
| Open-Meteo Marine | `https://marine-api.open-meteo.com/v1/marine` | CC BY 4.0; free for non-commercial use | "Weather data by Open-Meteo.com" | Hourly waves, swell, currents, SST (`marine_forecast`) |
| Open-Meteo Forecast | `https://api.open-meteo.com/v1/forecast` | CC BY 4.0; free for non-commercial use | "Weather data by Open-Meteo.com" | Wind and gusts at 10 m (`marine_forecast`, H6) |
| NOAA OISST v2.1 NRT | CoastWatch ERDDAP `ncdcOisst21NrtAgg` | US Government work, public domain | NOAA NCEI / CoastWatch | Sea-surface temperature grid (`sst_grid`) |
| NOAA-20 VIIRS chlorophyll-a NRT | CoastWatch ERDDAP `noaacwN20VIIRSchlaDaily` | US Government work, public domain | NOAA CoastWatch / NESDIS | Chlorophyll grid (`chl_grid`) |
| India–Sri Lanka maritime boundary | UN DOALOS treaty texts: [1974](https://www.un.org/depts/los/LEGISLATIONANDTREATIES/PDFFILES/TREATIES/LKA-IND1974BW.PDF), [1976](https://www.un.org/depts/los/LEGISLATIONANDTREATIES/PDFFILES/TREATIES/LKA-IND1976MB.PDF) | Public treaty text | Agreements of 26/28 June 1974 and 23 March 1976 | IMBL line for H2 (`fence_check`) — `data/layers/imbl.geojson` |
| World Database on Protected Areas | UNEP-WCMC WDPA site 556326231 | WDPA terms of use (non-commercial; no redistribution of the full dataset) | UNEP-WCMC and IUCN, Protected Planet | Gulf of Mannar marine park + eco-sensitive zone for H3 — `data/layers/mpa_gom.geojson` |
| NDMA SACHET (CAP 1.2) | `sachet.ndma.gov.in` — active-alert list, CAP XML, alert polygons | Public alerting service of the Government of India; credit the issuing agency | IMD / INCOIS as issuer, disseminated by NDMA SACHET | Live IMD and INCOIS warnings (H1, H7) — `imd_warnings`, `incois_alerts` |
| Natural Earth 1:10m land | `ne_10m_land` (GitHub mirror of naturalearthdata.com) | Public domain | Natural Earth | Land mask for route search — `data/layers/land.geojson` |
| IMD API | `https://api.imd.gov.in/api/v1/` | IP-whitelisted; credit IMD | India Meteorological Department | Not used (IMD alerts arrive through SACHET) |
| INCOIS PFZ advisories | `incois.gov.in` pages | Public pages; respect site terms | INCOIS, Ministry of Earth Sciences | PFZ — **captured into snapshots; no live feed** |

## Knowledge-base documents (Milestone 4) — `kb/sources/manifest.yaml`

| Document | Source | Licence / terms | Notes |
|---|---|---|---|
| Uniform 61-day fishing ban (PIB release, 25 Mar 2025) | pib.gov.in | Government press release; attribute PIB | PIB refuses automated clients: indexed only from a copy saved by hand in `kb/sources/captured/` |
| Maritime Zones of India Act, 1976 | UN DOALOS copy (un.org) | Act of Parliament | |
| Tamil Nadu Marine Fishing Regulation Act 1983, Amendment 2017, Rules 2020 | fisheries.tn.gov.in | State law, public | 1983 Act is a scanned gazette: OCR text |
| Marine Fish Landings in India 2024 | eprints.cmfri.org.in | ICAR-CMFRI technical report; cite FRAEED, CMFRI, 2025 | |
| Live bulletins | NDMA SACHET CAP alerts | Credit the issuing agency | Indexed with their validity windows |
| Safety SOPs | Written by the TarangYukti team | — | DRAFT, pending review by fisheries officials |

Embeddings: Google Gemini Embedding 2 (`gemini-embedding-2`, 768-d). Conversion and chunking: Docling (MIT).

Map displays must label the IMBL source and follow the Geospatial Guidelines 2021 (official India boundaries).

## Platform services

| Service | Use |
|---|---|
| Supabase (Auth, Postgres, Storage) | Platform; private `snapshots` bucket |
| Neo4j AuraDB | Constraint Ledger (Milestone 3) |
| Google Gemini API | Agents and embeddings (Milestones 4–5) |
| Sarvam AI | Speech and translation (Milestone 6) |
| CopilotKit | Agent runtime and client (MIT) |
