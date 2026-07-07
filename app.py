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
st.sidebar.markdown("Modifica i vincoli fisici e tecnologici per testare la resilienza del sistema elettrico:")

# Slider dinamici per il colloquio
wind_peak = st.sidebar.slider("Picco della Rampa Eolica (MW)", min_value=600, max_value=1300, value=1000, step=50)
thermal_min = st.sidebar.slider("Minimo Tecnico Centrale Termica (MW)", min_value=100, max_value=300, value=150, step=25)
sg_threshold = st.sidebar.slider("Soglia di Sicurezza Smart Grid / BESS (MW)", min_value=700, max_value=950, value=850, step=25)

st.sidebar.markdown("---")
st.sidebar.info("""💡 **Info:** Aumentando la produzione eolica il 'Redispatch Semplice' fallisce rendendo obbligatorio l'uso delle tecnologie Smart Grid.""")

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

# Scenario 0: No Redispatching
thermal_scen0 = np.ones(len(minuti)) * 350
p_linea_scen0 = eolico_mw + solare_mw + thermal_scen0

# Scenario 1: Redispatching Semplice (Termico scende al minimo configurato al min 20)
thermal_scen1 = np.where(minuti < 20, 350, thermal_min)
p_linea_scen1 = eolico_mw + solare_mw + thermal_scen1

# Scenario 2: Smart Grid (Peak Shaving basato sulla soglia configurata)
p_linea_scen2 = np.minimum(p_linea_scen1, sg_threshold)

# Modello Dinamico di Integrazione Termica
def calcola_temperatura_cavo(potenza_mw_vettore):
    V_linea = 380000  # 380 kV
    cos_phi = 0.9
    I_max = 1600.0    # Corrente limite nominale
    T_ambient = 25.0
    T_max = 85.0
    tau = 20.0        # Costante di tempo termica (minuti)
    dt = 1.0
    
    corrente_ampere = (potenza_mw_vettore * 1e6) / (np.sqrt(3) * V_linea * cos_phi)
    t_cavo = [T_ambient + (corrente_ampere[0]/I_max)**2 * (T_max - T_ambient)]
    
    for i in range(len(minuti) - 1):
        T_target = T_ambient + (corrente_ampere[i] / I_max)**2 * (T_max - T_ambient)
        dT = (1.0 / tau) * (T_target - t_cavo[-1]) * dt
        t_cavo.append(t_cavo[-1] + dT + np.random.normal(0, 0.02))
    return t_cavo

t_scen0 = calcola_temperatura_cavo(p_linea_scen0)
t_scen1 = calcola_temperatura_cavo(p_linea_scen1)
t_scen2 = calcola_temperatura_cavo(p_linea_scen2)


# --- INTERFACCIA UTENTE A TAB ---
tab1, tab2, tab3 = st.tabs(["⚡Capacità di generazione - Sardegna", "🗺️ Mappa degli Asset", "📊 Simulazioni"])

