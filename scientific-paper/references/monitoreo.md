# When the results come from MonitorEO

(Optional page: it applies only to papers that use results of MonitorEO, https://github.com/monitoreo-obsnev/monitoreo. Delete it, and its mention at the end of `SKILL.md`, if you do not use MonitorEO.)

MonitorEO (Observatorio de Cambio Global de Sierra Nevada, University of Granada) computes maps, series, trends,
comparisons and burn severity of satellite variables in Google Earth Engine. The results come with what the paper
needs; take it from them, do not write it from memory.

## Cite

- MonitorEO: Observatorio de Cambio Global de Sierra Nevada (2026). MonitorEO [Software]. Zenodo.
  https://doi.org/10.5281/zenodo.23814894 (the version of the release used: each release has its own DOI on Zenodo;
  the tool `about` and the repository's `CITATION.cff` give the current one).
- Google Earth Engine: Gorelick, N., Hancher, M., Dixon, M., Ilyushchenko, S., Thau, D., & Moore, R. (2017). Google
  Earth Engine: Planetary-scale geospatial analysis for everyone. *Remote Sensing of Environment*, 202, 18–27.
  https://doi.org/10.1016/j.rse.2017.06.031
- Every result carries `references` and `credits`: the references (with DOI) of the formula or algorithm of each
  variable, of its Earth Engine datasets (as the dataset's page in the Earth Engine catalog suggests), of the pixel
  filters, of the method (Mann-Kendall and Sen, burn severity) and of the region (WDPA, RESOLVE, FAO GAUL, Global
  Islands). Include **all of them, as they are**, in the bibliography, and cite each where it is used. The credit lines
  that the terms of use of the data ask for (Copernicus Sentinel, USGS Landsat, Copernicus DEM, MERIT Hydro, FAO GAUL,
  RESOLVE) go in the acknowledgements or the figure captions.
- Funding, when the journal asks (EVEREST, NevadEO, PRESINMED): the text is in the description of the MonitorEO tool
  `about`; copy it, do not paraphrase it.

## Take the methods and numbers from the files

- Each file that a tool writes has a **README** next to it: what each column or band is, its **unit in UDUNITS**, how it
  was computed, how to reproduce it and how to cite it. Put units in the paper in SI notation (`mm d-1` becomes
  `mm d$^{-1}$`), as the UDUNITS name says.
- The results say which data they come from (`data_source`: collection and product level) and their charts say it in a
  line «Data: ...»: give it in the methods. Report the period and the **warnings** of the result (days without images,
  periods before the first image of a sensor): they limit what the paper can claim.
- The results include the **parameters** of the analysis as JSON (`save_parameters`): put them in the supplement, or
  cite the deposited file, so that anyone can repeat the analysis in any tool (`apply_parameters`).
- The manual of each variable (its wiki page, in English and Spanish) says what it is and how it is computed; link it
  in the supplement, and describe the formula in the paper from the catalog's references, not from the wiki.
- Say the **version of MonitorEO** (and the release date) used, and the date the Earth Engine data were computed: the
  data of Earth Engine may gain images afterwards.

## Do not

- Do not report a variable without its sensor, its pixel size and its pixel filters (clouds, water, snow, aerosols).
- Do not compare periods across Landsat 5 and Landsat 8 as if they were one sensor: the app does not harmonize them
  (the residual difference is documented); say it in the limits.
- Do not present trends without the test and the p-value (Mann-Kendall, Sen's slope), or burn severity classes without
  the index and its thresholds (dNBR, RBR, RdNBR).
