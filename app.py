import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import segno
import io


# --- INTESTAZIONE PRINCIPALE ---
st.title("⚡ Digital Twin PoC for Terna Asset Management")
st.markdown("""
*Strumento di simulazione interattiva per l'analisi del transitorio termico sulla dorsale elettrica a 380 kV e la valutazione dei meccanismi di flessibilità di rete.*
""")

# --- SIDEBAR INTERATTIVA (PARAMETRI DI INPUT) ---
st.sidebar.header("🎛️ Parametri del Simulatore")

# Slider dinamici 
wind_peak = st.sidebar.slider("Picco della Rampa Eolica (MW)", min_value=0, max_value=1200, value=1000, step=50) # slider eolico
percentuale_eolico = (wind_peak / 1193.20) * 100
st.sidebar.caption(f"💨 Equivale al **{percentuale_eolico:.1f}%** della potenza netta installata.")

thermal_nominal = st.sidebar.slider("Potenza Termica Nominale Iniziale (MW)", min_value=300, max_value=600, value=450, step=25, help="Livello di generazione delle centrali termoelettriche prima dell'evento meteo.") # slider potenza termica iniziale nominale
percentuale_nominal = (thermal_nominal / 2174.92) * 100
st.sidebar.caption(f"🏭 Equivale al **{percentuale_nominal:.1f}%** della potenza netta termica.")

thermal_min = st.sidebar.slider("Minimo Tecnico Centrale Termica (MW)", min_value=100, max_value=int(thermal_nominal), value=150, step=25, help="Il limite inferiore a cui la centrale può scendere durante il redispatching.") # slider minimo tecnico centrali termiche
percentuale_termico = (thermal_min / 2174.92) * 100
st.sidebar.caption(f"💨 Equivale al **{percentuale_termico:.1f}%** della potenza netta termica.")

sg_threshold = st.sidebar.slider("Capacità di accumulo stand alone (MW)", min_value=0.0, max_value=61.90, value=61.90, step=5.0) # slider BESS
percentuale_BESS = (sg_threshold / 61.90) * 100
st.sidebar.caption(f"💨 Equivale al **{percentuale_BESS:.1f}%** della potenza netta di accumulo.")

st.sidebar.markdown("---")
st.sidebar.subheader("🌤️ Condizioni Meteo Ambientali")

t_ambient = st.sidebar.slider("Temperatura Ambiente (°C)", min_value=-5.0, max_value=50.0, value=25.0, step=1.0) # slider temperatura ambiente

st.sidebar.markdown("---")
st.sidebar.info("""💡 **Info:** Modifica gli slider per simulare scenari differenti.""")

st.sidebar.markdown("---")
st.sidebar.subheader("📱 Link al progetto")

url_progetto = "https://ternadigitaltwinsardegna-8qhaxkm4racpwab2w3xxvr.streamlit.app/"

# Genera il QR Code in memoria
qrcode = segno.make_qr(url_progetto)

# Converte il QR code in un flusso di immagini PNG 
buffer = io.BytesIO()
qrcode.save(buffer, kind='png', scale=5, dark='#000000', light='#ffffff')

# Rendering su Streamlit
st.sidebar.image(buffer.getvalue(), caption="Inquadra per accedere alla web-app", use_container_width=True)

