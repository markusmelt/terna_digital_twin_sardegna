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
st.caption("Gradino di energia eolica disponibile al tramonto: il simulatore mostra quanto tempo c'è per intervenire prima degli 85 °C, il ruolo del termico al minimo, dell'intervento BESS e del Tyrrhenian link a regime. "
           "Modello semplificato e dimostrativo: limiti dichiarati nel tab «Assunzioni».")
st.info("📱 Su mobile apri il menu (☰) in alto a sinistra per i parametri.")

# ---------------- input ----------------
sb = st.sidebar
sb.header("🎛️ Parametri")
wind_peak = sb.slider("Picco rampa eolica (MW)", 0, 1200, 1000, 50)
thermal_nominal = sb.slider("Termico iniziale (MW)", 300, 600, 450, 25)
thermal_min = sb.slider("Minimo tecnico termico (MW)", 100, int(thermal_nominal), min(225, int(thermal_nominal)), 25)
line_cap = sb.slider("Soglia di gestione della dorsale (MW)", 600, 1100, 800, 10,
                     help=f"Il imite termico a 1600 A, 380 kV e cos φ 0,9 è ≈ {m.thermal_limit_mw():.0f} MW.")
sb.subheader("Flessibilità")
bess_mw = sb.slider("BESS stand-alone, potenza (MW)", 0.0, 61.9, 61.9, 5.0)
bess_h = sb.slider("BESS, durata a potenza nominale (h)", 0.5, 4.0, 2.0, 0.5)
link_on = sb.toggle("Attivazione Tyrrhenian Link", True,
                    help="Scenario a regime con entrata in esercizio dell'opera.")
link_mw = sb.slider("Capacità Link (MW)", 0, 1000, 1000, 50, disabled=not link_on)
sb.subheader("Ambiente")
t_amb = sb.slider("Temperatura ambiente (°C)", -5.0, 50.0, 25.0, 1.0)
wind_ms = sb.slider("Vento sul conduttore (m/s)", 0.0, 10.0, 0.6, 0.1,
                    help="Componente perpendicolare alla linea. 0,6 m/s è la condizione convenzionale di calibrazione (caso conservativo).")
sb.caption(f"= {wind_ms * 3.6:.0f} km/h · fattore di scambio f = {m.wind_factor(wind_ms):.2f}")
sb.markdown("---")
sb.subheader("📱 Link al progetto")
buf = io.BytesIO()
segno.make_qr(URL).save(buf, kind="png", scale=5, dark="#000000", light="#ffffff")
sb.image(buf.getvalue(), caption="Apri la web-app", width="stretch")

P = m.Params(wind_peak=wind_peak, thermal_nominal=thermal_nominal, thermal_min=thermal_min, line_cap=line_cap,
             bess_mw=bess_mw, bess_mwh=bess_mw * bess_h, link_mw=link_mw, link_available=link_on,
             t_amb=t_amb, wind_ms=wind_ms)
D = m.simulate(P)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["📊 Simulazione", "🔍 Sensibilità", "📋 Assunzioni", "✅ Verifiche", "⚡ Capacità Sardegna", "🗺️ Contesto"])

