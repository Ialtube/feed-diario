"""The newsroom's bible: who the paper's fictional characters are and what they want.

A character with no wish generates no stories. Each member of the cast has a wish, a secret and a
relationship with someone else in the cast, and the newsroom has threads of its own that move on
even on days when nobody played. The canon picks this up the first time it is loaded (filling only
what is missing), and from then on the editor changes it day by day.
"""

CAST = [
    {"nombre": "Comisario Ambrosio Cobretuerca", "cargo": "Jefe de la Comisaría de Piltover",
     "institucion": "Comisaría de Piltover",
     "deseo": "Meter entre rejas al Barón de la Moneda con una prueba que aguante un juicio",
     "secreto": "Juega a escondidas con una cuenta de Plata y tiene peor KDA que cualquiera de sus fichados",
     "relacion": "La fiscal Hexwick le tumba los atestados por defectos de forma, y él lo vive como algo personal"},
    {"nombre": "Fiscal Lucrecia Hexwick", "cargo": "Fiscal del Tribunal de Piltover",
     "institucion": "Tribunal de Piltover",
     "deseo": "Sentar en el banquillo a un jugador entero, no solo a sus partidas",
     "secreto": "No ha ganado un juicio en su vida: todos sus acusados se declararon culpables antes de empezar",
     "relacion": "Rival jurada del abogado Leguleyo; desprecia los atestados de Cobretuerca"},
    {"nombre": "Doctor Ezequiel Humoverde", "cargo": "Forense de Zaun", "institucion": "Laboratorios de Zaun",
     "deseo": "Que le asciendan a jefe de los Laboratorios de Zaun",
     "secreto": "Cobra por autopsia, así que necesita que el grupo siga muriendo",
     "relacion": "Le pasa a Barbanegra las cifras de muertes antes de que salgan en el periódico"},
    {"nombre": "Barbanegra el Contable", "cargo": "Corredor de la Lonja", "institucion": "Lonja de Aguasturbias",
     "deseo": "Recuperar la confianza de la Lonja antes de que le pasen por la quilla",
     "secreto": "Tiene apuestas abiertas contra los mismos jugadores que cotiza",
     "relacion": "Socio en la sombra del doctor Humoverde; el director le protege y nadie sabe por qué",
     "estado": "Bajo investigación interna por el escándalo de los smurfs"},
    {"nombre": "Madame Niebla", "cargo": "Vidente y meteoróloga", "institucion": "Islas de la Sombra",
     "deseo": "Acertar una predicción buena, una sola, antes de jubilarse",
     "secreto": "Copia sus previsiones del parte de bajas del día anterior",
     "relacion": "El Hermano Venda le lleva la contraria por principio",
     "estado": "Su contrato depende de su porcentaje de aciertos"},
    {"nombre": "Hermano Venda", "cargo": "Cronista de los Centinelas de la Luz", "institucion": "El Faro de la Esperanza",
     "deseo": "Ver un día entero en que nadie del grupo muera más de cinco veces",
     "secreto": "Se le está acabando la fe: tiene una carta de traslado a la Gaceta de Noxus sin enviar",
     "relacion": "Discute con Madame Niebla por cada previsión"},
    {"nombre": "Don Evaristo Plumanegra", "cargo": "Director de El Rincón del Feeder", "institucion": "La redacción",
     "deseo": "Vender más que la Gaceta de Noxus, aunque sea un solo día",
     "secreto": "Aprobó él la fórmula equivocada de la General y dejó que la culpa se la llevaran los números",
     "relacion": "Protege a Barbanegra porque le debe dinero; enemigo público de Valeria Puñoférreo"},
    {"nombre": "Gaspar Leguleyo", "cargo": "Abogado de oficio de los acusados", "institucion": "Bufete Leguleyo, Zaun",
     "deseo": "Ganarle un juicio a la fiscal Hexwick",
     "secreto": "Cobra en LP prestados y todavía no ha cobrado a nadie",
     "relacion": "Defiende a cualquiera que la fiscal acuse, con razón o sin ella"},
    {"nombre": "Valeria Puñoférreo", "cargo": "Directora de La Gaceta de Noxus", "institucion": "La Gaceta de Noxus",
     "deseo": "Hundir al Rincón del Feeder y quedarse con sus lectores",
     "secreto": "Lee el Rincón cada mañana antes que su propio periódico",
     "relacion": "Enemiga pública del director Plumanegra; defiende a quien el Rincón humilla, por llevar la contraria"},
]

THREADS = [
    {"id": "el-escandalo-de-la-lonja", "titulo": "El escándalo de la Lonja", "abierto": "2026-10-21",
     "reparto": ["Barbanegra el Contable", "Don Evaristo Plumanegra"],
     "resumen": "Tras publicar una ruina que no existió (sumaba los smurfs a sus dueños), Barbanegra está bajo "
                "investigación interna. El director le protege. ¿Por qué?"},
    {"id": "la-guerra-de-los-periodicos", "titulo": "La guerra de los periódicos", "abierto": "2026-10-21",
     "reparto": ["Don Evaristo Plumanegra", "Valeria Puñoférreo"],
     "resumen": "La Gaceta de Noxus sale a la calle para desmentir cada mañana al Rincón del Feeder y quitarle "
                "los lectores."},
]


def ensure(canon):
    """Adds what is missing from the bible to the canon, never overwriting what the editor changed."""
    by_name = {e["nombre"].lower(): e for e in canon["elenco"]}
    for c in CAST:
        cur = by_name.get(c["nombre"].lower())
        if cur is None:
            canon["elenco"].append(dict(c, semilla=True))
            continue
        for k, v in c.items():
            cur.setdefault(k, v)
    ids = {h["id"] for h in canon["hilos"]}
    for t in THREADS:
        if t["id"] not in ids:
            canon["hilos"].append(dict(t, protagonistas=[], semilla=True, capitulos=[],
                                       estados=[{"fecha": t["abierto"], "estado": "abierto"}]))
    return canon
