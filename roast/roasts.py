"""Template-based roast writer. Free, deterministic (same day -> same text) and always on.

Each detector looks at a player's daily facts and, if it fires, produces a news item with
a headline, a short body, a big number and a severity. The page shows the most severe
items first. If an Anthropic API key is configured, llm.py can rewrite the wording later,
but the facts always come from here.
"""
import random

from .util import fmt_int, fmt_num, fmt_pct, fmt_minutes

# --------------------------------------------------------------------------- sections
# Each section has a "desk" somewhere in Runeterra, printed next to the section name.
DESKS = {
    "DAÑO": "Instituto Hextech de Piltover",
    "ECONOMÍA": "Lonja de Aguasturbias",
    "SUCESOS": "Comisaría de Piltover",
    "EL TIEMPO": "Islas de la Sombra",
    "DEPORTES": "Arena de Noxus",
    "SOCIEDAD": "Ecos de Jonia",
    "CIENCIA": "Academia de Piltover",
    "AGRICULTURA": "Cosechas de Demacia",
    "COMUNICACIÓN": "Radio Zaun",
    "POLÍTICA": "Corte de Demacia",
    "SALUD": "Laboratorios de Zaun",
    "CULTURA": "Biblioteca de Shurima",
    "VAR": "Observatorio del Monte Targon",
    "DERBI": "Arena de Noxus",
    "AUSENTES": "Perdidos en el Vacío",
    "EL FARO DE LA ESPERANZA": "Centinelas de la Luz",
    "SOLOQ CHALLENGE": "Enviado especial a la cola de Solo/Dúo",
}

