# Mémo de décision — Dispositif anti-annulation de commande

**À** : Comité d'investissement | **De** : Analyse business & données | **Sujet** : Faut-il investir dans un dispositif de retry de paiement + pré-vérification anti-fraude + réservation de stock au checkout ?

## 1. Constat

**7,18 % des commandes sont annulées** (2 761 sur 38 463, mesuré sur 24 mois
complets de la base opérationnelle). La commande annulée moyenne vaut
**1 788 €** — sur ~19 200 commandes/an, c'est un flux de valeur perdue non
négligeable, avant même de parler de coût d'acquisition client gâché.

Ce n'est pas une hypothèse : c'est une requête sur la base réelle (voir
`src/model.py::fetch_baseline`).

## 2. Proposition

Un dispositif technique à trois volets, réduisant une partie des annulations :
retry automatique en cas d'échec de paiement, pré-vérification anti-fraude
avant validation, réservation de stock dès le checkout (évite l'annulation
"rupture" au moment du paiement).

## 3. Chiffrage (cas de base)

| Hypothèse | Valeur | Origine |
|---|---:|---|
| Points d'annulation récupérés | 2,0 pt (7,18 % → 5,18 %) | Hypothèse, dans la fourchette basse d'un bench sectoriel |
| Marge brute | 25 % | Hypothèse (non présente dans le schéma OLTP) |
| Investissement initial | 120 000 € | Implémentation + intégration paiement + formation |
| Coût annuel du dispositif | 60 000 € | Licence anti-fraude + ~0,3 ETP exploitation |
| Taux d'actualisation | 10 % | Coût du capital assumé |
| Horizon | 3 ans, montée en charge 40 % / 80 % / 100 % | Déploiement progressif réaliste |

**Résultat** : **NPV +36 081 €**, **IRR 22,4 %**, **payback 2,3 ans**.

Positif, mais pas confortablement — c'est un dossier qui mérite une
sensibilité avant d'engager le budget, pas une évidence.

## 4. Sensibilité — le vrai enjeu de la décision

| Réduction annulation \ Marge | 15 % | 20 % | 25 % | 30 % | 35 % |
|---|---:|---:|---:|---:|---:|
| 0,5 pt | -223 k€ | -208 k€ | -193 k€ | -178 k€ | -162 k€ |
| 1,0 pt | -178 k€ | -147 k€ | -117 k€ | -86 k€ | -56 k€ |
| 1,5 pt | -132 k€ | -86 k€ | -40 k€ | **+6 k€** | +51 k€ |
| **2,0 pt** | -86 k€ | -25 k€ | **+36 k€** | +97 k€ | +158 k€ |
| 2,5 pt | -40 k€ | +36 k€ | +112 k€ | +189 k€ | +265 k€ |
| 3,0 pt | +6 k€ | +97 k€ | +189 k€ | +280 k€ | +372 k€ |

**Le point de bascule est net** : en dessous de **~1,5 point** de réduction
d'annulation (à marge 25 %), le projet détruit de la valeur. Le cas de base
(2,0 pt) n'a qu'une marge de sécurité d'environ **0,5 point** avant de
repasser négatif.

## 5. Recommandation

**Go conditionnel, pas un feu vert inconditionnel.** Avant d'engager les
120 k€ :

1. **Exiger une preuve contractuelle** du fournisseur anti-fraude sur le
   taux de réduction attendu (SLA ou clause de performance), pas une
   promesse commerciale — la sensibilité montre que le projet ne supporte
   pas une sur-estimation de plus de 0,5 point.
2. **Piloter un test A/B sur un sous-périmètre** (ex. une catégorie ou une
   zone) avant le déploiement complet, pour mesurer la réduction réelle
   avant d'engager le coût annuel plein (60 k€) sur toute la base.
3. Si le test confirme ≥ 2 points de réduction à marge ≥ 25 %, déployer :
   le dossier devient alors confortablement positif (NPV > 100 k€ dès
   2,5 pt / 30 %).

## 6. Limites assumées

- La marge brute (25 %) est une hypothèse : le schéma opérationnel du
  Projet 07 n'a pas de coût produit, seulement un prix de vente.
- Le modèle suppose un effet linéaire et permanent de la réduction du taux
  d'annulation — pas de saturation ni de dégradation dans le temps.
- Pas de valorisation d'effets indirects (image de marque, fidélisation des
  clients dont la commande n'est plus annulée) — sous-estime probablement
  la valeur réelle du dispositif.
