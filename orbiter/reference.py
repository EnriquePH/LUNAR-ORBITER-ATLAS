"""Reference tabs: summarised facts about the Moon and the Lunar Orbiter program.

The text summarises two Wikipedia articles in Spanish and English, so it is
licensed CC BY-SA 4.0, not MIT; each tab links its source and the licence.
"""

from __future__ import annotations

from dash import html

WIKIPEDIA_LICENSE = "CC BY-SA 4.0"
LICENSE_URLS = {
    "es": "https://creativecommons.org/licenses/by-sa/4.0/deed.es",
    "en": "https://creativecommons.org/licenses/by-sa/4.0/",
}
MOON_SOURCE = ("Wikipedia (es) · «Luna»", "https://es.wikipedia.org/wiki/Luna")
PROGRAM_SOURCE = (
    "Wikipedia (en) · «Lunar Orbiter program»",
    "https://en.wikipedia.org/wiki/Lunar_Orbiter_program",
)

CONTENT = {
    "es": {
        "moon_kicker": "SATÉLITE NATURAL",
        "moon_title": "La Luna",
        "program_kicker": "NASA · 1966—1967",
        "program_title": "Programa Lunar Orbiter",
        "in_numbers": "En cifras",
        "mission_log": "Diario de las misiones",
        "source": ("Resumen de ", ", bajo licencia "),
        "mission_header": [
            "Misión",
            "Lanzamiento",
            "Fotografías",
            "Impacto",
            "Objetivo",
        ],
        "moon_facts": [
            (
                "Cuerpo",
                [
                    ("Diámetro ecuatorial", "3474,8 km (¼ del terrestre)"),
                    ("Masa", "7,349 × 10²² kg (1/81 de la Tierra)"),
                    ("Densidad media", "3,34 g/cm³"),
                    ("Volumen", "2,1958 × 10¹⁰ km³"),
                    ("Superficie", "38 millones de km²"),
                    ("Gravedad superficial", "1,62 m/s²"),
                    ("Velocidad de escape", "2,38 km/s"),
                ],
            ),
            (
                "Órbita y rotación",
                [
                    ("Distancia media", "384 403 km"),
                    ("Perigeo / apogeo", "363 300 km / 405 500 km"),
                    ("Excentricidad", "0,0549"),
                    ("Inclinación orbital", "5,145°"),
                    ("Periodo sideral", "27 d 7 h 43 min"),
                    ("Periodo sinódico (fases)", "29 d 12 h 44 min"),
                    ("Rotación", "Síncrona: 27 d 7 h 44 min"),
                    ("Inclinación del eje", "1,54°"),
                ],
            ),
            (
                "Superficie y entorno",
                [
                    ("Albedo", "0,12 (tan oscura como el carbón)"),
                    ("Magnitud aparente", "−12,6 (Luna llena)"),
                    ("Temperatura", "−233 °C mín. · 123 °C máx."),
                    ("Media día / noche", "107 °C / −153 °C"),
                    ("Presión en superficie", "3 × 10⁻¹⁰ Pa (casi sin atmósfera)"),
                    (
                        "Corteza",
                        "O 43 % · Si 21 % · Al 10 % · Ca 9 % · Fe 9 % · Mg 5 %",
                    ),
                ],
            ),
        ],
        "moon_summary": [
            "Único satélite natural de la Tierra y el quinto mayor del sistema "
            "solar; en proporción a su planeta es el satélite más grande, y el "
            "segundo más denso tras Ío.",
            "Gira de forma síncrona con la Tierra, así que siempre muestra la misma "
            "cara: mares oscuros de origen volcánico entre montañas antiguas y "
            "cráteres de impacto.",
            "Su gravedad produce las mareas y alarga poco a poco el día terrestre. "
            "Desde la Tierra se ve del mismo tamaño que el Sol, lo que permite los "
            "eclipses solares totales.",
            "Se formó hace unos 4500 millones de años, probablemente tras un gran "
            "impacto contra la Tierra primitiva.",
            "Es el único cuerpo celeste pisado por humanos: el Apolo 8 la orbitó en "
            "1968 y seis misiones Apolo alunizaron entre 1969 y 1972, trayendo más "
            "de 380 kg de roca.",
            "El Lunojod 1 soviético (1970) fue el primer vehículo robótico en su "
            "superficie. Orbitadores recientes han confirmado hielo de agua en "
            "cráteres polares en sombra permanente, y el programa Artemis (desde "
            "2022) prepara la vuelta de astronautas.",
        ],
        "program_facts": [
            (
                "Misiones",
                "5 naves no tripuladas de EE. UU. (1966–1967), todas con éxito",
            ),
            ("Lanzador", "Atlas-Agena D"),
            (
                "Objetivo",
                "Cartografiar la Luna para elegir los lugares de alunizaje del Apolo",
            ),
            (
                "Cobertura",
                "99 % de la superficie, con resolución de 60 m o mejor (hasta 1 m)",
            ),
            ("Fotogramas", "2180 de alta resolución y 882 de resolución media"),
            ("Cámara", "Kodak de doble objetivo: 610 mm (alta) y 80 mm (media)"),
            (
                "Película",
                "70 mm revelada a bordo, escaneada y enviada como vídeo analógico",
            ),
            ("Nave", "Cono truncado de 1,65 m de alto y 1,5 m de base; 375 W solares"),
            ("Gestión y coste", "NASA Langley · unos 200 millones de dólares"),
        ],
        "program_summary": [
            "Las misiones 1 a 3 volaron en órbitas de baja inclinación para "
            "fotografiar 20 posibles lugares de alunizaje tripulado.",
            "Las misiones 4 y 5 usaron órbitas polares altas con fines científicos: "
            "la 4 cubrió toda la cara visible y el 9 % de la oculta, y la 5 completó "
            "la cara oculta y 36 zonas seleccionadas.",
            "Tomaron las primeras fotos de la Tierra desde la Luna (Lunar Orbiter 1, "
            "agosto de 1966) y la primera imagen de la Tierra completa (Lunar "
            "Orbiter 5, 8 de agosto de 1967).",
            "El seguimiento Doppler de las naves permitió cartografiar el campo "
            "gravitatorio lunar y descubrir los mascons, concentraciones de masa "
            "bajo algunos mares.",
            "Al terminar, todas las naves se estrellaron a propósito contra la Luna "
            "para no interferir con las misiones Apolo.",
            "Desde 2007, el proyecto LOIRP recupera las imágenes desde las cintas "
            "analógicas originales, con mucha más resolución que las de los años "
            "sesenta.",
        ],
        "missions": [
            (
                "Lunar Orbiter 1",
                "10 ago 1966",
                "18–29 ago 1966",
                "29 oct 1966",
                "Alunizaje",
            ),
            (
                "Lunar Orbiter 2",
                "6 nov 1966",
                "18–25 nov 1966",
                "11 oct 1967",
                "Alunizaje",
            ),
            (
                "Lunar Orbiter 3",
                "5 feb 1967",
                "15–23 feb 1967",
                "9 oct 1967",
                "Alunizaje",
            ),
            (
                "Lunar Orbiter 4",
                "4 may 1967",
                "11–26 may 1967",
                "~31 oct 1967",
                "Cartografía",
            ),
            (
                "Lunar Orbiter 5",
                "1 ago 1967",
                "6–18 ago 1967",
                "31 ene 1968",
                "Cartografía y alta resolución",
            ),
        ],
    },
    "en": {
        "moon_kicker": "NATURAL SATELLITE",
        "moon_title": "The Moon",
        "program_kicker": "NASA · 1966—1967",
        "program_title": "Lunar Orbiter program",
        "in_numbers": "In numbers",
        "mission_log": "Mission log",
        "source": ("Summary of ", ", licensed under "),
        "mission_header": ["Mission", "Launch", "Imaging", "Impact", "Purpose"],
        "moon_facts": [
            (
                "Body",
                [
                    ("Equatorial diameter", "3,474.8 km (¼ of Earth's)"),
                    ("Mass", "7.349 × 10²² kg (1/81 of Earth)"),
                    ("Mean density", "3.34 g/cm³"),
                    ("Volume", "2.1958 × 10¹⁰ km³"),
                    ("Surface area", "38 million km²"),
                    ("Surface gravity", "1.62 m/s²"),
                    ("Escape velocity", "2.38 km/s"),
                ],
            ),
            (
                "Orbit and rotation",
                [
                    ("Mean distance", "384,403 km"),
                    ("Perigee / apogee", "363,300 km / 405,500 km"),
                    ("Eccentricity", "0.0549"),
                    ("Orbital inclination", "5.145°"),
                    ("Sidereal period", "27 d 7 h 43 min"),
                    ("Synodic period (phases)", "29 d 12 h 44 min"),
                    ("Rotation", "Synchronous: 27 d 7 h 44 min"),
                    ("Axial tilt", "1.54°"),
                ],
            ),
            (
                "Surface and environment",
                [
                    ("Albedo", "0.12 (as dark as coal)"),
                    ("Apparent magnitude", "−12.6 (full Moon)"),
                    ("Temperature", "−233 °C min · 123 °C max"),
                    ("Mean day / night", "107 °C / −153 °C"),
                    ("Surface pressure", "3 × 10⁻¹⁰ Pa (almost no atmosphere)"),
                    ("Crust", "O 43% · Si 21% · Al 10% · Ca 9% · Fe 9% · Mg 5%"),
                ],
            ),
        ],
        "moon_summary": [
            "Earth's only natural satellite and the fifth largest in the Solar "
            "System; relative to its planet it is the largest satellite, and the "
            "second densest after Io.",
            "It rotates synchronously with Earth, so it always shows the same face: "
            "dark volcanic maria between ancient highlands and impact craters.",
            "Its gravity raises the tides and slowly lengthens Earth's day. Seen "
            "from Earth it is the same size as the Sun, which makes total solar "
            "eclipses possible.",
            "It formed about 4.5 billion years ago, probably after a giant impact "
            "with the early Earth.",
            "It is the only celestial body humans have walked on: Apollo 8 orbited "
            "it in 1968 and six Apollo missions landed between 1969 and 1972, "
            "bringing back more than 380 kg of rock.",
            "The Soviet Lunokhod 1 (1970) was the first robotic rover on its "
            "surface. Recent orbiters have confirmed water ice in permanently "
            "shadowed polar craters, and the Artemis program (since 2022) is "
            "preparing the return of astronauts.",
        ],
        "program_facts": [
            ("Missions", "5 uncrewed US spacecraft (1966–1967), all successful"),
            ("Launch vehicle", "Atlas-Agena D"),
            ("Goal", "Map the Moon to select Apollo landing sites"),
            (
                "Coverage",
                "99% of the surface at 60 m resolution or better (down to 1 m)",
            ),
            ("Frames", "2,180 high-resolution and 882 medium-resolution"),
            ("Camera", "Kodak dual-lens: 610 mm (high) and 80 mm (medium)"),
            ("Film", "70 mm, developed on board, scanned and sent as analog video"),
            ("Spacecraft", "Truncated cone 1.65 m tall, 1.5 m base; 375 W solar power"),
            ("Management and cost", "NASA Langley · about US$200 million"),
        ],
        "program_summary": [
            "Missions 1 to 3 flew low-inclination orbits to image 20 potential "
            "crewed landing sites.",
            "Missions 4 and 5 used high polar orbits for broader science: Lunar "
            "Orbiter 4 covered the entire near side and 9% of the far side, and "
            "Lunar Orbiter 5 completed the far side and 36 preselected areas.",
            "They took the first pictures of Earth from the Moon (Lunar Orbiter 1, "
            "August 1966) and the first image of the whole Earth (Lunar Orbiter 5, "
            "8 August 1967).",
            "Doppler tracking of the spacecraft mapped the Moon's gravity field and "
            "revealed mascons, mass concentrations beneath some maria.",
            "When their work was done, every spacecraft was deliberately crashed "
            "into the Moon so it would not interfere with Apollo flights.",
            "Since 2007 the LOIRP project has recovered the images from the original "
            "analog tapes, at far higher resolution than the 1960s releases.",
        ],
        "missions": [
            (
                "Lunar Orbiter 1",
                "10 Aug 1966",
                "18–29 Aug 1966",
                "29 Oct 1966",
                "Landing sites",
            ),
            (
                "Lunar Orbiter 2",
                "6 Nov 1966",
                "18–25 Nov 1966",
                "11 Oct 1967",
                "Landing sites",
            ),
            (
                "Lunar Orbiter 3",
                "5 Feb 1967",
                "15–23 Feb 1967",
                "9 Oct 1967",
                "Landing sites",
            ),
            (
                "Lunar Orbiter 4",
                "4 May 1967",
                "11–26 May 1967",
                "~31 Oct 1967",
                "Mapping",
            ),
            (
                "Lunar Orbiter 5",
                "1 Aug 1967",
                "6–18 Aug 1967",
                "31 Jan 1968",
                "Mapping and high-resolution survey",
            ),
        ],
    },
}