# --------------------------------------------------------------------------- templates
T = {
    "portada": [
        ("{alias}, peor jugador del día: {wl} y {d} muertes en {games} partidas",
         "Con un KDA de {kda} y {dmg_txt}, {alias} se corona hoy como lastre oficial del grupo. "
         "Fuentes cercanas confirman que ya está en cola para la siguiente."),
        ("Escándalo en la Grieta: {alias} firma un {wl} y nadie le pide explicaciones porque ya no hacen falta",
         "{games} partidas, {d} muertes y un KDA de {kda}. La redacción ha revisado los datos tres veces "
         "buscando un error. No lo hay."),
        ("{alias} vuelve a hacerlo: {d} muertes, KDA {kda} y cero vergüenza",
         "El día de {alias} se resume en {wl}. {dmg_txt_cap}. El equipo rival ha pedido que se le "
         "conceda la medalla al mérito civil."),
        ("Última hora: {alias} confirma que sigue sin saber jugar ({wl})",
         "Tras {games} partidas, el veredicto es unánime: {d} muertes y un KDA de {kda}. "
         "Su campeón más sufrido hoy: {champ}."),
        ("{alias} lidera la clasificación de la vergüenza con un {wl} que ya es historia",
         "Ni el peor día de cualquier otro se le acerca: {d} muertes, KDA {kda} y {dmg_txt}. "
         "Mañana, más."),
    ],
    "dano": [
        ("{alias} fue el que menos daño hizo de su equipo en {n} de {g} partidas",
         "En su peor caso, con {champ} ({kdas}), se quedó en {dmg} de daño a campeones: el {share} "
         "de su equipo. Hasta el que menos aportaba le pasó por encima."),
        ("Investigación: ¿dónde está el daño de {alias}? Último en daño {n} veces",
         "Con {champ} firmó un {share} del daño de su equipo ({dmg}). Repartiendo a partes iguales "
         "le tocaba un 20 %. Ni eso."),
        ("{alias} dispara con balas de fogueo: {n} partidas como el que menos daño de su equipo",
         "Su obra cumbre: {champ}, {dmg} de daño, el {share} del total. Los súbditos enemigos "
         "sufrieron más que los campeones."),
    ],
    "economia": [
        ("La Lonja de Aguasturbias congela los fondos de {alias}: {gold} del oro, {share} del daño",
         "Con {champ} cobró {gap} puntos más de oro que de daño. En Aguasturbias han colgado a gente "
         "por estafas más pequeñas."),
        ("Malversación de fondos: {alias} se quedó el {gold} del oro y devolvió el {share} del daño",
         "Con {champ} recibió {gap} puntos más de oro que de daño. El equipo pagó los objetos; "
         "el enemigo no se enteró."),
        ("{alias}, el fichaje más caro y el que menos rinde: {gold} del oro, {share} del daño",
         "Partida con {champ}: {gap} puntos de diferencia entre lo que cobró y lo que aportó. "
         "Hacienda investiga."),
    ],
    "sucesos": [
        ("Detenido {alias} por alimentar al enemigo: {d} muertes con {champ}",
         "Los hechos ocurrieron en una {queue} de {mins} minutos. Resultado: {kdas}. "
         "{res_cap}. El rival ya le ha enviado una cesta de agradecimiento."),
        ("{alias} muere {d} veces en una sola partida y la policía de Piltover abre una investigación",
         "{champ}, {kdas}, {res}. Testigos aseguran que lo vieron entrar solo a la jungla enemiga "
         "una y otra vez."),
        ("Récord de {alias}: {d} muertes en {mins} minutos",
         "Con {champ} murió cada {every} de media. {res_cap}. El contador de muertes pidió una pausa."),
    ],
    "tiempo": [
        ("Previsión para {alias}: Niebla Negra durante {dead_mins} minutos",
         "Las Islas de la Sombra reclamaron a {alias} durante {dead_mins} minutos, el {dead_pct} de su "
         "tiempo en partida. Se esperan claros mañana, pero nadie lo garantiza."),
        ("Previsión para {alias}: gris durante {dead_mins} minutos",
         "Hoy pasó {dead_mins} minutos muerto, el {dead_pct} de su tiempo en partida. "
         "Probabilidad de respawn: alta. Probabilidad de servir de algo: baja."),
        ("{alias} se pasa {dead_mins} minutos en la pantalla gris",
         "El {dead_pct} de su día en la Grieta lo pasó mirando el contador de reaparición. "
         "Ya se sabe de memoria el mapa en blanco y negro."),
    ],
    "racha": [
        ("{alias} encadena {n} derrotas seguidas y sigue dándole a «Jugar otra vez»",
         "Su día terminó {wl}. Los expertos recomiendan apagar el ordenador; {alias} recomienda "
         "otra partida rápida."),
        ("Racha negra: {n} derrotas consecutivas para {alias}",
         "Ni cambiando de campeón ({champs}) consiguió cortar la sangría. Día cerrado con {wl}."),
    ],
    "pleno": [
        ("{alias} completa un pleno perfecto: {wl}",
         "{games} partidas, {games} derrotas. Ni una. La estadística también es un deporte y "
         "{alias} lo domina."),
        ("Cero victorias para {alias}: {wl} y a dormir",
         "Lo intentó con {champs}. El resultado no cambió. Mañana el contador vuelve a cero, "
         "que es justo donde lo dejó."),
    ],
    "desaparecido": [
        ("Se busca: {alias} solo participó en el {kp} de las kills de su equipo",
         "Su equipo peleaba y {alias} estaba en otra parte. Si alguien lo ve en la Grieta, "
         "que le avise de que hay una partida en curso."),
        ("{alias}, desaparecido en combate: {kp} de participación en kills",
         "De cada diez kills de su equipo, en más de seis no estaba. Fuentes cercanas apuntan a "
         "una larga relación con los súbditos de su línea."),
    ],
    "vision": [
        ("{alias} juega a ciegas: {vspm} de visión por minuto",
         "Ni un ward a la vista. Los arbustos de la Grieta guardan secretos que {alias} "
         "prefiere no conocer."),
    ],
    "farmeo": [
        ("Crisis en el campo: {alias} farmea {cspm} súbditos por minuto",
         "Los súbditos de su línea mueren de viejos. Un agricultor de verdad habría perdido la cosecha "
         "entera; {alias} solo perdió la partida."),
        ("{alias} y su relación pacífica con los súbditos: {cspm} por minuto",
         "Les deja vivir. Les deja pasar. Los súbditos lo consideran un aliado."),
    ],
    "pings": [
        ("{alias} hace {pings} pings en una sola partida",
         "Sus aliados confirman que ninguno sirvió para nada. Riot estudia ponerle un límite "
         "diario solo a él."),
    ],
    "rendicion": [
        ("Demacia no se rinde, pero {names} sí: {n_txt}",
         "Garen ha pedido que no se mencione su tierra en esta noticia. Votar sí antes de tiempo "
         "también es una forma de jugar; no la más honorable."),
        ("Bandera blanca: {names} {verb} {n_txt} hoy",
         "Votar sí antes de tiempo también es una forma de jugar. No la mejor."),
        ("Ante la duda, rendición: {names} {verb} {n_txt}",
         "Otros remontan; aquí se pulsa el botón de rendirse y se ahorra tiempo para la siguiente derrota."),
    ],
    "adiccion": [
        ("{alias} juega {games} partidas en un día y su familia pregunta por él",
         "{wl} y {hours} horas dentro del cliente. La luz del sol sigue esperándole."),
        ("Maratón de {alias}: {games} partidas, {wl}",
         "{hours} horas de LoL en un día. Si la constancia diera LP, ya sería Challenger."),
    ],
    "maldito": [
        ("{alias} insiste con {champ}: {n} partidas, {n} derrotas",
         "La definición de locura es repetir lo mismo esperando otro resultado. {alias} lo "
         "repitió {n} veces."),
        ("{champ} pide una orden de alejamiento contra {alias}: 0–{n}",
         "{n} partidas juntos y ninguna victoria. Hay relaciones que no deberían existir."),
    ],
    "penta": [
        ("{alias} hace un pentakill y la redacción lo revisa en el VAR",
         "Sí, ha pasado. Lo vamos a mencionar una vez y no volveremos a hablar del tema."),
    ],
    "gris": [
        ("Sin noticias de {alias}: {wl} y KDA {kda}",
         "Ni para bien ni para mal. El gris absoluto. Es casi peor."),
        ("Día anodino para {alias} ({wl}), lo cual para él ya es un éxito",
         "Sin escándalos, sin hazañas. La redacción se ha quedado sin material, que es lo más "
         "cerca que estará de un elogio."),
    ],
    "mencion": [
        ("El Faro de la Esperanza ilumina hoy a {alias}: {wl}",
         "Mientras la Niebla Negra cubría al resto del grupo, {alias} aguantó con un KDA de {kda}. "
         "Los Centinelas de la Luz no van a reclutarle, pero hoy al menos no se ha perdido en la Ruina."),
        ("Una luz en la Ruina: {alias} ({wl}) no ha sido el peor",
         "Los Centinelas de la Luz confirman un rayo de esperanza en el grupo: KDA {kda}. "
         "Que nadie se emocione; mañana vuelve la Niebla."),
        ("Desde el Faro, una señal: {alias} sobrevive al día ({wl})",
         "El mejor del grupo, que no es decir mucho. Los Centinelas de la Luz lo anotan en su diario "
         "con letra pequeña, por si acaso."),
    ],
    "duo": [
        ("{a} y {b}, dúo del desastre: {w}–{l} juntos",
         "Juntos suman más derrotas que victorias. Por separado, al menos, pierden en partidas distintas."),
        ("Sociedad limitada: {a} + {b} se van {w}–{l}",
         "La sinergia de este dúo es la de una tostadora en la bañera."),
    ],
    "derbi": [
        ("Derbi en la Grieta: {winner} humilla a {loser}",
         "{winner} ({winner_champ}, {winner_kda}) contra {loser} ({loser_champ}, {loser_kda}). "
         "La amistad sigue, el respeto no."),
        ("{loser} pierde el derbi contra {winner} y ya no puede hablar en el grupo",
         "{loser_champ} {loser_kda} contra {winner_champ} {winner_kda}. Se le ha retirado el derecho "
         "a opinar hasta nuevo aviso."),
    ],
    "ausentes": [
        ("Ausentes hoy: {names}",
         "Sus equipos habituales lo celebran. Mañana volverán, como siempre."),
        ("Desaparecidos del día: {names}",
         "Ni una partida. La Grieta respira tranquila por un día."),
    ],
    "vacio": [
        ("Día de luto: nadie del grupo ha jugado",
         "Ni una partida en 24 horas. La redacción, sin material, se ha ido a casa. Mañana más."),
        ("El Vacío se traga al grupo entero: cero partidas",
         "Ni rastro de ninguno en la Grieta. Desde Piltover piden calma: volverán, por desgracia."),
    ],
}

