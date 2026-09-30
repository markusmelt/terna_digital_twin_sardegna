"""Modello del transitorio termico di una dorsale 380 kV (PoC dimostrativo).

Modello del primo ordine: tau * dT/dt + T = T_target, con
T_target = T_amb + (I / I_MAX)^2 * DT_MAX / f   (f = 1 senza vento).
Integrazione esatta per passo (target costante nel minuto), non Eulero.
"""
from dataclasses import dataclass
import numpy as np

V_LINE = 380e3      # V concatenata
COS_PHI = 0.9
I_MAX = 1600.0      # A, corrente di calibrazione
T_LIMIT = 85.0      # °C, limite di sicurezza
DT_MAX = 60.0       # °C a I_MAX con T_amb = 25 °C, senza vento (85 - 25)
TAU = 20.0          # min, costante di tempo senza vento
RAMP_MIN = 20       # minuto della rampa eolica
N_MIN = 121
# Raffreddamento da vento (illustrativo, NON IEEE 738): h_eff = h_ref * f
V_RATED, WIND_RATED = 12.0, 1200.0   # m/s e MW di riferimento per il proxy del vento
V0, CONV_SHARE = 0.6, 0.5            # velocita' di calibrazione; quota di convezione in h_ref


@dataclass(frozen=True)
class Params:
    wind_peak: float = 1000.0
    thermal_nominal: float = 450.0
    thermal_min: float = 225.0
    line_cap: float = 800.0        # soglia di gestione, non limite termico
    bess_mw: float = 61.9
    bess_mwh: float = 123.8        # ASSUNZIONE: 2 h alla potenza nominale
    link_mw: float = 1000.0
    link_available: bool = True
    t_amb: float = 25.0
    dlr: bool = False              # raffreddamento da vento
    dlr_k: float = 0.3             # frazione di vento efficace sul conduttore


def current_a(p_mw):
    return np.asarray(p_mw) * 1e6 / (np.sqrt(3) * V_LINE * COS_PHI)


def thermal_limit_mw():
    """Potenza trifase alla corrente di calibrazione (~948 MW)."""
    return float(np.sqrt(3) * V_LINE * I_MAX * COS_PHI / 1e6)


def temperature(p_mw, t_amb, wind_mw=None, dlr=False, k=0.3):
    i = current_a(p_mw)
    f = np.ones(len(i))
    if dlr and wind_mw is not None:
        v = V_RATED * (np.clip(wind_mw, 0, None) / WIND_RATED) ** (1 / 3) * k
        f = 1 + CONV_SHARE * ((np.maximum(v, V0) / V0) ** 0.6 - 1)
    target = t_amb + (i / I_MAX) ** 2 * DT_MAX / f
    tau = TAU / f
    out = np.empty(len(i))
    out[0] = target[0]
    for j in range(len(i) - 1):
        out[j + 1] = target[j] + (out[j] - target[j]) * np.exp(-1.0 / tau[j])
    return out


def dispatch(p: Params):
    """Profili di potenza e azioni di flessibilita' (passo 1 min)."""
    t = np.arange(N_MIN)
    rng = np.random.default_rng(42)
    wind = np.clip(np.where(t < RAMP_MIN, 100, p.wind_peak) + rng.normal(0, 10, t.size), 0, None)
    solar = np.clip(100 - 1.2 * t + rng.normal(0, 2, t.size), 0, None)
    inj0 = wind + solar + p.thermal_nominal
    inj1 = wind + solar + np.where(t < RAMP_MIN, p.thermal_nominal, p.thermal_min)
    bess, link, curt = (np.zeros(t.size) for _ in range(3))
    soc = 0.0  # MWh assorbiti
    link_cap = p.link_mw if p.link_available else 0.0
    for k in range(RAMP_MIN, t.size):
        exc = max(inj1[k] - p.line_cap, 0.0)
        b = min(p.bess_mw, exc, max(p.bess_mwh - soc, 0.0) * 60)
        soc += b / 60
        bess[k] = b
        exc -= b
        link[k] = min(exc, link_cap)
        curt[k] = exc - link[k]
    return dict(t=t, wind=wind, solar=solar, inj0=inj0, inj1=inj1, bess=bess, link=link, curt=curt,
                line2=inj1 - bess - link - curt, soc_mwh=float(bess.sum() / 60),
                curt_mwh=float(curt.sum() / 60), link_mwh=float(link.sum() / 60))


def simulate(p: Params):
    d = dispatch(p)
    args = dict(t_amb=p.t_amb, wind_mw=d["wind"], dlr=p.dlr, k=p.dlr_k)
    d["T0"] = temperature(d["inj0"], **args)
    d["T1"] = temperature(d["inj1"], **args)
    d["T2"] = temperature(d["line2"], **args)
    return d


def kpi_rows(d):
    rows = []
    for name, T in (("Termico rigido", d["T0"]), ("Termico al minimo", d["T1"]), ("BESS + Link", d["T2"])):
        post = T[RAMP_MIN:] > T_LIMIT
        rows.append({"Scenario": name, "T max (°C)": f"{T.max():.1f}",
                     "Tempo di intervento": f"{int(np.argmax(post))} min" if post.any() else "nessun superamento",
                     "Minuti sopra 85 °C": int((T > T_LIMIT).sum())})
    return rows


def self_checks():
    """Verifiche numeriche mostrate nell'app."""
    n = 60
    ss = temperature(np.full(n, thermal_limit_mw()), 25.0)[-1]
    p0, p1 = 0.5 * thermal_limit_mw(), 1.2 * thermal_limit_mw()
    step = temperature(np.r_[np.full(10, p0), np.full(n, p1)], 25.0)
    t0, t1 = [25 + (current_a(x) / I_MAX) ** 2 * DT_MAX for x in (p0, p1)]
    exact = t1 + (t0 - t1) * np.exp(-20.0 / TAU)
    return [("Regime a I_MAX (atteso 85,0 °C)", 85.0, float(ss)),
            ("Risposta a gradino dopo 20 min", float(exact), float(step[10 + 20 - 1 + 1]))]
