"""Datos iniciales. Las coordenadas son cartográficas OSM, no levantamientos GPS.
Fuentes consultadas el 10/11/2026. Los horarios se consultan en el operador.
"""
CHECKED_ON = '2026-11-10'
SOURCES = {
    'operator': {'label': 'Tren Maya: estaciones de Tabasco', 'url': 'https://www.trenmaya.gob.mx/comunicado080725.php'},
    'guide': {'label': 'INAH: Gran Guía del Tren Maya', 'url': 'https://www.trenmaya.gob.mx/images/granguiainah.pdf'},
    'tenosique': {'label': 'Gobierno de Tabasco: inicio de operaciones de Tenosique', 'url': 'https://tabasco.gob.mx/comunicados/inicia-operaciones-la-estacion-tenosique-del-tren-maya-marca-una-nueva-etapa-de'},
    'tramo': {'label': 'Tren Maya: estaciones del Tramo 1', 'url': 'https://www.trenmaya.gob.mx/comunicado150724.php'},
}
STATIONS = [
    {
        'slug': 'boca-del-cerro', 'name': 'Boca del Cerro', 'municipality': 'Tenosique', 'order': 1,
        'latitude': '17.4297800', 'longitude': '-91.4957500',
        'summary': 'Una puerta de entrada a los paisajes del Usumacinta y al patrimonio maya de Tenosique.',
        'history': 'Boca del Cerro forma parte del Tramo 1 del Tren Maya. Su entorno conecta la experiencia ferroviaria con el paisaje ribereño. La guía del INAH vincula esta zona con Pomoná y el Cañón del Usumacinta; estos atractivos requieren traslados adicionales desde la estación.',
        'coordinates_source': 'https://www.openstreetmap.org/way/1237337318',
        'sources': [SOURCES['operator'], SOURCES['guide'], SOURCES['tramo'], {'label': 'Coordenadas cartográficas OSM / Mapcarta', 'url': 'https://mapcarta.com/es/W1237337318'}],
    },
    {
        'slug': 'tenosique', 'name': 'Tenosique', 'municipality': 'Tenosique', 'order': 2,
        'latitude': '17.4603900', 'longitude': '-91.4306000',
        'summary': 'Conexión con la cabecera municipal, su identidad cultural y los recorridos de la región Ríos.',
        'history': 'La estación Tenosique inició operaciones el 7 de julio de 2025, según el Gobierno de Tabasco. La ceremonia incluyó la Danza del Pochó y un viaje hacia El Triunfo. Es una estación distinta de Boca del Cerro, aunque ambas se encuentran en el mismo municipio.',
        'coordinates_source': 'https://www.openstreetmap.org/way/1237432410',
        'sources': [SOURCES['operator'], SOURCES['tenosique'], SOURCES['tramo'], {'label': 'Coordenadas cartográficas OSM / Mapcarta', 'url': 'https://mapcarta.com/es/W1237432410'}],
    },
    {
        'slug': 'el-triunfo', 'name': 'El Triunfo', 'municipality': 'Balancán', 'order': 3,
        'latitude': '17.9238400', 'longitude': '-91.1709900',
        'summary': 'Punto de conexión ferroviaria de Balancán con el patrimonio arqueológico y natural de la región.',
        'history': 'El Triunfo integra el corredor Palenque–Escárcega. La Gran Guía del INAH la presenta como acceso a Moral-Reforma y a las Cascadas de Reforma, con traslado terrestre adicional. La antigua estación ferroviaria de El Triunfo tiene una historia propia: no debe confundirse con las instalaciones actuales del Tren Maya.',
        'coordinates_source': 'https://www.openstreetmap.org/way/1237431003',
        'sources': [SOURCES['operator'], SOURCES['guide'], SOURCES['tramo'], {'label': 'Secretaría de Cultura: antigua estación El Triunfo', 'url': 'https://sic.cultura.gob.mx/ficha.php?table=fnme&table_id=146'}, {'label': 'Coordenadas cartográficas OSM / Mapcarta', 'url': 'https://mapcarta.com/es/W1237431003'}],
    },
]
