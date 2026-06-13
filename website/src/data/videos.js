// Tutorial video catalog. `youtubeId: null` renders a "coming soon" placeholder;
// fill in the ID once the video is published.
export default [
  {
    id: 'intro',
    category: 'start',
    youtubeId: 'ju4jlqBOt4k',
    start: 2,
    wiki: 'getting-started',
    title: {
      'en-US': 'FARM tools introduction',
      'pt-BR': 'Introdução ao FARM tools',
    },
    desc: {
      'en-US': 'What FARM tools is, the seven modules, and a quick tour of the interface.',
      'pt-BR': 'O que é o FARM tools, os sete módulos e um tour rápido pela interface.',
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
      'en-US': 'Install from the QGIS Plugin Manager, create a Google Cloud project, and sign in to Google Earth Engine.',
      'pt-BR': 'Instale pelo Gerenciador de Plugins do QGIS, crie um projeto Google Cloud e autentique-se no Google Earth Engine.',
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
      'en-US': 'Draw an AOI on the canvas or load it from an existing vector layer — the starting point of every module.',
      'pt-BR': 'Desenhe uma AOI no mapa ou carregue de uma camada vetorial existente — o ponto de partida de todos os módulos.',
    },
  },
  {
    id: 'optical-timeseries',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Sentinel-2 vegetation index time series',
      'pt-BR': 'Séries temporais de índices de vegetação Sentinel-2',
    },
    desc: {
      'en-US': 'Build NDVI, EVI, SAVI, and GNDVI time series with cloud (SCL) filtering and interactive charts.',
      'pt-BR': 'Monte séries temporais de NDVI, EVI, SAVI e GNDVI com filtragem de nuvens (SCL) e gráficos interativos.',
    },
  },
  {
    id: 'optical-download',
    category: 'imagery',
    youtubeId: null,
    wiki: 'optical',
    title: {
      'en-US': 'Composites & multispectral download',
      'pt-BR': 'Composições & download multiespectral',
    },
    desc: {
      'en-US': 'Preview RGB and index composites, then batch-download multispectral GeoTIFFs for your AOI.',
      'pt-BR': 'Visualize composições RGB e de índices e baixe GeoTIFFs multiespectrais em lote para sua AOI.',
    },
  },
  {
    id: 'landsat',
    category: 'imagery',
    youtubeId: null,
    wiki: 'landsat',
    title: {
      'en-US': 'Landsat long-term series & downloads',
      'pt-BR': 'Séries longas & downloads Landsat',
    },
    desc: {
      'en-US': 'Decades of Landsat history: time series, scene preview, batch and super-resolution downloads.',
      'pt-BR': 'Décadas de histórico Landsat: séries temporais, pré-visualização de cenas, downloads em lote e super-resolução.',
    },
  },
  {
    id: 'sar',
    category: 'imagery',
    youtubeId: null,
    wiki: 'sar',
    title: {
      'en-US': 'Sentinel-1 SAR backscatter analysis',
      'pt-BR': 'Análise de retroespalhamento SAR Sentinel-1',
    },
    desc: {
      'en-US': 'Radar that sees through clouds: retrieve, filter, plot, and render Sentinel-1 backscatter.',
      'pt-BR': 'Radar que enxerga através das nuvens: obtenha, filtre, plote e renderize o retroespalhamento Sentinel-1.',
    },
  },
  {
    id: 'dem',
    category: 'terrain',
    youtubeId: null,
    wiki: 'dem',
    title: {
      'en-US': 'DEM download & terrain products',
      'pt-BR': 'Download de DEM & produtos de terreno',
    },
    desc: {
      'en-US': 'Browse the elevation catalog, download a DEM for your AOI, and render hillshade and terrain styles.',
      'pt-BR': 'Navegue pelo catálogo de elevação, baixe um DEM para sua AOI e renderize sombreamento e estilos de terreno.',
    },
  },
  {
    id: 'sysi',
    category: 'terrain',
    youtubeId: null,
    wiki: 'sysi',
    title: {
      'en-US': 'SYSI synthetic bare-soil composites',
      'pt-BR': 'Composições sintéticas de solo exposto SYSI',
    },
    desc: {
      'en-US': 'Generate a synthetic bare-soil image with GEOS3 multi-temporal detection for soil mapping.',
      'pt-BR': 'Gere uma imagem sintética de solo exposto com detecção multitemporal GEOS3 para mapeamento de solos.',
    },
  },
  {
    id: 'climaplots',
    category: 'terrain',
    youtubeId: null,
    wiki: 'climaplots',
    title: {
      'en-US': 'ClimaPlots: NASA POWER climate charts',
      'pt-BR': 'ClimaPlots: gráficos climáticos NASA POWER',
    },
    desc: {
      'en-US': 'Plot precipitation, temperature, and other NASA POWER climate series alongside your vegetation data.',
      'pt-BR': 'Plote precipitação, temperatura e outras séries climáticas NASA POWER junto aos seus dados de vegetação.',
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
      'en-US': 'Capture points on the map, enter coordinates manually, and generate sampling designs per parcel.',
      'pt-BR': 'Capture pontos no mapa, insira coordenadas manualmente e gere planos de amostragem por talhão.',
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
      'en-US': 'Place one point per polygon at the raster maximum — objective, reproducible sampling locations.',
      'pt-BR': 'Posicione um ponto por polígono no máximo do raster — locais de amostragem objetivos e reproduzíveis.',
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
      'en-US': 'Open Google Maps routes and export your session as CSV, GPX waypoints, a QGIS layer, or a phone-friendly PDF.',
      'pt-BR': 'Abra rotas no Google Maps e exporte sua sessão como CSV, waypoints GPX, camada QGIS ou PDF para celular.',
    },
  },
]
