// Precision-agriculture catalog — from the theoretical foundations (spatial
// variability, geostatistics, remote sensing, vegetation indices, variable
// rate) to the applied workflow done in QGIS. Companion to the vendor-neutral
// GIS basics in data/lessons.js.
//
// Videos are Brazilian-Portuguese and deliberately drawn from a range of
// authors (Embrapa/TECGRAF, InCeres, university labs, independent creators).
// Titles/descriptions carry an English fallback so the cards still read in
// either UI language. Categories drive grouping on the Precision-Ag page
// (see CATEGORY_ORDER in PrecisionAgPage.vue).
export default [
  // ── Theoretical foundations ──────────────────────────────────────
  {
    id: 'ap-intro',
    category: 'concepts',
    youtubeId: '7gYDnaAWK14', // TECGRAF AGRO — Eduardo Speranza (Embrapa)
    title: {
      'en-US': 'Precision agriculture in the digital era',
      'pt-BR': 'Agricultura de precisão na era digital',
    },
    desc: {
      'en-US': 'A lecture-style overview of precision agriculture: what it is, the decision cycle, and where it is heading — by a researcher from Embrapa.',
      'pt-BR': 'Uma visão geral em formato de palestra: o que é a agricultura de precisão, o ciclo de decisão e para onde ela caminha — com pesquisador da Embrapa.',
    },
  },
  {
    id: 'ap-variabilidade',
    category: 'concepts',
    youtubeId: 'yveP9GpQ8fk', // Agromax - Agricultura de Precisão
    title: {
      'en-US': 'Spatial & temporal variability',
      'pt-BR': 'Variabilidade espacial & temporal',
    },
    desc: {
      'en-US': 'The core premise: a field is not uniform. Understand spatial and temporal variability and why it justifies site-specific management.',
      'pt-BR': 'A premissa central: o talhão não é uniforme. Entenda a variabilidade espacial e temporal e por que ela justifica o manejo localizado.',
    },
  },
  {
    id: 'geoestatistica',
    category: 'concepts',
    youtubeId: 'E7g2vebIWvQ', // InCeres TV
    title: {
      'en-US': 'Geostatistics & the semivariogram',
      'pt-BR': 'Geoestatística & o semivariograma',
    },
    desc: {
      'en-US': 'The theory behind the maps: spatial dependence, the semivariogram, and how geostatistics turns sample points into surfaces. Webinar by InCeres.',
      'pt-BR': 'A teoria por trás dos mapas: dependência espacial, o semivariograma e como a geoestatística transforma pontos amostrais em superfícies. Webinar InCeres.',
    },
  },
  {
    id: 'sensoriamento',
    category: 'concepts',
    youtubeId: 'GO5LA8r_x2I', // Agricultura Sustentável
    title: {
      'en-US': 'Remote sensing fundamentals',
      'pt-BR': 'Fundamentos do sensoriamento remoto',
    },
    desc: {
      'en-US': 'How remote sensing works — the electromagnetic spectrum, sensors and platforms — and what it measures about crops and soil.',
      'pt-BR': 'Como funciona o sensoriamento remoto — espectro eletromagnético, sensores e plataformas — e o que ele mede sobre a cultura e o solo.',
    },
  },
  {
    id: 'indices-vegetacao',
    category: 'concepts',
    youtubeId: 'sP0wwuB3ZX8', // Super Importadora
    title: {
      'en-US': 'What is a vegetation index?',
      'pt-BR': 'O que é um índice de vegetação?',
    },
    desc: {
      'en-US': 'The idea behind NDVI, NDRE, VARI and others — why red and near-infrared reflectance reveal plant condition.',
      'pt-BR': 'A ideia por trás de NDVI, NDRE, VARI e outros — por que a reflectância no vermelho e no infravermelho próximo revela a condição da planta.',
    },
  },
  {
    id: 'taxa-variavel-conceito',
    category: 'concepts',
    youtubeId: 'UvLdLG04XFI', // Ric Rural
    title: {
      'en-US': 'The variable-rate concept',
      'pt-BR': 'O conceito de taxa variável',
    },
    desc: {
      'en-US': 'Applying inputs according to the needs of each part of the field instead of a single field-wide rate — the payoff of the whole workflow.',
      'pt-BR': 'Aplicar insumos conforme a necessidade de cada parte do talhão, em vez de uma dose única para a área toda — o objetivo de todo o fluxo.',
    },
  },

  // ── Data collection ──────────────────────────────────────────────
  {
    id: 'yield-map',
    category: 'data',
    youtubeId: 'gHi15zD0wrY', // Laboratório de Agricultura de Precisão II
    title: {
      'en-US': 'Yield maps: cleaning harvester data',
      'pt-BR': 'Mapas de produtividade: limpeza dos dados de colheita',
    },
    desc: {
      'en-US': 'Import the combine yield-monitor points and remove erroneous readings (overlaps, fill/empty, speed spikes) before mapping productivity.',
      'pt-BR': 'Importe os pontos do monitor de produtividade da colhedora e remova as leituras errôneas (sobreposição, enche/esvazia, picos de velocidade) antes de mapear.',
    },
  },
  {
    id: 'soil-sampling',
    category: 'data',
    youtubeId: 'QlOsc4IK9kA', // Max Rabelo
    title: {
      'en-US': 'Georeferenced grid soil sampling',
      'pt-BR': 'Amostragem de solo em grade georreferenciada',
    },
    desc: {
      'en-US': 'Build a regular georeferenced sampling grid over the field to guide soil collection — the basis of any fertility map.',
      'pt-BR': 'Monte uma grade amostral regular georreferenciada sobre o talhão para guiar a coleta de solo — base de qualquer mapa de fertilidade.',
    },
  },
  {
    id: 'ndvi-pratica',
    category: 'data',
    youtubeId: 'QQtxqSqv8_s', // Rodrigo Lima Santos
    title: {
      'en-US': 'Generating & analysing NDVI in QGIS',
      'pt-BR': 'Gerando & analisando NDVI no QGIS',
    },
    desc: {
      'en-US': 'Generate and analyse an NDVI layer in QGIS from satellite imagery to read crop vigour across the field.',
      'pt-BR': 'Gere e analise uma camada de NDVI no QGIS a partir de imagem de satélite para ler o vigor da cultura no talhão.',
    },
  },

  // ── Analysis ─────────────────────────────────────────────────────
  {
    id: 'interpolation',
    category: 'analysis',
    youtubeId: 'rY-z41ccYyg', // Agricultura Digital
    title: {
      'en-US': 'Interpolating soil attributes (kriging)',
      'pt-BR': 'Interpolando atributos do solo (krigagem)',
    },
    desc: {
      'en-US': 'Turn discrete sample points into a continuous surface with ordinary kriging using the Smart-Map plugin.',
      'pt-BR': 'Transforme pontos amostrais discretos em uma superfície contínua com krigagem ordinária usando o plugin Smart-Map.',
    },
  },
  {
    id: 'management-zones',
    category: 'analysis',
    youtubeId: 'Z4mlN2Cc0K8', // GITAP Feagri
    title: {
      'en-US': 'Defining management zones',
      'pt-BR': 'Definindo zonas de manejo',
    },
    desc: {
      'en-US': 'Cluster the interpolated layers into differentiated management zones with the Precision Zones plugin for QGIS.',
      'pt-BR': 'Agrupe as camadas interpoladas em zonas de manejo diferenciadas com o plugin Precision Zones no QGIS.',
    },
  },

  // ── Prescription & output ────────────────────────────────────────
  {
    id: 'vrt-prescription',
    category: 'output',
    youtubeId: 'e3oJj5jRJlM', // PROJECÉU - Projetos e Consultoria Agrícola
    title: {
      'en-US': 'Variable-rate prescription maps',
      'pt-BR': 'Mapas de prescrição a taxa variável',
    },
    desc: {
      'en-US': 'Build a variable-rate prescription map — here, seeding rate driven by soil clay content — ready to send to the controller.',
      'pt-BR': 'Monte um mapa de prescrição a taxa variável — aqui, taxa de sementes em função do teor de argila do solo — pronto para enviar ao controlador.',
    },
  },
]
