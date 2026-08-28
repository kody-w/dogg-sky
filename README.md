# dogg-sky — a federated node of the global tick network

**Astronomy as a seed: sunrise, sunset, day length, and moon phase for eight reference
cities, computed in pure Python from NOAA solar-position equations — no API, no key,
no dependency on any service staying alive.**

This repo keeps its own append-only chain of rapp/1 frames in `sky/`. Once a day a
GitHub Action reads the current tick anchor from the spine at
[kody-w/dogg](https://github.com/kody-w/dogg) and appends one frame of this node's
outlook, referencing that tick — so this chain joins every other node's data on the
same clock. Other nodes poll live markets or feeds that stop answering the moment
their API does; this one polls the sky, which answers from arithmetic.

## Why this node is different: the algorithm is the heirloom

Every other tick-network node's data is a claim about a service that has to still be
reachable to check: "this is what the market said." This node's data is a claim about
geometry. `tools/sky.py` is a self-contained, dependency-free implementation of:

- **Solar position** — the NOAA Solar Calculator's algorithm (Meeus low-precision
  solar coordinates): mean longitude, equation of center, apparent longitude,
  obliquity, declination, equation of time, and the sunrise/sunset hour angle at the
  standard 90.833° zenith (disk radius + average refraction).
- **Moon phase** — a mean-synodic-month approximation anchored to a known new moon
  (2000-01-06 18:14 UTC), giving age-in-days and percent illuminated.

Nothing in that file touches the network. Give it a latitude, a longitude, and a
calendar date — any date, past or future, any of the eight cities or a new one you
add — and it returns the same numbers this chain recorded, without needing this chain,
this repo, or the internet to exist. **The chain is the witness** (this repo saw a
given tick and hashed what the sky looked like then); **the algorithm is the
heirloom** (the method for computing it outlives any server, any API key, any
company). That is the property this node is built to demonstrate: a piece of data
that is still fully alive with zero live infrastructure behind it.

## What's in a frame

Each frame's payload carries, for eight reference cells (Atlanta, New York, London,
Tokyo, Sydney, Nairobi, Sao Paulo, Reykjavik — spread across longitudes and both
hemispheres) on the frame's UTC date:

| field | meaning | unit |
|---|---|---|
| `lat`, `lon` | the cell's coordinates | decimal degrees |
| `sunrise_utc_min` | UTC clock-minute-of-day (0–1439) the sun crosses the horizon rising | minutes |
| `sunset_utc_min` | UTC clock-minute-of-day (0–1439) the sun crosses the horizon setting | minutes |
| `day_length_min` | time the sun is above the horizon | minutes |
| `moon_phase_pct` | fraction of the moon's disk illuminated (0 new → 100 full) | percent |
| `moon_age_days` | days since the last new moon (0 → ~29.53) | days |

`rapp/1` canonical hashing forbids floats, so decimals ride as fixed-precision
strings (`"33.7490"`, `"63.4"`) and whole minutes ride as plain ints.

## Precision and limits — read this before trusting a number

- **Solar times** are accurate to roughly **±1 minute** of clock time for years
  ~1900–2100 at non-polar latitudes. The algorithm does not model local horizon
  elevation (mountains, sea-level vs. altitude) or unusual atmospheric refraction —
  only the standard average.
- **`sunrise_utc_min`/`sunset_utc_min`** are the UTC wall-clock minute the event
  happens at *for that cell's local calendar date*. For longitudes far from
  Greenwich (Sydney, Tokyo), that clock moment can fall on the UTC calendar date
  before or after the date the frame is filed under — Sydney's local-morning sunrise
  is often still "yesterday" in UTC. The minute-of-day is exact; the UTC calendar
  date it falls on is not separately tracked. Documented, not a bug.
- **Moon phase/age** use a *mean* synodic month (29.530588853 days), not a full
  ephemeris — the real lunar orbit is eccentric and perturbed, so age can drift up to
  roughly **±0.5 day** from an almanac over the coming decades, and the illumination
  percent is a simple phase-angle model, not true illuminated-limb geometry. Good
  enough to name the phase; not JPL Horizons.
- None of the eight cells are near the poles, so `sunrise_utc_min`/`sunset_utc_min`
  are never `null` in practice — but the field can be `null` for a cell/date where the
  sun never rises or sets (`tools/sky.py` handles this; the network's canonical form
  allows `null` in payload values).

**Verify it yourself:** `python3 tools/verify_thread.py` re-checks every frame with the
reference implementation from [kody-w/rapp-1](https://github.com/kody-w/rapp-1). CI runs
the same oracle on every push. To check a specific number, not just the chain's
internal consistency: run `tools/sky.py`'s `sun_times()` / `moon_phase()` against the
same (lat, lon, date) yourself and compare — that's the whole point.

**Start your own node:** fork this repo, edit `THEME` / `STREAM` / `CELLS` at the top
of `tools/collect.py` (keyless https APIs or, as here, pure computation; small factual
payloads; numbers as strings/ints), and enable the scheduled workflow. Your chain, your
outlook, same clock — announce it on the spine's registry
([kody-w/dogg](https://github.com/kody-w/dogg) issues) so agents can find it.

## Trust

<!--trust-->
No ratings yet — used this chain? [Rate it](../../issues/new?template=rate.yml): valid ratings publish automatically as verifiable frames.
<!--/trust-->
