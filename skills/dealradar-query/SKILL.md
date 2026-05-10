---
name: dealradar-query
description: Recherche conversationnelle dealradar à partir d'une description en langage naturel. Lance un scrape ciblé, retourne les top 3-5 résultats analysés.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [dealradar, ad-hoc, search, on-demand]
    category: business
---

Recherche conversationnelle ad-hoc sur les marketplaces, avec analyse LLM des résultats.

Couvre la story PRD S41 du dealradar v2 (conversational search).

## Inputs

- `/dealradar-query <description NL>` — exemples :
  - `/dealradar-query enceintes Bose ≤ 100€ Nice`
  - `/dealradar-query MacBook Pro 14 M3 dans le 06`
  - `/dealradar-query trouve-moi des LEGO Star Wars retired moins de 200€`

## Procédure

1. **Parser l'intention** via le LLM principal Hermes. Extraire :
   - `keywords` (whitelist)
   - `keywords_blacklist` (si "sauf" / "pas de" mentionnés)
   - `platforms` (déduite de "sur LBC", "Vinted", etc., sinon toutes)
   - `city` + `radius_km` (si lieu mentionné)
   - `price_max`, `price_min`
2. **Trigger scrape** : POST `/api/search` sur dealradar API avec ces paramètres. Reçoit listings (jusqu'à 50).
3. **Triage rapide** : invoquer `dealradar-analyst` mode `triage` sur les résultats. Retourner les **top 3-5** par score marge × confidence.
4. **Pour chaque top item** : invoquer `dealradar-pricer` + `dealradar-analyst` mode `verdict` rapide (sans cross-platform lookup approfondi pour rester rapide).
5. **Réponse** : formater liste compacte avec verdict + URL.

## Format de réponse Telegram

```
🔎 Recherche : "enceintes Bose ≤ 100€ Nice"

5 résultats trouvés, 3 recommandés :

✅ ACHETER — Bose SoundLink Mini II
   60€ sur LBC | Revente ~110€ | Marge nette ~38€ | Vélocité 5j
   📝 État neuf, vendeur actif depuis 2 ans
   🔗 [URL]

⚠️ VÉRIFIER — Bose Companion 2
   45€ sur Vinted | Revente potentielle 80€ | 1 seul comparable
   📝 Photos de qualité moyenne, vérifier état
   🔗 [URL]

✅ ACHETER — Bose QuietComfort 25
   80€ sur LBC | Revente ~140€ | Marge nette ~45€ | Vélocité 7j
   📝 Avec écouteurs et housse
   🔗 [URL]

(2 autres résultats non recommandés : prix trop hauts ou red flags)
```

## Cas d'erreur

| Erreur | Réponse |
|---|---|
| Intention pas claire | "Je n'ai pas bien compris. Précise plus : produit, prix max, ville ?" |
| 0 résultats | "Aucun résultat. Essaye d'élargir la recherche (plus de plateformes, prix max plus haut)." |
| LLM unavailable | Fallback : retourner les top 5 résultats brut sans verdict |
| dealradar API down | "Backend dealradar indisponible. Réessayer plus tard." |

## Constraints

- **Pas de persistance** par défaut : les résultats ne sont PAS sauvegardés en deals (skill ad-hoc), sauf si `--save` flag dans la query.
- **Capital filter** : appliquer `price_max ≤ capital × 0.8` même si user ne précise pas, et le mentionner dans la réponse ("Filtre capital appliqué : ≤ 480€").
- **Bans** : skip silencieusement les catégories bannies, mais le mentionner si tous les résultats sont bannis ("Tous les résultats étaient dans des catégories bannies, recherche ajustée").
- **Tout en français**

## Tools utilisés

- `terminal` — curl POST sur dealradar API
- LLM principal Hermes — pour parsing NL intent
- Sub-skills : `dealradar-analyst` (triage rapide), `dealradar-pricer` (estimation light)

## See also

- [[dealradar-check]] — pour une URL spécifique
- [[dealradar-strategy-create]] — pour transformer une recherche récurrente en stratégie persistante
