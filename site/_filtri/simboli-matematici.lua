--[[
  Quattro segni dei «Frammenti» che nessun carattere da testo disegna: il
  cerchio puntato e le graffe orizzontali con cui Simone Weil raggruppava i
  termini delle formule. Nell'HTML il browser li pesca da un carattere di
  scorta; nel PDF resterebbero buchi bianchi, perché Linux Libertine non li
  ha. Qui vengono resi con i corrispondenti simboli matematici di LaTeX.

  Si potrebbe fare in preambolo con `newunicodechar`, ma è un pacchetto in
  più da installare: così il PDF si compone con quello che TinyTeX ha già.
]]

local SEGNI = {
  ["⊙"] = "\\ensuremath{\\odot}",
  ["⏜"] = "\\ensuremath{\\frown}",
  ["⏝"] = "\\ensuremath{\\smile}",
  ["⏞"] = "\\ensuremath{\\overbrace{\\hspace{1.5em}}}",
}

-- Divide il testo nei pezzi separati dai segni, sostituendo ogni segno con la
-- sua resa matematica. Restituisce nil se non ce n'è nessuno, così l'elemento
-- resta com'è.
local function spezza(testo)
  local pezzi = {}

  while true do
    local inizio, fine, segno
    for candidato in pairs(SEGNI) do
      local i, f = testo:find(candidato, 1, true)
      if i and (not inizio or i < inizio) then
        inizio, fine, segno = i, f, candidato
      end
    end
    if not inizio then
      break
    end
    if inizio > 1 then
      pezzi[#pezzi + 1] = pandoc.Str(testo:sub(1, inizio - 1))
    end
    pezzi[#pezzi + 1] = pandoc.RawInline("tex", SEGNI[segno])
    testo = testo:sub(fine + 1)
  end

  if #pezzi == 0 then
    return nil
  end
  if testo ~= "" then
    pezzi[#pezzi + 1] = pandoc.Str(testo)
  end
  return pezzi
end

function Str(elemento)
  return spezza(elemento.text)
end
