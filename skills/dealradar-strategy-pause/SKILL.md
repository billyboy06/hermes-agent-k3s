---
name: dealradar-strategy-pause
description: Met en pause, reprend ou supprime une stratégie dealradar par son ID ou son nom.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, strategy, crud]
    category: business
---

Modifie le statut d'une stratégie dealradar.

## Inputs

- `/dealradar-strategy-pause <strategy_id_or_name>` — pause la stratégie
- `/dealradar-strategy-pause <id> unpause` — réactive
- `/dealradar-strategy-pause <id> delete` — supprime définitivement (irréversible, demande confirmation)

## Procédure

1. Résoudre l'ID via GET `/api/strategies` si l'argument est un nom (substring match).
   - Si plusieurs matchs → demander précision à l'utilisateur, abort.
   - Si aucun match → erreur explicite.
2. Selon l'action :
   - `pause` → PATCH `/api/strategies/{id}` avec `{"status": "paused"}`
   - `unpause` → PATCH `/api/strategies/{id}` avec `{"status": "active"}`
   - `delete` → demander confirmation explicite ("OK pour supprimer 'X' ? Réponds CONFIRMER"), puis DELETE `/api/strategies/{id}`
3. Confirmer le changement à l'utilisateur

## Format de réponse

```
⏸️ Stratégie 'Casques Sony WH-1000XM5' (strat_001) mise en pause.
Pour réactiver : /dealradar-strategy-pause strat_001 unpause
```

ou

```
▶️ Stratégie 'Ski matériel saison' (strat_004) réactivée.
Prochaine exécution : 19:00.
```

ou

```
🗑️ Stratégie 'Old test strat' (strat_005) supprimée définitivement.
```

## Constraints

- **Confirmation pour delete** : jamais de suppression sans réplique explicite "CONFIRMER" de l'utilisateur (le pause est sans risque, le delete est irréversible)
- **Lifecycle automatique** : si une strat est en `expired`, elle est déjà inactive — pas besoin de la pauser, juste delete pour faire le ménage.
- **Tout en français**

## Tools utilisés

- `terminal` — curl PATCH/DELETE sur dealradar API

## See also

- [[dealradar-strategy-create]]
- [[dealradar-strategy-list]]
