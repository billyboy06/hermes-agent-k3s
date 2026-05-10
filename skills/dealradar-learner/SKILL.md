---
name: dealradar-learner
description: Apprend des retours utilisateur (deals achetés / passés à tort / faux positifs) pour améliorer les futures analyses. Persiste les leçons dans son SKILL.md, lu par dealradar-strategist et dealradar-analyst au prochain cycle.
version: 0.2.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, feedback, learning, memory]
    category: business
---

## [OPERATING RULES — DO NOT VIOLATE]

1. **EDIT IN-PLACE only this SKILL.md.** Use the `patch` tool to insert a new bullet in the §"Retours enregistrés" section. Do NOT write feedback to a database, log file, or other skill. The SKILL.md is the source of truth for the cross-cycle learning loop.
2. **NEVER re-touch the §"Comment ça marche", §"Comment utiliser les retours", §"Format de mise à jour", §"Synthèse périodique", §"Constraints", §"See also" sections.** Append-only on §"Retours enregistrés" only.
3. **IDEMPOTENT** — receiving the same `(deal_id, action)` twice creates ONE entry, not two. Read the section first, deduplicate against existing bullets.
4. **MAX 50 active entries.** When the section reaches 50, trigger the synthesis cycle (consolidate, drop the weakest 10, keep the most recent + most reinforced).
5. **OUTPUT JSON STRICT** — schema in §"Format de sortie". The caller (`dealradar-feedback`) needs `lesson_added` and `lessons_total` to decide UX feedback to user.

Tu es le module d'apprentissage de DealRadar. Tu intègres les retours utilisateur pour faire évoluer le scoring sans toucher au code.

## Comment ça marche

L'utilisateur peut donner du feedback via :
- POST `/api/deals/{id}/feedback` — endpoint backend (à intégrer dans dealradar)
- Slash command `/dealradar-feedback <listing_url> <good|bad|false-positive> [<note>]` (skill séparé à créer)
- Réplique Telegram à un alert (parsing du reply pour détecter "ok / nope / acheté / pas acheté")

À chaque feedback reçu, ce skill **ajoute un bullet point ci-dessous** avec la date et la leçon. Au prochain cycle, `dealradar-strategist` et `dealradar-analyst` lisent ce SKILL.md et adaptent leur comportement.

## Retours enregistrés

(À éditer in-place via `patch` ou `write_file` sur ce SKILL.md. Les entrées les plus récentes en haut.)

- 2026-03-26 : Pièces moto/Vespa pas intéressant → exclure systématiquement ces catégories du triage
- 2026-04-12 : Marantz toujours bon → boost confiance +0.1 sur audio vintage Marantz Pioneer Sansui
- 2026-04-15 : Faux positif sur "Rolex" 280€ — c'était une contrefaçon. Confirmer la règle "montres luxe < 500€ = ban"

(les retours sont ajoutés en bullet points ci-dessus, ordonnés par date desc)

## Comment utiliser les retours (par les skills consommateurs)

Quand `dealradar-strategist` ou `dealradar-analyst` est invoqué, ils :

1. Lisent ce SKILL.md (section "Retours enregistrés")
2. Pour chaque entrée, l'interprètent :
   - "X pas intéressant" → ajouter X aux bans
   - "Y toujours bon" → boost confiance +0.1 sur Y
   - "Faux positif sur Z" → renforcer le red flag pour Z
   - "Acheté Z et bien revendu" → confirmer le pattern, accroître priorité catégorie
3. Adaptent leur prompt système / leurs seuils en conséquence

## Format de mise à jour

Quand un nouveau feedback arrive, ce skill :

1. Lit le feedback (objet : `{deal_id, action, note, timestamp}`)
2. Si la leçon est **nouvelle** (pas déjà dans la liste), l'ajoute :
   ```
   - YYYY-MM-DD : <leçon en 1 phrase>
   ```
3. Si la leçon **renforce une existante**, met à jour la date / accroît la priorité (préfixer avec ⭐ si renforcé 3+ fois)
4. Si la leçon **contredit** une existante, marquer la précédente comme révoquée (préfixer avec ~~)

## Inputs

- `feedback` — objet `{deal_id, action: "good"|"bad"|"false_positive", note, timestamp}`

## Tools utilisés

- `read_file` — lire l'état actuel de ce SKILL.md
- `patch` — édition fuzzy in-place (ajout d'une bullet)
- `terminal` — curl GET /api/deals/{id} pour récupérer le contexte du deal feedback-é (catégorie, plateforme, prix)

## Format de sortie

```json
{
  "feedback_processed": true,
  "lesson_added": true,
  "lesson": "2026-05-09 : Casques Sony WH-1000XM5 vendus en 3 jours sur Vinted → boost vélocité catégorie casques pro",
  "lessons_total": 12,
  "skill_md_updated": true
}
```

## Synthèse périodique (auto-curation)

Tous les 7 jours (ou tous les 50 feedbacks, peu importe), un cycle de **synthèse** est invoqué :

1. Lire toutes les leçons accumulées
2. Identifier les redondances et consolider
3. Identifier les contradictions et trancher (en faveur du feedback le plus récent et le plus fréquent)
4. Réécrire la section "Retours enregistrés" avec les leçons consolidées (max 50 entrées actives)

Ce cycle est déclenché par un cron Hermes natif (skill `dealradar-learner-synthesize` à créer si besoin, sinon manuellement).

## Constraints

- **Idempotent** : recevoir 2 fois le même feedback ne crée pas 2 entrées
- **Append-only par défaut** : pas de suppression sauf via cycle de synthèse
- **Limite 50 entrées actives** : au-delà, déclencher synthèse
- **Tout en français**

## See also

- [[dealradar-strategist]] — consomme les leçons pour ajuster les niches/bans
- [[dealradar-analyst]] — consomme les leçons pour ajuster confidence par catégorie
- [[dealradar-feedback]] — skill séparé pour interface utilisateur (à créer)
