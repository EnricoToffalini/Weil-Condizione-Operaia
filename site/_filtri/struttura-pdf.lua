--[[
  Differenze strutturali intenzionali tra il sito e il libro PDF.

  La «Nota al testo» descrive il sito e deve quindi restare soltanto nella
  versione HTML. La Prefazione, invece, resta nel libro ma non deve comparire
  nell'indice del PDF. Il filtro è dichiarato esclusivamente sotto `pdf` in
  `_quarto.yml`, perciò non modifica né le pagine né la navigazione HTML.
]]

local function titolo(intestazione)
  return pandoc.utils.stringify(intestazione.content)
end

function Pandoc(documento)
  local blocchi_pdf = pandoc.Blocks({})

  for _, blocco in ipairs(documento.blocks) do
    if blocco.t == "Header" and blocco.level == 1 then
      local testo = titolo(blocco)

      if testo == "Nota al testo" then
        -- È l'ultimo capitolo: scartando da qui in poi non ne rimangono nel
        -- PDF né il titolo, né il testo, né la voce nell'indice.
        break
      end

      if testo == "Prefazione" then
        blocco.classes:insert("unnumbered")
        blocco.classes:insert("unlisted")
      end
    end

    blocchi_pdf:insert(blocco)
  end

  documento.blocks = blocchi_pdf
  return documento
end
