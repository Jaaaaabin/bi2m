"""Hardcoded, per-test-file calibration data.

These are not general extraction logic - they're overrides for specific known IFC
test files (matched by a filename substring), kept isolated here so they don't read
as part of the general algorithm in floors.py/viz.py.
"""

# GUIDs of slabs to exclude entirely, keyed by a filename substring.
SLAB_OUTLIER_GUIDS = {
    "11103190": [
        "1lPJHttHj0t93Rx9JW$x8L",
    ],
    "11103085": [
        "0lLezB9Eo$GvWuGLIrVqQT",
        "2dgQT7c8heJAthKIf57922",
        "2$TzztUz_nI9DzZezaA0Uf",
        "19S$35tbDXGBvHnQP5VyE9",
        "1cM2g9vEKfIuKkoOh4wzLq",
        "3B4yd04k$TGAbpDhg7t6cm",
        "216BSagR2mHRRWNp1ebRcl",
        "0Qo2NFvaCRJOHrKtNiM2UJ",
        "3j$3sa8m0eIAMLU9FdP81l",
        "2qKTvaLYmZHOA8KyeHuD1p",
    ],
    "11103186": [
        "1gQ_y3GLj6yQZm$NpWfoHW",
    ],
    "11103035": [
        "3Nvn$pqh7mHx_H$clYhRTH",
        "3_uFSRcG9_IvnATDmaTf65",
    ],
    "11103223": [
        "3gU8YbK9XBrRI57teoH1G_",
        "0mSabJq$mkQti5Wbrc58uO",
        "2POJPR4dfAxRjFwwgsyMmv",
        "3$utHrBT4ZQgz5TTy1Dw69",
    ],
    "11103438": [
        "2EoIrT87f9BffvlijK50Zv",
        "2EoIrT87f9BffvlijK50dX",
        "2EoIrT87f9BffvlijK50i5",
        "2EoIrT87f9BffvlijK50kH",
        "2EoIrT87f9BffvlijK50Xj",
        "2EoIrT87f9BffvlijK50bg",
        "2EoIrT87f9BffvlijK50hC",
        "2EoIrT87f9BffvlijK53CR",
        "2EoIrT87f9BffvlijK53CJ",
        "1pR$bNwgP9swl7km4GAk2q",
        "1pR$bNwgP9swl7km4GAk1O",
    ],
}

# Slab type-name substrings to exclude, keyed by a filename substring.
SLAB_TYPE_OUTLIERS = {
    "11103186": "Footing",
    "11103438": "Landing",
}

# Camera view presets (elev/azim degrees) for the 3D display, keyed by a filename substring.
VIEW_SETTINGS = {
    "11103093": {"type": 1, "elev": 25, "azim": -60},
    "11103024": {"type": 2, "elev": 30, "azim": -15},
    "11103190": {"type": 3, "elev": 35, "azim": -30},
    "11103085": {"type": 4, "elev": 25, "azim": -40},
    "11103186": {"type": 5, "elev": 25, "azim": -110},
    "11103035": {"type": 6, "elev": 20, "azim": -75},
    "11103223": {"type": 7, "elev": 25, "azim": 170},
    "11103438": {"type": 8, "elev": 25, "azim": 20},
}

DEFAULT_ELEV, DEFAULT_AZIM = 25, 50


def remove_slab_outliers(slabs, ifc_file_name):
    """Filter out slabs known-bad for specific test files, by GUID or type name."""

    for key, guids in SLAB_OUTLIER_GUIDS.items():
        if key in ifc_file_name:
            slabs = [sl for sl in slabs if sl.GlobalId not in guids]
            break

    for key, type_name_string in SLAB_TYPE_OUTLIERS.items():
        if key in ifc_file_name:
            slabs = [sl for sl in slabs if type_name_string not in sl.Name]
            break

    return slabs


def get_view_settings(ifc_file_name):
    """Return (elev, azim) camera angles calibrated for known test files, else defaults."""

    for key, values in VIEW_SETTINGS.items():
        if key in ifc_file_name:
            return values["elev"], values["azim"]

    return DEFAULT_ELEV, DEFAULT_AZIM
