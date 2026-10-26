"""SoloQ Challenge: sign-ups, the robot's pass over Riot, standings, the website and the newspaper."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from roast import soloq, soloq_web  # noqa: E402
from roast.dossier import _soloq as soloq_angles  # noqa: E402
from roast.site import _soloq as soloq_section  # noqa: E402

HOUR = 3600 * 1000
CFG = {"timezone": "Europe/Madrid", "cutoff_hour": 7, "platform": "euw1", "site_title": "El Rincón del Feeder",
       "soloq": {"inicio": "2026-10-27", "fin": "2026-11-30", "min_partidas": 2}}
FRIENDS = [{"riot_id": "grangalax#OVD", "alias": "grangalax", "slug": "grangalax"}]


class FakeRiot:
    """Serves accounts, Solo/Duo entries and matches; `ladder` is edited between passes."""

    def __init__(self):
        self.accounts = {"grangalax#ovd": "p-gran", "lobo#euw": "p-lobo", "pato#euw": "p-pato"}
        self.ladder = {}
        self.games = {}

    def account_by_riot_id(self, name, tag):
        puuid = self.accounts.get(f"{name}#{tag}".lower())
        return {"puuid": puuid, "gameName": name, "tagLine": tag} if puuid else None

    def summoner_by_puuid(self, puuid):
        return {"profileIconId": 29, "summonerLevel": 300}

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


class SoloQTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.datos = soloq.Datos(Path(self.tmp.name))
        self.r = soloq.reto(CFG)
        self.t0 = self.r["inicio_ms"] + 10 * HOUR
        self.riot = FakeRiot()

    def tearDown(self):
        self.tmp.cleanup()

    def sign_up(self):
        rows = [
            {"id": 1, "riot_id": "grangalax # OVD", "apodo": "La Moneda", "objetivo": "DIAMOND", "lema": "Este mes sí",
             "created_at": "2026-10-27T10:00:00+01:00"},
            {"id": 2, "riot_id": "Lobo#EUW", "apodo": "Lobo", "jugador": "nadie", "created_at": "2026-10-27T10:05:00+01:00"},
            {"id": 3, "riot_id": "Pato#EUW", "apodo": "Pato", "created_at": "2026-10-27T10:06:00+01:00"},
            {"id": 4, "riot_id": "NoExiste#EUW", "apodo": "Fantasma", "created_at": "2026-10-27T10:07:00+01:00"},
            {"id": 5, "riot_id": "sin almohadilla", "apodo": "Mal", "created_at": "2026-10-27T10:08:00+01:00"},
            {"id": 6, "riot_id": "LOBO#euw", "apodo": "Lobo bis", "created_at": "2026-10-27T10:09:00+01:00"},
        ]
        return soloq.sincronizar(self.datos, rows, self.r, FRIENDS, {"grangalax"}, self.t0)

    def test_sign_ups_are_cleaned_and_deduplicated(self):
        new = self.sign_up()
        self.assertEqual(sorted(new), ["grangalax#ovd", "lobo#euw", "noexiste#euw", "pato#euw"])
        c = self.datos.cuentas["grangalax#ovd"]
        self.assertEqual((c["riot_id"], c["jugador"], c["objetivo"]), ("grangalax#OVD", "grangalax", "DIAMOND"))
        self.assertIsNone(self.datos.cuentas["lobo#euw"]["jugador"])     # an unknown slug is not trusted
        # a row deleted in Supabase drops the account; an unreadable Supabase changes nothing
        soloq.sincronizar(self.datos, None, self.r, FRIENDS, set(), self.t0)
        self.assertEqual(self.datos.cuentas["pato#euw"]["estado"], "pendiente")
        soloq.sincronizar(self.datos, [{"id": 1, "riot_id": "grangalax#OVD", "apodo": "x"}], self.r, FRIENDS, set(), self.t0)
        self.assertEqual(self.datos.cuentas["pato#euw"]["estado"], "baja")

    def test_robot_pass_standings_and_newspaper(self):
        self.sign_up()
        R = self.riot
        R.ladder = {"p-gran": ("GOLD", "II", 50, 10, 10), "p-lobo": ("SILVER", "I", 80, 5, 5)}
        self.assertTrue(soloq.actualizar(R, self.datos, self.r, self.t0, log=lambda *_: None))
        self.assertEqual(self.datos.cuentas["noexiste#euw"]["estado"], "no_encontrado")
        self.assertEqual(self.datos.cuentas["grangalax#ovd"]["icono"], 29)
        # nothing moved: a second pass stores nothing new
        self.assertFalse(soloq.actualizar(R, self.datos, self.r, self.t0 + HOUR, log=lambda *_: None))

        # next evening: grangalax loses three and drops a division, Lobo wins two and goes up, Pato places
        t1 = self.t0 + 30 * HOUR
        for i, (p, win) in enumerate([("p-gran", False), ("p-gran", False), ("p-gran", False), ("p-lobo", True),
                                      ("p-lobo", True), ("p-pato", True)]):
            R.games[f"EUW1_{i}"] = (p, t1 - (6 - i) * 40 * 60000, win)
        R.ladder = {"p-gran": ("GOLD", "III", 70, 10, 13), "p-lobo": ("GOLD", "IV", 20, 7, 5),
                    "p-pato": ("BRONZE", "I", 10, 5, 0)}
        self.assertTrue(soloq.actualizar(R, self.datos, self.r, t1, log=lambda *_: None))
        self.datos.save()
        datos = soloq.Datos(Path(self.tmp.name))          # what was saved reads back the same

        ref = soloq.ultimo_corte(self.r, t1)
        rows = soloq.tabla(datos, self.r, t1, ref)
        self.assertEqual([x["apodo"] for x in rows], ["La Moneda", "Lobo", "Pato"])
        gran, lobo = rows[0], rows[1]
        self.assertEqual((gran["partidas"], gran["victorias"], gran["racha"], gran["lp_hoy"]), (3, 0, -3, -80))
        self.assertEqual((lobo["liga"], lobo["lp_hoy"], lobo["cambio"]), ("Oro IV · 20 LP", 40, 0))
        self.assertEqual(gran["falta"], 2400 - 1370)
        self.assertEqual((rows[2]["liga"], rows[2]["cambio"]), ("Bronce I · 10 LP", 0))   # was there unranked at 07:00

        moves = soloq.movimientos(datos, self.r, ref, t1)
        self.assertEqual({m["tipo"] for m in moves}, {"descenso", "ascenso", "liga"})

        sq = soloq.resumen(CFG, ref, t1, datos=datos)
        self.assertEqual(sq["lider"], "La Moneda")
        self.assertEqual(sq["clasificacion"][0]["derrotas_dia"], 3)
        angles = []
        soloq_angles(lambda tipo, slug, tema, titulo, datos_, score, **kw: angles.append((tipo, slug)), sq)
        self.assertIn(("soloq_hundimiento", "grangalax"), angles)
        self.assertIn(("soloq_ascenso", None), angles)       # Lobo is not in the group: no player page
        self.assertIn(("soloq_promesa", "grangalax"), angles)

        html = soloq_section({"soloq": sq}, "")
        self.assertIn("La clasificación al cierre de esta edición", html)
        self.assertIn('href="jugadores/grangalax.html"', html)

        out = Path(self.tmp.name) / "web"
        soloq_web.build(CFG, datos, out, t1, roster=[{"slug": "grangalax", "alias": "grangalax"}])
        page = (out / "index.html").read_text(encoding="utf-8")
        for text in ("La Moneda", "Oro III", "NoExiste#EUW", "Inscripción", "Muro de la vergüenza", "El Rincón del Feeder"):
            self.assertIn(text, page)
        self.assertTrue((out / "datos.json").exists() and (out / "soloq.js").exists())

    def test_empty_site_builds(self):
        out = Path(self.tmp.name) / "web"
        soloq_web.build(CFG, self.datos, out, self.t0)
        self.assertIn("Aún no hay valientes", (out / "index.html").read_text(encoding="utf-8"))
        self.assertIsNone(soloq.resumen(CFG, self.t0 - HOUR, self.t0, datos=self.datos))


if __name__ == "__main__":
    unittest.main()