# Configurazione della pagina Streamlit 
st.set_page_config(
    page_title="Terna Digital Twin Sardegna - Proof of Concept",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- MOTORE DI CALCOLO DELLA SIMULAZIONE ---
minuti = np.arange(0, 121)
np.random.seed(42)

# Generazione profili meteo-dipendenti basati sugli input dello slider
wind_base = np.where(minuti < 20, 100, wind_peak)
eolico_mw = np.clip(wind_base + np.random.normal(0, 10, len(minuti)), 0, None)
solare_mw = np.clip(100 - (minuti * 1.2) + np.random.normal(0, 2, len(minuti)), 0, None)

# Scenario 0: No Redispatching (Il termico rimane rigido al valore scelto nello slider)
thermal_scen0 = np.ones(len(minuti)) * thermal_nominal
p_linea_scen0 = eolico_mw + solare_mw + thermal_scen0

# Scenario 1: Redispatching Semplice (Termico parte dal nominale e scende al minimo configurato al min 20)
thermal_scen1 = np.where(minuti < 20, thermal_nominal, thermal_min)
p_linea_scen1 = eolico_mw + solare_mw + thermal_scen1

# Scenario 2: Smart Grid Tech (Azione combinata BESS + HVDC Tyrrhenian Link)
# Al minuto 20 si attivano le batterie che assorbono potenza fino al loro limite di targa (sg_threshold)
bess_absorption = np.where(minuti < 20, 0, sg_threshold)

# La potenza residua sulla linea viene alleggerita dall'assorbimento BESS. 
# Il rimanente surplus viene preso in carico dall'HVDC verso il continente.
p_linea_scen2 = np.clip(p_linea_scen1 - bess_absorption, 0, None)

# Modello Dinamico di Integrazione Termica (Equazione del bilancio termico transitorio)
def calcola_temperatura_cavo(potenza_mw_vettore, T_ambient):
    V_linea = 380000  # 380 kV
    cos_phi = 0.9
    I_max = 1600.0    # Corrente limite nominale

    # Delta T di progetto: a pieno carico (I_max), il cavo si scalda di 60°C sopra la temperatura ambiente
    delta_T_max_joule = 60.0 
    tau = 20.0        # Costante di tempo termica (minuti)
    dt = 1.0
    
    corrente_ampere = (potenza_mw_vettore * 1e6) / (np.sqrt(3) * V_linea * cos_phi)
    
    # Temperatura iniziale (Stato stazionario al minuto 0)
    t_iniziale = T_ambient + ((corrente_ampere[0] / I_max) ** 2) * delta_T_max_joule
    t_cavo = [t_iniziale]
    
    for i in range(len(minuti) - 1):
        T_target = T_ambient + ((corrente_ampere[i] / I_max) ** 2) * delta_T_max_joule ## Il target è: Temperatura Ambiente + l'effetto Joule proporzionale al quadrato della corrente
        dT = (1.0 / tau) * (T_target - t_cavo[-1]) * dt # Equazione differenziale del transitorio termico
        t_cavo.append(t_cavo[-1] + dT + np.random.normal(0, 0.02))
    return t_cavo

t_scen0 = calcola_temperatura_cavo(p_linea_scen0, t_ambient)
t_scen1 = calcola_temperatura_cavo(p_linea_scen1, t_ambient)
t_scen2 = calcola_temperatura_cavo(p_linea_scen2, t_ambient)


# --- INTERFACCIA UTENTE A TAB ---
tab1, tab2, tab3 = st.tabs(["⚡Capacità di generazione - Sardegna", "🗺️ Mappa degli Asset", "📊 Simulazioni"])

# ==========================================
# TAB 1: CAPACITA' DI GENERAZIONE
# ==========================================
with tab1:
    #st.subheader("📊 Capacità di Generazione Regionale (Sardegna)")
    st.markdown("""
    Analisi della **Potenza Efficiente Lorda e Netta**.""") # I dati evidenziano il divario di autoconsumo delle centrali termoelettriche e la crescente quota di accumuli stand-alone

# 1. Definizione dei Dati Reali estratti dalla Dashboard Terna
    fonti = ['Eolico', 'Fotovoltaico', 'Termoelettrico', 'Idrico', 'Accumulo Stand-alone']
    potenza_lorda = [1193.52, 1722.09, 2395.47, 467.85, 63.90]
    potenza_netta = [1193.20, 1722.09, 2174.92, 463.42, 61.90]
    
    totale_lordo = sum(potenza_lorda)
    totale_netto = sum(potenza_netta)
    autoconsumo_totale = totale_lordo - totale_netto

# 2. KPI Summary Cards in alto
    kpi1, kpi2, kpi3 = st.columns(3)
  
    with kpi1:
        st.metric(label="Capacità Lorda Totale", value=f"{totale_lordo:,.2f} MW".replace(",", "."))
    with kpi2:
        st.metric(label="Capacità Netta Immissibile", value=f"{totale_netto:,.2f} MW".replace(",", "."), delta=f"-{autoconsumo_totale:.2f} MW Servizi Ausiliari", delta_color="inverse")
    with kpi3:
        quota_res = ((potenza_netta[0] + potenza_netta[1] + potenza_netta[3]) / totale_netto) * 100
        st.metric(label="Quota Rinnovabili (sul Netto)", value=f"{quota_res:.1f} %")

    st.markdown("---")

# 3. Creazione dei Grafici e Mappa su Layout a 3 Colonne (Proporzioni 4:4:3)
    grafico_col1, grafico_col2 = st.columns(2)

    with grafico_col1:
        st.subheader("Confronto Lordo vs Netta")
        
        fig_confronto = go.Figure()
        fig_confronto.add_trace(go.Bar(
            x=fonti, y=potenza_lorda, name='Lorda', marker_color='#1f77b4'
        ))
        fig_confronto.add_trace(go.Bar(
            x=fonti, y=potenza_netta, name='Netta', marker_color='#2ca02c'
        ))

        fig_confronto.update_layout(
            barmode='group',
            xaxis_title="Fonte",
            yaxis_title="Potenza [MW]",
            legend=dict(x=0.75, y=0.95, bgcolor='rgba(255,255,255,0.1)'),
            margin=dict(l=10, r=10, t=30, b=10),
            height=380
        )
        st.plotly_chart(fig_confronto, use_container_width=True)

    with grafico_col2:
        st.subheader("Mix Energetico (Netto)")
        
        fig_mix = go.Figure(data=[go.Pie(
            labels=fonti,
            values=potenza_netta,
            hole=.3,
            textinfo='percent', # Mostra solo la percentuale per non affollare il grafico
            marker=dict(colors=['#4CAF50', '#FFC107', '#FF5722', '#00BCD4', '#9C27B0'])
        )])

        fig_mix.update_layout(
            showlegend=True,
            legend=dict(orientation="h", y=-0.1, x=0), # Legenda orizzontale sotto il grafico
            margin=dict(l=10, r=10, t=30, b=10),
            height=380
        )
        st.plotly_chart(fig_mix, use_container_width=True)



# ==========================================
# TAB 2: MAPPA DEGLI ASSET
# ==========================================
with tab2:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📖 Il Contesto della Rete Sarda")
        st.markdown(f"""
        La simulazione analizza il comportamento della rete di trasmissione sarda durante una giornata caratterizzata dall'arrivo di un repentino fronte meteorologico nell'isola in concomitanza con il tramonto solare.        
        * **Lo shock eolico:** Con il tramonto, la produzione fotovoltaica si azzera bruscamente, ma l'arrivo simultaneo di una perturbazione comporta un'accelerazione del vento tale da comportare un picco di produzione eolica di **{wind_peak} MW**.
        * **Il Vincolo Fisico:** Per garantire la stabilità di tensione e l'inerzia elettrica, le centrali termoelettriche non possono essere spente del tutto ma devono mantenere una generazione minima (**{thermal_min} MW**).
        * **Il Problema:** La somma della generazione termica rigida e dell'esplosione eolica sovraccarica la dorsale di trasmissione a 380 kV in ingresso alla Stazione elettrica di Selargius.
        * **Il Limite dell'Accumulo Stand Alone:** La Sardegna dispone di un comparto di accumulo stand alone (BESS) che, sebbene in forte crescita, è limitato a una capacità operativa netta di **{sg_threshold} MW**. Davanti a un surplus energetico imprevisto, le batterie reali possono saturare la loro capacità di assorbimento in pochi minuti, risultando da sole insufficienti a contenere la congestione.
        * **La Soluzione di Rete - il Tyrrhenian Link:** In corrispondenza della stazione elettrica di Selargius, l'energia in eccesso viene governata e deviata sul nuovo elettrodotto sottomarino **HVDC Tyrrhenian Link** per essere esportata verso la Sicilia e la Campania, decongestionando l'isola e garantendo la stabilità della rete elettrica.
        """)
        
        

    with col2:
        st.subheader("🗺️ Visualizzazione della rete elettrica")
        
        # Dizionario Geografico delle infrastrutture coinvolte
        data_asset = {
            'Sito': ['Stazione elettrica Selargius', 'Terra Mala (Cagliari)','Fiumetorto (Termini Imerese)', 'Torre Tuscia Magazzeno (Battipaglia)'],
            'Lat': [39.2600, 39.1961085, 37.9725134, 40.569476],
            'Lon': [9.1600, 9.3295586, 13.7556869, 14.8238343],
            'Tipo': ['Hub di Controllo & Stazione', 'Nodo di Esportazione','Hub di Importazione ed Esportazione','Hub di Importazione ed Esportazione'],
            'Dimensioni': [20, 10, 20, 20]
        }
        df_asset = pd.DataFrame(data_asset)

        # Creazione Mappa GIS Interattiva con Plotly Mapbox (Stile Open-Street-Map nativo)
        fig_map = go.Figure()

        # Linea 1: Dorsale Sarda Nord-Sud 
        fig_map.add_trace(go.Scattermapbox(
            lat=[40.8400, 39.2600], lon=[8.3200, 9.1600],
            mode='lines+markers',
            line=dict(width=4, color='#ff7f0e'),
            name='Dorsale Elettrica 380 kV',
            hoverinfo='text',
            text='Dorsale Principale di Trasmissione Sarda (Soggetta a Sovraccarico Termico)'
        ))
        
        # Linea 2: Elettrodotto HVDC Tyrrhenian link
        fig_map.add_trace(go.Scattermapbox(
            lat=[39.2600, 39.1961085, 37.9725134, 40.569476], lon=[9.1600, 9.3295586, 13.7556869, 14.8238343],
            mode='lines',
            line=dict(width=4, color='#2ca02c'), 
            name='Tyrrhenian Link',
            hoverinfo='text',
            text='Collegamento in Corrente Continua'
        ))

        # Aggiunta dei nodi puntuali sulla mappa
        fig_map.add_trace(go.Scattermapbox(
            lat=df_asset['Lat'], lon=df_asset['Lon'],
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=df_asset['Dimensioni'],
                color=['#d62728', '#d62728', '#d62728','#d62728'],
                opacity=0.9
            ),
            text=df_asset['Sito'] + "<br>" + df_asset['Tipo'],
            hoverinfo='text',
            name='Infrastrutture Chiave'
        ))

        # Impostazioni Layout Mappa (Tema scuro per perfetto contrasto con la legenda)
        fig_map.update_layout(
            mapbox=dict(
                style="open-street-map", # Cambiato in tema scuro nativo
                center=dict(lat=40.2, lon=10.5),
                zoom=5.5
            ),
            margin=dict(l=0, r=0, t=0, b=0),
            height=450,
            showlegend=True,
            # NUOVA LEGENDA TRASPARENTE: Sfrutta lo sfondo scuro per far risaltare il testo bianco di Streamlit
            legend=dict(
                x=0.02,
                y=0.98,
                xanchor="left",
                yanchor="top",
                bgcolor="rgba(0, 0, 0, 0)", # Completamente trasparente
                font=dict(color="blue")     
            )
        )
        
        st.plotly_chart(fig_map, use_container_width=True)

