---
name: dealradar-feedback
description: Enregistre un retour utilisateur sur un deal (good / bad / false-positive) pour alimenter le learner. Met à jour le SKILL.md de dealradar-learner avec la leçon en NL.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, feedback, learning, ux]
    category: business
---

Capture le feedback utilisateur sur un deal et alimente le learner.

Couvre la story PRD S49 du dealradar v2 (user feedback loop).

## Inputs

- `/dealradar-feedback <deal_id> <action> [<note>]`
- `action` ∈ `good` | `bad` | `false-positive`
- `note` (optionnel) : explication courte en NL

Exemples :
- `/dealradar-feedback deal_123 good`
- `/dealradar-feedback deal_124 bad acheté mais pas vendu en 2 mois`
- `/dealradar-feedback deal_125 false-positive contrefaçon évidente`

## Procédure

1. GET `/api/deals/{id}` pour récupérer le contexte (titre, prix, catégorie, plateforme, verdict, vendeur, scraped_at, sold_at si dispo).
2. POST `/api/deals/{id}/feedback` avec `{action, note}` côté backend dealradar (persistance).
3. **Synthèse de la leçon** via le LLM principal Hermes (qwen36-mtp en prod, Claude en test) :
   - Input : contexte deal + action + note utilisateur
   - Output : 1 phrase courte généralisable, ex :
     - `feedback: bad on Marantz 2225` → "Marantz 2225 spécifiquement difficile à revendre, prix demandés en chute"
     - `feedback: good on Bose QC25` → "Bose QC25 très liquide sur Vinted, à boost"
     - `feedback: false-positive on Rolex 280€` → "Rolex < 500€ confirmé contrefaçon, ban absolu"
4. Mettre à jour `~/.hermes/skills/business/dealradar-learner/SKILL.md` :
   - Ajouter la leçon en bullet point en haut de la section "Retours enregistrés"
   - Format : `- YYYY-MM-DD : <leçon>`
   - Utiliser le tool `patch` (édition fuzzy) pour insertion in-place
5. Confirmer à l'utilisateur via Telegram.

## Format de réponse

```
✅ Feedback enregistré pour deal_124.
Leçon retenue : "Marantz 2225 spécifiquement difficile à revendre, prix demandés en chute"
Cette leçon sera prise en compte dès le prochain cycle (toutes les 15 min en fenêtre).
```

## Cas d'erreur

| Erreur | Réponse |
|---|---|
| Deal_id introuvable | "Deal introuvable. ID exact requis (visible dans les alertes Telegram)." |
| Action invalide | "Action acceptée : good, bad, false-positive." |
| Backend dealradar down | "Feedback enregistré localement, sera synced au prochain cycle." (TODO: gérer via memory Hermes) |

## Synthèse périodique

Tous les 7 jours OU tous les 50 feedbacks (peu importe), un cycle de **synthèse** est invoqué automatiquement (ou à la demande via `/dealradar-learner-synthesize`) :
- Lire toutes les leçons accumulées
- Consolider les redondances
- Trancher les contradictions (priorité au plus récent et fréquent)
- Réécrire la section "Retours enregistrés" du learner avec max 50 entrées actives

Implémenté dans le skill `dealradar-learner` (mode `synthesize`).

## Constraints

- **Idempotent** : recevoir 2x le même `(deal_id, action)` ne crée pas 2 entrées (la 2e overwrite la 1ère).
- **Append-only** par défaut : la suppression manuelle d'une leçon passe par le skill `dealradar-learner` (édition manuelle ou cycle de synthèse).
- **Tout en français** dans la leçon et la réponse user.

## Tools utilisés

- `terminal` — curl GET/POST sur dealradar API
- LLM principal Hermes — pour synthèse leçon
- `read_file` + `patch` — édition in-place du SKILL.md de `dealradar-learner`

## See also

- [[dealradar-learner]] — stocke les leçons consolidées
- [[dealradar-strategist]] — consomme les leçons pour ajuster niches
- [[dealradar-analyst]] — consomme les leçons pour ajuster confidence