# ==========================================
# TAB 1: CAPACITA' DI GENERAZIONE
# ==========================================
with tab1:
    #st.subheader("📊 Capacità di Generazione Regionale (Sardegna)")
    st.markdown("""
    Analisi della **Potenza Efficiente Lorda e Netta** censita sul territorio sardo.""") # I dati evidenziano il divario di autoconsumo delle centrali termoelettriche e la crescente quota di accumuli stand-alone

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
            legend=dict(x=1.5, y=0.95, bgcolor='rgba(255,255,255,0.1)'),
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
        La simulazione analizza l'asse elettrico Nord-Sud della Sardegna durante una giornata caratterizzata da un improvviso fronte di vento nel Nord dell'isola (+{wind_peak} MW) in concomitanza con il tramonto solare.
        
        * **Il Vincolo Fisico:** Le centrali tradizionali del Nord (es. Fiume Santo) e del Sud (es. Sulcis) devono mantenere una generazione minima (**{thermal_min} MW**) per garantire la stabilità della tensione e della frequenza (Inerzia di rete).
        * **Il Problema:** La somma della generazione termica rigida e dell'esplosione eolica sovraccarica la dorsale di trasmissione a 380 kV.
        * **Il Centro del Nodo Tecno-Geografico:** La **Stazione Elettrica di Selargius (CA)**. È qui che l'energia in eccesso viene governata attraverso i Compensatori Sincroni (inerzia artificiale) e deviata sull'elettrodotto sottomarino **SA.PE.I.** per essere esportata in corrente continua verso il Lazio, salvando la stabilità isolana.
        """)
        
        st.info("📌 *Usa la mappa a destra per esplorare visivamente il tragitto dell'energia dai centri di produzione eolici del Nord fino all'hub tecnologico di Selargius e al Continente.*")

    with col2:
        st.subheader("🗺️ Visualizzazione GIS degli Asset Terna")
        
        # Dizionario Geografico delle infrastrutture coinvolte
        data_asset = {
            'Sito': ['Hub Eolico / Fiume Santo', 'Nodo Strategico Selargius', 'Terminale SA.PE.I. Lazio'],
            'Lat': [40.8400, 39.2600, 41.4800],
            'Lon': [8.3200, 9.1600, 12.8800],
            'Tipo': ['Produzione (Nord)', 'Hub di Controllo & Stazione (Sud)', 'Esportazione (Continente)'],
            'Dimensioni': [20, 25, 15]
        }
        df_asset = pd.DataFrame(data_asset)

        # Creazione Mappa GIS Interattiva con Plotly Mapbox (Stile Open-Street-Map nativo)
        fig_map = go.Figure()

        # Linea 1: Dorsale Sarda Nord-Sud (CORRETTA la chiusura delle parentesi)
        fig_map.add_trace(go.Scattermapbox(
            lat=[40.8400, 39.2600], lon=[8.3200, 9.1600],
            mode='lines+markers',
            line=dict(width=4, color='#ff7f0e'),
            name='Dorsale Elettrica 380 kV',
            hoverinfo='text',
            text='Dorsale Principale di Trasmissione Sarda (Soggetta a Sovraccarico Termico)'
        ))
        
        # Linea 2: Elettrodotto HVDC SA.PE.I. (Selargius -> Lazio)
        fig_map.add_trace(go.Scattermapbox(
            lat=[39.2600, 41.4800], lon=[9.1600, 12.8800],
            mode='lines',
            line=dict(width=4, color='#2ca02c'), 
            name='Elettrodotto Sottomarino HVDC SA.PE.I.',
            hoverinfo='text',
            text='Collegamento in Corrente Continua (Esportazione Eccedenze Verde)'
        ))

        # Aggiunta dei nodi puntuali sulla mappa
        fig_map.add_trace(go.Scattermapbox(
            lat=df_asset['Lat'], lon=df_asset['Lon'],
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=df_asset['Dimensioni'],
                color=['#d62728', '#1f77b4', '#7f7f7f'],
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
    fig_dash.add_trace(go.Scatter(x=minuti, y=p_linea_scen0, name="Livello 0: No Redispatching (Termico Rigido)", line=dict(color='#d62728', width=2, dash='dot')), row=1, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=p_linea_scen1, name="Livello 1: Redispatch Semplice (Termico al Minimo)", line=dict(color='#ff7f0e', width=2)), row=1, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=p_linea_scen2, name="Livello 2: Smart Grid Tech (Peak Shaving BESS/HVDC)", line=dict(color='#2ca02c', width=3)), row=1, col=1)

    # --- GRAFICO 2: TEMPERATURE CAVO ---
    fig_dash.add_trace(go.Scatter(x=minuti, y=t_scen0, name="Temp - No Redispatching", line=dict(color='#d62728', width=2, dash='dot'), showlegend=False), row=2, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=t_scen1, name="Temp - Redispatch Semplice", line=dict(color='#ff7f0e', width=2), showlegend=False), row=2, col=1)
    fig_dash.add_trace(go.Scatter(x=minuti, y=t_scen2, name="Temp - Smart Grid Tech", line=dict(color='#2ca02c', width=3.5), showlegend=False), row=2, col=1)

    # Linea limite di sicurezza normativa CEI
    fig_dash.add_hline(y=75.0, line_dash="dash", line_color="black", line_width=2,
                  annotation_text="Limite CEI EN 50341 (75°C)", annotation_position="bottom left", row=2, col=1)

    # Ottimizzazione del Layout per eliminare i problemi di sovrapposizione visiva
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
            delta=f"+{max(t_scen0)-75.0:.1f} °C sopra il limite", 
            delta_color="inverse"
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
            label="Temperatura Max (Smart Grid Tech)", 
            value=f"{max(t_scen2):.1f} °C", 
            delta=f"-{75.0-max(t_scen2):.1f} °C sotto il limite", 
            delta_color="off"
        )
