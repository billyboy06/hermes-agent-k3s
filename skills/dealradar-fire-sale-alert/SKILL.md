---
name: dealradar-fire-sale-alert
description: Détecte les vendeurs en clear-out (fire-sale cluster) et émet une alerte Telegram dédiée avec leur top items. Utilise le seller fire_sale_score calculé en backend.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, fire-sale, seller, alert]
    category: business
---

Détecte et notifie les **vendeurs en fire-sale** (déménagement, succession, urgence financière) qui mettent en vente plusieurs items intéressants en peu de temps.

Le scoring fire-sale est calculé côté backend dealradar (déjà existant en v2 : `compute_fire_sale_score(seller)` agrège volume + diversity + urgency keywords).

## Quand l'invoquer

Dans le cycle `dealradar-triage` après le scrape (step 4.5 — entre fetch listings et Phase A) :
- Récupérer les sellers dont `fire_sale_score ≥ 70` ET `last_seen_at < 24h`
- Pour chacun, vérifier qu'on n'a pas déjà alerté dans les 7 derniers jours (table `alerts` côté backend, dedup naturel)
- Lancer ce skill pour formater + envoyer

## Inputs

- `seller_id` — ID du vendeur côté backend dealradar
- `mode` — `"detect"` (auto, depuis triage) ou `"check"` (ad-hoc, pour un seller URL fourni par user)

## Procédure

1. GET `/api/sellers/{id}` sur dealradar API. Reçoit profile + listings + fire_sale_score.
2. Si `fire_sale_score < 70` → skip, exit (pas de fire-sale).
3. Vérifier dedup : alerte déjà envoyée pour ce seller_id < 7j ? Si oui, skip.
4. Identifier les **top 3 listings** du seller par marge potentielle (rapide, sans Phase B complète) :
   - Filtrer dans le whitelist de catégories
   - Skip les bans
   - Skip les prix > capital × 0.8
   - Trier par `(estimated_resale - price) DESC`
5. Formater l'alerte Telegram (format dédié, voir ci-dessous).
6. POST sur Telegram Bot API.
7. POST `/api/alerts` (backend) pour persister + dedup.

## Format Telegram

```
🚨 Fire-sale détecté — [seller_name]

📦 [N] listings actifs — score [X]/100
🎯 Catégories : [cat1, cat2, cat3]
💡 Mots-clés détectés : [déménagement, succession, sacrifié]
📅 Premier vu : [date]
📍 Localisation : [ville]

Top 3 items à vérifier :
  • [item 1] — [prix]€ → revente ~[X]€ marge ~[Y]€ [URL]
  • [item 2] — [prix]€ → revente ~[X]€ marge ~[Y]€ [URL]
  • [item 3] — [prix]€ → revente ~[X]€ marge ~[Y]€ [URL]

🔗 Tous les listings du vendeur : [seller URL]
```

## Constraints

- **Anti-spam** : 1 alerte max par seller_id par 7 jours (dedup côté backend table alerts).
- **Sécurité** : ne JAMAIS afficher d'info personnelle sur le seller (numéro téléphone, etc.). Juste seller_name (souvent un pseudo) et URL profile.
- **Capital filter** : si tous les top items sont au-delà du capital, encore alerter mais mentionner "items hors budget actuel — utile pour tracker".
- **Tout en français**

## Tools utilisés

- `terminal` — curl GET/POST sur dealradar API + curl POST Telegram Bot API
- Sub-skill : `dealradar-pricer` (estimation rapide pour top 3, sans cross-platform full)

## See also

- [[dealradar-triage]] — invoque ce skill au step 4.5
- [[dealradar-alerter]] — format push instant standard pour les deals individuels
- Backend : `src/services/scoring.py` (compute_fire_sale_score)
