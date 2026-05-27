> **Note (May 2026):** The notebooks listed below implement Methodology v1
> (MODIS NDVI on H3 hexagons) and are superseded by Methodology v2. New v2
> work lives under `src/acquisition/` and `notebooks/v2_acquisition.ipynb`.
> See [text/Methodology_v2.md](../text/Methodology_v2.md) and the Stage 0
> spec at
> [docs/superpowers/specs/2026-05-26-stage-0-tier1-acquisition-design.md](../docs/superpowers/specs/2026-05-26-stage-0-tier1-acquisition-design.md).

# Overview over notebooks in this folder

- [Overview over notebooks in this folder](#overview-over-notebooks-in-this-folder)
  - [H3-Hexagons.ipynb](#h3-hexagonsipynb)
  - [Data-Acquisition.ipynb](#data-acquisitionipynb)
    - [Yearly Medians (2000-2022)](#yearly-medians-2000-2022)
    - [For Quarters](#for-quarters)
      - [Concatenator.ipynb](#concatenatoripynb)
  - [Data-Viz.ipynb](#data-vizipynb)
  - [seasonal\_analysis.ipynb](#seasonal_analysisipynb)
  - [Basin\_mapping.ipynb](#basin_mappingipynb)

## H3-Hexagons.ipynb
Fits H3 Hexagons to the area, based on Argentinan data of cuencos: 
- Salar di Cauchari
- Laguna de Guayatayoc
- Salar de Olaroz
- Salinas Grandes de Jujuy y Salta

And stores them at: "Lithium/Data/lithium_hexagons_res6.geojson"

## Data-Acquisition.ipynb
Downloads MODIS Combined 16-Day NDVI from: https://developers.google.com/earth-engine/datasets/catalog/MODIS_MCD43A4_006_NDVI

### Yearly Medians (2000-2022)
Stores data at "Lithium/Data/NDVI_Annual_Median_batch_1_of_1.geojson"
### For Quarters
Downloads data for quarters and stores them as batches at: "Lithium/Data/NDVI_Seasonal"
#### Concatenator.ipynb
Accesses batched data and stores them in a single geojson.
Stores data at "Lithium/Data/lithium_ndvi_seasonal.geojson"

## Data-Viz.ipynb
Visualises the annual median data as trends from 2000-2022

## seasonal_analysis.ipynb
Visualises the seasonal data 

## Basin_mapping.ipynb
Initial analysis of the cuencas 
