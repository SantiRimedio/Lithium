# Methodology v2 — Lithium Mining Impact in the Argentine Puna

*Working draft, May 2026. Supersedes the v1 design described in `text/Mining_Impact_Proposal.pdf`.*

## 0. Executive summary

The v1 design — MODIS NDVI annual medians averaged over H3 hexagons across COHIFE endorheic basins, per-hexagon OLS trend — could not work. The signal communities describe lives in bofedales (groundwater-fed peatlands) that occupy <5% of any given hexagon; averaging at H3 res-6 (~36 km²) buries a 0.5 km² vega in two orders of magnitude of bare-ground noise. The design also had no causal identification: trends couldn't be separated from the 2010s mega-drought, and "mining" was a binary basin-level label rather than a dose-response treatment.

v2 makes four structural changes:

1. **Unit of analysis** moves from H3 hexagons to **individual bofedal polygons** drawn from existing inventories (Izquierdo & Grau 2016 for Argentina; the 2026 global high-altitude wetland map for cross-validation).
2. **Treatment** moves from binary basin-level to **two continuous variables: distance to nearest brine extraction well and distance to nearest freshwater well**, with cumulative pond area as a secondary intensity measure. The split into brine vs freshwater is forced on us by Corkran et al. 2025, who show freshwater pumping has ~200–2,300% larger wetland impact than equivalent brine pumping.
3. **Identification** moves from per-unit OLS trend to **Callaway–Sant'Anna staggered difference-in-differences** at the bofedal level, with non-mining-salar bofedales as controls and conditional parallel trends on SPEI. Operations open at different years (Fénix 1998, Olaroz 2015, Cauchari-Olaroz 2023, others 2024+), which is exactly what CS-DiD is designed for. A **spatial regression discontinuity** with distance-to-well as the running variable is the secondary, novel design — no one in this literature has tried it.
4. **Sensors** move from MODIS to **harmonized Landsat 5/7/8/9 + Sentinel-2** (NDVI, NDWI, LST, ET) for optical, plus **Sentinel-1 InSAR via LiCSAR/LiCSBAS** for ground subsidence as a mechanically independent indicator of brine drawdown.

The qualitative bridge — testimony validation — is anchored on the **Vega del Río Trapiche / Salar del Hombre Muerto** case, the single most documented "river running dry" claim in Argentine lithium discourse and the only Argentine site with both 25+ years of mining (Livent/Fénix since 1998) and explicit community-led testimony of vega desiccation.

The biggest design risk is what we'll call the **Moran–Corkran trap**: vegetation in these systems is fed by groundwater that may be decades to millennia old, so vegetation response lags pumping by years, and the mega-drought of 2010–2018 confounds attribution. Two responses: (a) split brine-vs-freshwater treatment so we can test the Corkran prediction directly, and (b) commit upfront to publishing the result either way — a credible null is a contribution in this literature, not a failure.

---

## 1. Findings from deep research that drive the design

The full research report is preserved in conversation; key findings that change v1 → v2:

