"""
Cœur du business case — modélisation financière, réutilisée par
business_case.py (rapport) et app.py (Streamlit interactif).

Décision étudiée : faut-il investir dans un dispositif anti-annulation de
commande (retry de paiement en temps réel + pré-vérification anti-fraude +
réservation de stock au checkout) ? Le taux d'annulation réel de la base du
Projet 07 (7,18 %, mesuré ci-dessous, pas inventé) est le point de départ.

Aucune dépendance externe pour le calcul financier (pas de numpy-financial) :
NPV = somme actualisée, IRR = recherche de racine par bissection sur NPV(r).
"""
import os
from dataclasses import dataclass

import psycopg2

DSN = os.environ.get("DATABASE_URL",
                      "postgresql://portfolio:portfolio@127.0.0.1:5433/ecommerce")


@dataclass
class Baseline:
    """Mesuré en base (Projet 07) — pas une hypothèse."""
    annual_orders: float
    cancellation_rate: float
    avg_value_cancelled: float
    is_live: bool = True       # False = instantané de repli (base non joignable)
    snapshot_date: str = ""    # renseigné seulement quand is_live=False


# Instantané figé des 3 chiffres mesurés le 2026-08-28 (voir README) — sert
# de repli quand la base du Projet 07 n'est pas joignable (ex. démo publique
# Streamlit Cloud : elle ne peut pas atteindre le Postgres local en Docker).
# En local, avec la base lancée, fetch_baseline() interroge toujours le vrai
# Postgres — ce repli n'est qu'un filet pour l'environnement de démo.
SNAPSHOT = Baseline(
    annual_orders=19_232.0,
    cancellation_rate=0.0718,
    avg_value_cancelled=1_787.57,
    is_live=False,
    snapshot_date="2026-08-28",
)


def fetch_baseline() -> Baseline:
    try:
        conn = psycopg2.connect(DSN, connect_timeout=3)
    except psycopg2.OperationalError:
        return SNAPSHOT

    cur = conn.cursor()
    cur.execute("""
        SELECT count(*), count(*) FILTER (WHERE status = 'cancelled'),
               count(DISTINCT date_trunc('month', order_date))
        FROM orders
        WHERE date_trunc('month', order_date) < date_trunc('month', now())
    """)
    nb_orders, nb_cancelled, nb_months = cur.fetchone()
    cur.execute("""
        SELECT avg(rev) FROM (
            SELECT sum(oi.quantity * oi.unit_price) AS rev
            FROM order_item oi JOIN orders o ON o.id = oi.order_id
            WHERE o.status = 'cancelled'
            GROUP BY oi.order_id
        ) t
    """)
    avg_value_cancelled = float(cur.fetchone()[0])
    cur.close(); conn.close()

    return Baseline(
        annual_orders=nb_orders / nb_months * 12,
        cancellation_rate=nb_cancelled / nb_orders,
        avg_value_cancelled=avg_value_cancelled,
    )


@dataclass
class Assumptions:
    """Le jugement business du memo — tout est ici, rien de caché ailleurs."""
    reduction_pts: float = 0.02        # points de taux d'annulation récupérés (7,18% -> 5,18%)
    gross_margin_pct: float = 0.25     # marge brute (non présente dans le schéma OLTP)
    investment_cost: float = 120_000.0  # implémentation + intégration paiement + formation, année 0
    annual_program_cost: float = 60_000.0  # licence anti-fraude + ~0,3 ETP exploitation, années 1..N
    discount_rate: float = 0.10        # taux d'actualisation (coût du capital assumé)
    horizon_years: int = 3
    ramp_up: tuple = (0.4, 0.8, 1.0)   # montée en charge : 40% l'année 1, pleine efficacité en année 3


@dataclass
class Result:
    cash_flows: list          # [CF0, CF1, ..., CFn] non actualisés
    npv: float
    irr: float | None
    payback_years: float | None


def cash_flows(base: Baseline, a: Assumptions) -> list:
    recovered_orders = base.annual_orders * a.reduction_pts
    incremental_margin = recovered_orders * base.avg_value_cancelled * a.gross_margin_pct
    flows = [-a.investment_cost]
    for year in range(a.horizon_years):
        ramp = a.ramp_up[year] if year < len(a.ramp_up) else 1.0
        flows.append(incremental_margin * ramp - a.annual_program_cost)
    return flows


def npv(flows: list, rate: float) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))


def irr(flows: list, lo: float = -0.99, hi: float = 5.0, tol: float = 1e-7) -> float | None:
    """Bissection sur NPV(r) = 0. None si aucune racine dans [lo, hi]
    (flux constamment positif ou négatif — pas de taux d'équilibre)."""
    f_lo, f_hi = npv(flows, lo), npv(flows, hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(flows, mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def payback_period(flows: list) -> float | None:
    """Délai de récupération non actualisé, en années (interpolé)."""
    cumulative = flows[0]
    if cumulative >= 0:
        return 0.0
    for year, cf in enumerate(flows[1:], start=1):
        prev = cumulative
        cumulative += cf
        if cumulative >= 0:
            return year - 1 + (-prev / cf if cf else 0)
    return None


def evaluate(base: Baseline, a: Assumptions) -> Result:
    flows = cash_flows(base, a)
    return Result(
        cash_flows=flows,
        npv=npv(flows, a.discount_rate),
        irr=irr(flows),
        payback_years=payback_period(flows),
    )


def self_check(base: Baseline, a: Assumptions) -> None:
    """Un `assert` par invariant financier — pas de chiffre publié sans preuve."""
    flows = cash_flows(base, a)
    assert abs(npv(flows, 0.0) - sum(flows)) < 1e-6, "NPV à taux 0% doit égaler la somme brute des flux"
    r = irr(flows)
    if r is not None:
        assert abs(npv(flows, r)) < 1e-3, "NPV(IRR) doit être ~0 par définition de l'IRR"
    pb = payback_period(flows)
    if pb is not None and pb > 0:
        cumulative = sum(flows[:int(pb) + 2])  # cumul jusqu'à la fin de l'année où le seuil est franchi
        assert cumulative >= -1e-6, "Le cumul à l'année de payback doit être >= 0"


if __name__ == "__main__":
    b = fetch_baseline()
    self_check(b, Assumptions())
    r = evaluate(b, Assumptions())
    origin = "mesuré en direct" if b.is_live else f"instantané de repli du {b.snapshot_date} (base non joignable)"
    print(f"Baseline ({origin}) : {b.annual_orders:,.0f} commandes/an, "
          f"{b.cancellation_rate:.2%} d'annulation, "
          f"valeur moy. commande annulée {b.avg_value_cancelled:,.0f} €")
    print(f"NPV {r.npv:,.0f} € · IRR {r.irr:.1%} · payback {r.payback_years:.1f} ans"
          if r.irr is not None else f"NPV {r.npv:,.0f} € · IRR indéfini · payback {r.payback_years}")
