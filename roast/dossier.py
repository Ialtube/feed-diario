"""The day's dossier: every story angle the data allows, scored and checked against the
last few editions so the paper does not tell the same stories every day.

The robot used to decide the paper (fixed detectors -> fixed stories). Now it only proposes:
Claude, as editor, picks the angles, their weight on the page and their format.
Every number in an angle comes from the stored match data, so the stories can be checked.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta

from .analyze import REMAKE_SECONDS, build_facts, game_rows
from .site import general_leaderboard
from .util import fmt_int, fmt_minutes, fmt_num, fmt_pct, get_tz, ms_to_local

RECENT_DAYS = 3          # an angle used in the last 3 editions loses most of its score
FIXED = {"faro", "ausentes"}  # appear every day on purpose; never penalised

# Angles of editions written before the dossier existed, rebuilt from the kind of their items.
LEGACY_KINDS = {"sucesos": "muertes", "economia": "oro_dano", "tiempo": "gris", "dano": "ultimo_dano",
                "racha": "racha", "mencion": "faro", "duo": "duo", "pings": "pings", "penta": "multikill",
                "rendicion": "rendicion", "ausentes": "ausentes", "maldito": "maldito", "pleno": "dia_negro"}


def used_keys(edition):
    if "angulos_usados" in edition:
        return edition["angulos_usados"]
    keys = []
    for it in edition.get("items", []):
        tipo = LEGACY_KINDS.get(it.get("kind"))
        if tipo:
            keys.append(":".join(x for x in (tipo, it.get("player")) if x))
    return keys


def _players(store, friends):
    out = []
    for f in friends:
        puuid = store.player_state(f["riot_id"]).get("puuid")
        if puuid:
            out.append(dict(f, puuid=puuid))
    return out


def _history(store, players, before_ms, ignored):
    """Every game of every friend that ended before the edition window, by player."""
    by_puuid = {p["puuid"]: p for p in players}
    rows = defaultdict(list)
    for m in store.matches().values():
        if m["end"] >= before_ms or m["queue"] in ignored or m["dur"] < REMAKE_SECONDS:
            continue
        for r in game_rows(m, by_puuid):
            rows[r["slug"]].append(r)
    for v in rows.values():
        v.sort(key=lambda r: r["end"])
    return rows


def _kda(r):
    return f"{r['k']}/{r['d']}/{r['a']}"


def _mins(sec):
    return int(round(sec / 60))


def build_dossier(cfg, store, friends, edition, editions):
    start, end = edition["window"]
    tz = get_tz(cfg["timezone"])
    players = _players(store, friends)
    facts = build_facts(store.matches(), players, start, end, cfg["ignored_queues"])
    hist = _history(store, players, start, cfg["ignored_queues"])
    prev = sorted([e for e in editions if e["date"] < edition["date"]], key=lambda e: e["date"])
    recent = prev[-RECENT_DAYS:]
    used_on = {}
    for e in recent:
        for k in used_keys(e):
            used_on[k] = e["date"]
    type_count = Counter(k.split(":")[0] for e in recent for k in set(used_keys(e)))

    angles = []

    def add(tipo, slug, tema, titulo, datos, score, positivo=False, extra=None, campeon=None, alias=None):
        key = ":".join(str(x) for x in (tipo, slug, extra) if x)
        novedad = "nuevo"
        if tipo not in FIXED:
            if key in used_on:
                score *= 0.35
                novedad = f"usado el {used_on[key]}"
            elif type_count[tipo] >= 2:
                score *= 0.7
                novedad = f"tema frecuente ({type_count[tipo]} de los últimos {len(recent)} días)"
        angles.append({"clave": key, "tipo": tipo, "tema": tema, "jugador": slug, "alias": alias,
                       "titulo": titulo, "positivo": positivo, "puntuacion": int(round(score)),
                       "novedad": novedad, "campeon": campeon, "datos": datos})

    # ------------------------------------------------------------------ per player
    for s in facts["players"]:
        slug, alias, rows = s["slug"], s["alias"], s["rows"]
        P = dict(alias=alias)
        past = hist.get(slug, [])

        worst = max(rows, key=lambda r: r["d"])
        if worst["d"] >= 8:
            add("muertes", slug, "SUCESOS", f"{alias} muere {worst['d']} veces con {worst['champ']}",
                {"kda": _kda(worst), "campeon": worst["champ"], "minutos": _mins(worst["dur"]),
                 "muere_cada": fmt_minutes(worst["dur"] / max(worst["d"], 1)), "cola": worst["queue_name"],
                 "resultado": "victoria" if worst["win"] else "derrota"},
                30 + 4 * (worst["d"] - 8) + (0 if worst["win"] else 8), campeon=worst["champ"], **P)

        non_sup = [r for r in rows if not r["support"]]
        if non_sup:
            g = max(non_sup, key=lambda r: r["gold_share"] - r["dmg_share"])
            gap = (g["gold_share"] - g["dmg_share"]) * 100
            if gap >= 6:
                add("oro_dano", slug, "ECONOMÍA", f"{alias} cobra mucho más oro del daño que devuelve",
                    {"campeon": g["champ"], "oro": fmt_pct(g["gold_share"]), "dano": fmt_pct(g["dmg_share"]),
                     "diferencia_puntos": fmt_num(gap, 1), "kda": _kda(g)},
                    22 + 2 * gap, campeon=g["champ"], **P)
            low = [r for r in non_sup if r["lowest_dmg"]]
            if low:
                r = min(low, key=lambda r: r["dmg_share"])
                add("ultimo_dano", slug, "DAÑO", f"{alias}, el que menos daño hizo de su equipo",
                    {"veces": len(low), "partidas": len(non_sup), "campeon": r["champ"],
                     "dano": fmt_int(r["dmg"]), "cuota": fmt_pct(r["dmg_share"]), "kda": _kda(r)},
                    22 + 8 * len(low), campeon=r["champ"], **P)

        laners = [r for r in rows if r["pos"] in ("TOP", "MIDDLE", "BOTTOM") and r["dur"] >= 1200]
        if laners:
            r = min(laners, key=lambda r: r["cspm"])
            if r["cspm"] < 5.5:
                add("farmeo", slug, "AGRICULTURA", f"{alias} deja los súbditos sin recoger",
                    {"campeon": r["champ"], "farmeo": r["cs"], "por_minuto": fmt_num(r["cspm"], 1),
                     "minutos": _mins(r["dur"]), "diferencia_con_su_rival": r["cs_diff"], "rival": r["opp_champ"]},
                    28 + (5.5 - r["cspm"]) * 10, campeon=r["champ"], **P)
            r = min(laners, key=lambda r: r["gold_diff"] if r["gold_diff"] is not None else 0)
            if r["gold_diff"] is not None and r["gold_diff"] <= -2500:
                add("calle", slug, "DEPORTES", f"{alias} pierde su calle contra {r['opp_champ']}",
                    {"campeon": r["champ"], "rival": r["opp_champ"], "oro_de_diferencia": fmt_int(r["gold_diff"]),
                     "farmeo_de_diferencia": r["cs_diff"], "su_kda": _kda(r), "kda_del_rival": r["opp_kda"],
                     "resultado": "victoria" if r["win"] else "derrota"},
                    30 + abs(r["gold_diff"]) / 250, campeon=r["champ"], **P)

        long_rows = [r for r in rows if r["dur"] >= 1200]
        if long_rows:
            r = min(long_rows, key=lambda r: r["vspm"] / (2.5 if r["support"] else 1))
            limit = 1.2 if r["support"] else 0.45
            if r["vspm"] < limit:
                add("vision", slug, "CIENCIA", f"{alias} juega a ciegas",
                    {"campeon": r["champ"], "vision": r["vision"], "guardianes_puestos": r["wards"],
                     "minutos": _mins(r["dur"]), "rol": r["role"]},
                    24 + (limit - r["vspm"]) * 30, campeon=r["champ"], **P)

        tank = [r for r in rows if r["taken_share"] >= 0.3 and r["dmg_share"] < 0.2 and not r["support"]]
        if tank:
            r = max(tank, key=lambda r: r["taken_share"])
            add("saco", slug, "SALUD", f"{alias}, saco de boxeo oficial de su equipo",
                {"campeon": r["champ"], "dano_recibido": fmt_pct(r["taken_share"]), "dano_hecho": fmt_pct(r["dmg_share"]),
                 "kda": _kda(r)}, 26 + r["taken_share"] * 40, campeon=r["champ"], **P)

        late = [r for r in rows if 1 <= ms_to_local(r["start"], tz).hour < 7]
        if late:
            r = max(late, key=lambda r: ms_to_local(r["start"], tz).hour)
            add("madrugada", slug, "SOCIEDAD", f"{alias} juega de madrugada",
                {"hora_de_inicio": ms_to_local(r["start"], tz).strftime("%H:%M"), "partidas_de_madrugada": len(late),
                 "resultados": f"{sum(x['win'] for x in late)}–{sum(not x['win'] for x in late)}", "campeon": r["champ"]},
                30 + 6 * sum(not x["win"] for x in late), campeon=r["champ"], **P)

        if s["play_seconds"] >= 3 * 3600:
            add("maraton", slug, "SOCIEDAD", f"{alias} pasa el día entero en la Grieta",
                {"horas": fmt_num(s["play_seconds"] / 3600, 1), "partidas": s["games"],
                 "balance": f"{s['wins']}–{s['losses']}"}, 28 + s["play_seconds"] / 3600 * 4, **P)

        if s["losses"] >= 3 and s["losses"] - s["wins"] >= 2:
            add("dia_negro", slug, "DEPORTES", f"{alias} cierra el día con {s['wins']}–{s['losses']}",
                {"balance": f"{s['wins']}–{s['losses']}", "muertes": s["d"], "kda": fmt_num(s["kda"], 2),
                 "campeones": ", ".join(c for c, _ in s["champs"][:3])}, 32 + 5 * s["losses"], **P)
        if s["max_loss_streak"] >= 3:
            add("racha", slug, "DEPORTES", f"{alias} encadena {s['max_loss_streak']} derrotas seguidas",
                {"seguidas": s["max_loss_streak"], "balance": f"{s['wins']}–{s['losses']}"},
                26 + 6 * s["max_loss_streak"], **P)

        dead_min = s["dead"] / 60
        if dead_min >= 10:
            add("gris", slug, "EL TIEMPO", f"{alias} pasa {int(dead_min)} minutos en la pantalla gris",
                {"minutos": int(dead_min), "porcentaje": fmt_pct(s["dead"] / max(s["play_seconds"], 1))},
                16 + dead_min * 0.8, **P)

        if s["max_pings"] >= 40:
            add("pings", slug, "COMUNICACIÓN", f"{alias} manda {s['max_pings']} pings en una partida",
                {"pings": s["max_pings"]}, 18 + s["max_pings"] / 5, **P)

        if s["early_surrenders"]:
            add("rendicion", slug, "POLÍTICA", f"{alias} se rinde antes de tiempo",
                {"rendiciones_tempranas": s["early_surrenders"]}, 30, **P)

        # history-based angles
        champs_before = {r["champ"] for r in past}
        if len(past) >= 5:
            for r in rows:
                if r["champ"] not in champs_before:
                    add("estreno", slug, "CULTURA", f"{alias} estrena a {r['champ']} en la hemeroteca",
                        {"campeon": r["champ"], "kda": _kda(r), "resultado": "victoria" if r["win"] else "derrota",
                         "partidas_previas_registradas": len(past)},
                        24 + (12 if not r["win"] else 0) + max(0, r["d"] - 6) * 2, extra=r["champ"], campeon=r["champ"], **P)
                    break
            prev_max = max(x["d"] for x in past)
            if worst["d"] > prev_max:
                add("record", slug, "SUCESOS", f"Récord personal de muertes de {alias}",
                    {"muertes": worst["d"], "record_anterior": prev_max, "campeon": worst["champ"],
                     "partidas_en_la_hemeroteca": len(past) + len(rows)},
                    44 + 3 * (worst["d"] - prev_max), campeon=worst["champ"], **P)
        allrows = past + rows
        streak = 0
        for r in reversed(allrows):
            if r["win"]:
                break
            streak += 1
        days = {ms_to_local(r["end"], tz).date() for r in allrows[len(allrows) - streak:]} if streak else set()
        if streak >= 4 and len(days) >= 2:
            add("racha_larga", slug, "DEPORTES", f"{alias} lleva {streak} derrotas seguidas en {len(days)} días",
                {"derrotas_seguidas": streak, "dias": len(days)}, 30 + 4 * streak, **P)
        for champ, n in Counter(r["champ"] for r in allrows).items():
            wins = sum(r["win"] for r in allrows if r["champ"] == champ)
            if n >= 3 and wins == 0 and any(r["champ"] == champ for r in rows):
                add("maldito", slug, "CULTURA", f"{alias} y {champ}: 0–{n} en la hemeroteca",
                    {"campeon": champ, "balance": f"0–{n}"}, 30 + 5 * n, extra=champ, campeon=champ, **P)

        # good news (El Faro and the bright spots)
        for r in rows:
            lvl = 4 if r["multi"][3] else 3 if r["multi"][2] else 2 if r["multi"][1] else 0
            if lvl:
                name = {2: "triple kill", 3: "quadra kill", 4: "pentakill"}[lvl]
                add("multikill", slug, "EL FARO DE LA ESPERANZA", f"{alias} firma un {name}",
                    {"jugada": name, "campeon": r["champ"], "kda": _kda(r),
                     "resultado": "victoria" if r["win"] else "derrota"},
                    20 + 15 * lvl, positivo=True, campeon=r["champ"], **P)
                break
        good = [r for r in rows if r["win"] and r["kda"] >= 6]
        if good:
            r = max(good, key=lambda r: r["kda"])
            add("exhibicion", slug, "EL FARO DE LA ESPERANZA", f"{alias} se luce con {r['champ']}",
                {"campeon": r["champ"], "kda": _kda(r), "ratio": fmt_num(r["kda"], 2), "dano": fmt_pct(r["dmg_share"])},
                22 + r["kda"], positivo=True, campeon=r["champ"], **P)
        solo = [r for r in rows if r["solo"] >= 3]
        if solo:
            r = max(solo, key=lambda r: r["solo"])
            add("solokills", slug, "DEPORTES", f"{alias} gana {r['solo']} duelos en solitario",
                {"asesinatos_en_solitario": r["solo"], "campeon": r["champ"], "kda": _kda(r)},
                20 + 4 * r["solo"], positivo=True, campeon=r["champ"], **P)
        carry = [r for r in rows if not r["support"] and r["dmg_share"] >= 0.32]
        if carry:
            r = max(carry, key=lambda r: r["dmg_share"])
            add("carry", slug, "DAÑO", f"{alias} hace el {fmt_pct(r['dmg_share'], 0)} del daño de su equipo",
                {"campeon": r["champ"], "cuota": fmt_pct(r["dmg_share"]), "kda": _kda(r),
                 "resultado": "victoria" if r["win"] else "derrota"},
                24 + (r["dmg_share"] - 0.32) * 100, positivo=True, campeon=r["champ"], **P)

    # ------------------------------------------------------------------ the group
    players_today = facts["players"]
    if len(players_today) >= 2:
        best = players_today[-1]
        add("faro", best["slug"], "EL FARO DE LA ESPERANZA", f"{best['alias']}, el mejor del día",
            {"balance": f"{best['wins']}–{best['losses']}", "kda": fmt_num(best["kda"], 2),
             "campeones": ", ".join(c for c, _ in best["champs"][:3])}, 40, positivo=True, alias=best["alias"])
    tot = facts["totals"]
    if tot["games"] >= 3 and all(s["losses"] == 0 for s in players_today):
        add("pleno", None, "OPINIÓN", f"El grupo no pierde ni una: {tot['games']} de {tot['games']}",
            {"partidas": tot["games"], "partidas_distintas": tot["matches"], "muertes": tot["deaths"],
             "minutos_en_gris": int(tot["dead_seconds"] // 60), "minutos_jugados": int(tot["play_seconds"] // 60)},
            52 + 3 * tot["games"], positivo=True)
    elif tot["games"] >= 3 and all(s["wins"] == 0 for s in players_today):
        add("hundimiento", None, "SUCESOS", f"El grupo no gana ni una: 0 de {tot['games']}",
            {"partidas": tot["games"], "muertes": tot["deaths"]}, 55 + 3 * tot["games"])
    by_match = defaultdict(list)
    for s in players_today:
        for r in s["rows"]:
            by_match[r["match"]].append(r)
    premades = []
    for mid, rs in by_match.items():
        teams = defaultdict(list)
        for r in rs:
            teams[r["win"]].append(r)
        for won, team in teams.items():
            if len(team) >= 3:
                premades.append((mid, won, team))
    # only the three most striking group games, or a busy day is all premades
    premades.sort(key=lambda x: (x[1], -len(x[2])))
    for mid, won, team in premades[:3]:
        team.sort(key=lambda r: -r["kda"])
        add("premade", None, "DEPORTES", f"Partida de {len(team)} del grupo: {'victoria' if won else 'derrota'}",
            {"jugadores": ", ".join(f"{r['alias']} ({r['champ']}, {_kda(r)})" for r in team),
             "resultado": "victoria" if won else "derrota", "minutos": _mins(team[0]["dur"]),
             "kills_del_grupo": sum(r["k"] for r in team), "muertes_del_grupo": sum(r["d"] for r in team),
             "mejor": team[0]["alias"], "peor": team[-1]["alias"]},
            38 + (12 if not won else 0) + 4 * len(team), extra=mid, campeon=team[-1]["champ"])
    for d in facts["duos"]:
        if d["l"] > d["w"] and d["w"] + d["l"] >= 2:
            add("duo", f"{d['a']}+{d['b']}", "SOCIEDAD", f"{d['a']} y {d['b']}, {d['w']}–{d['l']} juntos",
                {"balance": f"{d['w']}–{d['l']}"}, 22 + 5 * (d["l"] - d["w"]))
    for d in facts["derbies"]:
        add("derbi", f"{d['winner']}+{d['loser']}", "DEPORTES", f"Derbi: {d['winner']} gana a {d['loser']}",
            dict(d), 36)
    if facts["absent"]:
        add("ausentes", None, "SOCIEDAD", f"{len(facts['absent'])} del grupo no juegan",
            {"ausentes": ", ".join(facts["absent"])}, 10)

    # general standings: did the leader change?
    if prev:
        before = general_leaderboard(prev)
        after = general_leaderboard(prev + [edition])
        if before and after and before[0]["slug"] != after[0]["slug"]:
            add("general", None, "DEPORTES", f"{after[0]['alias']} pasa a liderar la General de la vergüenza",
                {"nuevo_lider": after[0]["alias"], "puntos": after[0]["points"], "anterior": before[0]["alias"]}, 34)

    # evergreen: a week ago, and the profile of someone not featured lately
    d = date.fromisoformat(edition["date"])
    week = next((e for e in prev if e["date"] == (d - timedelta(days=7)).isoformat()), None)
    if week and week.get("items"):
        add("hemeroteca", None, "CULTURA", "Hace una semana en este periódico",
            {"fecha": week["date"], "portada_de_entonces": week["items"][0]["headline"],
             "clasificacion_de_entonces": ", ".join(f"{r['alias']} {r['wins']}–{r['losses']}" for r in week["ranking"][:4])},
            14, extra=week["date"])
    featured = Counter(k.split(":")[1] for e in recent for k in used_keys(e) if k.count(":") >= 1)
    pool = sorted([kv for kv in hist.items() if len(kv[1]) >= 5], key=lambda kv: (featured[kv[0]], -len(kv[1])))
    if pool:
        slug, rows = pool[0]
        wins = sum(r["win"] for r in rows)
        k = sum(r["k"] for r in rows); dd = sum(r["d"] for r in rows); a = sum(r["a"] for r in rows)
        champs = Counter(r["champ"] for r in rows).most_common(3)
        alias = rows[0]["alias"]
        add("perfil", slug, "REPORTAJE", f"Perfil: {alias} según la hemeroteca",
            {"partidas_registradas": len(rows), "balance": f"{wins}–{len(rows) - wins}",
             "kda": fmt_num((k + a) / max(dd, 1), 2), "muertes_totales": dd,
             "campeones_favoritos": ", ".join(f"{c} ({n})" for c, n in champs),
             "rol_habitual": Counter(r["role"] for r in rows).most_common(1)[0][0]},
            14, alias=alias, campeon=champs[0][0])

    # evergreen: the records of the whole archive
    every = [r for rows in hist.values() for r in rows] + [r for s in players_today for r in s["rows"]]
    if len(every) >= 20:
        md = max(every, key=lambda r: r["d"]); mk = max(every, key=lambda r: r["k"])
        lg = max(every, key=lambda r: r["dur"]); mp = max(every, key=lambda r: r["pings"])
        add("records", None, "CULTURA", "Los récords de la hemeroteca",
            {"mas_muertes_en_una_partida": f"{md['alias']}, {md['d']} con {md['champ']}",
             "mas_asesinatos_en_una_partida": f"{mk['alias']}, {mk['k']} con {mk['champ']}",
             "partida_mas_larga": f"{_mins(lg['dur'])} minutos ({lg['alias']} con {lg['champ']})",
             "mas_pings": f"{mp['alias']}, {mp['pings']}",
             "partidas_registradas": len({r['match'] for r in every})}, 12)

    angles.sort(key=lambda a: -a["puntuacion"])
    for i, a in enumerate(angles):
        a["id"] = f"a{i + 1}"
    return {
        "angulos": angles,
        "dias_recientes": [e["date"] for e in recent],
        "tipos_recientes": dict(type_count),
    }


def detailed_games(cfg, store, friends, edition):
    """Every friend's game in the edition window with all the stored stats, for the editor."""
    start, end = edition["window"]
    tz = get_tz(cfg["timezone"])
    facts = build_facts(store.matches(), _players(store, friends), start, end, cfg["ignored_queues"])
    out = []
    for s in facts["players"]:
        for r in s["rows"]:
            out.append({
                "jugador": r["alias"], "campeon": r["champ"], "rol": r["role"], "cola": r["queue_name"],
                "hora": ms_to_local(r["start"], tz).strftime("%H:%M"), "minutos": _mins(r["dur"]),
                "resultado": "victoria" if r["win"] else "derrota", "kda": _kda(r),
                "dano_equipo": fmt_pct(r["dmg_share"]), "oro_equipo": fmt_pct(r["gold_share"]),
                "dano_recibido_equipo": fmt_pct(r["taken_share"]), "participacion": fmt_pct(r["kp"]),
                "farmeo": r["cs"], "farmeo_minuto": fmt_num(r["cspm"], 1), "vision": r["vision"],
                "guardianes": r["wards"], "dano_objetivos": fmt_int(r["obj"]), "solo_kills": r["solo"],
                "multikills": {"dobles": r["multi"][0], "triples": r["multi"][1], "quadras": r["multi"][2],
                               "pentas": r["multi"][3]},
                "primera_sangre": r["fb"], "pings": r["pings"], "minutos_muerto": round(r["dead"] / 60, 1),
                "rival_de_calle": r["opp_champ"], "oro_vs_rival": r["gold_diff"], "farmeo_vs_rival": r["cs_diff"],
                "kda_rival": r["opp_kda"], "aliados_del_grupo": r["allies"], "rivales_del_grupo": r["rivals"],
            })
    return out
