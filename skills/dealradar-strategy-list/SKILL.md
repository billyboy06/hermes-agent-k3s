---
name: dealradar-strategy-list
description: Liste les stratégies dealradar (active, paused, expired) avec leurs métriques (deals trouvés, marge cumulée, prochaine exécution).
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, strategy, crud]
    category: business
---

Liste les stratégies de recherche dealradar avec leurs métriques.

## Inputs

Filtre optionnel en argument :
- `/dealradar-strategy-list` — toutes les stratégies actives (défaut)
- `/dealradar-strategy-list all` — toutes (active + paused + expired)
- `/dealradar-strategy-list paused` — uniquement les pausées
- `/dealradar-strategy-list <name>` — détail d'une strat par nom (substring match)

## Procédure

1. GET `/api/strategies?status=<filter>` sur dealradar API
2. Pour chaque stratégie, récupérer :
   - id, name, status
   - keywords, platforms, prix_min/max
   - métriques : deals_found_count, total_margin_eur_cumul, last_run_at, next_run_at
   - cycle_count, success_rate
3. Formater en réponse Telegram lisible (table compacte)

## Format de sortie Telegram

```
📋 Stratégies dealradar — 3 actives, 1 pausée

🟢 [strat_001] Casques Sony WH-1000XM5
   Statut : active | Expire : 2026-06-08 (28j)
   Prix : ≤180€ | Plateformes : LBC, Vinted | Géo : Nice 50km
   Deals trouvés : 4 | Marge cumul : 165€
   Prochain run : 19:00 (dans 25 min)

🟢 [strat_002] R9700 32GB tracker
   Statut : active | Expire : 2026-08-01 (long terme)
   Prix : ≤1200€ | Plateformes : LBC, eBay | Géo : France
   Deals trouvés : 0 (en attente)
   Prochain run : 20:00 (dans 1h25)

🟢 [strat_003] LEGO retired Star Wars
   Statut : active | Expire : 2026-05-30 (21j)
   Prix : ≤150€ | Plateformes : LBC, Vinted | Géo : Nice 100km
   Deals trouvés : 2 | Marge cumul : 75€
   Prochain run : 18:45 (dans 10 min)

⏸️ [strat_004] Ski matériel saison
   Statut : paused (saison hors période)
   Pour réactiver : /dealradar-strategy-pause strat_004 unpause
```

## Format JSON brut (pour scripting / parsing)

Si `--json` fourni :
```json
{
  "strategies": [
    {"id": "strat_001", "name": "...", "status": "active", "metrics": {...}, ...}
  ],
  "counts": {"active": 3, "paused": 1, "expired": 0},
  "total_capital_locked_eur": 1380
}
```

## Tools utilisés

- `terminal` — curl GET sur dealradar API

## See also

- [[dealradar-strategy-create]] — créer une nouvelle stratégie
- [[dealradar-strategy-pause]] — pauser/reprendre
