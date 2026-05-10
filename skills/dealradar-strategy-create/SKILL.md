---
name: dealradar-strategy-create
description: Crée une nouvelle stratégie de recherche dealradar à partir d'une description en langage naturel. Parse keywords, prix max, vélocité cible, etc., et persiste via POST /api/strategies.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, strategy, crud]
    category: business
---

Tu crées des stratégies de recherche ciblées pour dealradar à partir d'instructions en langage naturel.

## Inputs

Description NL en argument du slash command, exemple :
- `/dealradar-strategy-create casques Sony WH-1000XM5, prix max 180€, marge min 40, vélocité 7j, plateformes LBC+Vinted, durée 14j`
- `/dealradar-strategy-create tracker R9700 32GB, prix max 1200€, France entière, alerte instantanée`
- `/dealradar-strategy-create stratégie ski matériel pour saison oct-fev, prix max 200€, 50km Nice`

## Procédure

1. Lire l'argument NL.
2. Extraire les champs structurés via le LLM principal :
   - `name` (court, 3-5 mots)
   - `description` (NL)
   - `keywords_whitelist` (array, mots-clés à matcher)
   - `keywords_blacklist` (array, optionnel)
   - `platforms` (subset de `["leboncoin", "vinted", "wallapop", "ebay"]`)
   - `geo` (`{"city": "Nice", "radius_km": 50}` ou `null` pour France entière)
   - `price_min`, `price_max` (EUR, integers)
   - `min_margin_eur` (default 30)
   - `max_velocity_days` (default 14)
   - `min_cross_platform_sources` (default 2)
   - `cadence_minutes` (default 30 pour POST /api/search ciblé)
   - `expiry_days` (default 30, durée de vie de la stratégie)
   - `priority_boost` (0 à 10, augmente le score Phase A pour les listings matchant)
   - `max_capital_eur` (réservation soft du capital, optionnel)
3. Valider la cohérence (prix_max > prix_min, dates futures, etc.)
4. POST `/api/strategies` (sur dealradar API) avec le payload JSON
5. Confirmer à l'utilisateur via Telegram ou réponse skill

## Format de réponse

```json
{
  "strategy_id": "strat_xxx",
  "name": "Casques Sony WH-1000XM5",
  "status": "active",
  "created_at": "2026-05-09T18:30:00Z",
  "expires_at": "2026-06-08T18:30:00Z",
  "next_search_at": "2026-05-09T19:00:00Z"
}
```

## Constraints

- **Capital ladder** : si `max_capital_eur` > capital actuel × 0.8, refuser et expliquer (besoin de cumuler plus avant d'activer cette strat)
- **Bans** : refuser si keywords match un ban (vélos électriques, iPhone < 13, montres luxe < 500€). Expliquer pourquoi.
- **Limite stratégies actives** : max 10 stratégies actives en simultané (sinon focus dilué)
- **Tout en français** dans le `name` et `description`

## Tools utilisés

- `terminal` — curl POST sur dealradar API
- LLM principal Hermes — pour parse NL → JSON structuré

## See also

- [[dealradar-strategy-list]] — lister les strats actives
- [[dealradar-strategy-pause]] — pauser une strat
- [[dealradar-strategist]] — consomme les strats actives pour générer requêtes scraping
