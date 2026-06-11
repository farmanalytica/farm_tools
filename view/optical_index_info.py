# -*- coding: utf-8 -*-
"""
Vegetation-index reference content for the Optical (Sentinel-2) page.

``INDEX_ORDER`` is the canonical combo order; ``VEGETATION_INDICES`` maps each
index name to an HTML description + formula shown in the Inputs-tab explanation
panel. Content ported from the legacy ``modules/vegetation_index_info.py``
(English). The trailing ``Custom…`` combo entry is handled by the page, not
stored here.
"""

INDEX_ORDER = [
    "NDVI", "GNDVI", "EVI", "EVI2", "SAVI", "MSAVI", "SFDVI", "CIgreen",
    "NDRE", "ARVI", "NDMI", "NBR", "SIPI", "NDWI", "ReCI", "MTCI", "MCARI",
    "VARI", "TVI",
]

CUSTOM_INDEX_LABEL = "Custom…"

# Bands allowed in a custom expression (Sentinel-2), with friendly names.
CUSTOM_BAND_REFERENCE = [
    ("B1", "Coastal aerosol (443 nm, 60 m)"),
    ("B2", "Blue (490 nm, 10 m)"),
    ("B3", "Green (560 nm, 10 m)"),
    ("B4", "Red (665 nm, 10 m)"),
    ("B5", "Red Edge 1 (705 nm, 20 m)"),
    ("B6", "Red Edge 2 (740 nm, 20 m)"),
    ("B7", "Red Edge 3 (783 nm, 20 m)"),
    ("B8", "NIR (842 nm, 10 m)"),
    ("B8A", "Narrow NIR (865 nm, 20 m)"),
    ("B9", "Water vapor (945 nm, 60 m)"),
    ("B11", "SWIR 1 (1610 nm, 20 m)"),
    ("B12", "SWIR 2 (2190 nm, 20 m)"),
]