# ==========================================
# TAB 3: SIMULAZIONI
# ==========================================
with tab3:
    st.subheader("📊 Analisi Comparativa degli Scenari Operativi")
    st.markdown("""
    Visualizzazione in tempo reale dei flussi di potenza sulla dorsale interna a 380 kV e del profilo termico del conduttore. 
    L'azione combinata dei sistemi di stoccaggio energetico e del cavo sottomarino previene il superamento della temperatura critica.
    """)
    
    # Creazione della Dashboard a due livelli con distanze corrette
    fig_dash = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.15,
        subplot_titles=(
            "<b>1. Transito di Potenza Complessivo sulla Dorsale 380 kV (MW)</b>", 
            "<b>2. Dinamica della Temperatura del Conduttore (°C)</b>"
        )
    )

    # --- GRAFICO 1: FLUSSI DI POTENZA ---
    fig_dash.add_trace(go.Scatter(x=minuti, y=p_linea_scen0, name="Livello 0: No Redispatching (Termico Rigido)", line=dict(color='#E30613', width=2, dash='dot')), row=1, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=p_linea_scen1, name="Livello 1: Redispatch Semplice (Termico al Minimo)", line=dict(color='#ff7f0e', width=2)), row=1, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=p_linea_scen2, name="Livello 2: Smart Grid Tech (Peak Shaving BESS + Tyrrhenian Link)", line=dict(color='#2ca02c', width=3)), row=1, col=1)

    # --- GRAFICO 2: TEMPERATURE CAVO ---
    fig_dash.add_trace(go.Scatter(x=minuti, y=t_scen0, name="Temp - No Redispatching", line=dict(color='#E30613', width=2, dash='dot'), showlegend=False), row=2, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=t_scen1, name="Temp - Redispatch Semplice", line=dict(color='#ff7f0e', width=2), showlegend=False), row=2, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=t_scen2, name="Temp - Smart Grid Tech", line=dict(color='#2ca02c', width=3.5), showlegend=False), row=2, col=1)

    # Linea limite di sicurezza normativa CEI
    fig_dash.add_hline(y=75.0, line_dash="dash", line_color="magenta", line_width=2,
                        annotation_text="Limite CEI EN 50341 (75°C)", annotation_position="top left", row=2, col=1)

    # Ottimizzazione del Layout
    fig_dash.update_layout(
        margin=dict(t=60, b=40, l=60, r=40),
        height=650, 
        template="plotly_white", 
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
    )

    fig_dash.update_xaxes(title_text="Tempo (Minuti)", row=2, col=1)
    fig_dash.update_yaxes(title_text="Potenza [MW]", row=1, col=1)
    fig_dash.update_yaxes(title_text="Temperatura [°C]", row=2, col=1)

    # Rendering del grafico interattivo all'interno di Streamlit
    st.plotly_chart(fig_dash, use_container_width=True)
    
    # Sottoregistro dei dati di sintesi dinamici sotto il grafico
    st.markdown("### 📋 Indicatori di Performance Energetica (KPI) estratti in tempo reale:")
    kpi1, kpi2, kpi3 = st.columns(3)
    
    with kpi1:
        st.metric(
            label="Temperatura Max (No Redispatch)", 
            value=f"{max(t_scen0):.1f} °C", 
            delta=f"+{max(t_scen0)-75.0:.1f} °C sopra il limite" if max(t_scen0) > 75 else "Sicuro", 
            delta_color="inverse" if max(t_scen0) > 75 else "normal"
        )
    with kpi2:
        st.metric(
            label="Temperatura Max (Redispatch Semplice)", 
            value=f"{max(t_scen1):.1f} °C", 
            delta=f"+{max(t_scen1)-75.0:.1f} °C sopra il limite" if max(t_scen1) > 75 else "Sicuro",
            delta_color="inverse" if max(t_scen1) > 75 else "normal"
        )
    with kpi3:
        st.metric(
            label="Temperatura Max (Tyrrhenian link)", 
            value=f"{max(t_scen2):.1f} °C", 
            delta=f"-{75.0-max(t_scen2):.1f} °C sotto il limite" if max(t_scen2) < 75 else f"+{max(t_scen2)-75.0:.1f} °C sopra il limite", 
            delta_color="inverse" if max(t_scen2) > 75 else "off"
        )

    st.markdown("---")
    
    # Monitoraggio dinamico dello stato della sicurezza
    if max(t_scen0) > 75.0 or max(t_scen1) > 75.0:
        st.error(f"""
        ⚠️ **Rilevato Criticità Termica di Rete:** Nello Scenario 0 (e potenzialmente nello Scenario 1), l'energia eolica immessa supera la capacità di trasporto (*Ampacity*) dei conduttori a 380 kV diretti a Selargius. 
        Il superamento dei 75°C normativi CEI comporta una dilatazione termica del cavo con pericolosa riduzione delle franchigie dal suolo (rischio di scarica elettrica a terra).
        """)
        
    if max(t_scen2) <= 75.0:
        st.success(f"""
        ✅ **Stabilità Garantita (Scenario 2):** L'attivazione tempestiva dei {sg_threshold} MW di accumulo BESS coordinati dalla sottostazione intelligente di Selargius riduce istantaneamente il picco termico. 
        L'energia eccedente viene instradata in corrente continua sul **Tyrrhenian Link**, mantenendo la temperatura del cavo a un picco massimo di {max(t_scen2):.1f}°C, pienamente entro i margini di sicurezza.
        """)