FRASES = [
    "El LP no se pierde, se transforma en el del rival.",
    "Si te rindes a los 15, por lo menos has perdido rápido.",
    "No es feed si lo haces con convicción.",
    "Un ward a tiempo es una muerte menos. Nadie del grupo lo sabe.",
    "La culpa siempre es del jungla, salvo cuando el jungla eres tú.",
    "Hay dos tipos de jugadores: los que farmean y los de este grupo.",
    "Jugar otra vez no es un plan, es un síntoma.",
    "El daño a campeones no se mide en intenciones.",
    "Morir dos veces por la misma emboscada es tradición, no casualidad.",
    "Quien con Flash no salta, en el gris se acaba.",
    "Si no ves el mapa, el mapa sí te ve a ti.",
    "Cada partida es una oportunidad nueva de decepcionar a cuatro personas.",
    "Perder en ranked es temporal. El historial es para siempre.",
    "La pantalla gris también es contenido.",
    "Ningún súbdito ha sido farmeado durante la elaboración de esta partida.",
]


# --------------------------------------------------------------------------- helpers
def _wl(w, l):
    return f"{w}–{l}"


def _join(names):
    names = list(names)
    return ", ".join(names[:-1]) + " y " + names[-1] if len(names) > 1 else (names[0] if names else "")


