--[[
  Immagini remote nel PDF.

  I capitoli rimandano alle immagini di Wikimedia con il loro indirizzo
  completo: nell'HTML si caricano dalla rete e va bene così. Per il PDF, LaTeX
  vuole invece un file locale con l'estensione giusta; l'indirizzo di Wikimedia
  finisce con una stringa di parametri (`?utm_source=...`), il nome che ne
  ricava Pandoc resta senza estensione e la compilazione si ferma con
  «Cannot determine size of graphic».

  Questo filtro scarica ogni immagine una volta sola in `site/_immagini/`,
  con l'estensione giusta, e riscrive il rimando. La cartella è una cache:
  si può cancellare, viene ricostruita al render successivo (e finché è piena
  il PDF si compone anche senza rete).

  Le formule rese da Wikimedia sono SVG e non sono convertibili in PDF senza
  rsvg-convert, che qui non c'è: quelle immagini vengono tolte dal PDF. Non si
  perde nulla di leggibile, perché la trascrizione della formula è comunque
  nel capoverso che le precede.
]]

local sistema = pandoc.system
local mediabag = pandoc.mediabag

-- Il tipo dichiarato non è affidabile: Pandoc lo ricava dall'estensione
-- dell'indirizzo, e qui l'estensione è seguita dai parametri `?utm_source=...`,
-- così ogni immagine risulta «text/plain». Il formato si riconosce invece dai
-- primi byte del file.
local FIRME = {
  { firma = "\137PNG\r\n\26\n", estensione = ".png" },
  { firma = "\255\216\255", estensione = ".jpg" },
  { firma = "GIF87a", estensione = ".gif" },
  { firma = "GIF89a", estensione = ".gif" },
}

local ESTENSIONI = { ".png", ".jpg", ".gif" }

local function estensione_di(contenuto)
  for _, formato in ipairs(FIRME) do
    if contenuto:sub(1, #formato.firma) == formato.firma then
      return formato.estensione
    end
  end
  return nil
end

local CARTELLA = sistema.get_working_directory() .. "/_immagini"
local risolte = {}

local function e_remota(percorso)
  return percorso:match("^https?://") ~= nil
end

local function gia_scaricata(radice)
  for _, estensione in ipairs(ESTENSIONI) do
    local percorso = CARTELLA .. "/" .. radice .. estensione
    local file = io.open(percorso, "rb")
    if file then
      file:close()
      return percorso
    end
  end
  return nil
end

-- Wikimedia respinge le richieste troppo ravvicinate rispondendo con una
-- pagina di errore al posto dell'immagine: dopo tre o quattro file di fila
-- comincia a rifiutare. Si aspetta e si riprova; l'attesa è un ciclo a vuoto
-- perché Lua di Pandoc non ha una funzione di pausa. Riguarda soltanto il
-- primo render: dopo, le immagini arrivano dalla cache.
local TENTATIVI = 3

local function attendi(secondi)
  local fine = os.time() + secondi
  while os.time() < fine do end
end

local function preleva(url)
  for tentativo = 1, TENTATIVI do
    if tentativo > 1 then
      attendi(2 * (tentativo - 1))
    end
    local riuscito, _, contenuto = pcall(mediabag.fetch, url)
    if riuscito and contenuto then
      local estensione = estensione_di(contenuto)
      if estensione then
        return contenuto, estensione
      end
      -- Un SVG (le formule rese da Wikimedia) arriva davvero: è inutile
      -- riprovare, semplicemente non si può mettere in un PDF.
      if contenuto:match("^%s*<%?xml") or contenuto:match("^%s*<svg") then
        return nil
      end
    end
  end
  return nil
end

-- Restituisce il percorso locale dell'immagine, oppure nil se non è
-- utilizzabile nel PDF (formato non convertibile o scaricamento fallito).
local function scarica(url)
  if risolte[url] ~= nil then
    return risolte[url]
  end

  local radice = pandoc.utils.sha1(url)
  local percorso = gia_scaricata(radice)

  if not percorso then
    local contenuto, estensione = preleva(url)
    if not contenuto then
      io.stderr:write("[immagini-pdf] non recuperata, resta fuori dal PDF: " ..
        url .. "\n")
      risolte[url] = false
      return nil
    end

    sistema.make_directory(CARTELLA, true)
    percorso = CARTELLA .. "/" .. radice .. estensione
    local file = assert(io.open(percorso, "wb"))
    file:write(contenuto)
    file:close()
  end

  risolte[url] = percorso
  return percorso
end

function Image(immagine)
  if not e_remota(immagine.src) then
    return nil
  end
  local percorso = scarica(immagine.src)
  if not percorso then
    return {}
  end
  immagine.src = percorso
  return immagine
end

-- Un rimando che conteneva soltanto l'immagine tolta resta vuoto: si elimina
-- anche quello, altrimenti nel PDF compare un \href senza testo.
function Link(rimando)
  if #rimando.content == 0 then
    return {}
  end
  return nil
end