- **Bofedal polygons already exist for Argentina.** Izquierdo, Foguet & Grau 2016 (Ecología Austral; CONICET handle 11336/58267) classified 14.3 M ha of Argentine Puna into hydroecosystem complexes including 110,895 ha of freshwater vegas and 61,123 ha of saline peatbogs. A March 2026 *Scientific Data* paper released the first 30 m global high-altitude wetland map (Zenodo 18339573), independently derived. We don't have to build a vega mask from scratch.
- **Bofedales are not homogeneous.** The CONICET IMBIV floristic classification (Carilla et al. and Izquierdo group) distinguishes 5 classes — cushion / Juncaceae / Cyperaceae / halophyte groups. NDVI response to drought differs strongly across classes. Without stratifying by floristic class, the treatment effect dilutes.
- **The Corkran et al. 2025 result is the most important refinement.** *Water Resources Research* (10.1029/2024WR039511): freshwater abstraction has 200–2,300% larger wetland impact than equivalent halite-brine abstraction; observed 90% wetland reductions trace to freshwater wells, not brine ponds. **Treatment must split into freshwater-well distance and brine-well distance.** This is also the Moran et al. 2022 message: relic groundwater dominates wetland water budgets, so brine pumping from deep aquifers may not show up in surface vegetation at all.
- **InSAR has been done at Olaroz already.** Bonadeo et al. 2024 (IEEE 10530767) used Sentinel-1 SBAS on Salar de Olaroz 2018–2020: cumulative displacements +12 to −17 cm, max subsidence at drilling locations. This is a published proof of concept; we can extend it Argentina-wide and time-extend it to 2014–present.
- **A close competitor paper already exists.** Castro Sardiña et al. 2023 (*Sci of the Total Env*, S014019632300054X) compared wet-meadow NDVI near an Argentine open-pit mine to a national park control and concluded climate, not mining, drove the trend. We must clearly improve on this — multiple operations, staggered timing, continuous treatment, climate-conditional parallel trends, InSAR co-evidence — or the contribution is unclear to referees.
- **USGS published an Argentine lithium geodatabase** (DOI 10.5066/P9RLUH4F): 86 Argentine salars including 42 with known Li and 44 without. The 44 "no Li" salars are a ready-made convenience control set.
- **MapBiomas Argentina Collection 2** now has a "Puna y Altos Andes" working region (Landsat-based, 1998–2022) accessible via GEE. Use for cross-validation of the vega mask, not as primary.
- **Climate controls require bias correction.** Kirshen et al. 2025 (*Comm. Earth & Env.*) showed global hydrologic models overestimate inflows to Andean closed basins by 5–50×. MSWEP > CHIRPS > ERA5-Land for Altiplano precipitation per a 2025 Bolivia evaluation. SPEI-12 and SPEI-24 are appropriate accumulation windows for groundwater-fed bofedales (not SPI-3 as in standard dryland vegetation studies).
- **The spatial RDD angle is untried.** Bonadeo's InSAR shows mechanical subsidence is sharply localized to ~hundreds of meters from wells; Corkran shows freshwater drawdown extends ~kilometers. This is a bandwidth-bounded continuous treatment — textbook spatial RDD setup that nobody in the lithium-RS literature has used.

---

## 2. Autopsy: why v1 failed

For the record, since we'll need to explain this in the paper:

| v1 choice | Failure mode |
|---|---|
| H3 hexagon as unit | Vega : non-vega area ratio is ~1:20 inside any hex; signal drowned in noise |
| MODIS 250 m NDVI | Pixel straddles bofedal edges; bofedals are often <500 m wide |
| Binary basin-level treatment | No dose-response, no spatial gradient, no exogenous variation in intensity |
| Annual median NDVI | Bofedal stress shows up in dry-season anomalies first; annual median averages it out |
| OLS trend per unit | Confounded with mega-drought; no counterfactual |
| No climate control | Can't separate mining from climate |
| 4-basin sample (initially) | Underpowered for any test |

v1 wasn't wrong in intent — it was right to look at endorheic basins and right to want a comparative design. The selected basins (Cauchari/Olaroz vs Guayatayoc/Salinas Grandes) actually encode a strong natural experiment: same hydrology and climate, varies in mining presence because of community resistance. v2 keeps that selection logic but adds Hombre Muerto (longest history) and the staggered new operations, and re-poses everything at the right spatial scale.

---

## 3. v2 design

### 3.1 Spatial unit: the bofedal panel

The dataset is a panel of **bofedales × years**. A "bofedal" is a polygon from:

