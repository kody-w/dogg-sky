"""sky.py — NOAA solar-position equations + a moon-phase approximation.

Stdlib only (math). No network, no external ephemeris. Given a UTC calendar date and a
lat/lon, this reproduces (to the precision noted below) sunrise, sunset, day length,
and moon phase/age — the same quantities the chain records each tick. That means any
frame in sky/ is not the only way to get this data: run this file against the same
(lat, lon, date) offline, any time, forever, and you get the same answer back. The
chain is the witness (this repo saw and hashed it); the algorithm is the heirloom
(anyone can rederive it without the chain, without this repo, without the internet).

Method
------
Solar position: the NOAA Solar Calculator's algorithm (itself Jean Meeus, "Astronomical
Algorithms", low-precision solar coordinates), evaluated at 12:00 UTC of the given date:
mean longitude + equation of center -> true/apparent longitude, mean obliquity with
nutation correction, declination, equation of time, hour angle at the sunrise/sunset
zenith (90.833 deg, i.e. -50' for the solar disk's radius plus -34' for average
atmospheric refraction at the horizon). Accurate to roughly +/-1 minute of clock time
for years ~1900-2100 at non-polar latitudes; it does NOT model local horizon elevation,
unusual refraction, or leap seconds.

Moon phase: a mean-synodic-month approximation anchored to a known new moon (2000-01-06
18:14 UTC). This ignores the real lunar orbit's eccentricity and perturbations, so age
can drift up to roughly +/-0.5 day from a full ephemeris over the coming decades, and
"percent illuminated" is derived from that mean phase angle via a simple sin/cos model
rather than true illuminated-limb geometry. Good enough to name the phase and the
day-count; not an almanac-grade ephemeris.

Sunrise/sunset are returned as UTC-clock-minutes-of-day (0..1439): the wall-clock UTC
time the event happens at, for the LOCAL calendar date given. For longitudes far from
0 (Sydney, Tokyo), that clock moment can fall on the UTC calendar date before or after
the local date you asked about — e.g. Sydney's local-morning sunrise is often still
"yesterday" in UTC. The minute-of-day value is exact for that purpose; the UTC calendar
date it falls on is not tracked here (documented limitation, not a bug).
"""
import math

SYNODIC_MONTH_DAYS = 29.530588853
REF_NEW_MOON_JD = 2451550.1          # 2000-01-06 18:14 UTC, a known new moon


def julian_day(y, m, d):
    """Meeus JD at 0h UT for a Gregorian calendar date."""
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def _julian_century(jd):
    return (jd - 2451545.0) / 36525.0


def _declination_and_eqtime(y, m, d):
    """Solar declination (deg) and equation of time (minutes) at 12:00 UTC of the date."""
    jd = julian_day(y, m, d) + 0.5
    t = _julian_century(jd)
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m_anom = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    ecc = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m_anom)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
         + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    lam = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(lam))))
    y2 = math.tan(math.radians(eps / 2)) ** 2
    eqtime = 4 * math.degrees(
        y2 * math.sin(2 * math.radians(l0))
        - 2 * ecc * math.sin(mr)
        + 4 * ecc * y2 * math.sin(mr) * math.cos(2 * math.radians(l0))
        - 0.5 * y2 * y2 * math.sin(4 * math.radians(l0))
        - 1.25 * ecc * ecc * math.sin(2 * mr)
    )
    return decl, eqtime


def sun_times(lat, lon, y, m, d):
    """(sunrise_min, sunset_min, day_length_min) as UTC-minute-of-day floats.

    sunrise_min/sunset_min are None on the rare (lat, date) combination where the sun
    never crosses the horizon (polar day/night); day_length_min is still returned
    (1440.0 for polar day, 0.0 for polar night) since it needs no clock moment."""
    decl, eqtime = _declination_and_eqtime(y, m, d)
    lat_r, decl_r = math.radians(lat), math.radians(decl)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(lat_r) * math.cos(decl_r))
              - math.tan(lat_r) * math.tan(decl_r))
    if cos_ha > 1:
        return None, None, 0.0
    if cos_ha < -1:
        return None, None, 1440.0
    ha = math.degrees(math.acos(cos_ha))
    noon_min = 720 - 4 * lon - eqtime
    return noon_min - 4 * ha, noon_min + 4 * ha, 8 * ha


def moon_phase(y, m, d):
    """(age_days, illuminated_pct) at 12:00 UTC of the date, mean-synodic approximation.

    age_days: 0.0 at new moon, ~14.77 at full, wrapping at ~29.53 (the mean synodic
    month) back to the next new moon.
    illuminated_pct: 0 at new, 100 at full, via (1 - cos(2*pi*age/synodic)) / 2 * 100 —
    a mean phase-angle model, not true illuminated-limb geometry."""
    jd = julian_day(y, m, d) + 0.5
    age = (jd - REF_NEW_MOON_JD) % SYNODIC_MONTH_DAYS
    frac = age / SYNODIC_MONTH_DAYS
    illum_pct = (1 - math.cos(2 * math.pi * frac)) / 2 * 100
    return age, illum_pct
