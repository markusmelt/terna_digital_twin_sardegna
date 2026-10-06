import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import segno
import streamlit as st

import model as m

st.set_page_config(page_title="Gradino di corrente su un tratto critico di linea e DTR",
                   page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
URL = "https://sardinia-380kv-thermal.streamlit.app/"

st.title("⚡ Gradino di corrente su un tratto critico di dorsale: quanto tempo c'è, e cosa cambia con il DTR")
st.caption("Modello termico semplificato (primo ordine, un solo tratto critico, un solo limite di temperatura). "
           "Strumento dimostrativo, non affiliato a Terna S.p.A.: limiti dichiarati in «Assunzioni e limiti».")

# ---------------- input ----------------
sb = st.sidebar
sb.header("🎛️ Parametri")
sb.subheader("Corrente nel tratto critico")
i0 = sb.slider("Corrente prima del gradino (A)", 200, 1600, 850, 25)
i1 = sb.slider("Corrente dopo il gradino (A)", 500, 2800, 1850, 25)
sb.subheader("Condizioni reali")
t_amb = sb.slider("Temperatura ambiente (°C)", -5.0, 45.0, 25.0, 1.0)
wind_ms = sb.slider("Vento sul conduttore (m/s)", 0.0, 8.0, 2.0, 0.1,
                    help="Componente perpendicolare alla linea sulla campata peggio raffreddata.")
sb.subheader("Condizioni del rating statico")
t_ref = sb.slider("Temperatura convenzionale (°C)", 20.0, 45.0, 35.0, 1.0,
                  help="Ipotesi: i rating statici assumono condizioni conservative (estate, vento quasi nullo).")
v_ref = 0.6
sb.caption(f"Vento convenzionale: {v_ref} m/s (calibrazione del modello).")
sb.markdown("---")
buf = io.BytesIO()
segno.make_qr(URL).save(buf, kind="png", scale=5, dark="#000000", light="#ffffff")
sb.image(buf.getvalue(), caption="Apri la web-app", width="stretch")

f_real, f_ref = m.wind_factor(wind_ms), m.wind_factor(v_ref)
R_static = m.rating_a(t_ref, f_ref)
R_dyn = m.rating_a(t_amb, f_real)
t_lim_static = m.time_to_limit(i0, i1, t_ref, f_ref)
t_lim_dyn = m.time_to_limit(i0, i1, t_amb, f_real)
R30_static = m.rating_30min_a(i0, t_ref, f_ref)
R30_dyn = m.rating_30min_a(i0, t_amb, f_real)

fmt_t = lambda x: "mai (regime sotto 85 °C)" if x is None else ("già sopra 85 °C" if x <= 0 else f"{x:.0f} min")

# ---------------- risultati ----------------
c1, c2, c3 = st.columns(3)
c1.metric("Rating statico (regime, 85 °C)", f"{R_static:.0f} A",
          f"condizioni convenzionali: {t_ref:.0f} °C, {v_ref} m/s", delta_color="off")
c2.metric("Rating dinamico (regime, 85 °C)", f"{R_dyn:.0f} A",
          f"{(R_dyn / R_static - 1) * 100:+.0f} % rispetto allo statico", delta_color="normal")
c3.metric("Corrente dopo il gradino", f"{i1} A",
          f"{'supera' if i1 > R_static else 'entro'} il rating statico · "
          f"{'supera' if i1 > R_dyn else 'entro'} il dinamico", delta_color="off")

d1, d2 = st.columns(2)
d1.metric("Tempo prima di 85 °C, condizioni convenzionali", fmt_t(t_lim_static),
          f"corrente max sostenibile 30 min: {R30_static:.0f} A", delta_color="off")
d2.metric("Tempo prima di 85 °C, condizioni reali", fmt_t(t_lim_dyn),
          f"corrente max sostenibile 30 min: {R30_dyn:.0f} A", delta_color="off")

if i1 > R_static and (t_lim_dyn is None):
    st.success("Con il rating statico la corrente andrebbe limitata o gestita con redispatching; "
               "con le condizioni reali il tratto la regge a regime: è il beneficio del DTR.")
elif i1 > R_static:
    st.warning("La corrente supera il rating statico e, nelle condizioni reali, porta il conduttore oltre 85 °C: "
               "il tempo indicato è la finestra per intervenire (redispatching).")
else:
    st.info("La corrente è entro il rating statico: il DTR qui serve soprattutto a recuperare margine in più.")

# ---------------- grafici ----------------
tt, ia, T_real = m.step_response(i0, i1, t_amb, f_real)
_, _, T_ref = m.step_response(i0, i1, t_ref, f_ref)
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.3, 0.7],
                    subplot_titles=("Corrente nel tratto critico (A)", "Temperatura del conduttore (°C)"))
