--[[
  Residui di formule matematiche nel PDF.

  Nei capitoli tradotti da Wikisource restano frammenti del marcatore MathML
  della fonte, del tipo `{\displaystyle \left({\frac {n}{60}}\right)}`. Pandoc
  li riconosce come TeX grezzo: nell'HTML li lascia cadere, ma nel PDF li
  passerebbe al compilatore, che si ferma («Missing $ inserted», perché
  \overbrace e simili vogliono la modalità matematica).

  Qui vengono tolti anche dal PDF, così le due versioni mostrano la stessa
  cosa. La trascrizione leggibile della formula resta nel testo, perché la
  fonte la riporta accanto al marcatore.
]]

function RawInline(grezzo)
  if grezzo.format == "tex" or grezzo.format == "latex" then
    return {}
  end
  return nil
end
