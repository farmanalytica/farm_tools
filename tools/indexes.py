import re
import ast
import json
import os

PLUGIN_DIR = os.path.dirname(__file__)
JSON_PATH = os.path.join(PLUGIN_DIR, "custom_index.json")


def nvdi(image):
    return image.normalizedDifference(["B8", "B4"]).rename("index")


def gndvi(image):
    return image.normalizedDifference(["B8", "B3"]).rename("index")


def ndre(image):
    return image.normalizedDifference(["B8", "B5"]).rename("index")


def evi(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    blue = image.select("B2").divide(10000)
    return image.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {"NIR": nir, "RED": red, "BLUE": blue},
    ).rename("index")


def evi2(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    return image.expression(
        "2.5 * ((NIR - RED) / (NIR + RED + 1))",
        {"NIR": nir, "RED": red},
    ).rename("index")


def savi(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    L = 0.5
    return image.expression(
        "(1 + L) * ((NIR - RED) / (NIR + RED + L))",
        {"NIR": nir, "RED": red, "L": L},
    ).rename("index")


def msavi(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    return image.expression(
        "((2 * NIR + 1) - sqrt((2 * NIR + 1) ** 2 - 8 * (NIR - RED))) / 2",
        {"NIR": nir, "RED": red},
    ).rename("index")


def sfdvi(image):
    return image.expression(
        "((NIR + GREEN)/2 - (RED + REDEDGE)/2)",
        {
            "NIR": image.select("B8").divide(10000),  # Near-Infrared
            "GREEN": image.select("B3").divide(10000),  # Green
            "RED": image.select("B4").divide(10000),  # Red
            "REDEDGE": image.select("B5").divide(10000),  # Red Edge
        },
    ).rename("index")


def cigreen(image):
    nir = image.select("B8")
    green = image.select("B3")
    return image.expression("(NIR / GREEN) - 1", {"NIR": nir, "GREEN": green}).rename(
        "index"
    )


def arvi(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    blue = image.select("B2").divide(10000)
    return image.expression(
        "(NIR - (2 * RED - BLUE)) / (NIR + (2 * RED - BLUE))",
        {"NIR": nir, "RED": red, "BLUE": blue},
    ).rename("index")


def ndmi(image):
    return image.normalizedDifference(["B8", "B11"]).rename("index")


def nbr(image):
    return image.normalizedDifference(["B8", "B12"]).rename("index")


def sipi(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    blue = image.select("B2").divide(10000)
    return image.expression(
        "(NIR - BLUE) / (NIR - RED)",
        {"NIR": nir, "RED": red, "BLUE": blue},
    ).rename("index")


def ndwi(image):
    return image.normalizedDifference(["B3", "B8"]).rename("index")


def reci(image):
    nir = image.select("B8")
    rededge = image.select("B5")
    return image.expression(
        "(NIR / REDEDGE) - 1",
        {"NIR": nir, "REDEDGE": rededge},
    ).rename("index")


def mtci(image):
    nir = image.select("B8")
    rededge = image.select("B5")
    red = image.select("B4")
    return image.expression(
        "(NIR - REDEDGE) / (REDEDGE - RED)",
        {"NIR": nir, "REDEDGE": rededge, "RED": red},
    ).rename("index")


def mcari(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    green = image.select("B3").divide(10000)
    return image.expression(
        "((REDEDGE - RED) - 0.2 * (REDEDGE - GREEN)) * (REDEDGE / RED)",
        {"REDEDGE": nir, "RED": red, "GREEN": green},
    ).rename("index")


def vari(image):
    red = image.select("B4").divide(10000)
    green = image.select("B3").divide(10000)
    blue = image.select("B2").divide(10000)
    return image.expression(
        "(GREEN - RED) / (GREEN + RED - BLUE)",
        {"GREEN": green, "RED": red, "BLUE": blue},
    ).rename("index")


def tvi(image):
    nir = image.select("B8").divide(10000)
    red = image.select("B4").divide(10000)
    green = image.select("B3").divide(10000)
    return image.expression(
        "0.5 * (120 * (NIR - GREEN) - 200 * (RED - GREEN))",
        {"NIR": nir, "RED": red, "GREEN": green},
    ).rename("index")


INDEX_REGISTRY = {
    "NDVI": nvdi,
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


def validate_custom(name: str, expression: str):
    all_bands = [
        "B1",
        "B2",
        "B3",
        "B4",
        "B5",
        "B6",
        "B7",
        "B8",
        "B8A",
        "B9",
        "B11",
        "B12",
    ]

    name = name.upper()

    if not name:
        raise ValueError("Empty name.")

    if not expression:
        raise ValueError("Empty expression.")

    if not validate_expression(expression):
        raise ValueError("Invalid expression.")

    if name in all_bands or name in [k.upper() for k in INDEX_REGISTRY.keys()]:
        raise ValueError("Reserved name.")

    if name in [k.upper() for k in load_custom_indexes().keys()]:
        raise ValueError("Name already used.")

    return True


def apply_custom(image, name, expression):

    return calc_custom(image, expression).rename(name)


def calc_custom(image, expression):

    band1 = image.select("B1").divide(10000)  # Coastal aerosol
    band2 = image.select("B2").divide(10000)  # Blue
    band3 = image.select("B3").divide(10000)  # Green
    band4 = image.select("B4").divide(10000)  # Red
    band5 = image.select("B5").divide(10000)  # Red Edge 1
    band6 = image.select("B6").divide(10000)  # Red Edge 2
    band7 = image.select("B7").divide(10000)  # Red Edge 3
    band8 = image.select("B8").divide(10000)  # NIR
    band8a = image.select("B8A").divide(10000)  # Narrow NIR
    band9 = image.select("B9").divide(10000)  # Water vapor
    band11 = image.select("B11").divide(10000)  # SWIR 1
    band12 = image.select("B12").divide(10000)  # SWIR 2

    return image.expression(
        expression,
        {
            "B1": band1,
            "B2": band2,
            "B3": band3,
            "B4": band4,
            "B5": band5,
            "B6": band6,
            "B7": band7,
            "B8": band8,
            "B8A": band8a,
            "B9": band9,
            "B11": band11,
            "B12": band12,
        },
    )


def validate_expression(expression):
    if not expression:
        raise ValueError("A expressão não pode estar vazia.")

    clean_expr = re.sub(
        r"\b(B1|B2|B3|B4|B5|B6|B7|B8|B8A|B9|B11|B12)\b",
        "",
        expression,
        flags=re.IGNORECASE,
    )

    invalid_chars = re.sub(r"[+/*(). 0-9-]", "", clean_expr).strip()

    if invalid_chars:
        raise ValueError(f"Invalid characters: {invalid_chars}")

    dummy_expr = re.sub(
        r"\b(B1|B2|B3|B4|B5|B6|B7|B8|B8A|B9|B11|B12)\b",
        "1",
        expression,
        flags=re.IGNORECASE,
    )

    try:
        ast.parse(dummy_expr)
    except SyntaxError:
        raise ValueError("Mathematic sintax invalid. Check operators and parenthesis.")

    return True


def load_custom_indexes():

    try:
        with open(JSON_PATH, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_custom_indexes(name: str, expression: str):

    if validate_custom(name, expression):
        try:
            with open(JSON_PATH, "r") as file:
                saved_custom_indexes = json.load(file)
        except FileNotFoundError:
            saved_custom_indexes = {}

        saved_custom_indexes[name] = expression

        with open(JSON_PATH, "w") as file:
            json.dump(saved_custom_indexes, file)
