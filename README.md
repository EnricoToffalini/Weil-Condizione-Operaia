# La Condition ouvrière — corpus 1951 e traduzione italiana

Questa repository contiene il master francese degli scritti raccolti in *La
Condition ouvrière* di Simone Weil, una pipeline riproducibile di acquisizione
con i controlli necessari a verificarlo, e la traduzione italiana da cui si
genera il sito di lettura.

## Edizione canonica

Il corpus corrisponde a:

> Simone Weil, *La Condition ouvrière*, texte établi par Albert Camus, Paris,
> Gallimard, 1951.

La fonte digitale primaria è [l’edizione su Wikisource francese](https://fr.wikisource.org/wiki/La_Condition_ouvri%C3%A8re),
collegata al facsimile `Weil - La Condition ouvrière, 1951.djvu`. Wikisource è
usata perché associa trascrizione, scansioni, stato di proofreading e revisioni
MediaWiki identificabili; non sostituisce il volume come riferimento
bibliografico.

L’indice Wikisource ha 17 unità numerate, ma questa repository importa solo i
16 testi di Simone Weil. L’unità 01, *Avant-propos*, firmata da Albertine
Thévenon, è deliberatamente esclusa. I numeri nei nomi dei file conservano
l’ordine dell’edizione: il primo testo incluso è quindi `02_...`, non `01_...`.

## Metodo di acquisizione

Il download non analizza il layout delle pagine web. Usa la MediaWiki Action
API ufficiale:

1. `action=query` acquisisce in una sola richiesta gli ID e i timestamp delle
   revisioni dell’indice e delle 16 sottopagine selezionate;
2. `action=parse&oldid=...` espande ciascuna transclusione ProofreadPage alla
   revisione fissata;
3. viene convertito esclusivamente il contenitore semantico
   `prp-pages-output`;
4. le risposte API complete sono salvate in `source/snapshots/*.json`;
5. revision ID, timestamp, URL e checksum SHA-256 confluiscono nel manifest e
   nel front matter dei file Markdown.

La conversione conserva paragrafi, titoli e sottotitoli, corsivi, note, tabelle,
separatori e marcatori delle pagine stampate. Questi ultimi diventano anchor e
commenti HTML non invasivi, per esempio
`<a id="p35"></a><!-- page: 35; scan: Page:.../43 -->`. Le correzioni marcate
da Wikisource con il template `coquille` conservano in un commento anche la
lezione del facsimile. La pipeline non modernizza ortografia, lessico o
punteggiatura e non espande arbitrariamente abbreviazioni.

## Installazione

Richiede Python 3.10 o successivo. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Su macOS o Linux, sostituire l’attivazione con `source .venv/bin/activate`.

## Acquisire e ricostruire

Per confrontare Wikisource con il corpus incluso:

```powershell
python scripts/fetch_wikisource.py
```

Se revisioni o resa differiscono, il comando termina senza toccare i file
canonici e lascia il candidato in `source/staging/current/`. Dopo aver esaminato
diff e snapshot, l’aggiornamento esplicito è:

```powershell
python scripts/fetch_wikisource.py --update
```

Anche con `--update`, il fetcher interrompe l’operazione se l’hash di un file
canonico non coincide con quello registrato nel manifest: una modifica manuale
non viene mai sovrascritta silenziosamente. Per registrare consapevolmente una
modifica locale si deve prima rivederla e rigenerare il manifest.

Una ricostruzione indipendente, senza modificare il corpus incluso, può essere
creata in una directory nuova o vuota:

```powershell
python scripts/fetch_wikisource.py --output-dir build/reconstruction
python scripts/validate_corpus.py --root build/reconstruction
```

Il comando rifiuta una directory di output non vuota. Il manifest può essere
ricostruito deterministicamente dai file e dagli snapshot o soltanto verificato:

```powershell
python scripts/build_manifest.py
python scripts/build_manifest.py --check
```

## Validazione e test

```powershell
python scripts/validate_corpus.py
python -m pytest
```

La validazione controlla numero di unità rispetto all’indice, corrispondenza
manifest/file, file vuoti, UTF-8, titoli e front matter, ID duplicati, ordine,
URL, revisioni, classificazione autoriale e checksum di Markdown e snapshot.
Riguarda il master francese: la traduzione italiana in `corpus/it/` non è
vincolata al manifest, ed è verificata invece da
`python scripts/build_site.py --check`.

## Il sito italiano

Il sito pubblica soltanto la traduzione italiana: `corpus/fr/` resta nel
repository come riferimento di lavoro, ma non viene renderizzato. È un libro
Quarto con un capitolo per ciascuno dei sedici scritti, tutti in pagina unica.

Le cartelle in gioco, e chi le scrive:

| cartella | che cos'è | si modifica a mano? |
| --- | --- | --- |
| `corpus/it/` | la traduzione | **sì: è qui che si scrive** |
| `site/` | configurazione, prefazione, stile, struttura | sì, per la resa |
| `site/testi/` | i capitoli del libro | no, generati da `corpus/it/` |
| `docs/` | il sito pronto, quello che GitHub Pages pubblica | no, generato da `site/` |

### Modificare la traduzione

Si lavora **sempre** in `corpus/it/`, mai in `site/testi/`: quei file vengono
riscritti a ogni generazione e ogni modifica fatta lì andrebbe perduta.

```powershell
python scripts/build_site.py    # da corpus/it/ a site/testi/
quarto preview site             # anteprima con ricarica automatica
```

Per cambiare invece come un testo è articolato — quali titoli di sezione
compaiono e dove — si modifica [`site/sezioni.yml`](site/sezioni.yml), che è
commentato, e si rigenera. La prefazione è `site/index.qmd`, i criteri
editoriali dichiarati ai lettori sono in `site/nota-al-testo.qmd`, la grafica
in `site/styles.css`.

Per verificare, senza scrivere nulla, che i capitoli generati corrispondano
ancora al corpus — è il controllo eseguito anche in CI:

```powershell
python scripts/build_site.py --check
```

### Pubblicare

GitHub Pages serve direttamente la cartella `docs/` del ramo `main`: pubblicare
significa rigenerare e fare commit.

```powershell
python scripts/build_site.py
quarto render site
git add corpus/it site/testi docs
git commit -m "aggiorna la traduzione e il sito"
git push
```

Va abilitato una sola volta in *Settings → Pages*, scegliendo come sorgente il
ramo `main` e la cartella `/docs`. La resa è versionata apposta: quello che si
vede in `docs/` è esattamente quello che è online. `.gitattributes` la segnala a
GitHub come generata, così i suoi diff restano ripiegati.

`.github/workflows/verifica.yml` non pubblica nulla: controlla soltanto che il
corpus sia coerente, che i test passino, che `site/testi/` sia allineato a
`corpus/it/` e che il sito si renderizzi.

### Che cosa fa la generazione

Il corpus non viene mai modificato. Per ogni testo lo script porta il titolo
dal front matter all'intestazione del capitolo, trasforma in cappello la nota
che nel volume del 1951 è agganciata al titolo, e livella i titoletti già
presenti nel Markdown.

Gli scritti lunghi restano in una pagina sola ma ricevono titoli di sezione
editoriali, che alimentano l'indice laterale della pagina e sono resi con la
classe `.sez-ed` perché si distinguano dal testo di Simone Weil. Dove un titolo
editoriale cade su uno stacco del volume — un filetto o un asterismo — prende il
posto dello stacco. La pagina *Nota al testo* del sito lo dichiara ai lettori.

## Struttura

```text
.
├── corpus/
│   ├── manifest.yml              # riferimento strutturale e checksum
│   ├── fr/                       # 16 testi di Simone Weil, master francese
│   └── it/                       # traduzione italiana, fonte del sito
├── source/
│   ├── snapshots/                # payload API fissati per revisione
│   └── staging/                  # candidati non applicati, ignorati da Git
├── site/                         # sorgenti del sito
│   ├── _quarto.yml               # libro Quarto, solo italiano
│   ├── index.qmd                 # prefazione
│   ├── nota-al-testo.qmd         # fonte, criteri e interventi editoriali
│   ├── sezioni.yml               # struttura interna dei testi lunghi
│   ├── styles.css                # grafica
│   └── testi/                    # capitoli generati da corpus/it/
├── docs/                         # sito reso, pubblicato da GitHub Pages
├── glossary/glossary.yml         # sola policy speciale per “malheur”
├── prompts/                      # futura pipeline di traduzione/revisione
├── scripts/                      # fetch, manifest, validazione e sito
├── src/condition_ouvriere/       # implementazione Python
└── tests/
```

Ogni scritto rimane un file Markdown completo. Una futura segmentazione per la
traduzione dovrà essere derivata e rigenerabile, mai sostituire questi master.

## Nota editoriale nota

L’header MediaWiki della sottopagina 04 (*Lettre à Boris Souvarine*) rende
l’intervallo come `p. 29--`. I marcatori ProofreadPage nel testo identificano
però le pagine stampate 29–31; `page_end: 31` è quindi ricavato da tali marcatori
e la decisione è registrata nell’item del manifest.

## Licenze e attribuzione

Il codice è MIT. La rappresentazione derivata dalla trascrizione Wikisource è
distribuita sotto CC BY-SA 4.0 con attribuzione puntuale nel manifest. I diritti
sulle opere sottostanti possono dipendere dalla giurisdizione; si veda
[`LICENSE`](LICENSE).

## Fuori ambito

Non vengono eseguite segmentazione AI, normalizzazione linguistica o
sostituzioni terminologiche automatiche. Il glossario registra soltanto
`malheur` come termine concettualmente marcato da valutare nel contesto.
