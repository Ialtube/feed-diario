"""SoloQ Challenge: sign-ups, the starting gun, the robot's pass over Riot, standings, the board,
Discord and the newspaper."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from roast import soloq, soloq_web  # noqa: E402
from roast.dossier import _soloq as soloq_angles  # noqa: E402
from roast.site import page  # noqa: E402

HOUR = 3600 * 1000
CFG = {"timezone": "Europe/Madrid", "cutoff_hour": 7, "platform": "euw1", "site_title": "El Rincón del Feeder",
       "soloq": {"min_partidas": 2, "duracion_dias": 30, "castigo": "Paga la cena"}}
FRIENDS = [{"riot_id": "grangalax#OVD", "alias": "grangalax", "slug": "grangalax"}]
T0 = 1793512800000      # 2026-11-01 07:00 in Madrid


class FakeRiot:
    """Serves accounts, Solo/Duo entries and matches; `ladder` is edited between passes."""

    def __init__(self):
        self.accounts = {"monedanueva#ovd": "p-gran", "lobo#euw": "p-lobo", "pato#euw": "p-pato"}
        self.ladder = {}
        self.games = {}

    def account_by_riot_id(self, name, tag):
        puuid = self.accounts.get(f"{name}#{tag}".lower())
        return {"puuid": puuid, "gameName": name, "tagLine": tag} if puuid else None

    def summoner_by_puuid(self, puuid):
        return {"profileIconId": 29, "summonerLevel": 30}

    def league_entries(self, puuid):
        e = self.ladder.get(puuid)
        return [dict(queueType="RANKED_SOLO_5x5", tier=e[0], rank=e[1], leaguePoints=e[2], wins=e[3], losses=e[4])] if e else []

    def match_ids(self, puuid, start_time_s=None, count=20, queue=None, start=0):
        ids = [m for m, (p, end, _) in self.games.items() if p == puuid and end // 1000 >= (start_time_s or 0)]
        return sorted(ids, reverse=True)[start:start + count]

    def match(self, mid):
        puuid, end, win = self.games[mid]
        part = {"puuid": puuid, "championName": "Urgot", "teamPosition": "TOP", "teamId": 100, "win": win,
                "kills": 3, "deaths": 7, "assists": 4}
        return {"metadata": {"matchId": mid}, "info": {"queueId": 420, "gameEndTimestamp": end, "gameStartTimestamp": end - 1800000,
                                                       "gameDuration": 1800, "participants": [part]}}


SIGN_UPS = [
    {"id": 1, "riot_id": "MonedaNueva # OVD", "apodo": "La Moneda", "jugador": "grangalax", "objetivo": "DIAMOND",
     "lema": "Este mes sí", "created_at": "2026-10-30T10:00:00+01:00"},
    {"id": 2, "riot_id": "Lobo#EUW", "apodo": "Lobo", "jugador": "nadie", "created_at": "2026-10-30T10:05:00+01:00"},
    {"id": 3, "riot_id": "Pato#EUW", "apodo": "Pato", "created_at": "2026-10-30T10:06:00+01:00"},
    {"id": 4, "riot_id": "NoExiste#EUW", "apodo": "Fantasma", "created_at": "2026-10-30T10:07:00+01:00"},
    {"id": 5, "riot_id": "sin almohadilla", "apodo": "Mal", "created_at": "2026-10-30T10:08:00+01:00"},
    {"id": 6, "riot_id": "LOBO#euw", "apodo": "Lobo bis", "created_at": "2026-10-30T10:09:00+01:00"},
]


class SoloQTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.datos = soloq.Datos(Path(self.tmp.name))
        self.riot = FakeRiot()

    def tearDown(self):
        self.tmp.cleanup()

    def r(self):
        return soloq.reto_de(CFG, self.datos)

    def test_sign_ups_are_cleaned_and_deduplicated(self):
        new = soloq.sincronizar(self.datos, SIGN_UPS, self.r(), FRIENDS, {"grangalax"}, T0)
        self.assertEqual(sorted(new), ["lobo#euw", "monedanueva#ovd", "noexiste#euw", "pato#euw"])
        c = self.datos.cuentas["monedanueva#ovd"]
        self.assertEqual((c["riot_id"], c["jugador"], c["persona"], c["objetivo"]),
                         ("MonedaNueva#OVD", "grangalax", "grangalax", "DIAMOND"))
        self.assertIsNone(self.datos.cuentas["lobo#euw"]["jugador"])     # an unknown slug is not trusted
        # an unreadable Supabase changes nothing; a row deleted in Supabase drops the account
        soloq.sincronizar(self.datos, None, self.r(), FRIENDS, set(), T0)
        self.assertEqual(self.datos.cuentas["pato#euw"]["estado"], "pendiente")
        soloq.sincronizar(self.datos, SIGN_UPS[:1], self.r(), FRIENDS, set(), T0)
        self.assertEqual(self.datos.cuentas["pato#euw"]["estado"], "baja")

    def test_sign_up_phase_then_starting_gun(self):
        R = self.riot
        soloq.sincronizar(self.datos, SIGN_UPS, self.r(), FRIENDS, {"grangalax"}, T0 - 48 * HOUR)
        self.assertEqual(soloq.fase(self.r(), T0), "inscripcion")      # nobody plays until the admin says so
        soloq.actualizar(R, self.datos, self.r(), T0 - 47 * HOUR, log=lambda *_: None)
        self.assertEqual(self.datos.cuentas["noexiste#euw"]["estado"], "no_encontrado")
        self.assertEqual(self.datos.partidas, {})                       # no games are fetched before the start
        sq = soloq.resumen(CFG, T0 - 48 * HOUR, T0 - 24 * HOUR, datos=self.datos)
        self.assertEqual(sq["fase"], "inscripcion")
        self.assertEqual(sorted(sq["inscritos_del_dia"]), ["Lobo", "Pato", "grangalax"])
        angles = []
        soloq_angles(lambda tipo, slug, *a, **kw: angles.append((tipo, slug)), sq)
        self.assertIn(("soloq_inscripcion", "grangalax"), angles)
        notes = soloq.notas(soloq.puesta_al_dia(self.datos, self.r(), T0), "inscripcion", "2026-11-01")
        self.assertTrue(any("pistoletazo" in n["texto"] for n in notes))

        # the boss sets the date on the board (Supabase checks the password); the robot takes the newest one
        fila = {"id": 7, "inicio": "2026-11-01T20:00:00+01:00", "fin": None}
        self.assertTrue(soloq.aplicar_control(self.datos, fila))
        self.assertFalse(soloq.aplicar_control(self.datos, fila))        # already applied
        r = self.r()
        self.assertEqual((soloq.fase(r, T0), r["fin_ms"] - r["inicio_ms"]), ("inscripcion", 30 * 24 * HOUR))
        self.assertEqual(soloq.avisos_pendientes(self.datos, r, T0), ["programado"])
        self.assertEqual(soloq.cuando(r["inicio_ms"], r["tz"]), "domingo, 1 de noviembre de 2026 a las 20:00")
        self.assertIn("inicio", soloq.avisos_pendientes(self.datos, r, T0 + 14 * HOUR))
        payload = soloq.aviso_payload(soloq.cabecera(CFG, r, T0), CFG, "programado")
        self.assertIn("Empieza el domingo, 1 de noviembre de 2026 a las 20:00", payload["embeds"][0]["description"])

        r = soloq.empezar(self.datos, CFG, T0)
        self.assertEqual((soloq.fase(r, T0 + HOUR), r["fin_ms"]), ("en_juego", T0 + 30 * 24 * HOUR))
        self.assertEqual(soloq.fase(soloq.terminar(self.datos, CFG, T0 + 5 * HOUR), T0 + 6 * HOUR), "finalizado")

    def test_race_standings_board_discord_and_newspaper(self):
        R = self.riot
        soloq.sincronizar(self.datos, SIGN_UPS, self.r(), FRIENDS, {"grangalax"}, T0 - 2 * HOUR)
        soloq.actualizar(R, self.datos, self.r(), T0 - HOUR, log=lambda *_: None)    # brand-new accounts: unranked
        soloq.empezar(self.datos, CFG, T0)

        # first evening: everybody plays the placements
        t1 = T0 + 14 * HOUR
        n = 0
        for p, results in (("p-gran", [1, 1, 0, 1, 1]), ("p-lobo", [1, 0, 0, 0, 1]), ("p-pato", [1, 1, 1, 1, 1])):
            for win in results:
                R.games[f"EUW1_{n}"] = (p, t1 - (20 - n) * 40 * 60000, bool(win))
                n += 1
        R.ladder = {"p-gran": ("GOLD", "II", 50, 4, 1), "p-lobo": ("SILVER", "I", 80, 2, 3), "p-pato": ("GOLD", "IV", 0, 5, 0)}
        self.assertTrue(soloq.actualizar(R, self.datos, self.r(), t1, log=lambda *_: None))
        # next evening: the coin loses three and drops a division, Lobo wins two and goes up
        t2 = t1 + 24 * HOUR
        for p, win in (("p-gran", False), ("p-gran", False), ("p-gran", False), ("p-lobo", True), ("p-lobo", True)):
            R.games[f"EUW1_{n}"] = (p, t2 - (6 - n % 6) * 40 * 60000, win)
            n += 1
        R.ladder.update({"p-gran": ("GOLD", "III", 70, 4, 4), "p-lobo": ("GOLD", "IV", 20, 4, 3)})
        self.assertTrue(soloq.actualizar(R, self.datos, self.r(), t2, log=lambda *_: None))
        self.assertFalse(soloq.actualizar(R, self.datos, self.r(), t2 + HOUR, log=lambda *_: None))   # nothing new
        self.datos.save()
        datos = soloq.Datos(Path(self.tmp.name))          # what was saved reads back the same
        r = soloq.reto_de(CFG, datos)

        ref = soloq.ultimo_corte(r, t2)
        rows = soloq.puesta_al_dia(datos, r, t2, ref)
        self.assertEqual([x["nombre"] for x in rows], ["grangalax", "Lobo", "Pato"])   # the paper's name for the group
        gran, lobo, pato = rows
        self.assertEqual((gran["apodo"], gran["partidas"], gran["victorias"], gran["racha"], gran["lp_hoy"]),
                         ("La Moneda", 8, 4, -3, -80))
        self.assertEqual(gran["lp_reto"], -80)              # counted from its first league, after the placements
        self.assertEqual((lobo["liga"], lobo["lp_hoy"], lobo["cambio"]), ("Oro IV · 20 LP", 40, 1))   # overtakes Pato
        self.assertEqual((pato["cambio"], pato["lp_hoy"]), (-1, 0))
        self.assertEqual(gran["falta"], 2400 - 1370)
        self.assertEqual({m["tipo"] for m in soloq.movimientos(datos, r, ref, t2)}, {"descenso", "ascenso"})

        sq = soloq.resumen(CFG, ref, t2, datos=datos)
        self.assertEqual((sq["lider"], sq["dia_del_reto"]), ("grangalax", 2))
        self.assertEqual(sq["clasificacion"][0]["derrotas_dia"], 3)
        angles = []
        soloq_angles(lambda tipo, slug, *a, **kw: angles.append((tipo, slug)), sq)
        self.assertIn(("soloq_hundimiento", "grangalax"), angles)
        self.assertIn(("soloq_ascenso", None), angles)       # Lobo is not in the group: no player page

        payload = soloq.aviso_payload(soloq.resumen(CFG, ref - 24 * HOUR, ref, datos=datos), CFG, "diario",
                                      "https://x.github.io/feed-diario", {"texto": "Nota", "firma": "Anónimo"})
        self.assertEqual(payload["embeds"][0]["url"], "https://x.github.io/feed-diario/soloq/")
        self.assertIn("grangalax", payload["embeds"][0]["description"])
        datos.inscritos["avisos"] = {"inicio": r["inicio_ms"]}     # the starting gun was already announced
        self.assertEqual(soloq.avisos_pendientes(datos, r, T0 + 26 * HOUR), ["diario"])     # 09:00, the day after
        self.assertEqual(soloq.avisos_pendientes(datos, r, T0 + 24 * HOUR), [])             # 07:00: too early

        notes = soloq.notas(rows, "en_juego", "2026-11-03", ["Comisario Cobretuerca"])
        self.assertTrue(notes and all(n["texto"] and n["firma"] for n in notes))

        editions = [{"date": "2026-11-03", "window": [ref - 24 * HOUR, ref], "ai": {"version": 1},
                     "tablon": [{"texto": "La Moneda cae de cruz otra vez.", "firma": "Doña Tilt"}],
                     "items": [{"id": 3, "headline": "La Moneda se hunde en Oro", "body": "Tres seguidas.",
                                "section": "SOLOQ CHALLENGE", "player": "grangalax"}]}]
        out = Path(self.tmp.name) / "web"
        soloq_web.build(CFG, datos, out, t2, roster=[{"slug": "grangalax", "alias": "grangalax"}], editions=editions)
        page = (out / "index.html").read_text(encoding="utf-8")
        for text in ("Clasificación oficial", "La gráfica", "La Moneda", "Oro III", "NoExiste#EUW", "Bando de inscripción",
                     "Muro de la vergüenza", "La Moneda se hunde en Oro", "ediciones/2026-11-03.html#p-3",
                     "La Moneda cae de cruz otra vez.", "Volver a El Rincón del Feeder", "El pistoletazo"):
            self.assertIn(text, page)
        self.assertTrue((out / "datos.json").exists() and (out / "soloq.js").exists())

    def test_newspaper_only_gets_a_button(self):
        html = page({"site_title": "El Rincón del Feeder", "site_tagline": ""}, "x", "<p>cuerpo</p>", "../")
        self.assertIn('<a class="soloq" href="../soloq/index.html"', html)
        self.assertNotIn("pestanas", html)

    def test_empty_board_builds(self):
        out = Path(self.tmp.name) / "web"
        soloq_web.build(CFG, self.datos, out, T0)
        page = (out / "index.html").read_text(encoding="utf-8")
        self.assertIn("Nadie se ha apuntado todavía", page)
        self.assertIn("Inscripciones abiertas", page)
        self.assertIsNone(soloq.resumen(CFG, T0 - HOUR, T0, datos=self.datos))


if __name__ == "__main__":
    unittest.main()