# ---------------- tab 1 ----------------
with tab1:
    c = st.columns(3)
    r = m.kpi_rows(D)
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
with tab2:
    st.subheader("Quanto Link serve?")
    st.markdown("Potenza massima che il Link deve esportare (dopo il BESS), al variare di picco eolico e soglia di gestione. "
                "Il resto dei parametri è quello della barra laterale.")

    @st.cache_data
    def grid(base: m.Params):
        winds = np.arange(600, 1201, 100)
        caps = np.arange(600, 1001, 50)
        z = np.zeros((len(caps), len(winds)))
        for i, cp in enumerate(caps):
            for j, w in enumerate(winds):
                d = m.dispatch(m.Params(**{**base.__dict__, "wind_peak": float(w), "line_cap": float(cp),
                                           "link_mw": 5000.0, "link_available": True}))
                z[i, j] = d["link"].max()
        return winds, caps, z

    w, cps, z = grid(P)
    hm = go.Figure(go.Heatmap(x=w, y=cps, z=z, colorscale="YlOrRd", colorbar=dict(title="MW"),
                              hovertemplate="Eolico %{x} MW<br>Soglia %{y} MW<br>Link %{z:.0f} MW<extra></extra>"))
    hm.add_contour(x=w, y=cps, z=z, contours=dict(start=m.Params().link_mw, end=m.Params().link_mw, coloring="none"),
                   line=dict(color="black", width=2), showscale=False, hoverinfo="skip")
    hm.update_layout(height=420, xaxis_title="Picco eolico (MW)", yaxis_title="Soglia di gestione (MW)",
                     template="plotly_white", margin=dict(t=20, b=10, l=10, r=10))
    st.plotly_chart(hm, width="stretch")
    st.caption("La linea nera indica 1000 MW, capacità nominale di una tratta: oltre quella linea il Link da solo non basta.")

    st.subheader("Efficacia del BESS da solo")
    bd = m.simulate(m.Params(**{**P.__dict__, "link_available": False, "bess_mw": bess_mw}))
    st.write(f"Senza Link il BESS assorbe {bd['soc_mwh']:.0f} MWh in 100 minuti, ma restano {bd['curt_mwh']:.0f} MWh da ridurre: "
             "la potenza dello stand-alone (circa 62 MW) è piccola rispetto al surplus (centinaia di MW).")

# ---------------- tab 3 ----------------
with tab3:
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
    2. **Convezione e irraggiamento linearizzati** rispetto alla temperatura dell'aria: $q_c + q_r \approx h_{eff}\,(T_c - T_a)$.
    3. **Vento:** aumenta lo scambio secondo $f(V) = \left(\max(V, V_0)/V_0\right)^{1/2}$, cioè $h_{eff} = f(V)\,h_{ref}$.
       Con $V \le V_0$ = 0,6 m/s si ha $f = 1$ (caso conservativo). L'esponente 1/2 è un ordine di grandezza per la convezione forzata su un cilindro;
       il fattore scala **tutto** lo scambio, irraggiamento compreso, che in realtà non dipende dal vento: il beneficio del vento è quindi **leggermente sovrastimato**
       (temperature con vento un po' ottimistiche). Il vento è un **dato di input in m/s**, non è legato alla produzione eolica.
    4. **Resistenza costante:** $R(T_c) \approx R$. Trascura circa +0,4 %/°C, quindi **sottostima** il riscaldamento a temperature alte.
    5. **Risultato:** con $C = m C_p$ si ottiene un modello del primo ordine.
    """)
    st.latex(r"C\,\frac{dT_c}{dt} + f(V)\,h_{ref}\,(T_c - T_a) = I^2 R"
             r"\;\;\Rightarrow\;\;"
             r"\tau\,\frac{dT_c}{dt} + T_c = T_a + \frac{I^2 R}{f(V)\,h_{ref}},\qquad \tau=\frac{C}{f(V)\,h_{ref}}")
    st.markdown(r"""
    6. **Calibrazione su un solo punto**, senza dati di catalogo del conduttore: a $I_{max}$ = 1600 A, $T_a$ = 25 °C e vento $V_0$ ($f = 1$) il conduttore è a 85 °C,
       quindi $\Delta T_{max} = I_{max}^2 R / h_{ref} = 60$ °C. Questo punto è un'**ipotesi di scenario**, che rappresenta un tratto con portata termica ridotta,
       non la portata di una terna standard. Con i dati reali del tratto si ricalibrano due parametri ($I_{max}$ e $\tau_0$). Da cui:
    """)
    st.latex(r"T_{target} = T_a + \left(\frac{I}{I_{max}}\right)^2 \frac{\Delta T_{max}}{f(V)},\quad \tau = \frac{\tau_0}{f(V)}")
    st.markdown(r"""
    **Integrazione:** target costante nel minuto, quindi soluzione esatta per passo:
    $T_{j+1} = T_{target} + (T_j - T_{target})\,e^{-\Delta t/\tau}$.
    Le temperature assolute sono **indicative** (calibrazione su un punto); il confronto **tra scenari** è più robusto.
    """)
    st.table(pd.DataFrame({
        "Parametro": ["V concatenata", "cos φ", "I_max", "ΔT_max (V = V_0)", "τ_0 (V = V_0)", "V_0", "Esponente di f", "Limite", "Passo"],
        "Valore": ["380 kV", "0,9", "1600 A (≈ %.0f MW)" % m.thermal_limit_mw(), "60 °C", "20 min", "0,6 m/s", "0,5", "85 °C", "1 min"],
        "Origine": ["nominale", "tipico", "ipotesi di scenario (calibrazione)","= 85 − 25", "assunzione", "condizione convenzionale", "assunzione (ordine di grandezza)", "soglia di sicurezza", "esatto"]}))
    st.subheader("Cosa rappresenta il tratto modellato")
    st.markdown(f"""
    Un **tratto equivalente a capacità ridotta**, non un tratto specifico della rete sarda: la sua capacità è un'**ipotesi di scenario**.
    - **Perché 1600 A (≈ {m.thermal_limit_mw():.0f} MW)?** È un valore tondo vicino alla corrente nominale del conduttore standard Terna
      (1500 A per fase, circa 1000 MVA per terna, Terna UX LAE 08), scelto in modo che il picco eolico da {int(P.wind_peak)} MW la superi
      e lo scenario abbia un transitorio da studiare. È una scelta di scenario, non una misura.
    - **Cosa non è:** la portata termica del conduttore reale, che è più alta della corrente nominale (portata nominale e portata termica non coincidono).
    - **Con dati reali** (conduttore, condizioni di posa, rating del tratto) si ricalibrano $I_{{max}}$ e $\\tau_0$.
    """)
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
    - **Vento:** unico input in m/s, uniforme lungo la linea e indipendente dalla produzione eolica, perché i parchi sono in punti diversi dal tratto di trasporto. Il vento rilevante è quello sulla **campata peggio raffreddata** (componente perpendicolare), non quello dei parchi: per calibrarlo servirebbero campagne anemometriche lungo il tracciato o misure sulla linea.
    - **Calibrazione a un punto:** 1600 A → 85 °C è un'ipotesi di scenario, non un dato di catalogo. Il conduttore standard Terna (Ø 31,5 mm, fascio trinato) ha una corrente
      nominale di 1500 A per fase (Terna, UX LAE 08), che è un valore di progetto con margini, non il punto in cui il conduttore raggiunge 85 °C: portata nominale e portata termica non coincidono
      (ed è il tema del dynamic line rating). Con i dati reali del tratto il modello va ricalibrato.
    - **Sole:** il modello è notturno ($q_s = 0$); al tramonto un po' di irraggiamento solare c'è ancora e scalderebbe di più.
    - BESS: potenza e durata assunta, **senza** SoC iniziale né rendimento. Link: iniezione limitata, non un modello di convertitore.
    - Scenario Link **a regime**: verifica l'entrata in servizio effettiva.
    - Dati di capacità da fonti pubbliche Terna; ΔT e τ sono assunzioni. Strumento dimostrativo, non affiliato a Terna S.p.A.
    - Sviluppi naturali: rete piccola in AC (es. pandapower) con N-1, serie temporali orarie, DLR calibrato, sicurezza antincendio del BESS.
    """)

