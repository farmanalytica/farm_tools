# -*- coding: utf-8 -*-
"""
Sentinel-2 vegetation indices.

``INDEX_REGISTRY`` maps the names shown on the RAVI page to the functions that
build the corresponding Earth Engine band, and the ``*_custom_index*`` helpers
persist user-written formulas in ``custom_index.json`` next to this module.

Every function takes an ``ee.Image`` of raw Sentinel-2 L2A bands and returns a
single band renamed ``"index"``.
"""

import ast
import json
import os
import re

PLUGIN_DIR = os.path.dirname(__file__)
JSON_PATH = os.path.join(PLUGIN_DIR, "custom_index.json")

# Sentinel-2 L2A ships reflectance as integers scaled by this factor; indices
# whose formula has an additive constant must divide it back out first.
REFLECTANCE_SCALE = 10000

# The selectable bands, in band order. Alternation order matters to the
# validator regex, so B8 stays ahead of B8A as it does on the satellite.
SENTINEL2_BANDS = (
    "B1",   # Coastal aerosol
    "B2",   # Blue
    "B3",   # Green
    "B4",   # Red
    "B5",   # Red Edge 1
    "B6",   # Red Edge 2
    "B7",   # Red Edge 3
    "B8",   # NIR
    "B8A",  # Narrow NIR
    "B9",   # Water vapour
    "B11",  # SWIR 1
    "B12",  # SWIR 2
)

# Number of arguments each supported function must be called with.
FUNCTION_ARITY = {
    "sqrt": 1,
    "abs": 1,
    "exp": 1,
    "log": 1,
    "pow": 2,
    "min": 2,
    "max": 2,
}

_SAVI_SOIL_FACTOR = 0.5
_INDEX_BAND_NAME = "index"

_TOKEN_PATTERN = r"\b({})\b".format("|".join(SENTINEL2_BANDS + tuple(FUNCTION_ARITY)))
_ALLOWED_NON_TOKEN_CHARS = r"[+/*()., 0-9-]"


def _scaled(image, band):
    """``band`` as surface reflectance in 0..1."""
    return image.select(band).divide(REFLECTANCE_SCALE)


def ndvi(image):
    return image.normalizedDifference(["B8", "B4"]).rename(_INDEX_BAND_NAME)


def gndvi(image):
    return image.normalizedDifference(["B8", "B3"]).rename(_INDEX_BAND_NAME)


def ndre(image):
    return image.normalizedDifference(["B8", "B5"]).rename(_INDEX_BAND_NAME)


def evi(image):
    return image.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {
            "NIR": _scaled(image, "B8"),
            "RED": _scaled(image, "B4"),
            "BLUE": _scaled(image, "B2"),
        },
    ).rename(_INDEX_BAND_NAME)


def evi2(image):
    return image.expression(
        "2.5 * ((NIR - RED) / (NIR + RED + 1))",
        {"NIR": _scaled(image, "B8"), "RED": _scaled(image, "B4")},
    ).rename(_INDEX_BAND_NAME)


def savi(image):
    return image.expression(
        "(1 + L) * ((NIR - RED) / (NIR + RED + L))",
        {
            "NIR": _scaled(image, "B8"),
            "RED": _scaled(image, "B4"),
            "L": _SAVI_SOIL_FACTOR,
        },
    ).rename(_INDEX_BAND_NAME)


def msavi(image):
    return image.expression(
        "((2 * NIR + 1) - sqrt((2 * NIR + 1) ** 2 - 8 * (NIR - RED))) / 2",
        {"NIR": _scaled(image, "B8"), "RED": _scaled(image, "B4")},
    ).rename(_INDEX_BAND_NAME)


def sfdvi(image):
    return image.expression(
        "((NIR + GREEN)/2 - (RED + REDEDGE)/2)",
        {
            "NIR": _scaled(image, "B8"),
            "GREEN": _scaled(image, "B3"),
            "RED": _scaled(image, "B4"),
            "REDEDGE": _scaled(image, "B5"),
        },
    ).rename(_INDEX_BAND_NAME)


