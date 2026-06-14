export default {
  nav: {
    home: 'Início',
    tutorials: 'Tutoriais',
    geotech: 'Geotecnologia',
    precision: 'Agricultura de Precisão',
    wiki: 'Wiki',
    github: 'GitHub',
  },
  hero: {
    tag: 'Geoanálise multimódulo para QGIS',
    title: 'Um canivete suíço de geoanálise no QGIS',
    description:
      'Índices de vegetação, radar, elevação, composições de solo exposto, gráficos climáticos e amostragem de campo — os plugins apoiados pela FARM Analytica, unificados em uma única interface QGIS. A maioria dos módulos roda no Google Earth Engine; ClimaPlots e Guia de Campo funcionam sem ele.',
    ctaTutorials: 'Assistir tutoriais',
    ctaWiki: 'Ler a wiki',
    ctaGithub: 'Ver no GitHub',
    previewTitle: 'FARM tools',
    previewSubtitle: 'Oito módulos, um plugin QGIS',
    previewLabel: 'Módulos',
    previewItems: [
      'Imagens Óptico & Landsat',
      'Radar SAR & terreno DEM',
      'Solo exposto & dados climáticos',
      'Amostragem de campo & exportações',
    ],
  },
  intro: {
    label: 'Visão geral',
    title: 'Uma caixa de ferramentas para todo o fluxo de geoanálise',
    lead: 'O FARM tools unifica os plugins mantidos pela FARM Analytica — de índices de vegetação Sentinel-2 a radar, elevação, composições de solo exposto, gráficos climáticos e amostragem de campo — dentro do QGIS. A maioria dos módulos é movida pelo Google Earth Engine, enquanto ClimaPlots (dados climáticos NASA POWER & Open-Meteo) e Guia de Campo (rasters locais) não exigem conta GEE.',
  },
  modules: {
    label: 'Módulos',
    title: 'Módulos',
    lead: 'Cada módulo cobre uma etapa do fluxo de sensoriamento remoto e trabalho de campo.',
    wikiLink: 'Ler na wiki',
    items: {
      optical: {
        title: 'Óptico (Sentinel-2)',
        desc: 'Séries temporais de índices de vegetação (NDVI, EVI, SAVI, GNDVI), imagens RGB e sintéticas e download multiespectral.',
      },
      landsat: {
        title: 'Landsat',
        desc: 'Séries temporais e imagens Landsat de décadas para monitoramento histórico de terras e culturas.',
      },
      sar: {
        title: 'SAR (Sentinel-1)',
        desc: 'Análise de retroespalhamento de radar independente de nuvens para monitoramento em qualquer clima.',
      },
      dem: {
        title: 'DEM & Terreno',
        desc: 'Baixe dados de elevação e derive produtos de terreno para qualquer área de interesse.',
      },
      sysi: {
        title: 'SYSI Solo Exposto',
        desc: 'Composições sintéticas de solo exposto usando detecção multitemporal de solo exposto GEOS3.',
      },
      climaplots: {
        title: 'ClimaPlots',
        desc: 'Séries climáticas NASA POWER e gráficos interativos para qualquer área de interesse.',
      },
      fieldguide: {
        title: 'Guia de Campo',
        desc: 'Capture pontos em campo, amostre polígonos e selecione automaticamente locais ótimos por raster (ex.: picos de NDVI) — exporte para CSV, GPX e PDF.',
      },
      mapbiomas: {
        title: 'MapBiomas',
        desc: 'Explore o uso e cobertura da terra da Coleção 9 do Brasil por ano e execute análises configuráveis de transição de uso (ex.: pastagem → lavoura, desmatamento).',
      },
    },
  },
  how: {
    label: 'Fluxo de trabalho',
    title: 'Como Funciona',
    lead: 'Da autenticação aos resultados: escolha um módulo, configure as entradas e exporte — tudo no QGIS.',
    steps: [
      {
        title: 'Autenticar',
        desc: 'Configure seu ID de projeto Google Cloud e autentique-se no Google Earth Engine através do plugin.',
      },
      {
        title: 'Escolher módulo & configurar',
        desc: 'Escolha um módulo — Óptico, Landsat, SAR, DEM, SYSI, ClimaPlots, Guia de Campo ou MapBiomas — defina sua área e parâmetros, e execute.',
      },
      {
        title: 'Visualizar & Exportar',
        desc: 'Explore gráficos e camadas interativas e exporte como CSV, GPX, GeoTIFF ou PDF.',
      },
    ],
  },
  setup: {
    label: 'Configurar GEE',
    title: 'Primeiros Passos',
    lead: 'Configure o Google Earth Engine para liberar os módulos de satélite. ClimaPlots e Guia de Campo funcionam de imediato — sem conta GEE.',
    steps: [
      {
        title: 'Criar conta Google Earth Engine',
        desc: 'Cadastre-se gratuitamente em earthengine.google.com.',
        link: 'Ir para Earth Engine',
        href: 'https://earthengine.google.com/signup/',
      },
      {
        title: 'Criar projeto Google Cloud',
        desc: 'Crie um novo projeto e vincule-o à sua conta GEE.',
        link: 'Console Google Cloud',
        href: 'https://console.cloud.google.com/',
      },
      {
        title: 'Habilitar Earth Engine API',
        desc: 'No Console Cloud, procure por Earth Engine API e habilite-a.',
        link: 'Habilitar API',
        href: 'https://console.cloud.google.com/apis/library/earthengine.googleapis.com',
      },
      {
        title: 'Encontrar seu ID de projeto',
        desc: 'Abra o Editor de Código do Earth Engine para encontrar seu ID de projeto.',
        link: 'Editor de Código',
        href: 'https://code.earthengine.google.com/',
      },
      {
        title: 'Autenticar no FARM tools',
        desc: 'Abra o FARM tools no QGIS, clique em Configurar Autenticação, insira seu ID de projeto Cloud e autorize o acesso.',
        link: '',
        href: '',
      },
    ],
  },
  resources: {
    label: 'Recursos',
    title: 'Código, Suporte & Licença',
    lead: 'Tudo que você precisa para usar, solucionar problemas e contribuir com o FARM tools.',
    repo: {
      title: 'Repositório',
      desc: 'Navegue pelo código-fonte, versões e documentação no GitHub.',
      link: 'Abrir repositório',
    },
    issues: {
      title: 'Relatar Problemas',
      desc: 'Encontrou um bug ou tem uma sugestão? Abra uma issue e ajude a melhorar o FARM tools.',
      link: 'GitHub Issues',
    },
    license: {
      title: 'Licença',
      desc: 'O FARM tools é distribuído sob a GNU General Public License v2.0 ou superior.',
      link: 'Ler a licença',
    },
  },
  about: {
    label: 'Projeto',
    title: 'Sobre o Projeto',
    textPre: 'O FARM tools teve início como trabalho de conclusão de curso (TCC) de ',
    textMid: ', desenvolvido sob orientação do ',
    textPost: '. Atualmente é um projeto gratuito e de código aberto, mantido com o apoio da FARM Analytica, comprometido com a difusão tecnológica e o espírito do software livre.',
    sponsorLabel: 'Apoiado por',
    sponsorDesc: 'Tecnologia e inteligência de campo trabalhando juntas para apoiar operações práticas.',
    whatsapp: 'Fale no WhatsApp',
    sponsorCta: 'Fale com a FARM sobre soluções personalizadas exclusivas',
  },
  tutorials: {
    label: 'Tutoriais',
    title: 'Tutoriais em Vídeo',
    lead: 'Vídeos passo a passo para cada módulo do FARM tools — da primeira autenticação à amostragem de campo avançada. Novos vídeos são adicionados regularmente.',
    comingSoon: 'Vídeo em breve',
    watchWiki: 'Ler o artigo na wiki',
    categories: {
      start: 'Primeiros passos',
      imagery: 'Imagens & séries temporais',
      landcover: 'Cobertura & mudanças',
      terrain: 'Terreno, solo & clima',
      field: 'Trabalho de campo',
    },
  },
  geotech: {
    label: 'Geotecnologia',
    title: 'Fundamentos de geotecnologia',
    lead: 'Novo no SIG? Comece aqui. Lições curtas sobre os conceitos centrais do geoprocessamento — ensinados na prática no QGIS, o SIG desktop livre e de código aberto. Sem precisar de sensoriamento remoto ou conta do FARM tools: apenas os fundamentos que todo analista de mapas deve dominar.',
    comingSoon: 'Vídeo em breve',
    categories: {
      foundations: 'Fundamentos',
      data: 'Trabalhando com dados',
      analysis: 'Análise espacial',
      output: 'Compartilhando resultados',
    },
  },
  precision: {
    label: 'Agricultura de Precisão',
    title: 'Agricultura de precisão no QGIS',
    lead: 'Da teoria — variabilidade espacial, geoestatística, sensoriamento remoto, índices de vegetação — ao fluxo aplicado no QGIS: mapas de produtividade, amostragem de solo, interpolação, zonas de manejo e prescrições a taxa variável. Lições em português, reunidas de autores variados.',
    categories: {
      concepts: 'Fundamentos teóricos',
      data: 'Coleta de dados',
      analysis: 'Análise',
      output: 'Prescrição & saída',
    },
  },
  wiki: {
    label: 'Wiki',
    title: 'Wiki do FARM tools',
    lead: 'Documentação escrita de cada módulo: conceitos, parâmetros, metodologia e solução de problemas.',
    onThisPage: 'Artigos',
    edit: 'Encontrou um erro? Abra uma issue',
    next: 'Próximo artigo',
    prev: 'Artigo anterior',
    videos: 'Vídeos tutoriais',
  },
  footer: {
    textBefore: 'FARM tools, um projeto aberto e gratuito apoiado pela ',
    linkText: 'FARM Analytica',
    textAfter: '.',
    links: 'Links',
  },
  langToggle: {
    label: 'Idioma',
  },
}
