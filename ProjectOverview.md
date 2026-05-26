After meeting on 29.12.2026, we decided to take stock of what we have and what needs to be done next. 

## Basic idea 
Is given in the pdf text/Mining_Impact_Proposal.pdf
Summarises the core idea and gives overview over the literature, and possible data sources, methods.

## Methodology v2 (May 2026)
The v1 approach (MODIS NDVI on H3 hexagons, OLS trends) did not work — see autopsy in `text/Methodology_v2.md`. v2 pivots to a bofedal-polygon panel with staggered DiD and spatial RDD, splitting treatment into brine-well vs freshwater-well distance per Corkran et al. 2025, with Sentinel-1 InSAR as independent validation. Full spec in `text/Methodology_v2.md`.


## Data Acquistion: 
We have to create the basic data for the analysis.
The data has 4 dimensions. 
1. Basins:
   We decided on the Data set of COHIFE, extend data acquistion to all endorheic basins in the Puna
2. Environmental Indicators:
   Decision about which Environmental Indicator to pick.
3. Mining activity:
   Decide on measure, but extend might be the easiest to measure
4. Precipation Data:
   Decide on measure

## Data Analysis
After data acquistion, we should explore statisitical methods to run on top of descriptive analysis (Regression, Diff-in-Diff etc.)