- *Primary mask:* Izquierdo, Foguet & Grau 2016 freshwater-vega polygons within Argentine Puna.
- *Cross-validation mask:* the 2026 global high-altitude wetland map (Zenodo 18339573), v1.1 mountain-wetland layer subset to the Argentine Puna.
- *Reconciliation:* polygons accepted into the analysis set if both masks agree to >50% spatial overlap. Disputed polygons are hand-validated against Planet/Worldview imagery for ~50–100 sites before any inferential analysis runs. **This validation gate must close before Stage 3.**

Each bofedal is annotated with:

- Floristic class (1–5, from CONICET IMBIV).
- Hydroecosystem complex membership (Izquierdo & Grau).
- Containing salar / closed basin.
- Distance to nearest brine extraction well and nearest freshwater well, for each year (since wells come online at different dates).
- Elevation (SRTM 30 m).
- Micro-watershed identifier (HydroBASINS L10 or COHIFE sub-basin).

The unit deliberately is **not** the pixel and **not** the basin. Pixel introduces MAUP and coregistration noise; basin loses all spatial variation. Bofedal-polygon-level is the level the qualitative claims are actually made at.

### 3.2 Outcomes

Annual growing-season medians of:

- **NDVI** (primary) — harmonized Landsat 5/7/8/9 + Sentinel-2 via the HLS product. *Not MODIS.*
- **NDWI / MNDWI** — surface water, useful for salar margin and lagoon dynamics.
- **Day and Night LST** — Landsat thermal + MODIS LST as fallback for older years.
- **ET** — PML-V2 or OpenET-style (the deep research flagged ET as underused in this literature).
- **Sentinel-1 backscatter VV/VH** — independent of optical, immune to cloud, picks up salt-crust moisture.

The primary outcome is NDVI; everything else is robustness.

### 3.3 Treatments

**Two continuous treatments**, varying by year:

- `BrineDist_it` — distance from bofedal i to nearest active brine extraction well at year t.
- `FreshDist_it` — distance from bofedal i to nearest active freshwater well at year t.

Plus an intensity measure:

- `PondArea_bt` — cumulative evaporation-pond area in bofedal i's parent basin at year t.

And an event-time indicator:

- `YearsSinceMine_it` — for the nearest operation; negative for pre-treatment years.

Wells and ponds digitized from:

- Sentinel-2 (2015–present) at 10 m, annual mosaics.
- Landsat 5/7/8 (1997–2014) at 30 m, annual mosaics for Fénix-era extension.
- Hand-labeled training set + SVM following the 2025 *Sustainability* SOTA (MDPI 17/12/5631, R²=0.91 vs production data in Atacama).
- USGS Lithium Triangle geodatabase (DOI 10.5066/P9RLUH4F) as starting points.
- Argentine Environmental Impact Reports (EIR) — water-use volumes and well locations for Olaroz and Fénix were reverse-engineered by Paz et al. 2025 *Heliyon*.

### 3.4 Identification — two strategies running in parallel

**Strategy A: Staggered Difference-in-Differences.**

Callaway–Sant'Anna (2021) group-time ATT estimator. Treatment cohort = year operation opened. Control = bofedales in salars with no lithium operation (the USGS 44-no-Li set, restricted to those with comparable elevation and bofedal coverage).

ATT(g, t) for each operation-opening cohort g and year t, with conditional parallel trends:

```
Y_it = α_i + γ_t + Σ_g β_{g,t} · 1{G_i = g, t ≥ g} + θ · Climate_it + ε_it
```

where `Climate_it` is the bofedal-and-year-specific SPEI-12 and SPEI-24 from the global SPEI dataset (Nature s41597-024-03047-z). Doubly-robust estimation via the R `did` package (Callaway). TWFE specifically avoided due to negative-weighting problems with staggered treatment (Goodman-Bacon, de Chaisemartin, Sun-Abraham).

Pre-trends and placebo: ATT(g, t < g) should be statistically zero. Plot the event study.

**Strategy B: Spatial Regression Discontinuity (the novel angle).**