def cigreen(image):
    return image.expression(
        "(NIR / GREEN) - 1",
        {"NIR": image.select("B8"), "GREEN": image.select("B3")},
    ).rename(_INDEX_BAND_NAME)


def arvi(image):
    return image.expression(
        "(NIR - (2 * RED - BLUE)) / (NIR + (2 * RED - BLUE))",
        {
            "NIR": _scaled(image, "B8"),
            "RED": _scaled(image, "B4"),
            "BLUE": _scaled(image, "B2"),
        },
    ).rename(_INDEX_BAND_NAME)


def ndmi(image):
    return image.normalizedDifference(["B8", "B11"]).rename(_INDEX_BAND_NAME)


def nbr(image):
    return image.normalizedDifference(["B8", "B12"]).rename(_INDEX_BAND_NAME)


def sipi(image):
    return image.expression(
        "(NIR - BLUE) / (NIR - RED)",
        {
            "NIR": _scaled(image, "B8"),
            "RED": _scaled(image, "B4"),
            "BLUE": _scaled(image, "B2"),
        },
    ).rename(_INDEX_BAND_NAME)


def ndwi(image):
    return image.normalizedDifference(["B3", "B8"]).rename(_INDEX_BAND_NAME)


def reci(image):
    return image.expression(
        "(NIR / REDEDGE) - 1",
        {"NIR": image.select("B8"), "REDEDGE": image.select("B5")},
    ).rename(_INDEX_BAND_NAME)


def mtci(image):
    return image.expression(
        "(NIR - REDEDGE) / (REDEDGE - RED)",
        {
            "NIR": image.select("B8"),
            "REDEDGE": image.select("B5"),
            "RED": image.select("B4"),
        },
    ).rename(_INDEX_BAND_NAME)


def mcari(image):
    # REDEDGE is bound to B8 here, not B5. Kept as-is: changing it would change
    # every MCARI value the plugin has ever produced.
    return image.expression(
        "((REDEDGE - RED) - 0.2 * (REDEDGE - GREEN)) * (REDEDGE / RED)",
        {
            "REDEDGE": _scaled(image, "B8"),
            "RED": _scaled(image, "B4"),
            "GREEN": _scaled(image, "B3"),
        },
    ).rename(_INDEX_BAND_NAME)


def vari(image):
    return image.expression(
        "(GREEN - RED) / (GREEN + RED - BLUE)",
        {
            "GREEN": _scaled(image, "B3"),
            "RED": _scaled(image, "B4"),
            "BLUE": _scaled(image, "B2"),
        },
    ).rename(_INDEX_BAND_NAME)


def tvi(image):
    return image.expression(
        "0.5 * (120 * (NIR - GREEN) - 200 * (RED - GREEN))",
        {
            "NIR": _scaled(image, "B8"),
            "RED": _scaled(image, "B4"),
            "GREEN": _scaled(image, "B3"),
        },
    ).rename(_INDEX_BAND_NAME)


INDEX_REGISTRY = {
    "NDVI": ndvi,
    "EVI": evi,
    "EVI2": evi2,
    "SAVI": savi,
    "GNDVI": gndvi,
    "MSAVI": msavi,
    "SFDVI": sfdvi,
    "CIgreen": cigreen,
    "NDRE": ndre,
    "ARVI": arvi,
    "NDMI": ndmi,
    "NBR": nbr,
    "SIPI": sipi,
    "NDWI": ndwi,
    "ReCI": reci,
    "MTCI": mtci,
    "MCARI": mcari,
    "VARI": vari,
    "TVI": tvi,
}


def validate_custom(name: str, expression: str) -> bool:
    """Check a user-supplied index name and formula, raising ``ValueError`` if unusable."""
    name = name.upper()

    if not name:
        raise ValueError("Empty name.")

    if not expression:
        raise ValueError("Empty expression.")

    if not validate_expression(expression):
        raise ValueError("Invalid expression.")

    if name in SENTINEL2_BANDS or name in {key.upper() for key in INDEX_REGISTRY}:
        raise ValueError("Reserved name.")

    if name in {key.upper() for key in load_custom_indexes()}:
        raise ValueError("Name already used.")

    return True


