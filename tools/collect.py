#!/usr/bin/env python3
"""A federated tick-network node: this repo's own append-only chain, keyed to the
global tick spine at kody-w/dogg.

Every run reads the spine's current tick anchor, takes this node's themed snapshot,
and appends one frame referencing that tick. Different repos, run by different people,
each with their own outlook — all joinable on the tick key. Frames verify with the
reference implementation (tools/rapp.py, from kody-w/rapp-1); CI re-verifies the whole
chain on every push.

This node's outlook (astronomy) needs no network beyond the spine's own tick anchor:
tools/sky.py implements the NOAA solar-position equations and a moon-phase
approximation in pure Python. Every cell below is reproducible offline, for any date,
by anyone, forever — the chain witnesses it, the algorithm is the heirloom.
"""
import json, sys, pathlib, datetime

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import rapp as R
import chainio
import sky

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPINE_HEAD = "https://raw.githubusercontent.com/kody-w/dogg/main/ticks/HEAD.json"
TIMEOUT = 8

# ---- edit these three for your node -------------------------------------------------
THEME = "sky"                         # also the data directory name
STREAM = "sky:@kody-w/dogg-sky"                            # your stream id (your repo, your name)
# CELLS: name -> (lat, lon), one reference cell each. rapp/1 canonical hashing forbids
# floats: numeric facts ride as strings (decimals) or ints (whole minutes).
# -------------------------------------------------------------------------------------

CELLS = [
    ("atlanta",   33.7490,  -84.3880),
    ("new_york",  40.7128,  -74.0060),
    ("london",    51.5074,   -0.1278),
    ("tokyo",     35.6762,  139.6503),
    ("sydney",   -33.8688,  151.2093),
    ("nairobi",   -1.2921,   36.8219),
    ("sao_paulo",-23.5505,  -46.6333),
    ("reykjavik", 64.1466,  -21.9426),
]


def utc():
    n = datetime.datetime.now(datetime.timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%S.") + f"{n.microsecond // 1000:03d}Z"


def get(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": f"tick-node-{THEME}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def _cell(lat, lon, y, m, d):
    sunrise, sunset, day_len = sky.sun_times(lat, lon, y, m, d)
    age, illum_pct = sky.moon_phase(y, m, d)
    out = {
        "lat": f"{lat:.4f}", "lon": f"{lon:.4f}",
        "sunrise_utc_min": None if sunrise is None else int(round(sunrise)) % 1440,
        "sunset_utc_min": None if sunset is None else int(round(sunset)) % 1440,
        "day_length_min": int(round(day_len)),
        "moon_phase_pct": f"{illum_pct:.1f}",
        "moon_age_days": f"{age:.2f}",
    }
    return out


def _sources(date):
    y, m, d = date.year, date.month, date.day
    return {name: (lambda lat=lat, lon=lon: _cell(lat, lon, y, m, d))
            for name, lat, lon in CELLS}


def load_chain(d):
    return chainio.load_chain(d)


def main():
    spine = get(SPINE_HEAD)
    tick_n, tick_hash = spine["count"] - 1, spine["head_frame"]
    d = ROOT / THEME
    d.mkdir(exist_ok=True)
    chain = load_chain(d)
    head = chain[-1] if chain else None
    if head is not None and head["payload"].get("tick") == tick_n:
        print(f"{THEME}: tick {tick_n} already recorded — nothing to do")
        return
    fetched = datetime.datetime.now(datetime.timezone.utc)
    SOURCES = _sources(fetched)
    data, failed = {}, []
    for name, fn in SOURCES.items():
        try:
            data[name] = fn()
        except Exception:
            failed.append(name)
    payload = {"tick": tick_n, "tick_frame": tick_hash, "spine": "kody-w/dogg",
               "fetched_utc": utc(), "date": fetched.strftime("%Y-%m-%d"),
               THEME: data, "sources_failed": failed}
    if head is None:
        payload["about"] = (f"A federated node of the global tick network: this repo's "
                            f"own {THEME} outlook, one frame per observed tick, keyed to "
                            "the spine's tick anchors so it joins every other node's "
                            "data on the same clock. Every cell here is reproducible "
                            "offline from tools/sky.py — the chain is the witness, the "
                            "algorithm is the heirloom.")
    f = R.build_frame(f"{THEME}.snapshot", STREAM, (head["seq"] + 1) if head else 0,
                      utc(), payload, prev=(head["payload_hash"] if head else None))
    ok, step, why = R.verify_frame(f, head=head, stream_id_of_record=STREAM)
    if not ok:
        raise ValueError(f"refusing invalid frame: {step}: {why}")
    chainio.append_frame(d, f, STREAM)
    print(f"{THEME} frame {f['seq']} @ spine tick {tick_n}: {', '.join(data) or 'nothing'}"
          + (f" (failed: {', '.join(failed)})" if failed else ""))

if __name__ == "__main__":
    main()
