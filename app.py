import io
import plotly.graph_objects as go
import segno
import streamlit as st

import model as m

st.set_page_config(page_title="Calcolatore di margine di una linea 380 kV (DTR)", page_icon="⚡", layout="centered")
URL = "https://sardinia-380kv-thermal.streamlit.app/"

st.title("⚡ Calcolatore di margine di una linea 380 kV")
st.caption("Quanta corrente in più regge un conduttore, con vento e temperatura reali, rispetto al limite fisso (DTR). "
           "Strumento dimostrativo, non affiliato a Terna S.p.A.")

# ---------------- input ----------------
st.subheader("1. Imposta le condizioni")
i_now = st.slider("Corrente nella linea (A)", 200, 2800, 1800, 25,
                  help="Corrente per fase. Il valore nominale Terna è 1500 A.")
t_amb = st.slider("Temperatura ambiente (°C)", -5, 45, 25, 1)
wind = st.slider("Vento sul conduttore (m/s)", 0.0, 8.0, 2.0, 0.1)
sun = st.slider("Irraggiamento solare (W/m²)", 0, 1100, 800, 50,
                help="0 = notte; circa 1000 = sole pieno a mezzogiorno d'estate.")

# ---------------- calcolo ----------------
R_static = m.I_MAX                                  # 1500 A: 35 °C, 0,6 m/s, 1000 W/m²
R_dyn = m.rating_sun_a(t_amb, m.wind_factor(wind), sun)   # stesso limite 85 °C, condizioni reali
margin_s, margin_d = R_static - i_now, R_dyn - i_now

# ---------------- risultati ----------------
st.subheader("2. Margine")
c1, c2 = st.columns(2)
c1.metric("Limite fisso (statico)", f"{R_static:.0f} A", f"margine {margin_s:+.0f} A ({margin_s / R_static * 100:+.0f} %)",
          delta_color="normal")
c2.metric("Limite con condizioni reali (DTR)", f"{R_dyn:.0f} A", f"margine {margin_d:+.0f} A ({margin_d / R_dyn * 100:+.0f} %)",
          delta_color="normal")

if i_now <= R_static:
    st.success(f"Entro il limite fisso. Con le condizioni impostate la portata reale è {R_dyn:.0f} A ({R_dyn - R_static:+.0f} A sul limite fisso).")
elif i_now <= R_dyn:
    st.info("Oltre il limite fisso ma entro quello reale: con il solo limite fisso servirebbe ridurre il carico, "
            "con il DTR la linea regge. È il beneficio del DTR.")
else:
    st.warning("Oltre anche il limite reale: il conduttore supera 85 °C a regime, serve ridurre la corrente.")

fig = go.Figure()
fig.add_trace(go.Bar(y=["Limite fisso", "Limite reale (DTR)"], x=[R_static, R_dyn], orientation="h",
                     marker_color=["#E30613", "#2ca02c"], text=[f"{R_static:.0f} A", f"{R_dyn:.0f} A"], textposition="inside"))
fig.add_vline(x=i_now, line_width=3, line_dash="dash", line_color="#1f77b4",
              annotation_text=f"Corrente {i_now} A", annotation_position="top")
fig.update_layout(height=260, template="plotly_white", showlegend=False, xaxis_title="Corrente (A)",
                  xaxis_range=[0, 3200], margin=dict(t=40, b=10, l=10, r=10))
st.plotly_chart(fig, width="stretch")

# ---------------- spiegazione ----------------
with st.expander("Come funziona"):
    st.markdown(r"""
    - **Limite fisso**: 1500 A, la corrente nominale Terna per fase (conduttore ACSR 585,3 mm², UX LAE 08), assunta come portata
      a 85 °C in condizioni convenzionali prudenti (35 °C, vento 0,6 m/s, sole 1000 W/m²).
    - **Limite con condizioni reali**: stessa temperatura massima di 85 °C, ma con temperatura, vento e sole che hai impostato:
      $I = 1500\sqrt{f(V)\,(85-T_a)(1+s_0)/50 - s}$, con $f(V)=(\max(V,0{,}6)/0{,}6)^{1/2}$ e $s = s_0\,G/1000$, $s_0 = 0{,}14$
      (il sole aggiunge calore: circa 22 W/m a 1000 W/m², contro circa 157 W/m di effetto Joule a 1500 A).
    - **Margine** = limite − corrente.
    - Più vento, più freddo e meno sole, più portata; con caldo e vento debole il limite reale può scendere sotto quello fisso.
    - Modello semplificato: un solo tratto, sole come calore costante (assorbimento circa 0,7, stima), vento come fattore sintetico. 1500 A è un'ipotesi prudente,
      non il limite termico di catalogo.
    """)

sb = st.sidebar
buf = io.BytesIO()
segno.make_qr(URL).save(buf, kind="png", scale=5, dark="#000000", light="#ffffff")
sb.image(buf.getvalue(), caption="Apri la web-app", width="stretch")
