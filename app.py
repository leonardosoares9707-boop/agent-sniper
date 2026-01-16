import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import plotly.graph_objects as go
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="A.G.E.N.T. Sniper", layout="wide", page_icon="🦁")

# Estilo Dark Mode Forçado
st.markdown("""
<style>
    .stApp {background-color: #0e1117; color: white;}
    div[data-testid="stMetricValue"] {font-size: 18px;}
    h1 {color: #00FF00;}
</style>
""", unsafe_allow_html=True)

st.title("🦁 A.G.E.N.T. - Monitoramento Ao Vivo")

# --- BARRA LATERAL ---
st.sidebar.header("Painel de Comando")
ativos = st.sidebar.multiselect(
    "Ativos Monitorados", 
    ['BTC-USD', 'ETH-USD', 'SOL-USD', 'EURUSD=X', 'GC=F'],
    default=['BTC-USD', 'EURUSD=X']
)

# Botão de Auto-Atualização
auto_refresh = st.sidebar.checkbox("Atualizar Automaticamente (60s)", value=False)

if st.sidebar.button("🔄 Atualizar Agora"):
    st.cache_data.clear()

# --- FUNÇÕES ---
@st.cache_data(ttl=60) # Cache de 60 segundos para não travar
def pegar_dados(simbolo):
    try:
        df = yf.download(simbolo, period="3mo", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return df if len(df) > 30 else None
    except: return None

def calcular_sniper(df):
    # Identifica Topos e Fundos (Fractais)
    n = 5
    df['Min'] = df.iloc[argrelextrema(df['Low'].values, np.less_equal, order=n)[0]]['Low']
    df['Max'] = df.iloc[argrelextrema(df['High'].values, np.greater_equal, order=n)[0]]['High']
    fundos = df[df['Min'].notna()]['Low'].values
    topos = df[df['Max'].notna()]['High'].values
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return topos, fundos, rsi

# --- PAINEL PRINCIPAL ---
if not ativos:
    st.warning("Selecione pelo menos um ativo na barra lateral.")
else:
    # 1. TABELA DE PROBABILIDADE
    st.subheader("📡 Radar de Probabilidade")
    relatorio = []
    
    for ativo in ativos:
        df = pegar_dados(ativo)
        if df is not None:
            topos, fundos, rsi = calcular_sniper(df)
            atual = df.iloc[-1]
            
            # Score
            score = 50
            motivo = "Neutro"
            perto_suporte = any(abs(atual['Low'] - z)/z <= 0.02 for z in fundos)
            perto_resistencia = any(abs(atual['High'] - z)/z <= 0.02 for z in topos)
            
            rsi_val = rsi.iloc[-1]
            
            if perto_suporte:
                motivo = "Suporte"
                if rsi_val < 30: score += 30; motivo += " + RSI Baixo (Oportunidade)"
                else: score += 10
            elif perto_resistencia:
                motivo = "Resistência"
                if rsi_val > 70: score -= 30; motivo += " + RSI Alto (Perigo)"
                else: score -= 10
                
            cor = "🔴" if score < 40 else "🟢" if score > 60 else "🟡"
            
            relatorio.append({
                "Ativo": ativo,
                "Preço": f"{atual['Close']:.2f}",
                "RSI": f"{rsi_val:.0f}",
                "Sinal": f"{cor} {motivo}",
                "Score": score
            })
            
    if relatorio:
        st.dataframe(pd.DataFrame(relatorio).style.format({"Score": "{:.0f}"}), use_container_width=True)

    st.markdown("---")

    # 2. GRÁFICO SNIPER DETALHADO
    ativo_grafico = st.selectbox("Escolha um ativo para ver o Gráfico Sniper:", ativos)
    
    if ativo_grafico:
        df_chart = pegar_dados(ativo_grafico)
        if df_chart is not None:
            df_chart.reset_index(inplace=True)
            col_data = 'Date' if 'Date' in df_chart.columns else 'Datetime'
            
            topos, fundos, _ = calcular_sniper(df_chart)
            
            # Lógica dos Triângulos Sniper
            sniper_compra_x, sniper_compra_y = [], []
            sniper_venda_x, sniper_venda_y = [], []
            
            for i in range(1, len(df_chart)):
                curr = df_chart.iloc[i]; prev = df_chart.iloc[i-1]
                
                # Engolfos
                engolfo_alta = (curr['Close'] > curr['Open'] and prev['Close'] < prev['Open'] and curr['Open'] < prev['Close'] and curr['Close'] > prev['Open'])
                engolfo_baixa = (curr['Close'] < curr['Open'] and prev['Close'] > prev['Open'] and curr['Open'] > prev['Close'] and curr['Close'] < prev['Open'])
                
                # Filtro de Zona
                if engolfo_alta and any(abs(curr['Low'] - z)/z <= 0.02 for z in fundos):
                    sniper_compra_x.append(curr[col_data]); sniper_compra_y.append(curr['Low'])
                if engolfo_baixa and any(abs(curr['High'] - z)/z <= 0.02 for z in topos):
                    sniper_venda_x.append(curr[col_data]); sniper_venda_y.append(curr['High'])

            # Plot
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df_chart[col_data], open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Preço'))
            
            # Marcadores
            fig.add_trace(go.Scatter(x=sniper_compra_x, y=sniper_compra_y, mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00FF00'), name='COMPRA SNIPER'))
            fig.add_trace(go.Scatter(x=sniper_venda_x, y=sniper_venda_y, mode='markers', marker=dict(symbol='triangle-down', size=15, color='#FF0000'), name='VENDA SNIPER'))
            
            fig.update_layout(title=f"Gráfico Sniper: {ativo_grafico}", template="plotly_dark", height=500, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

# Lógica de Auto-Refresh (Truque para manter vivo)
if auto_refresh:
    time.sleep(60)
    st.rerun()