def _kdas(r):
    return f"{r['k']}/{r['d']}/{r['a']}"


def _champs(s, n=3):
    names = [c for c, _ in s["champs"][:n]]
    return ", ".join(names[:-1]) + " y " + names[-1] if len(names) > 1 else (names[0] if names else "?")


def _ctx(s):
    w = s["worst"]
    dmg_txt = (f"el {fmt_pct(s['dmg_share'])} del daño de su equipo" if s.get("dmg_share") is not None
               else "muy poco daño")
    return {
        "alias": s["alias"], "games": s["games"], "wl": _wl(s["wins"], s["losses"]),
        "d": s["d"], "kda": fmt_num(s["kda"], 2), "dmg_txt": dmg_txt,
        "dmg_txt_cap": dmg_txt[0].upper() + dmg_txt[1:] + " de media",
        "champ": w["champ"], "champs": _champs(s),
        "hours": fmt_num(s["play_seconds"] / 3600, 1),
    }


class Writer:
    def __init__(self, date_str):
        self.date = date_str
        self.items = []
        self.used = set()

    def _pick(self, kind, key):
        """Deterministic choice that avoids repeating a template inside the same edition."""
        rng = random.Random(f"{self.date}|{kind}|{key}")
        order = list(range(len(T[kind])))
        rng.shuffle(order)
        idx = next((i for i in order if (kind, i) not in self.used), order[0])
        self.used.add((kind, idx))
        return T[kind][idx]

    def add(self, kind, section, key, ctx, stat, stat_label, severity, player=None):
        head, body = self._pick(kind, key)
        self.items.append({
            "id": len(self.items), "kind": kind, "section": section, "desk": DESKS.get(section, ""),
            "player": player["slug"] if player else None,
            "alias": player["alias"] if player else None,
            "headline": head.format(**ctx), "body": body.format(**ctx),
            "stat": stat, "stat_label": stat_label, "severity": round(severity, 2),
            "facts": {k: v for k, v in ctx.items() if isinstance(v, (int, float, str))},
        })


