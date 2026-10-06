"""Modello termico di un tratto critico di linea aerea (PoC dimostrativo), in termini di corrente.

Partenza (W/m, forma IEEE 738):  q_c + q_r + m*Cp*dT/dt = q_s + I^2 R(T)
Semplificazioni: q_s = 0 (notte); q_c + q_r ~ h_eff * (T - T_a) (linearizzazione);
R(T) lineare con alfa = 0,4 %/°C attorno a 85 °C; il vento aumenta lo scambio secondo f(V) = (max(V, V0) / V0)^0.5, con h_eff = f * h_ref.
Con u = (I/I_MAX)^2 * DT_MAX / f(V):   (TAU/f) dT/dt = u * (1 + ALPHA (T - 85)) - (T - T_a)
cioe' un'equazione lineare in T con  T* = [u (1 - 85 ALPHA) + T_a] / (1 - u ALPHA)  e  tau_eff = (TAU/f) / (1 - u ALPHA).
Calibrazione su un punto: 85 °C a 1600 A, 25 °C, V = V0 = 0,6 m/s (f = 1)  ->  DT_MAX = 60 °C.
Integrazione esatta per passo (T* e tau_eff costanti nel minuto). Se u ALPHA >= 1 (runaway) si satura a T_RUNAWAY.
"""
import numpy as np

I_MAX = 1600.0      # A, corrente di calibrazione
T_LIMIT = 85.0      # °C, limite di sicurezza
DT_MAX = 60.0       # °C a I_MAX con T_amb = 25 °C, V = V0 (85 - 25)
TAU = 20.0          # min, costante di tempo con V = V0
V0_WIND, N_WIND = 0.6, 0.5   # m/s di calibrazione; esponente (ordine di grandezza)
ALPHA = 0.004       # 1/°C, coefficiente di temperatura della resistenza (alluminio, ordine di grandezza)
T_RUNAWAY = 300.0   # °C, saturazione numerica se u*ALPHA >= 1 (valore non fisico)


def wind_factor(v_ms):
    return (max(float(v_ms), V0_WIND) / V0_WIND) ** N_WIND


def _target_tau(i, t_amb, f):
    """T* e tau_eff per R(T) lineare (equazione lineare in T). Se u*ALPHA >= 1: runaway, saturazione."""
    i = np.atleast_1d(np.asarray(i, dtype=float))
    u = (i / I_MAX) ** 2 * DT_MAX / f
    k = 1.0 - u * ALPHA
    ok = k > 0.02
    ks = np.where(ok, k, 1.0)
    target = np.where(ok, (u * (1.0 - T_LIMIT * ALPHA) + t_amb) / ks, T_RUNAWAY)
    tau = np.where(ok, (TAU / f) / ks, TAU / f)
    return target, tau


def temperature(i_a, t_amb, f=1.0):
    """Temperatura (°C, passo 1 min) per un profilo di corrente; parte dal regime alla prima corrente."""
    i = np.asarray(i_a, dtype=float)
    target, tau = _target_tau(i, t_amb, f)
    out = np.empty(len(i))
    out[0] = target[0]
    for j in range(len(i) - 1):
        out[j + 1] = target[j] + (out[j] - target[j]) * np.exp(-1.0 / tau[j])
    return out


def rating_a(t_amb, f=1.0):
    """Corrente a regime che porta il conduttore a T_LIMIT: a 85 °C vale u = T_LIMIT - T_a, quindi I = I_MAX sqrt(f (T_LIMIT - T_a) / DT_MAX)."""
    return I_MAX * float(np.sqrt(max(f * (T_LIMIT - t_amb), 0.0) / DT_MAX))


def step_response(i0, i1, t_amb, f=1.0, t_step=10, n=121):
    """Corrente e temperatura per I = i0 prima di t_step, i1 dopo. Parte dal regime a i0."""
    t = np.arange(n)
    i = np.where(t < t_step, float(i0), float(i1))
    return t, i, temperature(i, t_amb, f)


def time_to_limit(i0, i1, t_amb, f=1.0):
    """Minuti dal gradino al superamento di T_LIMIT (forma chiusa). None se non viene raggiunto; 0 se gia' sopra."""
    tt0, _ = _target_tau(i0, t_amb, f)
    tt1, tau1 = _target_tau(i1, t_amb, f)
    t0, t1, tau = float(tt0[0]), float(tt1[0]), float(tau1[0])
    if t0 >= T_LIMIT:
        return 0.0
    if t1 <= T_LIMIT:
        return None
    return float(-tau * np.log((T_LIMIT - t1) / (t0 - t1)))


def rating_30min_a(i0, t_amb, f=1.0, minutes=30.0):
    """Corrente massima di un gradino che porta a T_LIMIT dopo esattamente 'minutes' minuti, partendo dal regime a i0 (bisezione)."""
    lo, hi = float(i0), 4.0 * I_MAX
    ts = time_to_limit(i0, hi, t_amb, f)
    if ts is not None and ts > minutes:
        return hi
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        ts = time_to_limit(i0, mid, t_amb, f)
        if ts is None or ts > minutes:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def self_checks():
    """Verifiche numeriche mostrate nell'app."""
    n = 60
    ss = temperature(np.full(n, I_MAX), 25.0)[-1]
    i0, i1 = 0.5 * I_MAX, 1.2 * I_MAX
    step = temperature(np.r_[np.full(10, i0), np.full(n, i1)], 25.0)
    (t0, _), (t1, tau1) = _target_tau(i0, 25.0, 1.0), _target_tau(i1, 25.0, 1.0)
    exact = float(t1[0] + (t0[0] - t1[0]) * np.exp(-20.0 / tau1[0]))
    # ODE integrata numericamente (Eulero a passo piccolo) come controllo indipendente della soluzione esatta
    T, dt = float(t0[0]), 0.001
    u = (i1 / I_MAX) ** 2 * DT_MAX
    for _ in range(int(20.0 / dt)):
        T += dt * (u * (1 + ALPHA * (T - T_LIMIT)) - (T - 25.0)) / TAU
    return [("Regime a I_MAX (atteso 85,0 °C)", 85.0, float(ss)),
            ("Risposta a gradino dopo 20 min (esatta)", exact, float(step[10 + 20 - 1 + 1])),
            ("Gradino: soluzione esatta vs Eulero fine", exact, T)]
