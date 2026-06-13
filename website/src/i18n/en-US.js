export default {
  nav: {
    home: 'Home',
    tutorials: 'Tutorials',
    wiki: 'Wiki',
    github: 'GitHub',
  },
  hero: {
    tag: 'Multi-module geo-analytics for QGIS',
    title: 'A Swiss-army toolbox for geo-analytics in QGIS',
    description:
      'Vegetation indices, radar, elevation, bare-soil composites, climate charts, and field sampling — the plugins supported by FARM Analytica, unified in one Google Earth Engine-powered interface.',
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
    lead: 'FARM tools unifies the plugins maintained by FARM Analytica — from Sentinel-2 vegetation indices to radar, elevation, bare-soil composites, climate charts, and field sampling — all integrated with Google Earth Engine inside QGIS.',
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
    lead: 'Set up Google Earth Engine and configure FARM tools to start using every module.',
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
    text: 'FARM tools began as the undergraduate final project (TCC) of Caio Arantes, developed under the supervision of Prof. Dr. Lucas dos Rios Amaral. Today it is a free and open-source project maintained with the support of FARM Analytica, committed to technology diffusion and the open-source philosophy.',
    sponsorLabel: 'Supported by',
    sponsorDesc: 'Technology and field intelligence working together to support practical operations.',
    whatsapp: 'Talk on WhatsApp',
    sponsorCta: 'Speak with FARM about exclusive custom solutions',
    supervisorsPrefix: 'Academic supervision by',
    supervisorsAnd: 'and',
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
      terrain: 'Terrain, soil & climate',
      field: 'Fieldwork',
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
    text: 'FARM tools, an open and free project supported by FARM Analytica.',
    links: 'Links',
  },
  langToggle: {
    label: 'Language',
  },
}
