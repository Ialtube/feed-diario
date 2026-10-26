"""Minimal Riot Games API client (account-v1, match-v5, league-v4, summoner-v4) with rate limiting.

Uses only the standard library so it runs anywhere (GitHub Actions, Windows, ...).
Default limits match a Development / Personal key: 20 requests/1 s and 100 requests/2 min.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque


class RiotError(Exception):
    pass


class RiotClient:
    def __init__(self, api_key, region="europe", platform="euw1",
                 limits=((20, 1.0), (100, 120.0)), sleep=time.sleep, clock=time.monotonic):
        if not api_key:
            raise RiotError("Falta RIOT_API_KEY")
        self.api_key = api_key
        self.region = region
        self.platform = platform
        self.limits = limits
        self.sleep = sleep
        self.clock = clock
        self.calls = deque()
        self.requests_made = 0

    # ---------------------------------------------------------------- rate limit
    def _wait_slot(self):
        longest = max(w for _, w in self.limits)
        while True:
            now = self.clock()
            while self.calls and now - self.calls[0] >= longest:
                self.calls.popleft()
            wait = 0.0
            for limit, window in self.limits:
                recent = [c for c in self.calls if now - c < window]
                if len(recent) >= limit:
                    wait = max(wait, window - (now - recent[0]) + 0.05)
            if wait <= 0:
                self.calls.append(now)
                return
            self.sleep(wait)

    # ---------------------------------------------------------------- http
    def _get(self, url, params=None):
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        last_error = None
        for attempt in range(6):
            self._wait_slot()
            req = urllib.request.Request(url, headers={
                "X-Riot-Token": self.api_key,
                "User-Agent": "el-feed-diario/1.0",
                "Accept": "application/json",
            })
            try:
                self.requests_made += 1
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code == 429:
                    retry = float(e.headers.get("Retry-After") or 10)
                    self.sleep(retry + 0.5)
                    last_error = e
                    continue
                if e.code in (500, 502, 503, 504):
                    self.sleep(min(2 ** attempt, 30))
                    last_error = e
                    continue
                if e.code in (401, 403):
                    raise RiotError(
                        f"Riot ha rechazado la clave (HTTP {e.code}). Las claves de desarrollo "
                        "caducan cada 24 h: usa una Personal API Key o renuévala.") from e
                raise RiotError(f"HTTP {e.code} pidiendo {url}") from e
            except urllib.error.URLError as e:
                last_error = e
                self.sleep(min(2 ** attempt, 30))
        raise RiotError(f"Demasiados reintentos pidiendo {url}: {last_error}")

    # ---------------------------------------------------------------- endpoints
    def _regional(self, path):
        return f"https://{self.region}.api.riotgames.com{path}"

    def account_by_riot_id(self, game_name, tag_line):
        q = urllib.parse.quote
        return self._get(self._regional(
            f"/riot/account/v1/accounts/by-riot-id/{q(game_name, safe='')}/{q(tag_line, safe='')}"))

    def match_ids(self, puuid, start_time_s=None, count=20, queue=None, start=0):
        params = {"count": max(1, min(int(count), 100))}
        if start_time_s:
            params["startTime"] = int(start_time_s)
        if queue:
            params["queue"] = int(queue)
        if start:
            params["start"] = int(start)
        return self._get(self._regional(f"/lol/match/v5/matches/by-puuid/{puuid}/ids"), params) or []

    def match(self, match_id):
        return self._get(self._regional(f"/lol/match/v5/matches/{match_id}"))

    def timeline(self, match_id):
        return self._get(self._regional(f"/lol/match/v5/matches/{match_id}/timeline"))

    def summoner_by_puuid(self, puuid):
        """Profile icon and summoner level."""
        return self._get(f"https://{self.platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}")

    def league_entries(self, puuid):
        """Ranked entries (Solo/Duo and Flex) of a player: tier, division, LP, wins, losses."""
        return self._get(f"https://{self.platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}") or []
