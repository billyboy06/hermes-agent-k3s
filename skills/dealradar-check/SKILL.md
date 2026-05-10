---
name: dealradar-check
description: Analyse à la volée une URL d'annonce LBC/Vinted/Wallapop/eBay et émet un verdict ACHETER / VÉRIFIER / PASSER avec marge nette estimée. Pour usage ad-hoc utilisateur.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, ad-hoc, verdict, on-demand]
    category: business
---

Analyse à la demande une URL d'annonce et retourne un verdict détaillé.

Couvre la story PRD S42 du dealradar v2 (single URL deep analysis).

## Inputs

- `/dealradar-check <url>` — URL d'annonce LBC, Vinted, Wallapop ou eBay

## Procédure

1. **Validation URL** : vérifier que l'URL appartient à une plateforme supportée. Sinon, refuser avec message explicite.
2. **Scrape ad-hoc** : POST `/api/scrape` sur dealradar API avec `{"url": "<url>"}`. Reçoit titre, description, prix, vendeur, photos, plateforme, condition.
3. **Cross-platform lookup** : invoquer skill `dealradar-lookup` (ou POST /api/search direct) avec les keywords extraits du titre. Récupérer comparables eBay sold + Vinted + Wallapop.
4. **Pricing** : invoquer skill `dealradar-pricer` avec listing + comparables → estimation revente + vélocité.
5. **Verdict** : invoquer skill `dealradar-analyst` mode `verdict` avec listing + comparables + pricing → verdict ACHETER/VÉRIFIER/PASSER détaillé.
6. **Persistance** : POST `/api/analyze` avec le verdict + flag `triggered_by: "user"`.
7. **Réponse** : formater le verdict pour Telegram (réutiliser le format de `dealradar-alerter` mode push instant).

## Format de réponse Telegram

Identique au format push instant de `dealradar-alerter`, avec en plus une mention :

```
🔍 ANALYSE À LA DEMANDE — [titre]

[verdict + détails comme dans dealradar-alerter]

📌 Cette annonce est ajoutée à dealradar (deal_id: deal_xxx)
🔁 Pour donner ton avis après achat : /dealradar-feedback deal_xxx
```

## Cas d'erreur

| Erreur | Réponse |
|---|---|
| URL invalide / non supportée | "Plateforme non supportée. Plateformes acceptées : LBC, Vinted, Wallapop, eBay." |
| Annonce déjà supprimée | "Annonce introuvable. Probablement déjà vendue ou retirée." |
| Scrape rate-limited (DataDome LBC) | "Plateforme bloque temporairement. Réessayer dans 10 min." |
| LLM unavailable | "Backend LLM indisponible. Réessayer plus tard." |
| Listing déjà analysé | "Cette annonce a déjà été analysée le [date]. Verdict : [X]. Pour ré-analyser : /dealradar-check <url> --refresh" |

## Constraints

- **Capital filter** : si prix > capital × 0.8, retourner `verdict: PASSER` avec raison explicite (au-delà de notre budget actuel).
- **Bans** : si la catégorie matche un ban (vélo élec, etc.), `verdict: PASSER` immédiatement, pas de cycle complet d'analyse.
- **Cache** : si la même URL a été analysée < 24h, retourner le verdict cached avec mention de la date. `--refresh` force ré-analyse.
- **Tout en français**

## Tools utilisés

- `terminal` — curl POST/GET sur dealradar API
- Sub-skills : `dealradar-lookup`, `dealradar-pricer`, `dealradar-analyst`, `dealradar-alerter`

## See also

- [[dealradar-triage]] — version batch (200 listings) du même flow
- [[dealradar-query]] — pour une recherche conversationnelle (pas une URL spécifique)