Within each operating salar, distance from active wells is a continuous spatial variable. Per Bonadeo 2024, subsidence falls off sharply within hundreds of meters; per Corkran 2025, freshwater drawdown extends a few km. Treat distance as the running variable; use a kernel-weighted local-linear estimator at the threshold.

This requires assuming bofedals just inside the drawdown radius are otherwise comparable to those just outside. We test the assumption with covariate-balance plots (elevation, floristic class, baseline NDVI, etc.) across the threshold.

The two strategies test very different things — A is the average treatment effect of mining onset, B is the marginal effect of being closer to a well. They should both show negative effects if mining matters; if only A is positive and B is null, the effect is likely confounded by basin-level factors.

### 3.5 Climate controls

- **SPEI-12 and SPEI-24** from the Beguería/Vicente-Serrano global SPEI dataset.
- **CHIRPS monthly precipitation** with bias correction against the limited SMN stations available in the Puna; document the bias correction transparently.
- **ERA5-Land** as a secondary product; never as primary.
- **MSWEP** as the preferred product if the deep-research-flagged Bolivia evaluation generalizes — needs to be tested against any Argentine station data we can scrape.
- A **mega-drought dummy** for 2010–2018 (Garreaud et al. 2020) included as robustness.

### 3.6 The Vega del Río Trapiche case study

In addition to the panel analysis, Salar del Hombre Muerto + Vega del Río Trapiche gets a dedicated case-study chapter:

- Longest mining history (Fénix/Livent since 1998) — 25-year window covers Landsat 5+7+8+9 and we can extend with ALOS-1 PALSAR (2006–2011) for L-band InSAR over the salt crust.
- Most concrete community testimony, including the 2024 Catamarca court ruling on cumulative impacts.
- Both brine and freshwater abstraction documented in EIRs (Paz et al. 2025).
- A clean before/after design (1985–1997 pre, 1998–present post) that is unavailable for newer operations.

This is the place to do the InSAR validation most thoroughly.

---

## 4. Workplan

Six stages with hard dependencies. Estimated effort is for a team of two (Santi + Jakob); halve speed for solo.

| Stage | What | Output | Effort |
|---|---|---|---|
| 0 | Acquire datasets (USGS gdb, Izquierdo polygons, 2026 global wetland map, SPEI, MapBiomas, CHIRPS, ERA5-Land, LiCSAR frame list) | `Data/external/` populated | 1 week |
| 1 | Build bofedal master polygon set; reconcile two masks; hand-validate 100 sites against high-res imagery | `Data/bofedales_v2.geojson` | 2–3 weeks |
| 2 | Digitize mining footprint time series (wells + ponds, annual, ~10 operations) | `Data/mining_footprint_yearly.geojson` | 2–3 weeks |
| 3 | Build the per-bofedal annual panel of outcomes + climate + distance treatments | `Data/bofedal_panel.parquet` | 2 weeks |
| 4a | Causal estimation Strategy A (CS-DiD); Strategy B (spatial RDD); robustness | Results notebooks + tables | 3 weeks |
| 4b | InSAR processing for all Argentine lithium salars via LiCSBAS, validation against Bonadeo 2024 | Subsidence time series per bofedal | 3 weeks (parallel to 4a) |
| 5 | Vega del Río Trapiche case study | Case-study chapter + maps | 2 weeks |
| 6 | Writeup | Paper draft | 4 weeks |

**Critical sequencing:** Stage 1 (bofedal validation) blocks everything. Don't skip the hand-validation step — bad polygons silently destroy the analysis. Stages 4a and 4b are independent; both should run.

**Pre-registration:** before Stage 4 starts, write a one-page pre-analysis plan committing to the estimator (CS-DiD), the control set (USGS no-Li salars), the covariates (SPEI-12, SPEI-24, elevation, floristic class), and the primary outcome (annual growing-season NDVI median). Test parallel trends on pre-1998 (Fénix) and pre-2015 (Olaroz) periods before estimating treatment effects.

