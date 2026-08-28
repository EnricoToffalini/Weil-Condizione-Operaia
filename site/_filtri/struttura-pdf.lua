--[[
  Differenze strutturali intenzionali tra il sito e il libro PDF.

  Il capitolo d'apertura si intitola «La Condizione Operaia» perché nel sito è
  la pagina iniziale; nel libro quel titolo sta già in copertina, perciò qui
  torna a chiamarsi «Prefazione» e resta fuori dall'indice. Il titolo non si
  può distinguere nel front matter di `index.qmd`: in un libro Quarto ricava i
  titoli dei capitoli prima di applicare le opzioni proprie di ciascun formato.

  La «Nota al testo» descrive il sito e deve quindi restare soltanto nella
  versione HTML. Il filtro è dichiarato esclusivamente sotto `pdf` in
  `_quarto.yml`, perciò non modifica né le pagine né la navigazione HTML.
]]

local TITOLO_APERTURA = "Prefazione"

local function titolo(intestazione)
  return pandoc.utils.stringify(intestazione.content)
end

function Pandoc(documento)
  local blocchi_pdf = pandoc.Blocks({})
  -- I capitoli confluiscono in un solo documento: il primo titolo di primo
  -- livello è quello del capitolo d'apertura.
  local apertura_attesa = true

  for _, blocco in ipairs(documento.blocks) do
    if blocco.t == "Header" and blocco.level == 1 then
      local testo = titolo(blocco)

      if testo == "Nota al testo" then
        -- È l'ultimo capitolo: scartando da qui in poi non ne rimangono nel
        -- PDF né il titolo, né il testo, né la voce nell'indice.
        break
      end

      if apertura_attesa then
        blocco.content = pandoc.Inlines({ pandoc.Str(TITOLO_APERTURA) })
        blocco.classes:insert("unnumbered")
        blocco.classes:insert("unlisted")
        apertura_attesa = false
      end
    end

    blocchi_pdf:insert(blocco)
  end

  documento.blocks = blocchi_pdf
  return documento
end
