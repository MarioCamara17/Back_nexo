"""Comprensión de lenguaje natural para el asistente NEXO.

No usa servicios externos: normaliza el texto, reconoce intenciones,
extrae radios/tiempos, categorías, municipios y nombres de lugares. Está
pensado para ser predecible y fácil de probar.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Iterable


# Orden de prioridad cuando varias intenciones compiten.
INTENT_PRIORITY = [
    "directions",
    "logistics",
    "legends",
    "history",
    "itinerary",
    "nearby",
    "popular",
    "filter",
    "favorites",
    "help",
    "thanks",
    "goodbye",
    "greeting",
    "place_info",
    "list",
]

INTENT_RULES: dict[str, tuple[str, ...]] = {
    "directions": (
        "como llego",
        "como llegar",
        "llegar a",
        "llegar desde",
        "direccion",
        "direcciones",
        "ruta desde",
        "trazar",
        "indicaciones",
        "me llevas",
        "ir a",
    ),
    "logistics": (
        "horario",
        "horarios",
        "abre",
        "abren",
        "cierra",
        "cierran",
        "costo",
        "costos",
        "precio",
        "precios",
        "entrada",
        "entradas",
        "tarifa",
        "cuanto cuesta",
        "cuanto sale",
        "cuanto vale",
    ),
    "legends": (
        "leyenda",
        "leyendas",
        "curiosidad",
        "curiosidades",
        "dato curioso",
        "datos curiosos",
        "misterio",
        "misterios",
        "sabias que",
        "mito",
        "mitos",
        "secreto",
        "secretos",
    ),
    "history": (
        "historia",
        "historico",
        "origen",
        "fundacion",
        "fue construido",
        "antecedente",
        "antecedentes",
        "pasado",
    ),
    "itinerary": (
        "itinerario",
        "ruta",
        "rutas",
        "recorrido",
        "recorridos",
        "plan",
        "planes",
        "un dia",
        "visitar en",
        "organiza",
        "organizar",
        "armar",
        "tour",
        "paradas",
    ),
    "nearby": (
        "cerca",
        "cercano",
        "cercana",
        "cercanos",
        "cercanas",
        "alrededor",
        "radio",
        "distancia",
        "distancias",
        "kilometros",
        "kilometro",
        "por aqui",
        "que hay cerca",
        "a pocos",
    ),
    "popular": (
        "destacado",
        "destacados",
        "popular",
        "populares",
        "recomienda",
        "recomiendame",
        "recomendacion",
        "recomendaciones",
        "imperdible",
        "imperdibles",
        "mejor",
        "mejores",
        "top",
        "favorito",
        "favoritos",
    ),
    "filter": (
        "filtrar",
        "filtro",
        "filtros",
        "categoria",
        "categorias",
        "solo",
        "muestrame",
        "ver lugares",
        "ensename",
        "mostrar",
    ),
    "favorites": (
        "favorito",
        "favoritos",
        "guardar",
        "guardo",
        "guardados",
        "guardar lugar",
        "mis lugares",
    ),
    "help": (
        "ayuda",
        "que puedes hacer",
        "opciones",
        "como funciona",
        "capacidades",
        "en que me puedes ayudar",
        "que sabes hacer",
    ),
    "thanks": (
        "gracias",
        "te agradezco",
        "muchas gracias",
        "muy amable",
    ),
    "goodbye": (
        "adios",
        "hasta luego",
        "nos vemos",
        "chao",
        "hasta pronto",
    ),
    "greeting": (
        "hola",
        "buenos dias",
        "buenas tardes",
        "buenas noches",
        "que tal",
        "hey",
        "saludos",
        "buen dia",
    ),
    "place_info": (
        "informacion",
        "donde esta",
        "que es",
        "hablame de",
        "cuentame de",
        "cuentame sobre",
        "detalles",
        "conocer",
        "sobre el lugar",
    ),
    "list": (
        "que lugares",
        "lista",
        "catalogo",
        "todos los lugares",
        "muestrame lugares",
        "sitios",
        "atractivos",
    ),
}

CATEGORY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "naturaleza": (
        "naturaleza",
        "natural",
        "ecoturismo",
        "selva",
        "rios",
        "rio",
        "cascada",
        "cascadas",
        "laguna",
        "lagunas",
        "paisaje",
        "paisajes",
    ),
    "cultura": (
        "cultura",
        "cultural",
        "museo",
        "museos",
        "arquitectura",
        "patrimonio",
        "pueblo",
        "pueblos",
        "iglesia",
        "iglesias",
    ),
    "historia": (
        "historia",
        "historico",
        "arqueologia",
        "arqueologico",
        "zona arqueologica",
        "ruinas",
        "sitio arqueologico",
    ),
    "aventura": (
        "aventura",
        "adrenalina",
        "senderismo",
        "caminata",
        "caminatas",
        "excursion",
        "excursiones",
        "trekking",
    ),
}

PLACE_ALIASES: dict[str, tuple[str, ...]] = {
    "parque museo la venta": ("la venta", "parque la venta", "museo la venta"),
    "yumka": ("yumka", "yumka centro de interpretacion"),
    "cascadas de reforma": ("cascadas de reforma", "cascadas", "reforma"),
    "museo regional de antropologia carlos pellicer camara": (
        "museo regional",
        "carlos pellicer",
        "museo de antropologia",
    ),
    "casa de los azulejos": ("casa de los azulejos", "azulejos", "museo de historia"),
    "laguna de las ilusiones": ("laguna de las ilusiones", "laguna", "ilusiones"),
    "zona arqueologica de moral reforma": (
        "moral reforma",
        "moral-reforma",
        "zona arqueologica moral",
        "moral",
    ),
    "zona arqueologica de pomona": (
        "pomona",
        "pomona",
        "zona arqueologica pomona",
    ),
    "canon del usumacinta": ("canon del usumacinta", "canon", "usumacinta"),
    "puente de boca del cerro": (
        "puente de boca del cerro",
        "boca del cerro",
        "puente",
    ),
    "parque central de balancan": (
        "parque central de balancan",
        "parque central",
    ),
    "malecon de emiliano zapata": (
        "malecon de emiliano zapata",
        "malecon",
    ),
    "parque de la raza": ("parque de la raza", "la raza", "raza"),
    "finca de los girasoles": ("finca de los girasoles", "girasoles", "finca"),
    "iglesia del senor de tila": (
        "iglesia del senor de tila",
        "iglesia de colores",
        "tila",
        "senor de tila",
    ),
}

STOPWORDS = {
    "a",
    "al",
    "algo",
    "algun",
    "alguna",
    "algunos",
    "algunas",
    "como",
    "con",
    "cual",
    "cuales",
    "cuando",
    "de",
    "del",
    "donde",
    "el",
    "en",
    "es",
    "esta",
    "este",
    "esto",
    "hay",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "mis",
    "muy",
    "para",
    "pero",
    "por",
    "que",
    "se",
    "sin",
    "sobre",
    "su",
    "sus",
    "un",
    "una",
    "uno",
    "y",
    "ya",
}

INTENT_WORDS = {
    word
    for phrases in INTENT_RULES.values()
    for phrase in phrases
    for word in phrase.split()
}

AFFIRMATIVE = {
    "si",
    "sí",
    "claro",
    "dale",
    "ok",
    "okay",
    "vale",
    "adelante",
    "por supuesto",
    "acepto",
    "correcto",
}

NEGATIVE = {
    "no",
    "nop",
    "nope",
    "ahora no",
    "despues",
    "luego",
    "cancelar",
    "cancela",
}


def normalize(text: str | None) -> str:
    """Minúsculas, sin acentos ni signos, con espacios simples."""

    if not text:
        return ""

    decomposed = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    cleaned = re.sub(r"[^a-zA-Z0-9ñÑ\s]", " ", without_accents)
    cleaned = cleaned.replace("ñ", "n").replace("Ñ", "N")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def words(text: str | None) -> list[str]:
    return [word for word in normalize(text).split() if word]


def detect_intent(text: str | None) -> str | None:
    """Devuelve la intención más probable, o ``None`` si no hay señal."""

    normalized = normalize(text)
    if not normalized:
        return None

    scores: dict[str, int] = {}

    for intent, phrases in INTENT_RULES.items():
        score = 0
        for phrase in phrases:
            if phrase in normalized:
                score += 1 + phrase.count(" ")
        if score:
            scores[intent] = score

    if not scores:
        return None

    # Expresiones que suelen pedir un recorrido aunque incluyan "cerca".
    if re.search(r"\b(recorrido|itinerario|plan|ruta|rutas)\b", normalized):
        scores["itinerary"] = scores.get("itinerary", 0) + 3

    if re.search(r"\b(cerca|cercanos|cercanas|alrededor)\b", normalized):
        scores["nearby"] = scores.get("nearby", 0) + 1

    # "¿Cómo guardo lugares y recorridos?" debe responder como ayuda de
    # favoritos, no como una petición de itinerario.
    if re.search(r"\b(guardar|guardo|guardados|favoritos?)\b", normalized):
        scores["favorites"] = scores.get("favorites", 0) + 4

    priority = {intent: index for index, intent in enumerate(INTENT_PRIORITY)}

    return max(
        scores,
        key=lambda intent: (scores[intent], -priority.get(intent, 999)),
    )


def extract_radius(text: str | None, default: float | None = None) -> float | None:
    """Extrae un radio en kilómetros de expresiones como ``10 km``."""

    normalized = normalize(text)
    if not normalized:
        return default

    patterns = (
        r"(\d+(?:[.,]\d+)?)\s*(?:km|kms|kilometro|kilometros)\b",
        r"radio\s*(?:de|:)?\s*(\d+(?:[.,]\d+)?)",
        r"a\s+(\d+(?:[.,]\d+)?)\s*(?:km|kms|kilometro|kilometros)\b",
    )

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            try:
                value = float(match.group(1).replace(",", "."))
            except ValueError:
                continue
            return min(100.0, max(0.5, value))

    return default


def extract_minutes(text: str | None) -> int | None:
    """Extrae una duración en minutos (acepta horas)."""

    normalized = normalize(text)
    if not normalized:
        return None

    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:min|mins|minuto|minutos)\b", normalized)
    if match:
        try:
            return max(1, int(float(match.group(1).replace(",", "."))))
        except ValueError:
            return None

    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:h|hr|hrs|hora|horas)\b", normalized)
    if match:
        try:
            return max(1, int(float(match.group(1).replace(",", ".")) * 60))
        except ValueError:
            return None

    return None


def extract_category(
    text: str | None,
    categories: Iterable[str] | None = None,
) -> str | None:
    """Detecta una categoría por nombre o sinónimos."""

    normalized = normalize(text)
    if not normalized:
        return None

    available = {
        normalize(category): str(category)
        for category in (categories or [])
        if category
    }

    for name, synonyms in CATEGORY_SYNONYMS.items():
        if any(re.search(rf"\b{re.escape(synonym)}\b", normalized) for synonym in synonyms):
            return available.get(normalize(name), name.capitalize())

    for normalized_name, original in available.items():
        if re.search(rf"\b{re.escape(normalized_name)}\b", normalized):
            return original

    return None


def extract_municipality(
    text: str | None,
    municipalities: Iterable[str] | None = None,
) -> str | None:
    normalized = normalize(text)
    if not normalized:
        return None

    for municipality in municipalities or []:
        candidate = normalize(municipality)
        if candidate and re.search(rf"\b{re.escape(candidate)}\b", normalized):
            return str(municipality)

    return None


def _place_tokens(name: str) -> set[str]:
    return {
        token
        for token in words(name)
        if len(token) > 2 and token not in STOPWORDS and token not in INTENT_WORDS
    }


def _query_tokens(text: str) -> set[str]:
    return {
        token
        for token in words(text)
        if len(token) > 2 and token not in STOPWORDS and token not in INTENT_WORDS
    }


def _score_place(text: str, place_name: str) -> float:
    normalized_text = normalize(text)
    normalized_name = normalize(place_name)

    if not normalized_text or not normalized_name:
        return 0.0

    if normalized_name in normalized_text:
        return 1.0

    aliases = PLACE_ALIASES.get(normalized_name, ())
    for alias in aliases:
        if normalize(alias) in normalized_text:
            return 0.98

    query_tokens = _query_tokens(text)
    place_tokens = _place_tokens(place_name)

    if not query_tokens or not place_tokens:
        return 0.0

    overlap = len(query_tokens & place_tokens) / len(place_tokens)
    sequence = difflib.SequenceMatcher(
        None,
        normalized_text,
        normalized_name,
    ).ratio()

    return max(overlap * 0.95, sequence * 0.82)


def find_place(text: str | None, places: Iterable) -> object | None:
    """Busca el lugar más probable dentro del catálogo.

    ``places`` puede ser una lista de objetos con ``name`` o una lista de
    diccionarios con ``name``. Devuelve el objeto original o ``None``.
    """

    if not text:
        return None

    ranked: list[tuple[float, object]] = []

    for place in places:
        name = place.get("name") if isinstance(place, dict) else getattr(place, "name", "")
        if not name:
            continue
        score = _score_place(text, str(name))
        if score:
            ranked.append((score, place))

    if not ranked:
        return None

    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, best_place = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0

    if best_score < 0.58:
        return None

    # Evita elegir un lugar al azar cuando dos fichas se parecen demasiado.
    if best_score < 0.9 and best_score - second_score < 0.08:
        return None

    return best_place


def is_affirmative(text: str | None) -> bool:
    normalized = normalize(text)
    return any(
        re.search(rf"\b{re.escape(phrase)}\b", normalized)
        for phrase in AFFIRMATIVE
    )


def is_negative(text: str | None) -> bool:
    normalized = normalize(text)
    return any(
        re.search(rf"\b{re.escape(phrase)}\b", normalized)
        for phrase in NEGATIVE
    )
