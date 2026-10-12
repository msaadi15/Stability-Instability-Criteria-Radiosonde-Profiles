"""Load and analyse University of Wyoming radiosonde soundings (fixed-width text).

    from sounding import load_sounding, profile, indices
    df, meta = load_sounding("data/raw/71043_norman-wells_2024-01-01_00Z.txt")
    p, T, Td = profile(df)            # pint quantities for MetPy
    print(indices(df))                # LCL, LFC, EL, CAPE, CIN, PW...

CLI:  python sounding.py data/raw/71043_norman-wells_2024-01-01_00Z.txt   -> prints a short summary (not the table)
"""
import sys

import numpy as np
import pandas as pd

COLUMNS = ["PRES", "HGHT", "TEMP", "DWPT", "FRPT", "RELH", "RELI",
           "MIXR", "DRCT", "SKNT", "THTA", "THTE", "THTV"]
UNITS = {"PRES": "hPa", "HGHT": "m", "TEMP": "degC", "DWPT": "degC", "FRPT": "degC",
         "RELH": "percent", "RELI": "percent", "MIXR": "g/kg", "DRCT": "degree",
         "SKNT": "knot", "THTA": "K", "THTE": "K", "THTV": "K"}
# older UWyo text output has 11 columns (no FRPT / RELI)
COLUMNS_11 = [c for c in COLUMNS if c not in ("FRPT", "RELI")]
WIDTH = 7


def _is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def load_sounding(path):
    """Return (DataFrame, header line). Handles 13- and 11-column files; blank cells -> NaN."""
    lines, meta = [], ""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if not all(_is_number(t) for t in line.split()):
                meta = meta or line.strip()
                continue
            lines.append(line)
    cols = COLUMNS if max(map(len, lines)) > WIDTH * len(COLUMNS_11) else COLUMNS_11
    rows = []
    for line in lines:
        line = line.rjust(WIDTH * len(cols))
        cells = [line[i * WIDTH:(i + 1) * WIDTH].strip() for i in range(len(cols))]
        rows.append([float(c) if c else np.nan for c in cells])
    df = pd.DataFrame(rows, columns=cols).reindex(columns=COLUMNS)
    return df.sort_values("PRES", ascending=False, ignore_index=True), meta


def profile(df):
    """Pressure, temperature, dewpoint as MetPy quantities (rows with NaN dropped)."""
    from metpy.units import units
    d = df.dropna(subset=["PRES", "TEMP", "DWPT"]).drop_duplicates("PRES")
    return (d["PRES"].values * units.hPa,
            d["TEMP"].values * units.degC,
            d["DWPT"].values * units.degC)


def indices(df):
    """Common stability indices (surface-based parcel)."""
    import metpy.calc as mpcalc
    p, T, Td = profile(df)
    prof = mpcalc.parcel_profile(p, T[0], Td[0]).to("degC")
    lcl_p, lcl_t = mpcalc.lcl(p[0], T[0], Td[0])
    out = {"LCL": f"{lcl_p:~.1f}, {lcl_t:~.1f}"}
    for name, fn in [("LFC", mpcalc.lfc), ("EL", mpcalc.el)]:
        try:
            lp, lt = fn(p, T, Td, prof)
            out[name] = f"{lp:~.1f}, {lt:~.1f}"
        except Exception as e:
            out[name] = f"n/a ({e.__class__.__name__})"
    cape, cin = mpcalc.cape_cin(p, T, Td, prof)
    out["CAPE"], out["CIN"] = f"{cape:~.1f}", f"{cin:~.1f}"
    out["PW"] = f"{mpcalc.precipitable_water(p, Td).to('mm'):~.1f}"
    return out


def skewt(df, title="", path=None):
    """Draw a Skew-T with parcel path and CAPE/CIN shading."""
    import matplotlib.pyplot as plt
    import metpy.calc as mpcalc
    from metpy.plots import SkewT
    p, T, Td = profile(df)
    prof = mpcalc.parcel_profile(p, T[0], Td[0]).to("degC")
    fig = plt.figure(figsize=(8, 9))
    skew = SkewT(fig, rotation=45)
    skew.plot(p, T, "r", label="T")
    skew.plot(p, Td, "g", label="Td")
    skew.plot(p, prof, "k--", label="parcel")
    skew.shade_cape(p, T, prof)
    skew.shade_cin(p, T, prof, Td)
    skew.plot_dry_adiabats(alpha=.3)
    skew.plot_moist_adiabats(alpha=.3)
    skew.plot_mixing_lines(alpha=.3)
    skew.ax.set_ylim(1050, 100)
    skew.ax.legend()
    skew.ax.set_title(title)
    if path:
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
    return skew


if __name__ == "__main__":
    df, meta = load_sounding(sys.argv[1] if len(sys.argv) > 1 else "data/raw/71043_norman-wells_2024-01-01_00Z.txt")
    print(meta)
    print(f"{len(df)} levels, {df['PRES'].max():g}..{df['PRES'].min():g} hPa, top {df['HGHT'].max():g} m")
    print(df.head(3).to_string())
    try:
        for k, v in indices(df).items():
            print(f"{k}: {v}")
    except ImportError:
        print("(metpy not available: use ~/miniconda3/envs/science/bin/python)")
