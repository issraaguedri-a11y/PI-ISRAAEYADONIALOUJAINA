-- fit_tables.lua
--
-- Pandoc, pour les tableaux "pipe" (Markdown simple), ne transmet pas
-- toujours de largeur de colonne au writer LaTeX. Le writer choisit alors
-- des colonnes de largeur "naturelle" (l/c/r), qui s'étendent hors marge
-- dès qu'une cellule contient du texte long. Ce filtre force des largeurs
-- relatives explicites (fractions de \linewidth) sur toutes les colonnes de
-- tous les tableaux, réparties selon la longueur du texte d'en-tête pour un
-- rendu proportionné plutôt qu'uniforme.

function Table(tbl)
  local n = #tbl.colspecs
  if n == 0 then return tbl end

  -- Largeur totale utilisable (petite marge de sécurité)
  local total = 0.94

  -- Largeur de chaque colonne = la cellule la plus longue de la colonne
  -- (en-tête INCLUS mais aussi et surtout le corps du tableau), pas
  -- seulement l'en-tête -- une colonne "Modèle" (en-tête court) contenant
  -- "Régression logistique" (contenu long) doit rester large.
  local max_len = {}
  for i = 1, n do max_len[i] = 0 end

  local function scan_row(row)
    for i, cell in ipairs(row.cells) do
      if i <= n then
        local text = pandoc.utils.stringify(cell.contents)
        -- longueur du mot le plus long de la cellule (pas la cellule entière) :
        -- une cellule longue mais faite de mots courts se laisse retourner à
        -- la ligne sans problème ; c'est le mot le plus long qui contraint
        -- la largeur minimale réellement nécessaire pour éviter la césure.
        local longest_word = 0
        for word in text:gmatch("%S+") do
          if #word > longest_word then longest_word = #word end
        end
        local total_len = #text
        -- on retient une longueur "cible" entre le mot le plus long (plancher)
        -- et une fraction de la longueur totale (plafond raisonnable)
        local target = math.max(longest_word, math.min(total_len, 22))
        if target > max_len[i] then max_len[i] = target end
      end
    end
  end

  for _, row in ipairs(tbl.head.rows) do scan_row(row) end
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do scan_row(row) end
  end

  local sum = 0
  for i = 1, n do
    if max_len[i] < 4 then max_len[i] = 4 end  -- longueur plancher (ex. colonnes de %)
  end

  -- Amortissement (racine carrée) : sans cela, une colonne à contenu très
  -- long (ex. "Modèle") écrase disproportionnellement les colonnes courtes
  -- (ex. "F1", "Rappel"), qui devenaient illisiblement étroites malgré un
  -- contenu propre (ex. "0,905"). La racine carrée resserre l'écart entre
  -- colonnes longues et courtes tout en conservant leur ordre relatif.
  local weight = {}
  for i = 1, n do
    weight[i] = math.sqrt(max_len[i])
    sum = sum + weight[i]
  end

  -- Plancher minimum : chaque colonne garde au moins 8 % de la largeur
  -- totale même si son poids relatif est faible, pour éviter tout écrasement.
  local min_frac = 0.08
  local new_colspecs = {}
  for i = 1, n do
    local align = tbl.colspecs[i][1]
    local width = math.max(total * weight[i] / sum, total * min_frac / n)
    new_colspecs[i] = {align, width}
  end

  -- Normalisation finale pour que la somme reste exactement `total`
  local width_sum = 0
  for i = 1, n do width_sum = width_sum + new_colspecs[i][2] end
  for i = 1, n do
    new_colspecs[i][2] = new_colspecs[i][2] * total / width_sum
  end

  tbl.colspecs = new_colspecs
  return tbl
end

-- Les chemins de fichiers et identifiants longs en code inline (ex.
-- `04_machine_learning/src/prepare_data.py`) n'ont aucun point de coupure
-- pour LaTeX et débordent donc de la marge. On insère un espace de largeur
-- nulle (U+200B) après chaque "/" et "_", invisible mais reconnu par
-- XeLaTeX comme point de coupure de ligne valide.
function Code(elem)
  local text = elem.text
  text = text:gsub("([/_])", "%1\u{200B}")
  elem.text = text
  return elem
end
