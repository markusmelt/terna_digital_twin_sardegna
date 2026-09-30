import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import segno
import streamlit as st

import model as m

st.set_page_config(page_title="Simulatore transitorio termico dorsale 380 kV",
                   page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")
URL = "https://dt-overheadconductors.streamlit.app/"
COL = {"0": "#E30613", "1": "#ff7f0e", "2": "#2ca02c"}

st.title("⚡ Simulatore del transitorio termico – dorsale 380 kV Sardegna")
st.caption("Rampa eolica serale: quanto tempo c'è per intervenire prima degli 85 °C, e cosa costa ciascuna leva. "
           "Modello semplificato e dimostrativo: limiti dichiarati nel tab «Assunzioni».")
st.info("📱 Su mobile apri il menu (☰) in alto a sinistra per i parametri.")

# ---------------- input ----------------
sb = st.sidebar
sb.header("🎛️ Parametri")
wind_peak = sb.slider("Picco rampa eolica (MW)", 0, 1200, 1000, 50)
thermal_nominal = sb.slider("Termico iniziale (MW)", 300, 600, 450, 25)
thermal_min = sb.slider("Minimo tecnico termico (MW)", 100, int(thermal_nominal), min(225, int(thermal_nominal)), 25)
line_cap = sb.slider("Soglia di gestione della dorsale (MW)", 600, 1100, 800, 10,
                     help=f"Non è il limite termico: a 1600 A, 380 kV e cos φ 0,9 il limite è ≈ {m.thermal_limit_mw():.0f} MW.")
sb.subheader("Flessibilità")
bess_mw = sb.slider("BESS stand-alone, potenza (MW)", 0.0, 61.9, 61.9, 5.0)
bess_h = sb.slider("BESS, durata a potenza nominale (h)", 0.5, 4.0, 2.0, 0.5,
                   help="Assunzione: il dato Terna riguarda la potenza, non l'energia.")
link_on = sb.toggle("Tyrrhenian Link disponibile (a regime)", True,
                    help="Scenario a regime: verifica lo stato di avanzamento dell'opera.")
link_mw = sb.slider("Capacità Link (MW)", 0, 1000, 1000, 50, disabled=not link_on)
sb.subheader("Ambiente")
t_amb = sb.slider("Temperatura ambiente (°C)", -5.0, 50.0, 25.0, 1.0)
dlr = sb.toggle("Raffreddamento da vento (DLR illustrativo)", False,
                help="Il vento che produce i MW raffredda anche il conduttore. Modello qualitativo, non IEEE 738.")
k = sb.slider("Quota di vento efficace sul conduttore", 0.1, 0.6, 0.3, 0.05, disabled=not dlr)
sb.markdown("---")
sb.subheader("📱 Link al progetto")
buf = io.BytesIO()
segno.make_qr(URL).save(buf, kind="png", scale=5, dark="#000000", light="#ffffff")
sb.image(buf.getvalue(), caption="Apri la web-app", width="stretch")

P = m.Params(wind_peak=wind_peak, thermal_nominal=thermal_nominal, thermal_min=thermal_min, line_cap=line_cap,
             bess_mw=bess_mw, bess_mwh=bess_mw * bess_h, link_mw=link_mw, link_available=link_on,
             t_amb=t_amb, dlr=dlr, dlr_k=k)
D = m.simulate(P)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Simulazione", "📋 Assunzioni", "✅ Verifiche", "⚡ Capacità Sardegna", "🗺️ Contesto"])

# ---------------- tab 1 ----------------
# SIMULAZIONE
# ---------------------------------------
with tab1:
  c = st.columns(3)
  r = m.kpi_rows(D)
  for col, row in zip(c, r):
      col.metric(row["Scenario"], f'{row["T max (°C)"]} °C', row["Tempo di intervento"], delta_color="off")
  st.caption("«Tempo di intervento» = minuti dalla rampa (min 20) al superamento di 85 °C: è la finestra per redispatching.")
  b = st.columns(3)
  b[0].metric("Energia esportata dal Link", f'{D["link_mwh"]:.0f} MWh')
  b[1].metric("Energia assorbita dal BESS", f'{D["soc_mwh"]:.0f} MWh')
  b[2].metric("Eolico ridotto (curtailment)", f'{D["curt_mwh"]:.0f} MWh',
              "costo dell'assenza del Link" if D["curt_mwh"] > 0 else None, delta_color="off")

  fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                      subplot_titles=("Transito sulla dorsale (MW)", "Temperatura del conduttore (°C)",
                                      "Leve di flessibilità (MW)"))
  t = D["t"]
  for key, y, name, dash in (("0", D["inj0"], "Termico rigido", "dot"), ("1", D["inj1"], "Termico al minimo", "solid"),
                             ("2", D["line2"], "Con BESS + Link", "solid")):
      fig.add_trace(go.Scatter(x=t, y=y, name=name, line=dict(color=COL[key], dash=dash, width=2)), row=1, col=1)
  fig.add_hline(y=line_cap, line_dash="dash", line_color="gray", row=1, col=1,
                annotation_text="Soglia di gestione", annotation_position="top left")
  for key, y, name, dash in (("0", D["T0"], "", "dot"), ("1", D["T1"], "", "solid"), ("2", D["T2"], "", "solid")):
      fig.add_trace(go.Scatter(x=t, y=y, line=dict(color=COL[key], dash=dash, width=2), showlegend=False), row=2, col=1)
  fig.add_hline(y=m.T_LIMIT, line_dash="dash", line_color="magenta", row=2, col=1,
                annotation_text="Limite 85 °C", annotation_position="top left")
  fig.add_trace(go.Scatter(x=t, y=D["bess"], name="BESS", line=dict(color="#1f77b4")), row=3, col=1)
  fig.add_trace(go.Scatter(x=t, y=D["link"], name="Tyrrhenian Link", line=dict(color="#9467bd")), row=3, col=1)
  fig.add_trace(go.Scatter(x=t, y=D["curt"], name="Curtailment", line=dict(color="#6b7280", dash="dot"),
                           showlegend=bool(D["curt"].max() > 0)), row=3, col=1)
  fig.add_vline(x=m.RAMP_MIN, line_dash="dot", line_color="lightgray")
  fig.update_xaxes(title_text="Tempo (min)", row=3, col=1)
  fig.update_layout(height=820, template="plotly_white", margin=dict(t=50, b=10, l=10, r=10),
                    legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"))
  st.plotly_chart(fig, width="stretch")
  st.dataframe(pd.DataFrame(r), hide_index=True, width="stretch")
  if not link_on:
      st.warning("Senza Link il surplus oltre la soglia va ridotto (curtailment): la rete resta sicura ma si perde energia rinnovabile.")


# ---------------- tab 2 ----------------
# ASSUNZIONI
# ---------------------------------------
with tab2:
    st.header("Assunzioni e limiti")
    st.subheader("Modello termico: dal bilancio di potenza per unità di lunghezza")
    st.markdown("Punto di partenza: bilancio termico transitorio del conduttore, in **W/m** (forma di IEEE 738):")
    st.latex(r"q_c + q_r + m\,C_p\,\frac{dT_c}{dt} = q_s + I^2\,R(T_c)")
    st.markdown(r"""
    - $q_c$: perdita per convezione [W/m]; $q_r$: perdita per irraggiamento [W/m]; $q_s$: guadagno solare [W/m]
    - $m\,C_p$: capacità termica per unità di lunghezza [J/(m·°C)]; $R(T_c)$: resistenza per unità di lunghezza [Ω/m]
    - $I^2 R$: riscaldamento per effetto Joule [W/m]; $T_c$ temperatura del conduttore, $T_a$ dell'aria

    **Semplificazioni, in ordine:**

    1. **Notte:** $q_s = 0$ (tramonto in poi).
    2. **Irraggiamento linearizzato** attorno al punto di lavoro:
       $q_r = \pi D \varepsilon \sigma\left[(T_c+273)^4-(T_a+273)^4\right] \approx h_r\,(T_c - T_a)$.
    3. **Convezione forzata:** $q_c = h_c(V)\,(T_c - T_a)$ con $h_c \propto V^{0,6}$ (esponente della forma ad alto vento di IEEE 738),
       con un minimo per la convezione naturale. Insieme: $q_c + q_r = h_{eff}(V)\,(T_c - T_a)$, con $h_{eff} = h_r + h_c(V)$.
    4. **Resistenza costante:** $R(T_c) \approx R$. Trascura circa +0,4 %/°C, quindi **sottostima** il riscaldamento a temperature alte.
    5. **Risultato:** con $C = m C_p$ si ottiene un modello del primo ordine.
    """)
    st.latex(r"C\,\frac{dT_c}{dt} + h_{eff}(V)\,(T_c - T_a) = I^2 R"
             r"\;\;\Rightarrow\;\;"
             r"\tau(V)\,\frac{dT_c}{dt} + T_c = T_a + \frac{I^2 R}{h_{eff}(V)},\qquad \tau(V)=\frac{C}{h_{eff}(V)}")
    st.markdown(r"""
    6. **Calibrazione su un solo punto**, senza dati di catalogo del conduttore: a $I_{max}$ = 1600 A, $T_a$ = 25 °C e vento di riferimento
       $V_0$ = 0,6 m/s (condizione convenzionale di portata statica) il conduttore è a 85 °C, quindi
       $\Delta T_{max} = I_{max}^2 R / h_{ref} = 60$ °C. Con $f(V) = h_{eff}(V)/h_{ref}$:
    """)
    st.latex(r"T_{target} = T_a + \left(\frac{I}{I_{max}}\right)^2 \frac{\Delta T_{max}}{f(V)},\quad"
             r"\tau = \frac{\tau_0}{f(V)},\quad"
             r"f(V) = (1-s) + s\left(\frac{\max(V,V_0)}{V_0}\right)^{0,6}")
    st.markdown(r"""
    dove $s$ è la quota di scambio dovuta alla convezione a $V_0$ (assunta 0,5). Senza vento utile ($V \le V_0$) si ha $f = 1$.

    7. **Velocità del vento dalla produzione eolica** (proxy grossolano): $V = k\,V_{rif}\,(P_{eol}/P_{rif})^{1/3}$, dalla legge cubica della potenza
       eolica. Il fattore $k$ tiene conto di angolo di incidenza, schermatura e distanza tra parchi e linea: è un'assunzione, non una misura.

    **Integrazione:** target costante nel minuto, quindi soluzione esatta per passo:
    $T_{j+1} = T_{target} + (T_j - T_{target})\,e^{-\Delta t/\tau}$.
    Le temperature assolute sono **indicative** (calibrazione su un punto); il confronto **tra scenari** è più robusto.
    """)
    st.table(pd.DataFrame({
        "Parametro": ["V concatenata", "cos φ", "I_max", "ΔT_max a I_max", "V_0", "τ_0 (a V_0)", "s", "k", "V_rif, P_rif", "Limite", "Passo"],
        "Valore": ["380 kV", "0,9", "1600 A (≈ %.0f MW)" % m.thermal_limit_mw(), "60 °C", "0,6 m/s", "20 min", "0,5",
                   "0,3 (regolabile)", "12 m/s, 1200 MW", "85 °C", "1 min"],
        "Origine": ["nominale", "tipico", "calibrazione", "= 85 − 25", "convenzione IEEE 738", "assunzione", "assunzione",
                    "assunzione", "assunzione", "soglia di sicurezza", "esatto"]}))
    st.subheader("Cosa rappresenta la soglia di gestione")
    st.markdown(f"La soglia ({line_cap} MW) è un **margine di esercizio**, non il limite termico (≈ {m.thermal_limit_mw():.0f} MW).")
    st.subheader("Scenari")
    st.markdown("""
    0. **Termico rigido**: il termico resta al valore iniziale.
    1. **Termico al minimo**: dal minuto 20 scende al minimo tecnico.
    2. **Con BESS + Link**: oltre la soglia, prima il BESS (limitato in potenza ed energia), poi il Link, poi curtailment.
    """)
    st.subheader("Limiti")
    st.markdown("""
    - Nessun flusso di carico, tensioni, reattivo, **N-1**, stabilità o inerzia: la dorsale è **un solo elemento** e le iniezioni si sommano.
    - BESS: potenza e durata assunta, **senza** SoC iniziale né rendimento. Link: iniezione limitata, non un modello di convertitore.
    - Scenario Link **a regime**: verifica l'entrata in servizio effettiva.
    - Dati di capacità da fonti pubbliche Terna; ΔT e τ sono assunzioni. Strumento dimostrativo, non affiliato a Terna S.p.A.
    - Sviluppi naturali: rete piccola in AC (es. pandapower) con N-1, serie temporali orarie, DLR calibrato, sicurezza antincendio del BESS.
    """)

# ---------------- tab 3 ----------------
# VERIFICHE NUMERICHE
# ---------------------------------------
with tab3:
    st.subheader("Verifiche numeriche del modello")
    rows = [{"Test": n, "Atteso": f"{a:.2f}", "Ottenuto": f"{b:.2f}", "Esito": "✅" if abs(a - b) < 0.05 else "❌"}
            for n, a, b in m.self_checks()]
    d0 = m.simulate(m.Params(**{**P.__dict__, "dlr": False}))
    d1 = m.simulate(m.Params(**{**P.__dict__, "dlr": True}))
    rows.append({"Test": "Il vento non peggiora la temperatura", "Atteso": "≤", "Ottenuto": f'{d1["T0"].max():.1f} vs {d0["T0"].max():.1f} °C',
                 "Esito": "✅" if d1["T0"].max() <= d0["T0"].max() else "❌"})
    bal = float(np.abs(D["inj1"] - D["line2"] - D["bess"] - D["link"] - D["curt"]).max())
    rows.append({"Test": "Bilancio di potenza (errore max)", "Atteso": "0", "Ottenuto": f"{bal:.1e} MW", "Esito": "✅" if bal < 1e-9 else "❌"})
    st.table(pd.DataFrame(rows))

# ---------------- tab 4 ----------------
# CAPACITA' SARDEGNA
# ---------------------------------------
with tab4:
    fonti = ["Eolico", "Fotovoltaico", "Termoelettrico", "Idrico", "Accumulo stand-alone"]
    lorda = [1193.52, 1722.09, 2395.47, 467.85, 63.90]
    netta = [1193.20, 1722.09, 2174.92, 463.42, 61.90]
    fmt = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    k1, k2, k3 = st.columns(3)
    k1.metric("Capacità lorda totale", fmt(sum(lorda)) + " MW")
    k2.metric("Capacità netta immissibile", fmt(sum(netta)) + " MW", f"-{fmt(sum(lorda) - sum(netta))} MW servizi ausiliari", delta_color="inverse")
    k3.metric("Quota rinnovabili (netto)", f"{(netta[0] + netta[1] + netta[3]) / sum(netta) * 100:.1f} %".replace(".", ","))
    f2 = go.Figure([go.Bar(x=fonti, y=lorda, name="Lorda", marker_color="#1f77b4"),
                    go.Bar(x=fonti, y=netta, name="Netta", marker_color="#2ca02c")])
    f2.update_layout(barmode="group", yaxis_title="MW", height=380, margin=dict(t=30, b=10, l=10, r=10),
                     legend=dict(orientation="h", y=1.08))
    st.plotly_chart(f2, width="stretch")
    f3 = go.Figure(go.Pie(labels=fonti, values=netta, hole=.3, textinfo="percent"))
    f3.update_layout(height=380, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.1))
    st.plotly_chart(f3, width="stretch")
    st.caption("Dati: dashboard Terna (potenza efficiente), come estratti dall'autore.")

