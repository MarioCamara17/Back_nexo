"""Compatibilidad con la primera versión del motor del chatbot.

La lógica geográfica vive en ``places.geo`` para poder reutilizarla desde la
API del mapa. Este módulo conserva los nombres históricos usados por el
chatbot y por sus pruebas.
"""

from places.geo import distance_km, nearby

__all__ = ["distance_km", "nearby"]
