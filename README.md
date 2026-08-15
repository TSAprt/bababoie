# Carte des offres — Topographie / Hydrographie / LiDAR / Géomatique

Carte interactive auto-mise-à-jour listant les offres d'emploi niveau
ingénieur (Bac+5) dans les domaines : topographie, géomètre, hydrographie,
bathymétrie, LiDAR, géomatique, photogrammétrie/drone, SIG.

**Zones couvertes** (ordre de priorité) : Europe (FR, GB, DE, NL, IT, PL, AT,
CH) → États-Unis → Canada → Asie (Inde, Singapour — voir limitation Chine
ci-dessous).

Le système tourne entièrement gratuitement sur GitHub (Actions + Pages) :
un script Python interroge l'API [Adzuna](https://developer.adzuna.com/)
chaque jour, écrit les résultats dans `data/jobs.geojson`, et la page
`index.html` (Leaflet.js) affiche la carte à partir de ce fichier.

---

## 1. Créer un compte Adzuna (gratuit)

1. Va sur https://developer.adzuna.com/ et crée un compte développeur.
2. Récupère ton **App ID** et ta **App Key** (tableau de bord).
3. Quota gratuit : généralement suffisant pour un usage quotidien de ce
   script (quelques centaines d'appels/jour).

## 2. Créer le dépôt GitHub

1. Crée un nouveau dépôt GitHub (public ou privé — Pages fonctionne sur les
   deux si tu as GitHub Pro pour le privé, sinon utilise un dépôt public).
2. Pousse-y l'intégralité de ce dossier :

```bash
cd geo-jobs-map
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<ton-compte>/<ton-repo>.git
git push -u origin main
```

## 3. Ajouter les secrets

Dans le dépôt GitHub : **Settings → Secrets and variables → Actions → New
repository secret**, ajoute :

- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`

## 4. Activer GitHub Pages

**Settings → Pages** → Source = `Deploy from a branch` → Branch = `main` /
`root`. Ta carte sera accessible à :

```
https://<ton-compte>.github.io/<ton-repo>/
```

## 5. Lancer le premier scraping

Va dans l'onglet **Actions** du dépôt → sélectionne le workflow
*"Update job map data"* → **Run workflow** (bouton manuel). Ça exécute
`scraper.py`, remplit `data/jobs.geojson`, et commit le résultat.

Ensuite, le workflow tourne automatiquement **tous les jours à 05h00 UTC**
(modifiable dans `.github/workflows/update.yml`, ligne `cron:`).

---

## Structure du projet

```
geo-jobs-map/
├── scraper.py                     # interroge Adzuna, filtre, génère le GeoJSON
├── requirements.txt
├── index.html                     # carte Leaflet + filtres + liste latérale
├── data/
│   └── jobs.geojson                # généré/actualisé automatiquement
├── .github/workflows/update.yml   # planification quotidienne + commit auto
└── README.md
```

## Personnaliser

- **Mots-clés / domaines** : liste `KEYWORDS` dans `scraper.py`.
- **Pays** : liste `COUNTRIES` (codes ISO Adzuna : `fr`, `gb`, `de`, `nl`,
  `it`, `pl`, `at`, `ch`, `us`, `ca`, `in`, `sg`).
- **Filtre niveau ingénieur** : liste `DEGREE_TERMS` — ajuste si le filtre
  est trop strict ou trop large.
- **Fréquence de mise à jour** : champ `cron` dans
  `.github/workflows/update.yml` (syntaxe cron standard).

## ⚠️ Limitation — Chine

Adzuna ne couvre pas la Chine (aucune API publique fiable et gratuite
n'existe pour 51job, Zhaopin ou Liepin à ma connaissance). Pour ce marché,
la meilleure approche reste :
- surveillance manuelle des pages carrières LinkedIn des filiales chinoises
  de Fugro, GEOxyz, CCCC, etc. ;
- alertes emploi LinkedIn avec mots-clés ciblés (voir recherches précédentes).

Si tu trouves une API chinoise exploitable, il suffit d'ajouter une fonction
`fetch_jobs_cn()` sur le même modèle que `fetch_jobs()` dans `scraper.py`
et de fusionner les résultats dans `features`.

## Deuxième source : Jooble (déjà intégrée, optionnelle)

Le scraper interroge maintenant **deux sources** et fusionne les résultats
dans le même `data/jobs.geojson`, en évitant les doublons (déduplication
par URL d'offre) :

1. **Adzuna** — obligatoire, avec coordonnées GPS déjà fournies par l'API.
2. **Jooble** — optionnelle. Couvre 60+ pays, gratuite, mais ne renvoie pas
   de coordonnées GPS : le script géocode donc chaque lieu via
   [Nominatim/OpenStreetMap](https://nominatim.org/) (gratuit, avec cache
   pour ne jamais interroger deux fois le même lieu et respecter leur
   limite d'1 requête/seconde).

### Activer Jooble

1. Va sur https://jooble.org/api/about et remplis le petit formulaire
   (nom, poste, email, site web, téléphone).
2. Jooble t'envoie une clé API par email (gratuite, sous quelques heures
   à 1-2 jours en général).
3. Ajoute-la comme secret GitHub : **Settings → Secrets and variables →
   Actions → New repository secret** → nom `JOOBLE_API_KEY`.
4. Relance le workflow (**Actions → Update job map data → Run workflow**).

Si `JOOBLE_API_KEY` n'est pas définie, le script l'ignore simplement et
continue de fonctionner avec Adzuna seul (aucune erreur).

⚠️ **Avant d'activer** : édite `scraper.py` et remplace l'adresse email
factice dans `GEOCODER_USER_AGENT` (ligne ~15) par une vraie adresse —
c'est une exigence de la politique d'usage de Nominatim, pas optionnelle
en pratique (ils peuvent bloquer les requêtes sans contact valide).

## Autres sources possibles à ajouter

- **USAJobs API** (https://developer.usajobs.gov/) — gratuit, spécifique
  postes fédéraux US (utile pour NOAA, Corps of Engineers, etc.).
- **Flux RSS Indeed** par pays (`indeed.com/rss?q=...&l=...`) — non
  officiel mais fonctionne encore dans de nombreux pays.

Chacune suit le même schéma que Jooble : récupérer les résultats, les
convertir en `Feature` GeoJSON, les ajouter à `features` avant l'écriture
du fichier — regarde `run_jooble()` dans `scraper.py` comme modèle.
