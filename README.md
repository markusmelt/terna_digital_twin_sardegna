# Simulatore del transitorio termico – dorsale 380 kV Sardegna

PoC dimostrativo: una rampa eolica serale carica la dorsale; il modello mostra in quanto tempo il conduttore supera 85 °C
e cosa cambia con termico al minimo, BESS e Tyrrhenian Link (a regime), incluso il costo in curtailment.

- Modello: primo ordine, integrazione esatta per passo (`model.py`), calibrato a 85 °C a 1600 A / 25 °C.
- Limiti: niente flusso di carico, N-1, tensioni, inerzia; dorsale come elemento unico; BESS con durata assunta.
- Non affiliato a Terna S.p.A.; dati di capacità da fonti pubbliche.

Avvio: `pip install -r requirements.txt && streamlit run app.py`
