"""Interface text in Spanish and English.

``t(lang, key, **params)`` returns the string for ``lang``, formatted with
``params``. Both languages must define the same keys (checked by the tests).
"""

from __future__ import annotations

LANGUAGES = ("es", "en")

TEXTS: dict[str, dict[str, str]] = {
    "es": {
        "html_lang": "es",
        "brand_subtitle": "ARCHIVO FOTOGRÁFICO / ATLAS DE CAMPO",
        "top_meta": "ARCHIVO DIGITAL LPI · VISOR LOCAL",
        "project_page_title": "Página del proyecto",
        "repository_link": "GITHUB ↗",
        "repository_title": "Código fuente en GitHub",
        "eyebrow": "EXPLORACIÓN FOTOGRÁFICA · 1966—1967",
        "title": "Atlas orbital lunar",
        "title_note": (
            "Fotogramas históricos del archivo LPI proyectados sobre una esfera "
            "interactiva."
        ),
        "tab_atlas": "Atlas",
        "tab_moon": "La Luna",
        "tab_program": "Programa Lunar Orbiter",
        "globe_label": "VISTA 3D  /  ARRASTRA PARA ROTAR · CLICK EN UNA FOTO PARA "
        "VER SUS DATOS",
        "globe_note": "PROYECTADAS DESDE LA NAVE · ORIENTACIÓN ESTIMADA",
        "labels_toggle": "ETIQUETAS",
        "legend_high_altitude": "TOMA DE GRAN ALTITUD (> {km} KM)",
        "note_high_altitude": (
            "Toma de gran altitud: cubre una zona amplia y se proyecta sobre la "
            "parte de la Luna que fotografió. Su orientación se estima a partir "
            "del borde de la Luna visible en la imagen."
        ),
        "archive_kicker": "ARCHIVO DE IMÁGENES",
        "frame_heading": "Fotograma",
        "mission_placeholder": "MISIÓN",
        "frame_placeholder": "FOTOGRAMA",
        "mosaic_preparing": "PREPARANDO MOSAICO…",
        "load_button": "Cargar ↗",
        "random_button": "Al azar",
        "random_title": "Cargar un fotograma al azar de la misión",
        "export_label": "EXPORTAR MISIÓN",
        "export_csv_title": "Metadatos de las fotos cargadas (CSV)",
        "export_geojson_title": "Huellas proyectadas de las fotos cargadas (GeoJSON)",
        "connecting": "CONECTANDO CON EL ARCHIVO LPI…",
        "preview_alt": "Vista previa del fotograma Lunar Orbiter",
        "preview_caption": "VISTA PREVIA LPI",
        "preview_format": "JPG · ORIGINAL ONLINE",
        "open_record": "ABRIR REGISTRO ORIGINAL ↗",
        "footer_source": "FUENTE DE IMAGEN Y METADATOS: LUNAR AND PLANETARY INSTITUTE",
        "footer_rights": "LAS IMÁGENES PERTENECEN A SUS RESPECTIVOS TITULARES",
        "meta_mission": "MISIÓN",
        "meta_frame": "FOTOGRAMA",
        "meta_principal_point": "PUNTO PRINCIPAL",
        "meta_altitude": "ALTITUD DE LA NAVE",
        "meta_spacecraft_position": "POSICIÓN DE LA NAVE",
        "meta_sun_azimuth": "ACIMUT SOLAR",
        "meta_incidence_emission": "INCIDENCIA / EMISIÓN",
        "meta_phase": "ÁNGULO DE FASE",
        "meta_camera": "CÁMARA",
        "camera_medium": "80 MM · RESOLUCIÓN MEDIA",
        "camera_high": "610 MM · ALTA RESOLUCIÓN (CENTRO)",
        "meta_footprint": "HUELLA EN EL SUELO",
        "footprint_projected": "{width} × {height} km",
        "footprint_approximate": "≈ {width} × {height} km (APROX.)",
        "meta_emission_check": "EMISIÓN LPI / CALCULADA",
        "emission_check": "{lpi}  /  {computed}  (Δ {delta})",
        "emission_check_rejected": "{lpi}  /  {computed}  (Δ {delta} > {tolerance})",
        "note_emission_rejected": (
            "La emisión calculada con la posición de la nave no coincide con la "
            "del LPI: la foto no se proyecta y se dibuja como un parche "
            "aproximado orientado al norte."
        ),
        "status_connection_error": "ERROR DE CONEXIÓN · {error}",
        "status_load_error": "NO SE PUDO CARGAR · {error}",
        "status_frame_loaded": "LPI EN LÍNEA · {frame_id} · VISTA PREVIA RECIBIDA",
        "status_mission_frames": "MISIÓN {mission} · {count} FOTOGRAMAS",
        "mosaic_unavailable": "MOSAICO NO DISPONIBLE · {error}",
        "mosaic_failed": " · {count} SIN DATOS",
        "mosaic_done": "MOSAICO · {count} FOTOS EN LA ESFERA{failed}",
        "mosaic_loading": "DESCARGANDO MOSAICO · {loaded}/{total}",
        "error_invalid_frame_id": "El identificador del fotograma debe contener "
        "solo números.",
        "error_no_coordinates": "No se encontraron coordenadas para el fotograma "
        "{frame_id}.",
        "error_no_preview": "No se encontró una vista previa para el fotograma "
        "{frame_id}.",
        "error_invalid_mission": "La misión debe estar entre 1 y {missions}.",
        "error_no_frames": "No se encontraron fotogramas para la misión {mission}.",
    },
    "en": {
        "html_lang": "en",
        "brand_subtitle": "PHOTO ARCHIVE / FIELD ATLAS",
        "top_meta": "LPI DIGITAL ARCHIVE · LOCAL VIEWER",
        "project_page_title": "Project page",
        "repository_link": "GITHUB ↗",
        "repository_title": "Source code on GitHub",
        "eyebrow": "PHOTOGRAPHIC SURVEY · 1966—1967",
        "title": "Lunar orbital atlas",
        "title_note": (
            "Historic frames from the LPI archive projected onto an interactive globe."
        ),
        "tab_atlas": "Atlas",
        "tab_moon": "The Moon",
        "tab_program": "Lunar Orbiter program",
        "globe_label": "3D VIEW  /  DRAG TO ROTATE · CLICK A PHOTO FOR ITS DETAILS",
        "globe_note": "PROJECTED FROM THE SPACECRAFT · ORIENTATION ESTIMATED",
        "labels_toggle": "LABELS",
        "legend_high_altitude": "HIGH-ALTITUDE FRAME (> {km} KM)",
        "note_high_altitude": (
            "High-altitude frame: it covers a wide area and is projected onto the "
            "part of the Moon it photographed. Its orientation is estimated from "
            "the lunar limb visible in the image."
        ),
        "archive_kicker": "IMAGE ARCHIVE",
        "frame_heading": "Frame",
        "mission_placeholder": "MISSION",
        "frame_placeholder": "FRAME",
        "mosaic_preparing": "PREPARING MOSAIC…",
        "load_button": "Load ↗",
        "random_button": "Random",
        "random_title": "Load a random frame of the mission",
        "export_label": "EXPORT MISSION",
        "export_csv_title": "Metadata of the loaded photos (CSV)",
        "export_geojson_title": "Projected footprints of the loaded photos (GeoJSON)",
        "connecting": "CONNECTING TO THE LPI ARCHIVE…",
        "preview_alt": "Preview of the Lunar Orbiter frame",
        "preview_caption": "LPI PREVIEW",
        "preview_format": "JPG · ORIGINAL ONLINE",
        "open_record": "OPEN ORIGINAL RECORD ↗",
        "footer_source": "IMAGE AND METADATA SOURCE: LUNAR AND PLANETARY INSTITUTE",
        "footer_rights": "IMAGES BELONG TO THEIR RESPECTIVE OWNERS",
        "meta_mission": "MISSION",
        "meta_frame": "FRAME",
        "meta_principal_point": "PRINCIPAL POINT",
        "meta_altitude": "SPACECRAFT ALTITUDE",
        "meta_spacecraft_position": "SPACECRAFT POSITION",
        "meta_sun_azimuth": "SUN AZIMUTH",
        "meta_incidence_emission": "INCIDENCE / EMISSION",
        "meta_phase": "PHASE ANGLE",
        "meta_camera": "CAMERA",
        "camera_medium": "80 MM · MEDIUM RESOLUTION",
        "camera_high": "610 MM · HIGH RESOLUTION (MIDDLE)",
        "meta_footprint": "GROUND FOOTPRINT",
        "footprint_projected": "{width} × {height} km",
        "footprint_approximate": "≈ {width} × {height} km (APPROX.)",
        "meta_emission_check": "EMISSION LPI / COMPUTED",
        "emission_check": "{lpi}  /  {computed}  (Δ {delta})",
        "emission_check_rejected": "{lpi}  /  {computed}  (Δ {delta} > {tolerance})",
        "note_emission_rejected": (
            "The emission implied by the spacecraft position does not match the "
            "LPI's: the photo is not projected and is drawn as an approximate "
            "north-up patch."
        ),
        "status_connection_error": "CONNECTION ERROR · {error}",
        "status_load_error": "COULD NOT LOAD · {error}",
        "status_frame_loaded": "LPI ONLINE · {frame_id} · PREVIEW RECEIVED",
        "status_mission_frames": "MISSION {mission} · {count} FRAMES",
        "mosaic_unavailable": "MOSAIC UNAVAILABLE · {error}",
        "mosaic_failed": " · {count} WITHOUT DATA",
        "mosaic_done": "MOSAIC · {count} PHOTOS ON THE GLOBE{failed}",
        "mosaic_loading": "DOWNLOADING MOSAIC · {loaded}/{total}",
        "error_invalid_frame_id": "The frame ID must contain digits only.",
        "error_no_coordinates": "No coordinates found for frame {frame_id}.",
        "error_no_preview": "No preview found for frame {frame_id}.",
        "error_invalid_mission": "The mission must be between 1 and {missions}.",
        "error_no_frames": "No frames found for mission {mission}.",
    },
}


def normalize_language(lang: str | None, default: str = "es") -> str:
    """Return a supported language code, falling back to ``default``.

    Only the first two letters count, case-insensitively, so ``"EN-us"`` gives
    ``"en"``. Unsupported or empty values give ``default``.
    """
    lang = (lang or "").lower()[:2]
    return lang if lang in LANGUAGES else default


def t(lang: str, key: str, **params: object) -> str:
    """Return the text for ``key`` in ``lang``, formatted with ``params``.

    Args:
        lang: Language code; unsupported values fall back to Spanish.
        key: A key of ``TEXTS``, e.g. ``"status_mission_frames"``.
        **params: Values for the ``{placeholders}`` in the text.

    Raises:
        KeyError: If ``key`` does not exist or a placeholder has no value.
    """
    return TEXTS[normalize_language(lang)][key].format(**params)