def _fact_rows(facts: list[tuple[str, str]]) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Span(label, className="meta-label"),
                    html.Span(value, className="meta-value"),
                ],
                className="meta-row",
            )
            for label, value in facts
        ],
        className="metadata",
    )


def _summary(paragraphs: list[str]) -> html.Ul:
    return html.Ul([html.Li(text) for text in paragraphs], className="summary-list")


def _source(source: tuple[str, str], lang: str) -> html.P:
    title, url = source
    before, between = CONTENT[lang]["source"]
    return html.P(
        [
            before,
            html.A(title, href=url, target="_blank", rel="noreferrer"),
            between,
            html.A(
                WIKIPEDIA_LICENSE,
                href=LICENSE_URLS[lang],
                target="_blank",
                rel="noreferrer",
            ),
            ".",
        ],
        className="source-note",
    )


def moon_tab(lang: str) -> html.Div:
    """Build the «Moon» tab: summary, source and fact cards in ``lang``."""
    text = CONTENT[lang]
    return html.Div(
        [
            html.Section(
                [
                    html.Div(text["moon_kicker"], className="section-kicker"),
                    html.H2(text["moon_title"], className="side-heading"),
                    _summary(text["moon_summary"]),
                    _source(MOON_SOURCE, lang),
                ],
                className="reference-intro",
            ),
            html.Div(
                [
                    html.Section(
                        [
                            html.H3(title, className="reference-heading"),
                            _fact_rows(facts),
                        ],
                        className="reference-card",
                    )
                    for title, facts in text["moon_facts"]
                ],
                className="reference-cards",
            ),
        ],
        className="reference-layout",
    )


def program_tab(lang: str) -> html.Div:
    """Build the «Lunar Orbiter program» tab: summary, facts and mission log."""
    text = CONTENT[lang]
    table = html.Table(
        [
            html.Thead(html.Tr([html.Th(cell) for cell in text["mission_header"]])),
            html.Tbody(
                [html.Tr([html.Td(cell) for cell in row]) for row in text["missions"]]
            ),
        ],
        className="mission-table",
    )
    return html.Div(
        [
            html.Section(
                [
                    html.Div(text["program_kicker"], className="section-kicker"),
                    html.H2(text["program_title"], className="side-heading"),
                    _summary(text["program_summary"]),
                    _source(PROGRAM_SOURCE, lang),
                ],
                className="reference-intro",
            ),
            html.Div(
                [
                    html.Section(
                        [
                            html.H3(text["in_numbers"], className="reference-heading"),
                            _fact_rows(text["program_facts"]),
                        ],
                        className="reference-card",
                    ),
                    html.Section(
                        [
                            html.H3(text["mission_log"], className="reference-heading"),
                            html.Div(table, className="table-scroll"),
                        ],
                        className="reference-card",
                    ),
                ],
                className="reference-cards",
            ),
        ],
        className="reference-layout",
    )
