---
name: dealradar-digest
description: Compile et envoie le digest 3×/jour (09h, 13h, 19h) avec les verdicts ACHETER non top-5% et les VÉRIFIER, regroupés et synthétisés. Évite la saturation Telegram tout en gardant l'info disponible.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, digest, telegram, schedule]
    category: business
---

Compile et envoie le digest dealradar 3 fois par jour. Complète le push instant top 5% pour assurer une couverture complète sans noyer l'utilisateur.

## Quand invoquer

Via le scheduler natif Hermes :

```
hermes cron add "0 9 * * *" /dealradar-digest morning
hermes cron add "0 13 * * *" /dealradar-digest noon
hermes cron add "0 19 * * *" /dealradar-digest evening
```

(syntaxe à confirmer avec la doc Hermes scheduler — variation possible NL "every day at 9am")

## Inputs

- `slot` — `morning` | `noon` | `evening` (juste pour libeller le message)

## Procédure

1. GET `/api/alerts/pending?status=pending&channel=digest` sur dealradar API. Récupère les verdicts marqués pour digest (= ACHETER non top-5% + VÉRIFIER avec confidence ≥ 0.6 ET margin ≥ 40€).
2. GET `/api/capital` pour mention dans l'entête.
3. GET `/api/strategies?status=active` pour récap stratégies actives.
4. Identifier les fire-sale alerts pending (depuis le dernier digest).
5. Compiler le message Telegram (format ci-dessous).
6. POST sur Telegram Bot API.
7. PATCH `/api/alerts/{id}/ack` pour chaque alert envoyé (status → sent).

## Format Telegram

```
📊 DealRadar — Digest [matin|midi|soir] [date]

💼 Capital actuel : [X]€  →  Palier suivant : [Y]€ ([progress]%)

✅ ACHETER ([N])
  • [titre 1] — [prix]€ → revente ~[X]€ | marge nette ~[Y]€ | vélocité [Zj]
    📝 [raisonnement court]
    🔗 [URL]
  • [titre 2] — [prix]€ → ...
  ...

⚠️ VÉRIFIER ([N])
  • [titre 1] — [prix]€ — [raison de l'incertitude]
    🔗 [URL]
  ...

🚨 Fire-sale ([N])
  • [seller name] — [N listings] — score [X] — [URL]
  ...

📈 Bilan depuis dernier digest :
   Cycles exécutés : [N]
   Listings analysés : [N]
   Verdicts ACHETER : [N total]  •  push instant : [N]  •  digest : [N]
   Stratégies actives : [N]
```

## Si digest vide

```
📊 DealRadar — Digest [matin|midi|soir] [date]

Rien de notable depuis le dernier digest.
[N] listings analysés, [N] PASSER (red flags ou hors budget/catégorie).

💼 Capital actuel : [X]€
```

## Constraints

- **Pas de doublon** avec les push instant top 5% (déjà envoyés). Filtrer sur `is_top_5pct = false`.
- **Cap 30 entrées max** par section ACHETER/VÉRIFIER (sinon trop long pour Telegram). Si dépassement, lien vers UI dealradar (`/api/deals?...`).
- **Tout en français**, format markdown Telegram (parse_mode=MarkdownV2 ou HTML).

## Tools utilisés

- `terminal` — curl sur dealradar API + Telegram Bot API
- Memory Hermes — pour récupérer le timestamp du dernier digest envoyé (filtre alerts depuis cette date)

## See also

- [[dealradar-alerter]] — push instant top 5% (complémentaire)
- [[dealradar-fire-sale-alert]] — alertes seller fire-sale (peut être incluse dans digest si pas de push instant)
- [[dealradar-triage]] — produit les verdicts qui alimentent le digest