fig.add_trace(go.Scatter(x=tt, y=ia, name="Corrente", line=dict(color="#1f77b4", width=2), showlegend=False), row=1, col=1)
fig.add_hline(y=R_static, line_dash="dash", line_color="#E30613", row=1, col=1,
              annotation_text="Rating statico", annotation_position="top left")
fig.add_hline(y=R_dyn, line_dash="dash", line_color="#2ca02c", row=1, col=1,
              annotation_text="Rating dinamico", annotation_position="bottom left")
fig.add_trace(go.Scatter(x=tt, y=T_ref, name="Condizioni convenzionali", line=dict(color="#E30613", width=2)), row=2, col=1)
fig.add_trace(go.Scatter(x=tt, y=T_real, name="Condizioni reali (DTR)", line=dict(color="#2ca02c", width=2)), row=2, col=1)
fig.add_hline(y=m.T_LIMIT, line_dash="dash", line_color="magenta", row=2, col=1,
              annotation_text="Limite 85 °C", annotation_position="top left")
fig.add_vline(x=10, line_dash="dot", line_color="lightgray")
fig.update_xaxes(title_text="Tempo (min)", row=2, col=1)
fig.update_yaxes(range=[0, 250], row=2, col=1)
fig.update_layout(height=620, template="plotly_white", margin=dict(t=50, b=10, l=10, r=10),
                  legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"))
st.plotly_chart(fig, width="stretch")
st.caption("Le temperature sopra 85 °C indicano quanto si sfora senza interventi: nella realtà le protezioni o l'esercizio agirebbero prima. "
           "Il dato utile è il tempo disponibile.")

st.subheader("Il rating dinamico al variare delle condizioni")
cc1, cc2 = st.columns(2)
vs = np.arange(0.0, 8.01, 0.1)
fa = go.Figure()
for ta, col in ((15, "#2ca02c"), (25, "#ff7f0e"), (35, "#E30613"), (45, "#7f1d1d")):
    fa.add_trace(go.Scatter(x=vs, y=[m.rating_a(ta, m.wind_factor(v)) for v in vs], name=f"{ta} °C", line=dict(color=col)))
fa.add_hline(y=i1, line_dash="dot", line_color="#1f77b4", annotation_text="Corrente dopo il gradino", annotation_position="top left")
fa.update_layout(height=360, template="plotly_white", xaxis_title="Vento sul conduttore (m/s)", yaxis_title="Rating a regime (A)",
                 margin=dict(t=30, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.25))
cc1.plotly_chart(fa, width="stretch")
ts = np.arange(-5.0, 45.1, 1.0)
fb = go.Figure()
for v, col in ((0.6, "#E30613"), (1.5, "#ff7f0e"), (3.0, "#2ca02c")):
    fb.add_trace(go.Scatter(x=ts, y=[m.rating_a(t, m.wind_factor(v)) for t in ts], name=f"{v} m/s", line=dict(color=col)))
fb.add_hline(y=i1, line_dash="dot", line_color="#1f77b4", annotation_text="Corrente dopo il gradino", annotation_position="top left")
fb.update_layout(height=360, template="plotly_white", xaxis_title="Temperatura ambiente (°C)", yaxis_title="Rating a regime (A)",
                 margin=dict(t=30, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.25))
cc2.plotly_chart(fb, width="stretch")
st.caption("Rating a regime ∝ √(f(V)·(85 − T_amb)): più vento e più freddo, più portata. "
           "Il dato conservativo del rating statico corrisponde al punto «caldo e senza vento».")

# ---------------- spiegazioni ----------------
with st.expander("Perché è collegato al DTR (Dynamic Thermal Rating)", expanded=True):
    st.markdown(f"""
    - **Rating statico**: portata fissata con condizioni convenzionali conservative (qui {t_ref:.0f} °C e {v_ref} m/s), valida sempre.
    - **Rating dinamico (DTR)**: portata ricalcolata con le condizioni reali (temperatura, vento, sole, corrente) misurate o stimate lungo la linea.
      Il Piano di Sviluppo Terna 2025 descrive il DTR con modello CIGRE, sensori sulle campate critiche e corrente massima sostenibile a 30 minuti.
    - **Gradino di corrente**: il conduttore ha inerzia termica (τ ≈ {20 / f_real:.0f} min con il vento attuale). Per un gradino il tratto può superare per un po' il rating a regime:
      il **tempo prima degli 85 °C** è la finestra per intervenire con il redispatching.
    - **Cosa mostra il PoC**: la stessa corrente è «fuori rating» con condizioni convenzionali e può essere accettabile con condizioni reali.
      Non dimostra un sovraccarico reale: mostra il metodo.
    """)

with st.expander("Assunzioni e limiti"):
    st.markdown(r"""
    **Modello.** Bilancio termico per unità di lunghezza (forma di IEEE 738), notte ($q_s=0$), scambio linearizzato, vento come fattore
    $f(V)=(\max(V,V_0)/V_0)^{1/2}$ con $V_0=0{,}6$ m/s, resistenza lineare in $T$ ($\alpha=0{,}4\,\%/°C$ attorno a 85 °C).
    Con $u=(I/I_{max})^2\,\Delta T_{max}/f$ si ottiene $T^*=[u(1-85\alpha)+T_a]/(1-u\alpha)$ e $\tau_{eff}=(\tau_0/f)/(1-u\alpha)$:
    soluzione esatta $T(t)=T^*+(T_0-T^*)\,e^{-t/\tau_{eff}}$.

    **Rating a regime (forma chiusa).** A 85 °C vale $u=85-T_a$, quindi $I_{rat}=I_{max}\sqrt{f\,(85-T_a)/\Delta T_{max}}$.

    **Calibrazione a un punto**: 85 °C a 1600 A, 25 °C e 0,6 m/s ($\Delta T_{max}=60$ °C, $\tau_0=20$ min). È un'**ipotesi di scenario**, non il dato di un conduttore:
    con i dati reali del tratto si ricalibrano $I_{max}$ e $\tau_0$.

    **Limiti.**
    - Un solo tratto critico equivalente, descritto solo dalla corrente: niente flusso di carico, N-1, tensioni o reattivo, e nessuna distinzione sull'origine della corrente.
    - Vento uniforme e perpendicolare, senza sole e senza direzione del vento.
    - Il fattore $f(V)$ scala tutto lo scambio, irraggiamento compreso: il beneficio del vento è un po' sovrastimato.
    - Le condizioni convenzionali del rating statico sono un'ipotesi: i rating reali dipendono dalla stagione e dal conduttore.
    - Le temperature assolute sono indicative; i confronti tra le condizioni sono più robusti.
    - Sviluppi naturali: dati del conduttore, serie meteo, sole (IEEE 738/CIGRE TB 601), campata critica, N-1.
    """)

with st.expander("Verifiche numeriche"):
    rows = [{"Test": n, "Atteso": f"{a:.2f}", "Ottenuto": f"{b:.2f}", "Esito": "✅" if abs(a - b) < 0.05 else "❌"}
            for n, a, b in m.self_checks()]
    r_chk = m.rating_a(25.0, 1.0)
    rows.append({"Test": "Rating a 25 °C, 0,6 m/s = corrente di calibrazione (A)", "Atteso": f"{m.I_MAX:.2f}", "Ottenuto": f"{r_chk:.2f}",
                 "Esito": "✅" if abs(r_chk - m.I_MAX) < 0.05 else "❌"})
    i_chk = max(i1, R_static + 100)
    tl = m.time_to_limit(i0, i_chk, t_ref, f_ref)
    _, _, T2 = m.step_response(i0, i_chk, t_ref, f_ref, n=181)
    disc = float(np.argmax(T2 > m.T_LIMIT) - 10) if (T2 > m.T_LIMIT).any() else float("nan")
    rows.append({"Test": "Tempo a 85 °C: forma chiusa vs simulazione (± 1 min)", "Atteso": f"{tl:.1f}" if tl is not None else "–",
                 "Ottenuto": f"{disc:.1f}", "Esito": "✅" if tl is not None and abs(tl - disc) <= 1.0 else "❌"})
    r30 = m.rating_30min_a(i0, t_ref, f_ref)
    t30 = m.time_to_limit(i0, r30, t_ref, f_ref)
    rows.append({"Test": "Rating 30 min: tempo a 85 °C = 30 min", "Atteso": "30.00", "Ottenuto": f"{t30:.2f}" if t30 is not None else "–",
                 "Esito": "✅" if t30 is not None and abs(t30 - 30) < 0.05 else "❌"})
    st.table(pd.DataFrame(rows))
