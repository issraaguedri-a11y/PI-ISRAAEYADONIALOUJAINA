# Projet Intégré — Analyse et Prédiction du Churn Client

> **École** : ESPRIT School of Business
> **Programme** : Master 1 — Business Analytics (M1 BA)
> **Tuteur du projet** : Aymen Ben Brik
> **Année** : 2026
> **Dépôt** : [PI-ISRAAEYADONIALOUJAINA](https://github.com/issraaguedri-a11y/PI-ISRAAEYADONIALOUJAINA)

Bienvenue. Ce dossier contient l'ensemble des supports nécessaires pour réaliser le projet.

## Par où commencer

1. Lisez les documents du dossier **`00_documentation/`** dans l'ordre :
   - `1_description_projet.md` — ce qu'on vous demande de faire et les livrables attendus.
   - `2_description_donnees.md` — la structure des données fournies.
   - `3_timeline.md` — le planning sur 4 semaines.
   - `4_guide_etudiant.md` — la démarche et les outils proposés étape par étape.
2. Placez les fichiers de données qui vous seront remis dans le dossier **`data/`** (ce dossier est ignoré par Git, voir `.gitignore`).
3. Travaillez dans les dossiers numérotés correspondants à chaque phase.

## État d'avancement

| Dossier | Contenu attendu | Statut |
|---|---|---|
| `00_documentation/` | Documents fournis par l'encadrant (ne pas modifier) | — |
| `01_etl/` | Scripts et notebooks ETL (extraction, nettoyage, transformation) | ✅ Fait |
| `02_data_warehouse/` | Scripts SQL de création du schéma, modèle dimensionnel, scripts de chargement | ✅ Fait |
| `03_power_bi/` | Fichiers `.pbix`, captures d'écran, documentation des KPIs | ⬜ À faire |
| `04_machine_learning/` | Notebooks ML, scripts d'entraînement, modèle final (branché sur PostgreSQL) | ✅ Fait |
| `05_web_app/` | Application Streamlit (KPIs, analyse du churn, prédiction, comptes à risque) | ✅ Fait (déploiement public à finaliser, voir `05_web_app/DEPLOY.md`) |
| `06_rapport/` | Sources du rapport (Word, LaTeX, etc.) et version PDF finale | ⬜ À faire |
| `07_presentation/` | Slides de présentation | ⬜ À faire |
| `data/` | Données brutes (**ne sera pas versionnée**) | — |

Le pipeline `01_etl → 02_data_warehouse → 04_machine_learning → 05_web_app`
est fonctionnel de bout en bout : les données brutes anonymisées sont
nettoyées et chargées dans un entrepôt PostgreSQL en modèle en étoile, le
modèle de churn (XGBoost) est entraîné directement depuis cet entrepôt (voir
`04_machine_learning/comparison.md` pour la démarche et les fuites de
données identifiées et corrigées), et l'application web interroge ce même
entrepôt et ce même modèle en temps réel. Détail des étapes d'exécution dans
le README de chaque dossier.

## Règles à respecter

- **Données confidentielles** : aucun fichier de données ne doit être commité sur GitHub. Le dossier `data/` est exclu via `.gitignore`.
- **Anonymat** : ne mentionnez l'origine des données dans aucun livrable (code, rapport, présentation).
- **Versioning régulier** : chaque membre de l'équipe doit commiter régulièrement, sur sa branche.
- **Reproductibilité** : votre code doit pouvoir être ré-exécuté à partir des instructions de ce README et des `requirements.txt` de chaque dossier.
- **Fichiers volumineux** : ne jamais forcer l'ajout d'un fichier de données brut (`*.txt`, `*.csv`...) dans un commit — vérifiez `git status` avant chaque commit. Voir l'incident documenté dans l'historique du projet si besoin de comprendre pourquoi cette règle est stricte.

## Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/issraaguedri-a11y/PI-ISRAAEYADONIALOUJAINA.git
cd PI-ISRAAEYADONIALOUJAINA

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows

# 3. Installer les dépendances (racine + dossiers spécifiques si besoin)
pip install -r requirements.txt

# 4. Placer les fichiers de données dans data/
# (les fichiers vous seront fournis séparément — voir data/README.md)
```

Pour exécuter le pipeline ETL → entrepôt → ML → application web dans l'ordre,
voir les README dédiés :
- [`01_etl/README.md`](./01_etl/README.md)
- [`02_data_warehouse/README.md`](./02_data_warehouse/README.md)
- [`04_machine_learning/README.md`](./04_machine_learning/README.md) (guide pas-à-pas complet + dépannage)
- [`05_web_app/README.md`](./05_web_app/README.md) et [`05_web_app/DEPLOY.md`](./05_web_app/DEPLOY.md)

## Livrables finaux

À la fin du projet, vous devez fournir :

1. **Le lien vers votre dépôt GitHub** (public, propre, documenté) :
   [PI-ISRAAEYADONIALOUJAINA](https://github.com/issraaguedri-a11y/PI-ISRAAEYADONIALOUJAINA).
2. **Le rapport PDF** (dans `06_rapport/`).
3. **Les slides de présentation** (dans `07_presentation/`).
4. **L'URL publique** de votre application web déployée : _à compléter une fois le déploiement Streamlit Community Cloud finalisé (voir `05_web_app/DEPLOY.md`)_.

## Composition de l'équipe

| Nom | Rôle principal | Email |
|---|---|---|
| **Israa Guedri** | Data engineering & ML — pipeline ETL, entrepôt PostgreSQL, modélisation du churn (`01_etl`, `02_data_warehouse`, `04_machine_learning`), déploiement de l'application web | _à compléter_ |
| **Eya Smeti** | Data engineering & ML — co-construction du pipeline de données et du modèle, analyse et interprétabilité (SHAP), documentation technique | _à compléter_ |
| **Donia Belamin** | Business Intelligence — visualisation Power BI, définition des KPIs métier (`03_power_bi`) | _à compléter_ |
| **Loujaina Guesmi** | Rapport & présentation — rédaction du rapport, structuration des livrables finaux (`06_rapport`, `07_presentation`) | _à compléter_ |

*Répartition proposée à partir de l'avancement réel du projet — à ajuster
librement selon l'organisation effective de l'équipe.*

## Contact tuteur

Aymen Ben Brik — _coordonnées à compléter par le tuteur_.