# ---------------- tab 4 ----------------
with tab4:
    st.subheader("Verifiche numeriche del modello")
    rows = [{"Test": n, "Atteso": f"{a:.2f}", "Ottenuto": f"{b:.2f}", "Esito": "✅" if abs(a - b) < 0.05 else "❌"}
            for n, a, b in m.self_checks()]
    d0 = m.simulate(m.Params(**{**P.__dict__, "wind_ms": 0.6}))
    d1 = m.simulate(m.Params(**{**P.__dict__, "wind_ms": 3.0}))
    rows.append({"Test": "Il vento non peggiora la temperatura", "Atteso": "≤", "Ottenuto": f'{d1["T0"].max():.1f} vs {d0["T0"].max():.1f} °C',
                 "Esito": "✅" if d1["T0"].max() <= d0["T0"].max() else "❌"})
    bal = float(np.abs(D["inj1"] - D["line2"] - D["bess"] - D["link"] - D["curt"]).max())
    rows.append({"Test": "Bilancio di potenza (errore max)", "Atteso": "0", "Ottenuto": f"{bal:.1e} MW", "Esito": "✅" if bal < 1e-9 else "❌"})
    st.table(pd.DataFrame(rows))

# ---------------- tab 5 ----------------
with tab5:
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

# ---------------- tab 6 ----------------
with tab6:
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
