"""
Explorateur interactif du business case — ajuste les hypothèses, regarde
NPV/IRR/payback bouger en direct.

Usage : streamlit run src/app.py
"""
import streamlit as st

from model import Assumptions, evaluate, fetch_baseline

st.set_page_config(page_title="Business case — anti-annulation", page_icon="💼", layout="centered")

PETROL = "#137A8B"

st.title("💼 Business case — dispositif anti-annulation de commande")
st.caption("Investir pour réduire le taux d'annulation mesuré sur la base du Projet 07 : "
           "ajuste les hypothèses ci-dessous, le résultat se recalcule en direct.")


@st.cache_data
def load_baseline():
    return fetch_baseline()


base = load_baseline()

if not base.is_live:
    st.info(f"Base Postgres non joignable depuis cette démo publique — constat figé sur "
            f"l'instantané mesuré le {base.snapshot_date} (voir README). En local, avec la base "
            f"du Projet 07 lancée, ces chiffres sont recalculés en direct.", icon="📸")

st.subheader("Constat mesuré (base réelle)")
c1, c2, c3 = st.columns(3)
c1.metric("Commandes / an", f"{base.annual_orders:,.0f}")
c2.metric("Taux d'annulation", f"{base.cancellation_rate:.1%}")
c3.metric("Valeur moy. commande annulée", f"{base.avg_value_cancelled:,.0f} €")

st.subheader("Hypothèses")
col1, col2 = st.columns(2)
with col1:
    reduction_pts = st.slider("Points d'annulation récupérés", 0.0, 5.0, 2.0, 0.1) / 100
    gross_margin_pct = st.slider("Marge brute", 10, 45, 25, 1) / 100
    discount_rate = st.slider("Taux d'actualisation", 2, 20, 10, 1) / 100
with col2:
    investment_cost = st.number_input("Investissement initial (€)", 0, 500_000, 120_000, 5_000)
    annual_program_cost = st.number_input("Coût annuel du dispositif (€)", 0, 200_000, 60_000, 5_000)
    horizon_years = st.slider("Horizon (années)", 1, 5, 3, 1)

a = Assumptions(reduction_pts=reduction_pts, gross_margin_pct=gross_margin_pct,
                investment_cost=investment_cost, annual_program_cost=annual_program_cost,
                discount_rate=discount_rate, horizon_years=horizon_years,
                ramp_up=(0.4, 0.8, 1.0, 1.0, 1.0)[:horizon_years])

result = evaluate(base, a)

st.subheader("Résultat")
c1, c2, c3 = st.columns(3)
c1.metric("NPV (VAN)", f"{result.npv:,.0f} €", delta="Favorable" if result.npv > 0 else "Défavorable")
c2.metric("IRR (TRI)", f"{result.irr:.1%}" if result.irr is not None else "indéfini")
c3.metric("Payback", f"{result.payback_years:.1f} ans" if result.payback_years is not None else "> horizon")

st.bar_chart({"Flux net (€)": result.cash_flows})

st.caption("Méthode et hypothèses détaillées dans le README et `docs/memo_decision.md`.")
