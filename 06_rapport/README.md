# 06 — Rapport final

Rapport final du projet (30 pages), au format **PDF** et **LaTeX**, structuré
selon le plan recommandé par le guide du projet (`00_documentation/4_guide_etudiant.md`,
section "Étape 7").

## Fichiers

```
06_rapport/
├── rapport_final.pdf         # le rapport final, prêt à soumettre
├── figures/                   # toutes les images utilisées (captures d'écran, diagrammes, graphiques)
└── sources/
    ├── metadata.yaml          # titre, auteurs, date (UTF-8 propre — voir note ci-dessous)
    ├── rapport_source.md      # source Markdown unique (assemblage des 5 parties)
    ├── part1_intro_donnees.md à part5_web_limites_conclusion.md  # sections sources, éditables séparément
    ├── template.tex           # template LaTeX (dérivé de 00_documentation/template.tex, avec support images ajouté)
    ├── fit_tables.lua         # filtre Pandoc : empêche tableaux et chemins de fichiers longs de déborder de la page
    └── rapport_final.tex      # source LaTeX autonome, compilable indépendamment de Pandoc (ex. sur Overleaf)
```

⚠️ **Ne pas passer le titre/auteurs via `-V title="..."` en ligne de commande** :
les caractères accentués (é, è...) peuvent être corrompus selon l'encodage du
shell utilisé. Toujours passer par `sources/metadata.yaml`, dont l'encodage
UTF-8 est garanti.

## Contenu du rapport

1. Résumé exécutif
2. Introduction et contexte
3. Description et exploration des données
4. Architecture de la solution
5. ETL et modélisation dimensionnelle
6. Analyses BI et tableaux de bord Power BI
7. Modélisation Machine Learning
8. Interface web et déploiement
9. Limites et perspectives
10. Conclusion
11. Annexes (glossaire, structure du dépôt, outils utilisés)

## Recompiler le PDF

### Option A — depuis le Markdown (recommandé, plus simple à éditer)

Éditez les fichiers `sources/part*.md` (un fichier par grande section), puis :

```bash
cd 06_rapport
cat sources/part1_intro_donnees.md sources/part2_architecture_etl.md \
    sources/part3_powerbi.md sources/part4_ml.md \
    sources/part5_web_limites_conclusion.md > sources/rapport_source.md

pandoc sources/metadata.yaml sources/rapport_source.md \
  --from markdown+smart \
  --template=sources/template.tex \
  --lua-filter=sources/fit_tables.lua \
  --pdf-engine=xelatex \
  --toc --toc-depth=2 \
  -o rapport_final.pdf
```

**Dépendances** (Ubuntu/Debian) :
```bash
apt-get install -y pandoc texlive-xetex texlive-lang-french \
  texlive-latex-extra texlive-fonts-recommended lmodern
```

### Option B — directement depuis le `.tex`

Pratique pour éditer sur [Overleaf](https://overleaf.com) sans installer de chaîne LaTeX localement, ou pour des retouches fines de mise en page.

```bash
cd 06_rapport/sources
cp -r ../figures .
xelatex rapport_final.tex
xelatex rapport_final.tex   # 2 passes nécessaires pour la table des matières
```

⚠️ Si vous éditez `rapport_final.tex` directement (option B), pensez à répercuter
manuellement vos changements dans les fichiers Markdown source si vous
comptez continuer à utiliser l'option A par la suite — les deux ne se
synchronisent pas automatiquement une fois le `.tex` édité à la main.

## Note sur les figures

Les captures d'écran de l'application web et de Power BI reflètent l'état
du projet à la date de rédaction. Si l'application ou le rapport Power BI
évoluent significativement, il est recommandé de régénérer ces captures
avant la soumission finale (voir `05_web_app/README.md` et
`03_power_bi/README.md` pour relancer l'application/le rapport).

Les diagrammes (`architecture.png`, `star_schema.png`) sont générés par
script Python (Graphviz) — modifiables en éditant les scripts correspondants
si le schéma de données ou l'architecture évolue.