VEGETATION_INDICES = {
    "NDVI": """
        <h3>Normalized Difference Vegetation Index (NDVI)</h3>
        <p>
            The Normalized Difference Vegetation Index (NDVI) is a widely used and well-established
            indicator of vegetation health and vigor. It exploits the contrasting spectral
            reflectance properties of plant pigments, particularly chlorophyll.
            Healthy vegetation strongly absorbs visible red light for photosynthesis while
            reflecting a significant portion of near-infrared (NIR) radiation.
            Conversely, non-vegetated areas like soil and water tend to reflect both red and
            NIR light more equally.
        </p>
        <p>
            The NDVI formula is calculated as follows:
        </p>
        <pre>
NDVI = (NIR - RED) / (NIR + RED)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
            </ul>
            By calculating the difference between NIR and red reflectance and normalizing it
            by their sum, NDVI effectively enhances the vegetation signal while minimizing
            the influence of factors like variations in illumination and atmospheric conditions.
            NDVI values typically range from -1 to 1.
            Higher values (closer to 1) generally indicate denser, healthier vegetation with
            higher leaf area and chlorophyll content.
            Lower values (closer to -1) often correspond to bare soil, water, or senescent
            (dying) vegetation.
        </p>
    """,
    "GNDVI": """
        <h3>Green Normalized Difference Vegetation Index (GNDVI)</h3>
        <p>
            The Green Normalized Difference Vegetation Index (GNDVI) is a modification of NDVI
            that utilizes the green band of the electromagnetic spectrum instead of the red band.
            Chlorophyll, the primary pigment involved in photosynthesis, strongly absorbs
            blue and red light while reflecting green light.
            Therefore, GNDVI is particularly sensitive to variations in chlorophyll content
            within plant canopies.
        </p>
        <p>
            The GNDVI formula is calculated as:
        </p>
        <pre>
GNDVI = (NIR - GREEN) / (NIR + GREEN)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>GREEN</b>: Reflectance in the green band</li>
            </ul>
            This sensitivity makes GNDVI a valuable tool for:
            <ul>
                <li>Monitoring plant stress and nutrient deficiencies</li>
                <li>Detecting early signs of disease or pest infestations</li>
                <li>Assessing crop vigor and yield potential</li>
                <li>Studying the impact of environmental factors on plant growth</li>
            </ul>
        </p>
    """,
    "EVI": """
        <h3>Enhanced Vegetation Index (EVI)</h3>
        <p>
            The Enhanced Vegetation Index (EVI) was developed to address some of the limitations
            of NDVI, particularly in areas of high biomass or atmospheric interference.
            EVI incorporates a blue band in its calculation, which helps to minimize the
            influence of atmospheric aerosols and soil background noise.
            Additionally, EVI uses a canopy background adjustment term to improve sensitivity
            in areas of high biomass and to better discriminate vegetation from non-vegetated
            surfaces.
        </p>
        <p>
            The EVI formula is calculated as:
        </p>
        <pre>
EVI = 2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>BLUE</b>: Reflectance in the blue band</li>
            </ul>
            EVI has proven to be highly effective in:
            <ul>
                <li>Monitoring vegetation dynamics in diverse ecosystems</li>
                <li>Estimating biomass and productivity</li>
                <li>Assessing the impact of climate change on vegetation</li>
                <li>Mapping vegetation cover and land use/land cover change</li>
            </ul>
        </p>
    """,
    "EVI2": """
        <h3>Enhanced Vegetation Index 2 (EVI2)</h3>
        <p>
            The Enhanced Vegetation Index 2 (EVI2) is a simplified version of the Enhanced Vegetation Index (EVI)
            that does not require the blue band. This makes it particularly useful for sensors that lack a blue band
            or in cases where the blue band data is unreliable.
        </p>
        <p>
            The EVI2 formula is calculated as:
        </p>
        <pre>
EVI2 = 2.5 * ((NIR - RED) / (NIR + RED + 1))
        </pre>
        <p>
            where:
            <ul>
            <li><b>NIR</b>: Reflectance in the near-infrared band</li>
            <li><b>RED</b>: Reflectance in the red band</li>
            </ul>
        </p>
        <p>
            EVI2 retains many of the advantages of EVI, such as improved sensitivity in areas of high biomass,
            while being computationally simpler and more broadly applicable.
        </p>
        """,
    "SAVI": """
        <h3>Soil-Adjusted Vegetation Index (SAVI)</h3>
        <p>
            The Soil-Adjusted Vegetation Index (SAVI) is specifically designed to minimize
            the influence of soil background reflectance, particularly in areas with sparse
            vegetation cover.
            In such areas, soil reflectance can significantly impact the accuracy of
            vegetation indices like NDVI.
        </p>
        <p>
            SAVI incorporates a soil brightness correction factor (L) into its calculation.
            This factor adjusts the sensitivity of the index to soil background,
            allowing for more accurate assessment of vegetation in areas with varying
            soil conditions. SAVI is particularly useful in:
            <ul>
                <li>Arid and semi-arid regions</li>
                <li>Agricultural areas with low plant cover</li>
                <li>Disturbed or degraded ecosystems</li>
            </ul>
        </p>
        <p>
            The SAVI formula is calculated as:
        </p>
        <pre>
SAVI = (1 + L) * ((NIR - RED) / (NIR + RED + L))
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>L</b>: Soil brightness correction factor (typically set to 0.5)</li>
            </ul>
        </p>
        <p><b>Note:</b> For this plugin, the soil brightness correction factor (L) is set to 0.5.</p>
    """,
    "MSAVI": """
        <h3>Modified Soil-Adjusted Vegetation Index (MSAVI)</h3>
        <p>
            The Modified Soil-Adjusted Vegetation Index (MSAVI) is an enhancement of the SAVI
            designed to further minimize soil background effects on vegetation monitoring.
            Unlike SAVI, which uses a constant soil adjustment factor (L), MSAVI dynamically
            adjusts this factor based on vegetation density, making it more responsive to
            variations in vegetative cover.
        </p>
        <p>
            MSAVI is particularly valuable in areas with mixed vegetation densities and varying
            soil backgrounds, as it reduces the need for prior knowledge of vegetation cover.
            This makes it ideal for:
            <ul>
                <li>Agricultural monitoring across different growth stages</li>
                <li>Ecological studies in heterogeneous landscapes</li>
                <li>Land degradation assessment</li>
                <li>Monitoring vegetation recovery after disturbances</li>
            </ul>
        </p>
        <p>
            The MSAVI formula is calculated as:
        </p>
        <pre>
MSAVI = (2 * NIR + 1 - sqrt((2 * NIR + 1)² - 8 * (NIR - RED))) / 2
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
            </ul>
        </p>
        <p>
            The self-adjusting nature of MSAVI provides more consistent measurements across
            diverse landscapes and vegetation conditions compared to NDVI and SAVI.
        </p>
    """,
    "SFDVI": """
        <h3>Structurally Focused Difference Vegetation Index (SFDVI)</h3>
        <p>
            The Spectral Feature Depth Vegetation Index (SFDVI) integrates the Red Edge band
            with the red band to investigate vegetation behavior by means of the spectral
            feature depth.  SFDVI shows more gradations in dense vegetation than NDVI and RENDVI.
        </p>
        <p>
            SFDVI is effective for:
            <ul>
                <li>Analyzing vegetation using spectral feature depth.</li>
                <li>Showing gradations in dense vegetation.</li>
            </ul>
        </p>
        <p>
            The SFDVI formula is calculated as:
        </p>
        <pre>
SFDVI = ((NIR + GREEN)/2 - (RED + REDEDGE)/2)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>GREEN</b>: Reflectance in the green band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>REDEDGE</b>: Reflectance in the red edge band</li>
            </ul>
        </p>
    """,
    "CIgreen": """
        <h3>Chlorophyll Index Green (CIgreen)</h3>
        <p>
            The Chlorophyll Index Green (CIgreen) is specifically designed to estimate
            chlorophyll content in plant leaves and canopies. Unlike normalized difference
            indices, CIgreen uses a ratio-based approach that has shown strong correlation
            with actual chlorophyll concentrations in various vegetation types.
        </p>
        <p>
            This index is particularly sensitive to subtle changes in chlorophyll levels,
            making it valuable for:
            <ul>
                <li>Early detection of plant stress</li>
                <li>Monitoring crop nitrogen status</li>
                <li>Assessing photosynthetic capacity</li>
                <li>Tracking seasonal changes in vegetation health</li>
            </ul>
        </p>
        <p>
            The CIgreen formula is calculated as:
        </p>
        <pre>
CIgreen = (NIR / GREEN) - 1
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>GREEN</b>: Reflectance in the green band</li>
            </ul>
        </p>
        <p>
            Higher CIgreen values generally indicate greater chlorophyll content and
            healthier vegetation. The index's simple formulation makes it computationally
            efficient while still providing valuable insights into plant physiological status.
        </p>
    """,
    "NDRE": """
        <h3>Normalized Difference Red Edge (NDRE)</h3>
        <p>
            The Normalized Difference Red Edge (NDRE) is an advanced vegetation index that
            utilizes the red edge portion of the electromagnetic spectrum. The red edge
            represents the rapid change in reflectance between the red and near-infrared
            regions (approximately 680-730 nm) and is highly sensitive to chlorophyll
            content and vegetation health.
        </p>
        <p>
            NDRE is particularly valuable in:
            <ul>
                <li>Detecting early signs of crop stress before visible symptoms appear</li>
                <li>Monitoring nitrogen status in crops with high precision</li>
                <li>Assessing vegetation health in dense canopies where NDVI may saturate</li>
                <li>Distinguishing between subtle variations in vegetation condition</li>
            </ul>
        </p>
        <p>
            The NDRE formula is calculated as:
        </p>
        <pre>
NDRE = (NIR - REDEDGE) / (NIR + REDEDGE)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>REDEDGE</b>: Reflectance in the red edge band (typically 720-740 nm)</li>
            </ul>
        </p>
        <p>
            NDRE values typically range from -1 to 1, with higher values indicating healthier
            vegetation. NDRE offers significant advantages over NDVI in dense vegetation where
            NDVI tends to saturate, making it especially useful for precision agriculture and
            advanced vegetation monitoring applications.
        </p>
    """,
    "ARVI": """
        <h3>Atmospherically Resistant Vegetation Index (ARVI)</h3>
        <p>
            The Atmospherically Resistant Vegetation Index (ARVI) is designed to be less sensitive
            to atmospheric effects (such as aerosols) compared to NDVI. It incorporates a correction
            factor using the blue band to compensate for atmospheric scattering.
        </p>
        <p>
            The ARVI formula is calculated as:
        </p>
        <pre>
ARVI = (NIR - (2 * RED - BLUE)) / (NIR + (2 * RED - BLUE))
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>BLUE</b>: Reflectance in the blue band</li>
            </ul>
        </p>
        <p>
            ARVI is useful in regions with significant atmospheric aerosol presence, providing a
            more accurate assessment of vegetation cover.
        </p>
    """,
    "NDMI": """
        <h3>Normalized Difference Moisture Index (NDMI)</h3>
        <p>
            The Normalized Difference Moisture Index (NDMI) is used to monitor vegetation moisture content.
            It is sensitive to changes in the water content of plant canopies.
        </p>
        <p>
            The NDMI formula is calculated as:
        </p>
        <pre>
NDMI = (NIR - SWIR) / (NIR + SWIR)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>SWIR</b>: Reflectance in the shortwave infrared band</li>
            </ul>
        </p>
        <p>
            NDMI is valuable in drought monitoring, irrigation management, and assessing vegetation stress
            related to water availability.
        </p>
    """,
    "NBR": """
        <h3>Normalized Burn Ratio (NBR)</h3>
        <p>
            The Normalized Burn Ratio (NBR) is designed to identify burned areas and assess burn severity.
            It uses the difference between near-infrared and shortwave infrared reflectance.
        </p>
        <p>
            The NBR formula is calculated as:
        </p>
        <pre>
NBR = (NIR - SWIR) / (NIR + SWIR)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>SWIR</b>: Reflectance in the shortwave infrared band</li>
            </ul>
        </p>
        <p>
            NBR is used extensively in post-fire assessment to map burned areas and monitor vegetation recovery.
        </p>
    """,
    "SIPI": """
        <h3>Structure Insensitive Pigment Index (SIPI)</h3>
        <p>
            The Structure Insensitive Pigment Index (SIPI) is used to assess vegetation canopy stress.
        </p>
        <p>
            The SIPI formula is calculated as:
        </p>
        <pre>
SIPI = (NIR - BLUE) / (NIR - RED)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>BLUE</b>: Reflectance in the blue band</li>
            </ul>
        </p>
        <p>
            SIPI is useful for minimizing canopy structure effects.
        </p>
    """,
    "NDWI": """
        <h3>Normalized Difference Water Index (NDWI)</h3>
        <p>
            The Normalized Difference Water Index (NDWI) is used to monitor changes in water content in
            vegetation.
        </p>
        <p>
            The NDWI formula is calculated as:
        </p>
        <pre>
NDWI = (GREEN - NIR) / (GREEN + NIR)
        </pre>
        <p>
            where:
            <ul>
                <li><b>GREEN</b>: Reflectance in the green band</li>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
            </ul>
        </p>
        <p>
            NDWI is sensitive to changes in liquid water content of vegetation canopies.
        </p>
    """,
    "ReCI": """
        <h3>Red Edge Chlorophyll Index (ReCI)</h3>
        <p>
            The Red Edge Chlorophyll Index (ReCI) is designed to estimate chlorophyll content in
            vegetation using the red edge band.
        </p>
        <p>
            The ReCI formula is calculated as:
        </p>
        <pre>
ReCI = (NIR / REDEDGE) - 1
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>REDEDGE</b>: Reflectance in the red edge band</li>
            </ul>
        </p>
        <p>
            ReCI is particularly useful in precision agriculture for monitoring crop health and
            nitrogen status.
        </p>
    """,
    "MTCI": """
        <h3>MERIS Terrestrial Chlorophyll Index (MTCI)</h3>
        <p>
            The MERIS Terrestrial Chlorophyll Index (MTCI) is sensitive to chlorophyll content in
            vegetation.
        </p>
        <p>
            The MTCI formula is calculated as:
        </p>
        <pre>
MTCI = (NIR - REDEDGE) / (REDEDGE - RED)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>REDEDGE</b>: Reflectance in the red edge band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
            </ul>
        </p>
        <p>
            MTCI is useful for estimating chlorophyll content and monitoring vegetation health.
        </p>
    """,
    "MCARI": """
        <h3>Modified Chlorophyll Absorption Ratio Index (MCARI)</h3>
        <p>
            The Modified Chlorophyll Absorption Ratio Index (MCARI) is designed to be sensitive to
            chlorophyll concentration.
        </p>
        <p>
            The MCARI formula is calculated as:
        </p>
        <pre>
MCARI = ((REDEDGE - RED) - 0.2 * (REDEDGE - GREEN)) * (REDEDGE / RED)
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band (used as REDEDGE)</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>GREEN</b>: Reflectance in the green band</li>
            </ul>
        </p>
        <p>
            MCARI can be used to assess vegetation stress.
        </p>
    """,
    "VARI": """
        <h3>Visible Atmospherically Resistant Index (VARI)</h3>
        <p>
            The Visible Atmospherically Resistant Index (VARI) minimizes atmospheric effects and
            enhances the vegetation signal in the visible part of the spectrum.
        </p>
        <p>
            The VARI formula is calculated as:
        </p>
        <pre>
VARI = (GREEN - RED) / (GREEN + RED - BLUE)
        </pre>
        <p>
            where:
            <ul>
                <li><b>GREEN</b>: Reflectance in the green band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>BLUE</b>: Reflectance in the blue band</li>
            </ul>
        </p>
        <p>
            VARI is useful when atmospheric correction is challenging.
        </p>
    """,
    "TVI": """
        <h3>Triangular Vegetation Index (TVI)</h3>
        <p>
            The Triangular Vegetation Index (TVI) is a transformation of the NDVI index.
        </p>
        <p>
            The TVI formula is calculated as:
        </p>
        <pre>
TVI = 0.5 * (120 * (NIR - GREEN) - 200 * (RED - GREEN))
        </pre>
        <p>
            where:
            <ul>
                <li><b>NIR</b>: Reflectance in the near-infrared band</li>
                <li><b>RED</b>: Reflectance in the red band</li>
                <li><b>GREEN</b>: Reflectance in the green band</li>
            </ul>
        </p>
    """,
}