# ---------------- tab 5 ----------------
# CONTESTO
# ---------------------------------------
with tab5:
    st.markdown(f"""
    Al tramonto il fotovoltaico si azzera mentre un fronte di vento porta l'eolico a **{wind_peak} MW**. Il termico non può scendere sotto il
    minimo tecnico (**{thermal_min} MW**, servizi di sicurezza). La somma carica la dorsale a 380 kV verso la stazione di Selargius.
    Il BESS stand-alone ({bess_mw:.1f} MW) da solo non basta; il **Tyrrhenian Link** esporta il surplus verso Sicilia e Campania.
    """)
    sites = pd.DataFrame({"Sito": ["Selargius (stazione)", "Terra Mala (Cagliari)", "Fiumetorto (Termini Imerese)", "Battipaglia"],
                          "lat": [39.26, 39.1961, 37.9725, 40.5695], "lon": [9.16, 9.3296, 13.7557, 14.8238]})
    mp = go.Figure()
    mp.add_trace(go.Scattermap(lat=[40.84, 39.26], lon=[8.32, 9.16], mode="lines+markers", line=dict(width=4, color="#ff7f0e"),
                               name="Dorsale 380 kV (schematica)"))
    mp.add_trace(go.Scattermap(lat=sites.lat, lon=sites.lon, mode="lines", line=dict(width=4, color="#2ca02c"),
                               name="Tyrrhenian Link (schematico)"))
    mp.add_trace(go.Scattermap(lat=sites.lat, lon=sites.lon, mode="markers", marker=dict(size=14, color="#d62728"),
                               text=sites.Sito, hoverinfo="text", name="Siti"))
    mp.update_layout(map=dict(style="open-street-map", center=dict(lat=39.6, lon=11.6), zoom=5),
                     margin=dict(l=0, r=0, t=0, b=0), height=480,
                     legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"))
    st.plotly_chart(mp, width="stretch")
    st.caption("Tracciati schematici, non i percorsi reali.")
