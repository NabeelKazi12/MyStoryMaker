/-
  Invariantes de la cronologia de una novela de MyStoryMaker.

  Este fichero NO se genera: es el que dice que tiene que cumplirse. Los datos llegan en
  `Datos.lean`, que si se genera desde SQLite en cada verificacion.

  Dos invariantes, que son los dos que SPEC-003 RF-LEAN-02 exige como minimo:

  1. `orden_temporal`: los eventos respetan el orden temporal declarado.
  2. `edad_no_negativa`: nadie participa en un evento anterior a su nacimiento.

  Un tercero, `no_ubicuidad`, queda declarado porque es barato sobre esta estructura y
  porque es la incoherencia que mas facilmente se cuela en una novela de recuerdos, donde
  el mismo verano se cuenta dos veces desde sitios distintos.
-/

import MyStoryMaker.Datos

namespace MyStoryMaker

/-- Los eventos estan ordenados de forma no decreciente por `momento`. -/
def orden_temporal (es : List Evento) : Prop :=
  List.Chain' (fun a b => a.momento ≤ b.momento) es

/-- Edad de un personaje en un momento dado. Puede salir negativa: eso es el fallo. -/
def edad (p : Personaje) (momento : Int) : Int :=
  momento - p.anio_de_nacimiento

/-- Nadie participa en un evento anterior a su nacimiento. -/
def edad_no_negativa (es : List Evento) (ps : List Personaje) : Prop :=
  ∀ e ∈ es, ∀ pid ∈ e.personajes,
    ∀ p ∈ ps, p.personaje_id = pid → 0 ≤ edad p e.momento

/-- Un personaje no esta en dos lugares distintos en el mismo momento. -/
def no_ubicuidad (es : List Evento) : Prop :=
  ∀ a ∈ es, ∀ b ∈ es,
    a.momento = b.momento →
      ∀ pid ∈ a.personajes, pid ∈ b.personajes → a.lugar_id = b.lugar_id

/-- La cronologia es coherente cuando cumple los tres. -/
def cronologia_coherente (es : List Evento) (ps : List Personaje) : Prop :=
  orden_temporal es ∧ edad_no_negativa es ps ∧ no_ubicuidad es

/-
  La verificacion concreta: sobre los datos generados, los tres invariantes se deciden
  por evaluacion. `decide` falla en compilacion si la cronologia de la novela los viola,
  y ese fallo es el que impide publicar la version (RF-LEAN-04).
-/
theorem cronologia_de_esta_novela_es_coherente :
    cronologia_coherente eventos personajes := by
  unfold cronologia_coherente orden_temporal edad_no_negativa no_ubicuidad
  decide

end MyStoryMaker
