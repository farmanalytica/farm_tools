// Geotechnology fundamentals catalog — short lessons teaching the basic concepts
// of geoprocessing using QGIS as the teaching tool. These are vendor-neutral GIS
// basics, independent of the FARM tools modules (those live in data/videos.js).
//
// `youtubeId: null` renders a "coming soon" placeholder; fill in the ID once the
// video is published. Each entry is scoped for a short 3–6 minute clip.
// Categories drive grouping on the Geotechnology page (see CATEGORY_ORDER in
// GeotechPage.vue).
export default [
  // ── Foundations ──────────────────────────────────────────────────
  {
    id: 'what-is-gis',
    category: 'foundations',
    youtubeId: 'TqogcbS2jks',
    title: {
      'en-US': 'What is GIS & geoprocessing?',
      'pt-BR': 'O que é SIG & geoprocessamento?',
    },
    desc: {
      'en-US': 'Geographic data, layers, and the idea of analysing the world by location. A tour of the QGIS interface — map canvas, layers panel, toolbars. (~5 min)',
      'pt-BR': 'Dados geográficos, camadas e a ideia de analisar o mundo pela localização. Um tour pela interface do QGIS — área do mapa, painel de camadas, barras de ferramentas. (~5 min)',
    },
  },
  {
    id: 'vector-vs-raster',
    category: 'foundations',
    youtubeId: 'rRZwu1CDf9Q',
    title: {
      'en-US': 'Vector vs. raster: the two data models',
      'pt-BR': 'Vetor vs. raster: os dois modelos de dados',
    },
    desc: {
      'en-US': 'Points, lines and polygons vs. grids of pixels — what each is good for, common file formats (Shapefile, GeoPackage, GeoTIFF) and when to use which. (~5 min)',
      'pt-BR': 'Pontos, linhas e polígonos vs. grades de pixels — para que cada um serve, formatos comuns (Shapefile, GeoPackage, GeoTIFF) e quando usar cada um. (~5 min)',
    },
  },
  {
    id: 'crs-projections',
    category: 'foundations',
    youtubeId: 'RhE2YUpkNMo',
    title: {
      'en-US': 'Coordinate reference systems & projections',
      'pt-BR': 'Sistemas de referência de coordenadas & projeções',
    },
    desc: {
      'en-US': 'Why the Earth is hard to flatten: geographic vs. projected CRS, EPSG codes, WGS84 vs. UTM/SIRGAS, and on-the-fly reprojection so layers line up. (~6 min)',
      'pt-BR': 'Por que achatar a Terra é difícil: SRC geográfico vs. projetado, códigos EPSG, WGS84 vs. UTM/SIRGAS e reprojeção em tempo real para as camadas se alinharem. (~6 min)',
    },
  },

  // ── Working with data ────────────────────────────────────────────
  {
    id: 'loading-data',
    category: 'data',
    youtubeId: '8x1lSK_Q0LM',
    title: {
      'en-US': 'Loading data & basemaps',
      'pt-BR': 'Carregando dados & mapas de base',
    },
    desc: {
      'en-US': 'Add vector and raster files, import a CSV of coordinates, and bring in XYZ tile basemaps (OpenStreetMap, satellite) for context. (~5 min)',
      'pt-BR': 'Adicione arquivos vetoriais e raster, importe um CSV de coordenadas e traga mapas de base XYZ (OpenStreetMap, satélite) para contexto. (~5 min)',
    },
  },
  {
    id: 'attribute-table',
    category: 'data',
    youtubeId: 'h0gqskwXUFc',
    title: {
      'en-US': 'The attribute table & field calculator',
      'pt-BR': 'A tabela de atributos & calculadora de campo',
    },
    desc: {
      'en-US': 'Every feature has data behind it: read and edit the attribute table, sort and filter, and compute new fields (e.g. area in hectares) with expressions. (~5 min)',
      'pt-BR': 'Cada feição tem dados por trás: leia e edite a tabela de atributos, ordene e filtre, e calcule novos campos (ex. área em hectares) com expressões. (~5 min)',
    },
  },
  {
    id: 'symbology',
    category: 'data',
    youtubeId: '_xZ11O325hk',
    title: {
      'en-US': 'Symbology: styling & thematic maps',
      'pt-BR': 'Simbologia: estilização & mapas temáticos',
    },
    desc: {
      'en-US': 'Turn raw layers into readable maps: single-symbol, categorized and graduated styles, colour ramps, labels, and styling raster layers. (~6 min)',
      'pt-BR': 'Transforme camadas cruas em mapas legíveis: estilos de símbolo único, categorizado e graduado, rampas de cor, rótulos e estilização de raster. (~6 min)',
    },
  },

  // ── Spatial analysis ─────────────────────────────────────────────
  {
    id: 'select-query',
    category: 'analysis',
    youtubeId: 'irShB-PQTkk',
    title: {
      'en-US': 'Selecting & querying features',
      'pt-BR': 'Selecionando & consultando feições',
    },
    desc: {
      'en-US': 'Select by attribute (expressions) and by location (spatial relationships like "within" and "intersects") — the foundation of every spatial question. (~5 min)',
      'pt-BR': 'Selecione por atributo (expressões) e por localização (relações espaciais como "dentro de" e "intercepta") — a base de toda pergunta espacial. (~5 min)',
    },
  },
  {
    id: 'vector-geoprocessing',
    category: 'analysis',
    youtubeId: 'Yd9Hac1Qwyw',
    title: {
      'en-US': 'Vector geoprocessing: buffer, clip, intersect, dissolve',
      'pt-BR': 'Geoprocessamento vetorial: buffer, recorte, interseção, dissolução',
    },
    desc: {
      'en-US': 'The core overlay toolkit — create buffers around features, clip to a boundary, intersect two layers, and dissolve features by a shared attribute. (~6 min)',
      'pt-BR': 'O conjunto central de sobreposição — crie buffers ao redor de feições, recorte por um limite, intercepte duas camadas e dissolva feições por um atributo comum. (~6 min)',
    },
  },
  {
    id: 'raster-analysis',
    category: 'analysis',
    youtubeId: 'NElKQyFNpsw',
    title: {
      'en-US': 'Raster basics: bands, raster calculator & reclassify',
      'pt-BR': 'Raster básico: bandas, calculadora raster & reclassificação',
    },
    desc: {
      'en-US': 'Read pixel values and bands, build map-algebra expressions in the raster calculator (e.g. a simple index), and reclassify continuous values into classes. (~6 min)',
      'pt-BR': 'Leia valores de pixel e bandas, monte expressões de álgebra de mapas na calculadora raster (ex. um índice simples) e reclassifique valores contínuos em classes. (~6 min)',
    },
  },

  // ── Sharing results ──────────────────────────────────────────────
  {
    id: 'map-layout',
    category: 'output',
    youtubeId: 'ZnnRllsUXds',
    title: {
      'en-US': 'Print layouts: composing & exporting a map',
      'pt-BR': 'Layouts de impressão: compondo & exportando um mapa',
    },
    desc: {
      'en-US': 'Build a finished map in the print layout — map frame, legend, scale bar, north arrow and title — and export it as PDF or high-resolution image. (~5 min)',
      'pt-BR': 'Monte um mapa final no layout de impressão — moldura, legenda, barra de escala, seta de norte e título — e exporte como PDF ou imagem em alta resolução. (~5 min)',
    },
  },
]