# --------------------------------------------------------------------------- detectors
def _player_candidates(s):
    """Yields (kind, section, ctx, stat, stat_label, severity) for one player."""
    base = _ctx(s)
    out = []
    rows = s["rows"]

    lowest = [r for r in rows if r["lowest_dmg"] and not r["support"]]
    if lowest:
        r = min(lowest, key=lambda r: r["dmg_share"])
        ctx = {**base, "n": len(lowest), "g": s["non_support_games"], "champ": r["champ"],
               "kdas": _kdas(r), "dmg": fmt_int(r["dmg"]), "share": fmt_pct(r["dmg_share"])}
        out.append(("dano", "DAÑO", ctx, f"{len(lowest)}/{s['non_support_games']}",
                    "partidas como el que menos daño de su equipo",
                    4 + 3 * len(lowest) / max(s["non_support_games"], 1)))

    gaps = [r for r in rows if not r["support"] and r["gold_share"] - r["dmg_share"] >= 0.04]
    if gaps:
        r = max(gaps, key=lambda r: r["gold_share"] - r["dmg_share"])
        gap = (r["gold_share"] - r["dmg_share"]) * 100
        ctx = {**base, "champ": r["champ"], "gold": fmt_pct(r["gold_share"]),
               "share": fmt_pct(r["dmg_share"]), "gap": fmt_num(gap, 1)}
        out.append(("economia", "ECONOMÍA", ctx, f"−{fmt_num(gap, 1)}", "puntos entre oro y daño",
                    3 + gap * 0.4))

    if s["max_deaths"] >= 10:
        r = max(rows, key=lambda r: r["d"])
        mins = r["dur"] / 60
        ctx = {**base, "d": r["d"], "champ": r["champ"], "kdas": _kdas(r), "queue": r["queue_name"],
               "mins": int(mins), "every": fmt_minutes(r["dur"] / max(r["d"], 1)),
               "res": "victoria" if r["win"] else "derrota",
               "res_cap": "Aun así ganaron, de milagro" if r["win"] else "Derrota, claro"}
        out.append(("sucesos", "SUCESOS", ctx, str(r["d"]), "muertes en una partida",
                    5 + (r["d"] - 10) * 0.4))

    if s["dead"] >= 480:
        ctx = {**base, "dead_mins": int(s["dead"] // 60),
               "dead_pct": fmt_pct(s["dead"] / max(s["play_seconds"], 1))}
        out.append(("tiempo", "EL TIEMPO", ctx, f"{int(s['dead'] // 60)} min", "en la pantalla gris",
                    2.5 + s["dead"] / 600))

    if s["wins"] == 0 and s["games"] >= 2:
        out.append(("pleno", "DEPORTES", base, base["wl"], "victorias–derrotas", 4.5 + s["games"] * 0.5))
    elif s["max_loss_streak"] >= 3:
        ctx = {**base, "n": s["max_loss_streak"]}
        out.append(("racha", "DEPORTES", ctx, str(s["max_loss_streak"]), "derrotas seguidas",
                    3 + s["max_loss_streak"]))

    if s["games"] >= 1 and s["kp"] < 0.35:
        ctx = {**base, "kp": fmt_pct(s["kp"])}
        out.append(("desaparecido", "SOCIEDAD", ctx, fmt_pct(s["kp"], 0), "participación en kills",
                    3 + (0.35 - s["kp"]) * 20))

    sup_games = sum(1 for r in rows if r["support"])
    if s["vspm"] < 0.45 and sup_games == 0:
        ctx = {**base, "vspm": fmt_num(s["vspm"], 2)}
        out.append(("vision", "CIENCIA", ctx, fmt_num(s["vspm"], 2), "visión por minuto", 1.5))

    if s.get("cspm") is not None and s["cspm"] < 5.5:
        ctx = {**base, "cspm": fmt_num(s["cspm"], 1)}
        out.append(("farmeo", "AGRICULTURA", ctx, fmt_num(s["cspm"], 1), "súbditos por minuto",
                    2 + (5.5 - s["cspm"])))

    if s["max_pings"] >= 40:
        ctx = {**base, "pings": s["max_pings"]}
        out.append(("pings", "COMUNICACIÓN", ctx, str(s["max_pings"]), "pings en una partida",
                    2 + s["max_pings"] / 40))

    if s["games"] >= 7:
        out.append(("adiccion", "SALUD", base, str(s["games"]), "partidas en un día",
                    2 + (s["games"] - 7) * 0.3))

    if s["cursed_champ"] and s["wins"] > 0:  # with 0 wins the "pleno" item already says it
        champ, n = s["cursed_champ"]
        ctx = {**base, "champ": champ, "n": n}
        out.append(("maldito", "CULTURA", ctx, f"0–{n}", f"con {champ}", 2.5 + n))

    if s["pentas"]:
        out.append(("penta", "VAR", base, str(s["pentas"]), "pentakills (sospechosos)", 2))

    return out


def write_edition(facts, date_str, items_per_player=2):
    w = Writer(date_str)
    players = facts["players"]

    if not players:
        w.add("vacio", "PORTADA", "nadie", {}, "0", "partidas", 10)
    else:
        worst = players[0]
        ctx = _ctx(worst)
        w.add("portada", "PORTADA", worst["slug"], ctx, ctx["wl"], "victorias–derrotas",
              100, player=worst)

    for s in players:
        cands = sorted(_player_candidates(s), key=lambda c: -c[5])
        if s is players[0]:  # the front page already reports their win-loss
            cands = [c for c in cands if c[0] != "pleno"]
        limit = items_per_player
        if not cands and s is not players[-1]:
            cands = [("gris", "SOCIEDAD", _ctx(s), _wl(s["wins"], s["losses"]), "victorias–derrotas", 1)]
        for kind, section, ctx, stat, label, sev in cands[:limit]:
            w.add(kind, section, s["slug"], ctx, stat, label, sev, player=s)

    if len(players) >= 2:
        best = players[-1]
        ctx = _ctx(best)
        w.add("mencion", "EL FARO DE LA ESPERANZA", best["slug"], ctx, ctx["wl"], "victorias–derrotas", 0.5, player=best)

    for d in [d for d in facts["duos"] if d["l"] > d["w"]][:2]:
        if d["l"] > d["w"]:
            ctx = {k: d[k] for k in ("a", "b", "w", "l")}
            w.add("duo", "SOCIEDAD", f"{d['a']}-{d['b']}", ctx, f"{d['w']}–{d['l']}", "juntos",
                  3 + d["l"] - d["w"])

    surr = [s for s in players if s["surrendered_losses"]]
    if surr:
        surr_matches = {r["match"] for s in surr for r in s["rows"] if r["surrendered_loss"]}
        n = len(surr_matches)
        ctx = {"names": _join([s["alias"] for s in surr]), "verb": "se rindieron" if len(surr) > 1 else "se rindió",
               "n_txt": "una vez" if n == 1 else f"{n} veces"}
        w.add("rendicion", "POLÍTICA", "rendicion", ctx, str(n), "partidas rendidas" if n > 1 else "partida rendida",
              2 + n)

    for d in facts["derbies"][:2]:
        w.add("derbi", "DERBI", d["match"], dict(d), d["loser_kda"], f"KDA de {d['loser']}", 3.5)

    if facts["absent"] and players:
        names = facts["absent"]
        w.add("ausentes", "AUSENTES", "ausentes", {"names": _join(names)}, str(len(names)),
              "no jugaron" if len(names) > 1 else "no jugó", 0.2)

    items = sorted(w.items, key=lambda i: -i["severity"])
    for i, it in enumerate(items):
        it["id"] = i
    frase = random.Random(f"frase|{date_str}").choice(FRASES)
    return {"items": items, "frase": frase}
