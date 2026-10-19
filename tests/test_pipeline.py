"""Run with:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from roast.analyze import build_facts, game_rows  # noqa: E402
from roast.demo import DemoRiot, generate_matches  # noqa: E402
from roast.fetch import fetch_new_matches, resolve_players  # noqa: E402
from roast.llm import polish  # noqa: E402
from roast.notify import discord_payload  # noqa: E402
from roast.pipeline import make_edition  # noqa: E402
from roast.riot import RiotClient  # noqa: E402
from roast.site import build_site  # noqa: E402
from roast.store import Store  # noqa: E402
from roast.util import load_config, slugify  # noqa: E402

FRIENDS = [
    {"riot_id": "grangalax#OVD", "alias": "grangalax", "slug": "grangalax"},
    {"riot_id": "TheTrevur#URGOD", "alias": "TheTrevur", "slug": "thetrevur"},
    {"riot_id": "Wôlf172#1075", "alias": "Wôlf", "slug": "wolf"},
    {"riot_id": "Fr4nux#EUW", "alias": "Fr4nux", "slug": "fr4nux"},
]
TZ = timezone(timedelta(hours=2))


class RateLimiterTest(unittest.TestCase):
    def test_waits_when_window_is_full(self):
        t = [0.0]
        slept = []

        def sleep(s):
            slept.append(s)
            t[0] += s

        c = RiotClient("key", limits=((2, 1.0), (3, 10.0)), sleep=sleep, clock=lambda: t[0])
        times = []
        for _ in range(4):
            c._wait_slot()
            times.append(t[0])
        self.assertGreaterEqual(times[2] - times[0], 1.0)   # max 2 per second
        self.assertGreaterEqual(times[3] - times[0], 10.0)  # max 3 per 10 s
        self.assertTrue(slept)


class AnalyzeTest(unittest.TestCase):
    def test_lowest_damage_and_shares(self):
        def p(puuid, team, dmg, gold, k=2, d=3, a=4, pos="MIDDLE", win=True):
            return {"puuid": puuid, "team": team, "dmg": dmg, "gold": gold, "k": k, "d": d, "a": a, "pos": pos,
                    "win": win, "champ": "Azir", "cs": 200, "vision": 20, "dead": 60, "pings": 5,
                    "multi": [0, 0, 0, 0], "fb": False, "surr": False, "esurr": False}
        parts = [p("me", 100, 5000, 12000), p("x1", 100, 20000, 11000), p("x2", 100, 15000, 10000),
                 p("x3", 100, 9000, 9000), p("x4", 100, 6000, 8000, pos="UTILITY")]
        parts += [p(f"e{i}", 200, 10000, 10000, win=False) for i in range(5)]
        match = {"id": "M1", "queue": 420, "dur": 1800, "end": 1, "parts": parts}
        rows = game_rows(match, {"me": {"alias": "Yo", "slug": "yo"}})
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertTrue(r["lowest_dmg"])
        self.assertAlmostEqual(r["dmg_share"], 5000 / 55000)
        self.assertAlmostEqual(r["gold_share"], 12000 / 50000)
        self.assertAlmostEqual(r["kp"], 6 / 10)


class PipelineTest(unittest.TestCase):
    def test_full_pipeline_with_demo_data(self):
        cfg = load_config()
        now = datetime(2026, 10, 19, 8, 0, tzinfo=TZ)
        raw = generate_matches(FRIENDS, days=3, seed=3, now=now)
        client = DemoRiot(FRIENDS, raw)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data")
            players = resolve_players(client, store, FRIENDS, log=lambda *_: None)
            self.assertEqual(len(players), 4)
            since = int((now - timedelta(days=4)).timestamp() * 1000)
            added = fetch_new_matches(client, store, players, since, max_per_player=100, log=lambda *_: None)
            self.assertEqual(added, len(raw))
            # a second fetch must not download anything again
            self.assertEqual(fetch_new_matches(client, store, players, since, 100, log=lambda *_: None), 0)

            # reload from disk to make sure storage round-trips
            store2 = Store(Path(tmp) / "data")
            self.assertEqual(len(store2.matches()), len(raw))

            end = now
            start = end - timedelta(days=3)
            ed = make_edition(cfg, store2, players, int(start.timestamp() * 1000), int(end.timestamp() * 1000),
                              "2026-10-19", 1)
            self.assertTrue(ed["items"])
            self.assertEqual(ed["items"][0]["section"], "PORTADA")
            for r in ed["ranking"]:
                self.assertGreater(r["games"], 0)
                self.assertEqual(r["wins"] + r["losses"], r["games"])
            for it in ed["items"]:
                self.assertNotIn("{", it["headline"])
                self.assertNotIn("{", it["body"])
            self.assertEqual(sum(r["games"] for r in ed["ranking"]), len(ed["games"]))
            store2.save_edition(ed)

            out = build_site(cfg, FRIENDS, store2.editions(), Path(tmp) / "docs")
            html = (out / "index.html").read_text(encoding="utf-8")
            self.assertIn(cfg["site_title"], html)
            self.assertIn(ed["items"][0]["headline"].split(":")[0][:20].replace("'", "&#x27;"), html)
            for f in FRIENDS:
                self.assertTrue((out / "jugadores" / f"{f['slug']}.html").exists())
            self.assertTrue((out / "ediciones" / "2026-10-19.html").exists())

            payload = discord_payload(ed, cfg, "https://ejemplo.github.io/feed/")
            self.assertEqual(payload["embeds"][0]["url"], "https://ejemplo.github.io/feed/")

    def test_empty_day(self):
        cfg = load_config()
        facts = build_facts({}, [dict(f, puuid="p" + f["slug"]) for f in FRIENDS], 0, 10)
        self.assertEqual(facts["players"], [])
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "data")
            ed = make_edition(cfg, store, [dict(f, puuid="p" + f["slug"]) for f in FRIENDS], 0, 10, "2026-01-01", 1)
            self.assertEqual(ed["items"][0]["kind"], "vacio")
            build_site(cfg, FRIENDS, [ed], Path(tmp) / "docs")

    def test_polish_without_key_is_a_no_op(self):
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            ed = {"date": "2026-01-01", "frase": "x", "items": []}
            self.assertFalse(polish(ed, "claude-opus-5-5", log=lambda *_: None))
        finally:
            if old is not None:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_slugify(self):
        self.assertEqual(slugify("Wôlf"), "wolf")
        self.assertEqual(slugify("RDV Canyon"), "rdv-canyon")


if __name__ == "__main__":
    unittest.main()