---

## 5. Risks and mitigations

1. **Moran–Corkran trap (most important).** Vegetation lag may be decades; brine pumping may not show up at all. Mitigations: (a) treatment split into brine-well vs freshwater-well distance — if Corkran is right we expect the freshwater coefficient to be 5–20× the brine one; this is a falsifiable prediction we can test; (b) include 25-year window via Fénix to give long lags room to manifest; (c) commit to publishing a credible null. A null *with* the brine/freshwater decomposition matching Corkran's theory is itself a contribution.
2. **Castro Sardiña 2023 already published null result.** We need to clearly explain in the introduction why our design is more informative: multiple operations, staggered timing, continuous distance treatment, climate-conditional parallel trends, InSAR co-evidence. The 2024 Annual Reviews synthesis flagged remote sensing as underused; we lean on that framing.
3. **SUTVA violation by within-basin groundwater flow.** Bofedales in the same salar share aquifers — treatment "spills over" to within-salar controls. Mitigation: controls drawn only from *different* unmined salars; never within-salar.
4. **Endogenous mine siting.** Mines are sited where brine reserves are richest, which correlates with basin hydrology, which correlates with bofedal abundance. Mitigation: control set restricted to USGS prospective-but-unmined salars (44 in the geodatabase), which were prospective enough to be assessed but didn't proceed; this is much closer to comparable than "any non-mining basin."
5. **InSAR salt-crust coherence loss.** C-band Sentinel-1 loses coherence on salt surfaces. Mitigations: SAOCOM L-band where available; PSI/SBAS rather than DInSAR; focus InSAR analysis on bofedal areas rather than salar interior (where the coherence problem is worst); cross-validate against Bonadeo 2024 published values.
6. **MapBiomas / Izquierdo polygon boundary errors.** Both products have boundary errors at bofedal edges. Mitigation: hand-validation in Stage 1, polygon-mean (not pixel-edge) extraction in Stage 3.
7. **No Argentine station data for bias correction.** CHIRPS bias correction in the Puna is limited by the near-absence of weather stations. Mitigation: use MSWEP as alternative; report all estimates under multiple precipitation products as robustness.

---

## 6. What we explicitly are *not* doing

- **Not MODIS.** 250 m is too coarse for bofedal polygons. MODIS LST as a secondary outcome only.
- **Not hexagons.** Aggregation unit is bofedal polygon, period.
- **Not OLS trend per unit.** Identification is via CS-DiD or spatial RDD.
- **Not single-basin analysis.** The Liu 2019 approach (one basin, one regression) is not a comparable design and we shouldn't replicate it as our own contribution.
- **Not GRACE.** ~300 km footprint is larger than most Argentine salars; not useful at our unit of analysis.
- **Not waiting for ground stations.** No reliable in-situ groundwater or precipitation data is available at scale. Remote sensing + bias-corrected reanalysis is the best available.

---

## 7. Datasets to acquire (Stage 0 checklist)

- [ ] **USGS Lithium Triangle geodatabase** (DOI 10.5066/P9RLUH4F) — Argentine salars + Li occurrences + facilities.
- [ ] **Izquierdo, Foguet & Grau 2016 hydroecosystem polygons** (CONICET handle 11336/58267).
- [ ] **2026 global high-altitude wetland map** (Zenodo record 18339573, *Sci Data* s41597-026-07020-w).
- [ ] **MapBiomas Argentina Collection 2 — Puna y Altos Andes** via GEE.
- [ ] **Global SPEI 1982–2021** (*Sci Data* s41597-024-03047-z).
- [ ] **CHIRPS v2, ERA5-Land, MSWEP** monthly precipitation via GEE.
- [ ] **HLS (harmonized Landsat–Sentinel)** NDVI / NDWI via GEE or LP DAAC.
- [ ] **Sentinel-1 LiCSAR** frames covering all Argentine lithium salars; **LiCSBAS** for processing.
- [ ] **SAOCOM L-band** scenes via CONAE (Argentine national space agency — local access advantage).
- [ ] **Paz et al. 2025 Heliyon water-footprint reverse-engineered data** for Olaroz and Fénix.
- [ ] **FARN reports** — Marchegiani et al. 2019 + Sal de Vida 2023 — for testimony geocoding.