def apply_custom(image, name, expression):
    """The custom ``expression`` evaluated on ``image``, renamed to ``name``."""
    return calc_custom(image, expression).rename(name)


def calc_custom(image, expression):
    """Evaluate a validated custom expression over the scaled Sentinel-2 bands."""
    validate_expression(expression)

    # Earth Engine's expression parser has no pow(); rewrite it to the operator.
    processed_expression = re.sub(
        r"\bpow\s*\(\s*([^,]+),\s*([^)]+)\s*\)",
        r"(\1 ** \2)",
        expression,
        flags=re.IGNORECASE,
    )

    return image.expression(
        processed_expression,
        {band: _scaled(image, band) for band in SENTINEL2_BANDS},
    )


def _split_top_level_args(args_str):
    """Split a function's argument string on commas, ignoring commas nested
    inside inner parenthesis (e.g. nested function calls)."""
    args = []
    depth = 0
    current = ""
    for char in args_str:
        if char == "(":
            depth += 1
            current += char
        elif char == ")":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            args.append(current)
            current = ""
        else:
            current += char
    args.append(current)
    return args


def _matching_paren(expression, open_paren):
    """Index of the parenthesis closing the one at ``open_paren``, or ``None``."""
    depth = 0
    for position in range(open_paren, len(expression)):
        if expression[position] == "(":
            depth += 1
        elif expression[position] == ")":
            depth -= 1
            if depth == 0:
                return position
    return None


def _validate_function_arity(expression):
    pattern = r"\b({})\s*\(".format("|".join(FUNCTION_ARITY))
    for match in re.finditer(pattern, expression, flags=re.IGNORECASE):
        func_name = match.group(1).lower()
        open_paren = match.end() - 1

        close_paren = _matching_paren(expression, open_paren)
        if close_paren is None:
            raise ValueError(f"Unbalanced parenthesis in '{func_name}(...)'.")

        args_str = expression[open_paren + 1 : close_paren]
        args = [] if not args_str.strip() else _split_top_level_args(args_str)
        expected = FUNCTION_ARITY[func_name]

        if len(args) != expected:
            raise ValueError(
                f"'{func_name}' expects {expected} argument(s), got {len(args)}."
            )


def validate_expression(expression) -> bool:
    """Check a custom formula for unknown tokens and syntax errors."""
    if not expression:
        raise ValueError("Expression can not be empty.")

    _validate_function_arity(expression)

    without_tokens = re.sub(_TOKEN_PATTERN, "", expression, flags=re.IGNORECASE)
    invalid_chars = re.sub(_ALLOWED_NON_TOKEN_CHARS, "", without_tokens).strip()
    if invalid_chars:
        raise ValueError(f"Invalid characters: {invalid_chars}")

    # Every band and function stands in as 1, so ast checks operators and
    # parenthesis without needing real values.
    dummy_expr = re.sub(_TOKEN_PATTERN, "1", expression, flags=re.IGNORECASE)
    try:
        ast.parse(dummy_expr)
    except SyntaxError:
        raise ValueError("Mathematic syntax invalid. Check operators and parenthesis.")

    return True


def load_custom_indexes() -> dict:
    """Every saved custom index as ``{name: expression}``; empty when none exist."""
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def _write_custom_indexes(custom_indexes):
    with open(JSON_PATH, "w", encoding="utf-8") as file:
        json.dump(custom_indexes, file, indent=4)


def save_custom_indexes(name: str, expression: str) -> None:
    """Persist a validated custom index, replacing any formula stored under ``name``."""
    if not validate_custom(name, expression):
        return
    custom_indexes = load_custom_indexes()
    custom_indexes[name] = expression
    _write_custom_indexes(custom_indexes)


def delete_custom_index(name: str) -> bool:
    """Delete the custom index called ``name``, matched case-insensitively."""
    custom_indexes = load_custom_indexes()

    found_key = next(
        (key for key in custom_indexes if key.lower() == name.lower()), None
    )
    if not found_key:
        raise ValueError(f"Custom index '{name}' not found.")

    del custom_indexes[found_key]
    _write_custom_indexes(custom_indexes)
    return True
