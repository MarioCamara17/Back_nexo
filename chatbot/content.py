"""
Contenido editorial del asistente NEXO.

Los datos breves proceden de las fichas registradas en NEXO.
RECOMMENDED_IDS define destacados editoriales, no popularidad medida.
"""

LEGENDS = {
    # Parque Museo La Venta
    "a8d67c6c-5c1d-453c-8822-ae36b06193fc": (
        "Según la ficha de NEXO, Carlos Pellicer Cámara impulsó "
        "el traslado de los monumentos olmecas a Villahermosa "
        "para protegerlos y exhibirlos en un entorno natural."
    ),

    # Yumká
    "c4f5c9c4-6531-4d41-b651-a2c2f1a096ae": (
        "Según la ficha de NEXO, Yumká reúne ambientes de selva, "
        "sabana y estanque en un espacio dedicado a la conservación "
        "y la educación ambiental."
    ),

    # Cascadas de Reforma
    "a6308418-6ea5-46ed-8d16-5604af809d73": (
        "Según la ficha de NEXO, estas cascadas forman parte "
        "de los atractivos naturales de Balancán y complementan "
        "los recorridos arqueológicos de la región Ríos."
    ),

    # Museo Regional de Antropología Carlos Pellicer Cámara
    "3fc2481f-13e3-480f-a90c-9ff7df36574c": (
        "Según la ficha de NEXO, el nombre del museo honra "
        "a Carlos Pellicer Cámara, poeta tabasqueño e impulsor "
        "de la preservación del patrimonio cultural del estado."
    ),

    # Casa de los Azulejos
    "ecf4f0d8-d94f-4922-a842-4639bb18a44b": (
        "Según la ficha de NEXO, esta casa es un ejemplo de "
        "arquitectura señorial del siglo XIX y alberga "
        "el Museo de Historia de Tabasco desde 1985."
    ),

    # Laguna de las Ilusiones
    "d81ebe9c-9346-47ef-90a4-cb6407f2f567": (
        "Según la ficha de NEXO, la laguna es un referente "
        "natural de Villahermosa y forma parte del paisaje "
        "y de la identidad ambiental de la ciudad."
    ),

    # Zona Arqueológica de Moral-Reforma
    "fa2892d8-89a1-4eea-96ed-6b04fee8086f": (
        "Según la ficha de NEXO, el sitio tuvo distintos nombres. "
        "Su denominación actual hace referencia a los árboles "
        "de moral y al ejido Reforma-Provincia."
    ),

    # Zona Arqueológica de Pomoná
    "f440f3ab-040b-47b0-937a-477d3b8004b5": (
        "Según la ficha de NEXO, la ubicación de Pomoná "
        "se relaciona con antiguas rutas de comunicación "
        "y comercio vinculadas al río Usumacinta."
    ),

    # Cañón del Usumacinta
    "b3b00e88-0af3-4659-b9a4-1f1a469c2680": (
        "Según la ficha de NEXO, este paisaje natural de Tenosique "
        "está vinculado al río Usumacinta y a la zona "
        "de Boca del Cerro."
    ),

    # Puente de Boca del Cerro
    "222577a2-6624-4a50-a2fc-6c0fe5554594": (
        "Según la ficha de NEXO, el puente original fue inaugurado "
        "en 1950 y su arco de acero se convirtió en un elemento "
        "representativo del paisaje de Boca del Cerro."
    ),

    # Parque Central de Balancán
    "cd5b0fcc-523b-4620-bc4a-c2e0001b470f": (
        "Según la ficha de NEXO, este parque ha sido un punto "
        "de encuentro para la convivencia y las actividades "
        "sociales de la cabecera municipal."
    ),

    # Malecón de Emiliano Zapata
    "ff7ef566-1773-480e-ab3b-57f2bbd631e4": (
        "Según la ficha de NEXO, el malecón refleja la relación "
        "de Emiliano Zapata con el río Usumacinta y funciona "
        "como espacio de encuentro para habitantes y visitantes."
    ),

    # Parque de la Raza
    "daa172c4-e113-4df0-a3e4-cedfed1c5d61": (
        "Según la ficha de NEXO, este espacio público de "
        "Emiliano Zapata puede integrarse como una parada "
        "de descanso en recorridos urbanos."
    ),

    # Finca de los girasoles
    "1a24d4e6-1116-484f-abae-9f895b6dbf86": (
        "Según la ficha de NEXO, comenzó como un cultivo comercial. "
        "El interés por sus paisajes durante la floración "
        "motivó su apertura al turismo. La floración es estacional."
    ),

    # Iglesia del Señor de Tila
    "7aa31cea-7445-4516-9141-4de1e6dde244": (
        "Según la ficha de NEXO, la construcción del templo "
        "fue impulsada mediante la organización y las colectas "
        "de la comunidad. Su fachada de colores es uno "
        "de sus elementos más representativos."
    ),
}

RECOMMENDED_IDS = [
    # Parque Museo La Venta
    "a8d67c6c-5c1d-453c-8822-ae36b06193fc",

    # Yumká
    "c4f5c9c4-6531-4d41-b651-a2c2f1a096ae",

    # Zona Arqueológica de Moral-Reforma
    "fa2892d8-89a1-4eea-96ed-6b04fee8086f",

    # Finca de los girasoles
    "1a24d4e6-1116-484f-abae-9f895b6dbf86",

    # Iglesia del Señor de Tila
    "7aa31cea-7445-4516-9141-4de1e6dde244",
]