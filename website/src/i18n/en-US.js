export default {
  nav: {
    home: 'Home',
    tutorials: 'Tutorials',
    geotech: 'Geotechnology',
    precision: 'Precision Agriculture',
    wiki: 'Wiki',
    github: 'GitHub',
  },
  hero: {
    tag: 'Multi-module geo-analytics for QGIS',
    title: 'A Swiss-army toolbox for geo-analytics in QGIS',
    description:
      'Vegetation indices, radar, elevation, bare-soil composites, climate charts, and field sampling — the plugins supported by FARM Analytica, unified in one QGIS interface. Most modules run on Google Earth Engine; ClimaPlots and Field Guide work without it.',
    ctaTutorials: 'Watch tutorials',
    ctaWiki: 'Read the wiki',
    ctaGithub: 'View on GitHub',
    previewTitle: 'FARM tools',
    previewSubtitle: 'Eight modules, one QGIS plugin',
    previewLabel: 'Modules',
    previewItems: [
      'Optical & Landsat imagery',
      'SAR radar & DEM terrain',
      'Bare-soil & climate data',
      'Field sampling & exports',
    ],
  },
  intro: {
    label: 'Overview',
    title: 'One toolbox for the whole geo-analytics workflow',
    lead: 'FARM tools unifies the plugins maintained by FARM Analytica — from Sentinel-2 vegetation indices to radar, elevation, bare-soil composites, climate charts, and field sampling — inside QGIS. Most modules are powered by Google Earth Engine, while ClimaPlots (NASA POWER & Open-Meteo climate data) and Field Guide (local rasters) need no GEE account.',
  },
  modules: {
    label: 'Modules',
    title: 'Modules',
    lead: 'Each module covers a stage of the remote-sensing and fieldwork workflow.',
    wikiLink: 'Read in the wiki',
    items: {
      optical: {
        title: 'Optical (Sentinel-2)',
        desc: 'Vegetation index time series (NDVI, EVI, SAVI, GNDVI), RGB and composite imagery, and multispectral download.',
      },
      landsat: {
        title: 'Landsat',
        desc: 'Decades-long Landsat time series and imagery for historical land and crop monitoring.',
      },
      sar: {
        title: 'SAR (Sentinel-1)',
        desc: 'Cloud-independent radar backscatter analysis for all-weather land monitoring.',
      },
      dem: {
        title: 'DEM & Terrain',
        desc: 'Download elevation data and derive terrain products for any area of interest.',
      },
      sysi: {
        title: 'SYSI Bare Soil',
        desc: 'Synthetic bare-soil image composites using GEOS3 multi-temporal bare-soil detection.',
      },
      climaplots: {
        title: 'ClimaPlots',
        desc: 'NASA POWER climate series and interactive charts for any area of interest.',
      },
      fieldguide: {
        title: 'Field Guide',
        desc: 'Capture field points, sample polygons, and auto-pick raster-optimal locations (e.g. NDVI peaks) — export to CSV, GPX, and PDF.',
      },
      mapbiomas: {
        title: 'MapBiomas',
        desc: 'Browse Brazilian Collection 9 land-use/land-cover by year and run configurable land-use transition analysis (e.g. pasture → crop, deforestation).',
      },
    },
  },
  how: {
    label: 'Workflow',
    title: 'How It Works',
    lead: 'From authentication to results: pick a module, configure inputs, and export — all in QGIS.',
    steps: [
      {
        title: 'Authenticate',
        desc: 'Set up your Google Cloud project ID and authenticate with Google Earth Engine through the plugin.',
      },
      {
        title: 'Pick a module & configure',
        desc: 'Choose a module — Optical, Landsat, SAR, DEM, SYSI, ClimaPlots, Field Guide, or MapBiomas — set your area and parameters, then run.',
      },
      {
        title: 'Visualize & Export',
        desc: 'Explore interactive charts and layers, then export as CSV, GPX, GeoTIFF, or PDF.',
      },
    ],
  },
  setup: {
    label: 'GEE Setup',
    title: 'Getting Started',
    lead: 'Set up Google Earth Engine to unlock the satellite modules. ClimaPlots and Field Guide work right away — no GEE account required.',
    steps: [
      {
        title: 'Create a Google Earth Engine account',
        desc: 'Sign up for free at earthengine.google.com.',
        link: 'Go to Earth Engine',
        href: 'https://earthengine.google.com/signup/',
      },
      {
        title: 'Create a Google Cloud project',
        desc: 'Create a new project and link it to your GEE account.',
        link: 'Google Cloud Console',
        href: 'https://console.cloud.google.com/',
      },
      {
        title: 'Enable Earth Engine API',
        desc: 'In Cloud Console, search for Earth Engine API and enable it.',
        link: 'Enable API',
        href: 'https://console.cloud.google.com/apis/library/earthengine.googleapis.com',
      },
      {
        title: 'Find your project ID',
        desc: 'Open the Earth Engine Code Editor to find your project ID.',
        link: 'Code Editor',
        href: 'https://code.earthengine.google.com/',
      },
      {
        title: 'Authenticate in FARM tools',
        desc: 'Open FARM tools in QGIS, click Setup Authentication, enter your Cloud project ID, and authorize access.',
        link: '',
        href: '',
      },
    ],
  },
  resources: {
    label: 'Resources',
    title: 'Source, Support & License',
    lead: 'Everything you need to use, troubleshoot, and contribute to FARM tools.',
    repo: {
      title: 'Repository',
      desc: 'Browse the source code, releases, and documentation on GitHub.',
      link: 'Open repository',
    },
    issues: {
      title: 'Report Issues',
      desc: 'Found a bug or have a suggestion? Open an issue and help improve FARM tools.',
      link: 'GitHub Issues',
    },
    license: {
      title: 'License',
      desc: 'FARM tools is released under the GNU General Public License v2.0 or later.',
      link: 'Read the license',
    },
  },
  about: {
    label: 'Project',
    title: 'About the Project',
    textPre: 'FARM tools began as the undergraduate final project (TCC) of ',
    textMid: ', developed under the supervision of ',
    textPost: '. Today it is a free and open-source project maintained with the support of FARM Analytica, committed to technology diffusion and the open-source philosophy.',
    sponsorLabel: 'Supported by',
    sponsorDesc: 'Technology and field intelligence working together to support practical operations.',
    whatsapp: 'Talk on WhatsApp',
    sponsorCta: 'Speak with FARM about exclusive custom solutions',
  },
  tutorials: {
    label: 'Tutorials',
    title: 'Video Tutorials',
    lead: 'Step-by-step videos for every FARM tools module — from first authentication to advanced field sampling. New videos are added regularly.',
    comingSoon: 'Video coming soon',
    watchWiki: 'Read the wiki article',
    categories: {
      start: 'Getting started',
      imagery: 'Imagery & time series',
      landcover: 'Land cover & change',
      terrain: 'Terrain, soil & climate',
      field: 'Fieldwork',
    },
  },
  geotech: {
    label: 'Geotechnology',
    title: 'Geotechnology foundations',
    lead: 'New to GIS? Start here. Short lessons on the core concepts of geoprocessing — taught hands-on in QGIS, the free and open-source desktop GIS. No remote sensing or FARM tools account needed: just the fundamentals every map analyst should know.',
    comingSoon: 'Video coming soon',
    categories: {
      foundations: 'Foundations',
      data: 'Working with data',
      analysis: 'Spatial analysis',
      output: 'Sharing results',
    },
  },
  precision: {
    label: 'Precision Agriculture',
    title: 'Precision agriculture in QGIS',
    lead: 'From the theory — spatial variability, geostatistics, remote sensing, vegetation indices — to the applied workflow in QGIS: yield maps, soil sampling, interpolation, management zones and variable-rate prescriptions. Lessons are in Brazilian Portuguese, gathered from a range of authors.',
    categories: {
      concepts: 'Theoretical foundations',
      data: 'Data collection',
      analysis: 'Analysis',
      output: 'Prescription & output',
    },
  },
  wiki: {
    label: 'Wiki',
    title: 'FARM tools Wiki',
    lead: 'Written documentation for every module: concepts, parameters, methodology, and troubleshooting.',
    onThisPage: 'Articles',
    edit: 'Found an error? Open an issue',
    next: 'Next article',
    prev: 'Previous article',
  },
  footer: {
    textBefore: 'FARM tools, an open and free project supported by ',
    linkText: 'FARM Analytica',
    textAfter: '.',
    links: 'Links',
  },
  langToggle: {
    label: 'Language',
  },
}
