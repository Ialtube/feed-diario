"""On-disk storage. Everything lives in plain JSON so the repo itself is the database.

data/
  state.json                 resolved PUUIDs + end of the last edition window
  matches/YYYY-MM.jsonl      one compact match summary per line
  editions/YYYY-MM-DD.json   one daily edition (facts + roast items)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .util import load_json, save_json


class Store:
    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        (self.dir / "matches").mkdir(parents=True, exist_ok=True)
        (self.dir / "editions").mkdir(parents=True, exist_ok=True)
        self.state = load_json(self.dir / "state.json", None) or {"players": {}, "last_edition_end": None}
        self._matches = None

    # ---------------------------------------------------------------- state
    def save_state(self):
        save_json(self.dir / "state.json", self.state)

    def player_state(self, riot_id):
        return self.state["players"].setdefault(riot_id, {})

    # ---------------------------------------------------------------- matches
    def matches(self):
        if self._matches is None:
            self._matches = {}
            for f in sorted((self.dir / "matches").glob("*.jsonl")):
                with open(f, encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            m = json.loads(line)
                            self._matches[m["id"]] = m
        return self._matches

    def has_match(self, match_id):
        return match_id in self.matches()

    def add_match(self, summary):
        if self.has_match(summary["id"]):
            return False
        month = datetime.fromtimestamp(summary["end"] / 1000, timezone.utc).strftime("%Y-%m")
        with open(self.dir / "matches" / f"{month}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.matches()[summary["id"]] = summary
        return True

    # ---------------------------------------------------------------- editions
    def editions(self):
        out = []
        for f in sorted((self.dir / "editions").glob("*.json")):
            out.append(load_json(f))
        return out

    def edition(self, date_str):
        return load_json(self.dir / "editions" / f"{date_str}.json", None)

    def save_edition(self, edition):
        save_json(self.dir / "editions" / f"{edition['date']}.json", edition)
