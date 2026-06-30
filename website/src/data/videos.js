// Tutorial video catalog. `youtubeId: null` renders a "coming soon" placeholder;
// fill in the ID once the video is published. Every entry maps to one feature of
// a module and is scoped for a 2–5 minute clip. Categories drive grouping on the
// Tutorials page (see CATEGORY_ORDER in TutorialsPage.vue).
export default [
  // ── Getting started ──────────────────────────────────────────────
  {
    id: 'intro',
    category: 'start',
    youtubeId: 'UqRL-3Tv3no',
    wiki: 'getting-started',
    title: {
      'en-US': 'FARM tools introduction',
      'pt-BR': 'Introdução ao FARM tools',
    },
    desc: {
      'en-US': 'What FARM tools is, the eight modules, and a quick tour of the interface. (~3 min)',
      'pt-BR': 'O que é o FARM tools, os oito módulos e um tour rápido pela interface. (~3 min)',
    },
  },
  {
    id: 'install-auth',
    category: 'start',
    youtubeId: null,
    wiki: 'getting-started',
    title: {
      'en-US': 'Installation & GEE authentication',
      'pt-BR': 'Instalação & autenticação no GEE',
    },
    desc: {
      'en-US': 'Install from the QGIS Plugin Manager, create a Google Cloud project, and sign in to Google Earth Engine via personal OAuth or a service account. (~5 min)',
      'pt-BR': 'Instale pelo Gerenciador de Plugins do QGIS, crie um projeto Google Cloud e autentique-se no Google Earth Engine via OAuth pessoal ou conta de serviço. (~5 min)',
    },
  },
  {
    id: 'aoi',
    category: 'start',
    youtubeId: null,
    wiki: 'getting-started',
    title: {
      'en-US': 'Defining your area of interest',
      'pt-BR': 'Definindo sua área de interesse',
    },
    desc: {
      'en-US': 'Draw an AOI on the canvas or load it from a vector layer; how it is reprojected to WGS84 so any project CRS works — the starting point of every module. (~3 min)',
      'pt-BR': 'Desenhe uma AOI no mapa ou carregue de uma camada vetorial; como ela é reprojetada para WGS84 para qualquer CRS funcionar — o ponto de partida de todos os módulos. (~3 min)',
    },
  },

  // ── Imagery & time series — Optical (Sentinel-2) ─────────────────
  {
    id: 'optical-timeseries',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: vegetation index time series',
      'pt-BR': 'Óptico: séries temporais de índices de vegetação',
    },
    desc: {
      'en-US': 'Build a Sentinel-2 index time series over your AOI, with one-scene-per-date deduplication and an interactive date-by-date chart. (~4 min)',
      'pt-BR': 'Monte uma série temporal de índice Sentinel-2 sobre sua AOI, com deduplicação de uma cena por data e gráfico interativo data a data. (~4 min)',
    },
  },
  {
    id: 'optical-indices',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: choosing among 19 spectral indices',
      'pt-BR': 'Óptico: escolhendo entre 19 índices espectrais',
    },
    desc: {
      'en-US': 'When to use NDVI, EVI/EVI2, SAVI/MSAVI, red-edge and chlorophyll indices (NDRE, ReCI, MTCI), moisture and burn indices — and how to define your own custom index. (~5 min)',
      'pt-BR': 'Quando usar NDVI, EVI/EVI2, SAVI/MSAVI, índices de red-edge e clorofila (NDRE, ReCI, MTCI), de umidade e de queimada — e como definir seu próprio índice customizado. (~5 min)',
    },
  },
  {
    id: 'optical-quality',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: cloud masking, quality filters & smoothing',
      'pt-BR': 'Óptico: máscara de nuvens, filtros de qualidade & suavização',
    },
    desc: {
      'en-US': 'Apply the SCL cloud/shadow mask, screen dates by tile cloud, in-AOI valid-pixel % and footprint coverage, and de-noise the curve with a Savitzky-Golay filter. (~5 min)',
      'pt-BR': 'Aplique a máscara de nuvem/sombra SCL, filtre datas por nuvem do tile, % de pixels válidos na AOI e cobertura da cena, e suavize a curva com filtro Savitzky-Golay. (~5 min)',
    },
  },
  {
    id: 'optical-points',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: point & per-field sampling',
      'pt-BR': 'Óptico: amostragem por ponto & por talhão',
    },
    desc: {
      'en-US': 'Extract the single-pixel series under a clicked point and a per-feature mean series per polygon, all plotted against the AOI-average reference curve. (~4 min)',
      'pt-BR': 'Extraia a série do pixel sob um ponto clicado e a série média por feição de cada polígono, plotadas contra a curva de referência média da AOI. (~4 min)',
    },
  },
  {
    id: 'optical-single-date',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: single-date RGB & index rasters',
      'pt-BR': 'Óptico: rasters RGB & de índice por data',
    },
    desc: {
      'en-US': 'Render any date as a true/false-colour RGB composite or a single-index pseudocolour raster, clipped to the AOI and exported as 10 m GeoTIFF. (~4 min)',
      'pt-BR': 'Renderize qualquer data como composição RGB em cor verdadeira/falsa ou raster pseudocolor de um índice, recortado na AOI e exportado como GeoTIFF de 10 m. (~4 min)',
    },
  },
  {
    id: 'optical-composite',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: composites & Area-Under-Curve maps',
      'pt-BR': 'Óptico: composições & mapas de Área-Sob-a-Curva',
    },
    desc: {
      'en-US': 'Collapse the season into one map — mean, median, min/max, amplitude, standard deviation, sum, or the trapezoidal AUC as a cumulative-productivity proxy. (~5 min)',
      'pt-BR': 'Resuma a safra em um mapa — média, mediana, mín/máx, amplitude, desvio-padrão, soma ou a AUC trapezoidal como proxy de produtividade acumulada. (~5 min)',
    },
  },
  {
    id: 'optical-download',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: multispectral batch download',
      'pt-BR': 'Óptico: download multiespectral em lote',
    },
    desc: {
      'en-US': 'Batch-download the full multispectral stack (or selected bands) for every displayed date as GeoTIFF, on a background thread that keeps QGIS responsive. (~3 min)',
      'pt-BR': 'Baixe em lote a pilha multiespectral completa (ou bandas selecionadas) de cada data exibida como GeoTIFF, em segundo plano sem travar o QGIS. (~3 min)',
    },
  },
  {
    id: 'optical-climate',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Optical: rainfall overlay on the index chart',
      'pt-BR': 'Óptico: sobreposição de chuva no gráfico de índice',
    },
    desc: {
      'en-US': 'Overlay NASA POWER monthly precipitation bars beneath the vegetation curve to relate green-up and stress to weather on a shared time axis. (~3 min)',
      'pt-BR': 'Sobreponha barras de precipitação mensal NASA POWER sob a curva de vegetação para relacionar verdejamento e estresse ao clima no mesmo eixo temporal. (~3 min)',
    },
  },

  // ── Imagery & time series — Landsat ──────────────────────────────
  {
    id: 'landsat-timeseries',
    category: 'imagery',
    youtubeId: null,
    wiki: 'landsat',
    title: {
      'en-US': 'Landsat: multi-mission time series (1999→now)',
      'pt-BR': 'Landsat: série temporal multimissão (1999→hoje)',
    },
    desc: {
      'en-US': 'Build a Landsat 7/8/9 Surface-Reflectance index series over the AOI, merged into one chronological record colour-coded by mission. (~4 min)',
      'pt-BR': 'Monte uma série de índice em Refletância de Superfície Landsat 7/8/9 sobre a AOI, mesclada em um registro cronológico colorido por missão. (~4 min)',
    },
  },
  {
    id: 'landsat-pansharpen',
    category: 'imagery',
    youtubeId: null,
    wiki: 'landsat',
    title: {
      'en-US': 'Landsat: 15 m HSV pan-sharpened true colour',
      'pt-BR': 'Landsat: cor verdadeira pan-sharpened HSV 15 m',
    },
    desc: {
      'en-US': 'How HSV pan-sharpening swaps the 15 m panchromatic band into the brightness channel to double apparent detail of the TOA true-colour image. (~4 min)',
      'pt-BR': 'Como o pan-sharpening HSV troca a banda pancromática de 15 m no canal de brilho para dobrar o detalhe aparente da imagem TOA em cor verdadeira. (~4 min)',
    },
  },
  {
    id: 'landsat-indices',
    category: 'imagery',
    youtubeId: null,
    wiki: 'landsat',
    title: {
      'en-US': 'Landsat: SR indices & multispectral composites',
      'pt-BR': 'Landsat: índices SR & composições multiespectrais',
    },
    desc: {
      'en-US': 'The 14 Surface-Reflectance indices (NDVI, EVI, SAVI/OSAVI/MSAVI, BSI, MNDWI…) and the four band combinations (real colour, CIR, SWIR composites). (~5 min)',
      'pt-BR': 'Os 14 índices em Refletância de Superfície (NDVI, EVI, SAVI/OSAVI/MSAVI, BSI, MNDWI…) e as quatro combinações de bandas (cor real, falsa-cor, composições SWIR). (~5 min)',
    },
  },
  {
    id: 'landsat-download',
    category: 'imagery',
    youtubeId: null,
    wiki: 'landsat',
    title: {
      'en-US': 'Landsat: scene preview, batch & super-resolution',
      'pt-BR': 'Landsat: pré-visualização, lote & super-resolução',
    },
    desc: {
      'en-US': 'Browse cloud-masked scenes that pass the minimum-valid-coverage filter, preview on the canvas, and download in batch or at super-resolution. (~4 min)',
      'pt-BR': 'Navegue por cenas mascaradas que passam no filtro de cobertura mínima válida, pré-visualize no mapa e baixe em lote ou em super-resolução. (~4 min)',
    },
  },

  // ── Imagery & time series — SAR (Sentinel-1) ─────────────────────
  {
    id: 'sar-backscatter',
    category: 'imagery',
    youtubeId: null,
    wiki: 'sar',
    title: {
      'en-US': 'SAR: backscatter time series in dB',
      'pt-BR': 'SAR: série temporal de retroespalhamento em dB',
    },
    desc: {
      'en-US': 'What VV/VH backscatter measures, why the orbit is fixed to descending, and how to read the cloud-free AOI-mean dB time series. (~4 min)',
      'pt-BR': 'O que o retroespalhamento VV/VH mede, por que a órbita é fixada em descendente e como ler a série temporal média da AOI em dB, livre de nuvens. (~4 min)',
    },
  },
  {
    id: 'sar-ard',
    category: 'imagery',
    youtubeId: null,
    wiki: 'sar',
    title: {
      'en-US': 'SAR: the Analysis-Ready Data pipeline',
      'pt-BR': 'SAR: o pipeline de Dados Prontos para Análise (ARD)',
    },
    desc: {
      'en-US': 'Border-noise removal, multi-temporal Gamma-MAP speckle filtering, and radiometric terrain flattening — why each step makes scenes comparable through time. (~5 min)',
      'pt-BR': 'Remoção de ruído de borda, filtragem de speckle Gamma-MAP multitemporal e nivelamento radiométrico de terreno — por que cada etapa torna as cenas comparáveis no tempo. (~5 min)',
    },
  },
  {
    id: 'sar-indices',
    category: 'imagery',
    youtubeId: null,
    wiki: 'sar',
    title: {
      'en-US': 'SAR: nine dual-polarization indices',
      'pt-BR': 'SAR: nove índices de dupla polarização',
    },
    desc: {
      'en-US': 'RVI, DpRVI, CR, NDPI, PD, DPSVIm, PRVI and mRVI — which track vegetation growth vs. change in scattering regime, and the linear-vs-dB scaling caveat. (~5 min)',
      'pt-BR': 'RVI, DpRVI, CR, NDPI, PD, DPSVIm, PRVI e mRVI — quais acompanham o crescimento da vegetação vs. mudança no regime de espalhamento, e a ressalva de escala linear vs. dB. (~5 min)',
    },
  },
  {
    id: 'sar-composites',
    category: 'imagery',
    youtubeId: null,
    wiki: 'sar',
    title: {
      'en-US': 'SAR: single-date images, composites & rendering',
      'pt-BR': 'SAR: imagens por data, composições & renderização',
    },
    desc: {
      'en-US': 'Export a single date or a composite (mean/median/amplitude/AUC…), and choose RGB qualitative vs. single-band pseudocolour quantitative rendering. (~4 min)',
      'pt-BR': 'Exporte uma data única ou uma composição (média/mediana/amplitude/AUC…) e escolha renderização RGB qualitativa vs. pseudocolor quantitativa de banda única. (~4 min)',
    },
  },

  // ── Land cover & change — MapBiomas ──────────────────────────────
  {
    id: 'mapbiomas-coverage',
    category: 'landcover',
    youtubeId: null,
    wiki: 'mapbiomas',
    title: {
      'en-US': 'MapBiomas: annual land-cover coverage (1985–2023)',
      'pt-BR': 'MapBiomas: cobertura anual da terra (1985–2023)',
    },
    desc: {
      'en-US': 'Step through 39 annual Collection 9 classifications with the year slider, read the official 63-class legend, and download a year as a styled classification raster. (~4 min)',
      'pt-BR': 'Percorra as 39 classificações anuais da Coleção 9 com o controle de ano, leia a legenda oficial de 63 classes e baixe um ano como raster de classificação estilizado. (~4 min)',
    },
  },
  {
    id: 'mapbiomas-transitions',
    category: 'landcover',
    youtubeId: null,
    wiki: 'mapbiomas',
    title: {
      'en-US': 'MapBiomas: first-transition-year analysis',
      'pt-BR': 'MapBiomas: análise do primeiro ano de transição',
    },
    desc: {
      'en-US': 'Map when each pixel first changed source→target (presets like pasture→crop or deforestation, or custom classes) and chart the converted hectares per year. (~5 min)',
      'pt-BR': 'Mapeie quando cada pixel mudou origem→destino (predefinições como pastagem→lavoura ou desmatamento, ou classes personalizadas) e gráfico de hectares convertidos por ano. (~5 min)',
    },
  },

  // ── Terrain, soil & climate — DEM ────────────────────────────────
  {
    id: 'dem-catalog',
    category: 'terrain',
    youtubeId: null,
    wiki: 'dem',
    title: {
      'en-US': 'DEM: browsing the elevation catalog',
      'pt-BR': 'DEM: navegando pelo catálogo de elevação',
    },
    desc: {
      'en-US': 'How the ~30-dataset catalog is filtered to only the products that truly cover your AOI, and how to choose DTM vs DSM for the job. (~4 min)',
      'pt-BR': 'Como o catálogo de ~30 conjuntos é filtrado para apenas os produtos que realmente cobrem sua AOI, e como escolher DTM vs DSM para o objetivo. (~4 min)',
    },
  },
  {
    id: 'dem-download',
    category: 'terrain',
    youtubeId: null,
    wiki: 'dem',
    title: {
      'en-US': 'DEM: clip, buffer, export & Magma rendering',
      'pt-BR': 'DEM: recorte, buffer, exportação & renderização Magma',
    },
    desc: {
      'en-US': 'Buffer the AOI ±300 m, export a 30 m elevation GeoTIFF masked to the polygon, and read the perceptually-uniform Magma elevation styling. (~4 min)',
      'pt-BR': 'Aplique buffer de ±300 m à AOI, exporte um GeoTIFF de elevação de 30 m mascarado pelo polígono e leia a estilização Magma de elevação perceptualmente uniforme. (~4 min)',
    },
  },

  // ── Terrain, soil & climate — SYSI bare soil ─────────────────────
  {
    id: 'sysi-generate',
    category: 'terrain',
    youtubeId: null,
    wiki: 'sysi',
    title: {
      'en-US': 'SYSI: generating a synthetic bare-soil image',
      'pt-BR': 'SYSI: gerando uma imagem sintética de solo exposto',
    },
    desc: {
      'en-US': 'How GEOS3 keeps only genuine bare-soil pixels across years and a temporal median fills gaps into one seamless 9-band, 10 m soil-reflectance image. (~5 min)',
      'pt-BR': 'Como o GEOS3 mantém apenas pixels de solo realmente exposto ao longo dos anos e uma mediana temporal preenche lacunas em uma imagem contínua de refletância de solo de 9 bandas e 10 m. (~5 min)',
    },
  },
  {
    id: 'sysi-tuning',
    category: 'terrain',
    youtubeId: null,
    wiki: 'sysi',
    title: {
      'en-US': 'SYSI: tuning months, thresholds & reading the result',
      'pt-BR': 'SYSI: ajustando meses, limiares & lendo o resultado',
    },
    desc: {
      'en-US': 'Restrict to the fallow/tillage months, set the NDVI and NBR2 ranges, and interpret soil colour (iron oxides, organic matter, sandy/eroded surfaces). (~5 min)',
      'pt-BR': 'Restrinja aos meses de pousio/preparo, defina as faixas de NDVI e NBR2 e interprete a cor do solo (óxidos de ferro, matéria orgânica, superfícies arenosas/erodidas). (~5 min)',
    },
  },

  // ── Terrain, soil & climate — ClimaPlots ─────────────────────────
  {
    id: 'climaplots-intro',
    category: 'terrain',
    youtubeId: null,
    wiki: 'climaplots',
    title: {
      'en-US': 'ClimaPlots: data sources & comparing two points',
      'pt-BR': 'ClimaPlots: fontes de dados & comparando dois pontos',
    },
    desc: {
      'en-US': 'Pick a point and a year range, choose NASA POWER (1981→) or ERA5/Open-Meteo (1940→), and overlay a second point B — even from the other dataset. (~4 min)',
      'pt-BR': 'Escolha um ponto e um intervalo de anos, selecione NASA POWER (1981→) ou ERA5/Open-Meteo (1940→) e sobreponha um segundo ponto B — mesmo do outro conjunto de dados. (~4 min)',
    },
  },
  {
    id: 'climaplots-trends',
    category: 'terrain',
    youtubeId: null,
    wiki: 'climaplots',
    title: {
      'en-US': 'ClimaPlots: annual trends, Mann–Kendall & Pettitt',
      'pt-BR': 'ClimaPlots: tendências anuais, Mann–Kendall & Pettitt',
    },
    desc: {
      'en-US': 'Read the annual trend chart and the two non-parametric verdicts: the Mann–Kendall trend direction/p-value and the Pettitt change-point year. (~5 min)',
      'pt-BR': 'Leia o gráfico de tendência anual e os dois veredictos não-paramétricos: direção/p-valor da tendência de Mann–Kendall e o ano de ponto de mudança de Pettitt. (~5 min)',
    },
  },
  {
    id: 'climaplots-walter-lieth',
    category: 'terrain',
    youtubeId: null,
    wiki: 'climaplots',
    title: {
      'en-US': 'ClimaPlots: the thermo-pluviometric diagram',
      'pt-BR': 'ClimaPlots: o diagrama termopluviométrico',
    },
    desc: {
      'en-US': 'Read the Walter–Lieth style climate diagram — monthly rainfall bars vs max/min temperature lines — to find wet/dry seasons and likely water-deficit months. (~3 min)',
      'pt-BR': 'Leia o diagrama climático estilo Walter–Lieth — barras de chuva mensal vs linhas de temperatura máx/mín — para achar estações seca/úmida e meses de provável déficit hídrico. (~3 min)',
    },
  },
  {
    id: 'climaplots-etccdi',
    category: 'terrain',
    youtubeId: null,
    wiki: 'climaplots',
    title: {
      'en-US': 'ClimaPlots: ETCCDI climate-extreme indices',
      'pt-BR': 'ClimaPlots: índices de extremos climáticos ETCCDI',
    },
    desc: {
      'en-US': 'The standardized WMO extreme indices — frost/summer days, TXx/TNn, Rx1day/Rx5day, R10mm, SDII, CDD/CWD — and what their trends say about a changing climate. (~5 min)',
      'pt-BR': 'Os índices de extremos padronizados da OMM — dias de geada/verão, TXx/TNn, Rx1day/Rx5day, R10mm, SDII, CDD/CWD — e o que suas tendências dizem sobre o clima em mudança. (~5 min)',
    },
  },
  {
    id: 'climaplots-spi',
    category: 'terrain',
    youtubeId: null,
    wiki: 'climaplots',
    title: {
      'en-US': 'ClimaPlots: the SPI drought index',
      'pt-BR': 'ClimaPlots: o índice de seca SPI',
    },
    desc: {
      'en-US': 'How the 90-day Standardized Precipitation Index expresses rainfall as a gamma-fitted anomaly, and how to read drought vs wet-spell severity. (~4 min)',
      'pt-BR': 'Como o Índice de Precipitação Padronizada de 90 dias expressa a chuva como anomalia ajustada por gama, e como ler a severidade de seca vs período úmido. (~4 min)',
    },
  },
  {
    id: 'climaplots-et0-gdd',
    category: 'terrain',
    youtubeId: null,
    wiki: 'climaplots',
    title: {
      'en-US': 'ClimaPlots: derived ET0 & Growing Degree Days',
      'pt-BR': 'ClimaPlots: ET0 & Graus-Dia derivados',
    },
    desc: {
      'en-US': 'The two agronomic variables computed from temperature — Hargreaves reference ET0 (water demand) and GDD (accumulated heat) — and how to use them. (~4 min)',
      'pt-BR': 'As duas variáveis agronômicas calculadas a partir da temperatura — ET0 de referência de Hargreaves (demanda hídrica) e Graus-Dia (calor acumulado) — e como usá-las. (~4 min)',
    },
  },

  // ── Fieldwork — Field Guide ──────────────────────────────────────
  {
    id: 'fieldguide-manual',
    category: 'field',
    youtubeId: null,
    wiki: 'fieldguide',
    title: {
      'en-US': 'Field Guide: capture, coordinates & CSV import',
      'pt-BR': 'Guia de Campo: captura, coordenadas & importação CSV',
    },
    desc: {
      'en-US': 'Click points on the canvas, type lat/lon (dot or comma decimals), import a CSV of past points, and manage the session list (remove, delete, append/replace). (~4 min)',
      'pt-BR': 'Clique pontos no mapa, digite lat/lon (vírgula ou ponto decimal), importe um CSV de pontos antigos e gerencie a lista da sessão (remover, excluir, anexar/substituir). (~4 min)',
    },
  },
  {
    id: 'fieldguide-sampling',
    category: 'field',
    youtubeId: null,
    wiki: 'fieldguide',
    title: {
      'en-US': 'Field Guide: point capture & polygon sampling',
      'pt-BR': 'Guia de Campo: captura de pontos & amostragem de polígonos',
    },
    desc: {
      'en-US': 'Generate sampling designs per parcel — fixed count or density per hectare — with centroid, spread-optimized, systematic-grid, or zigzag distribution. (~5 min)',
      'pt-BR': 'Gere planos de amostragem por talhão — contagem fixa ou densidade por hectare — com distribuição por centroide, otimizada, grade sistemática ou zigue-zague. (~5 min)',
    },
  },
  {
    id: 'fieldguide-raster',
    category: 'field',
    youtubeId: null,
    wiki: 'fieldguide',
    title: {
      'en-US': 'Field Guide: raster-optimal points (NDVI peaks)',
      'pt-BR': 'Guia de Campo: pontos ótimos por raster (picos de NDVI)',
    },
    desc: {
      'en-US': 'Place one point per polygon at the raster maximum, with cloud/no-data cleaning and edge-case handling — objective, reproducible sampling locations. (~4 min)',
      'pt-BR': 'Posicione um ponto por polígono no máximo do raster, com limpeza de nuvem/no-data e tratamento de casos extremos — locais de amostragem objetivos e reproduzíveis. (~4 min)',
    },
  },
  {
    id: 'fieldguide-exports',
    category: 'field',
    youtubeId: null,
    wiki: 'fieldguide',
    title: {
      'en-US': 'Field Guide: routes & exports (CSV, GPX, PDF)',
      'pt-BR': 'Guia de Campo: rotas & exportações (CSV, GPX, PDF)',
    },
    desc: {
      'en-US': 'Open Google Maps routes and export your session as CSV, GPX waypoints, a QGIS layer, or a phone-friendly PDF report with tappable per-point cards. (~4 min)',
      'pt-BR': 'Abra rotas no Google Maps e exporte sua sessão como CSV, waypoints GPX, camada QGIS ou relatório PDF para celular com cartões tocáveis por ponto. (~4 min)',
    },
  },
]