---

## 8. Key references (deep research subset)

**Bofedal mapping**
- Izquierdo, Foguet & Grau 2016, *Ecología Austral*. Argentine Puna hydroecosystems. CONICET handle 11336/58267.
- *Scientific Data* 2026, s41597-026-07020-w. Global 30 m high-altitude wetland map.
- Carilla et al. 2023, *Frontiers in Plant Science*, 10.3389/fpls.2022.1067096. Andean vegetation under hydroclimate variability.

**Causal identification**
- Callaway & Sant'Anna 2021, *J Econometrics*. Staggered DiD with multiple time periods.
- Fick et al. 2021, *Ecological Applications*, 10.1002/eap.2264. Synthetic control with remote sensing.
- Credit & Yiannakoulias 2023, *J Geographical Systems*. Spatial T-learner with causal forests.

**Lithium mining hydrology & impact**
- Liu, Agusdinata & Myint 2019, *IJAEOG* 80, 10.1016/j.jag.2019.04.016. Atacama, correlative.
- Chavez et al. 2022, *IJAEOG* 116, 10.1016/j.jag.2022.103138. Atacama peatland NDVI anomalies.
- Moran et al. 2022, *Earth's Future*, 10.1029/2021EF002555. Relic groundwater confounds attribution.
- Corkran et al. 2025, *Water Resources Research*, 10.1029/2024WR039511. **Brine vs freshwater impact decomposition — must read.**
- Kirshen et al. 2025, *Comm. Earth & Env.* s43247-025-02130-6. Freshwater inflows to closed Andean basins; global model bias.
- Paz et al. 2025, *Heliyon* S2405844025009030. Water footprint of Olaroz and Fénix.
- Castro Sardiña et al. 2023, *Sci of Total Env* S014019632300054X. **The competitor null result we must improve on.**

**InSAR**
- Bonadeo et al. 2024, IEEE 10530767. Salar de Olaroz subsidence 2018–2020.
- Delgado et al. 2024, IEEE TGRS, 10.1109/TGRS.2024.3423792. SAOCOM L-band anthropogenic deformation.
- LiCSAR/LiCSBAS — github.com/yumorishita/LiCSBAS.

**Mining footprint**
- *Sustainability* 2025, mdpi 17/12/5631. SVM pond delineation, R²=0.91. SOTA replacement for ISODATA.
- USGS DOI 10.5066/P9RLUH4F. Lithium Triangle geodatabase.

**Argentine community / political ecology**
- Marchegiani, Hellgren & Gómez 2019, FARN.
- FARN 2023, *Sal de Vida: A risky lithium mining project in Argentina*.
- Argento, Göbel, Yufra & Christel — recent ethnographic and conflict-mapping work (post-2022).
- Salica et al. 2024, *Aquatic Conservation*, 10.1002/aqc.4044. Frog populations under lithium pressure.

---

## 9. Open questions for discussion

1. Should the **first deliverable** be the panel-level paper (Stages 0–4a, 6) and the InSAR + case study (4b, 5) be a follow-up, or should we hold for the integrated version?
2. Do we want to include **Chilean Atacama operations** as additional treatment units for power, or strictly limit to Argentina?
3. The **floristic stratification** doubles the analysis size — worth it for the paper, or robustness only?
4. Pre-registration — informal (just our own commitment document) or formal (OSF / AEA registry)?
5. Who handles the **InSAR processing** — we do LiCSBAS ourselves, or collaborate with someone who has the pipeline already running (Bonadeo's group, ASF, COMET)?
