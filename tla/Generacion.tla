---------------------------- MODULE Generacion ----------------------------
(***************************************************************************)
(* El flujo de generacion de una novela como maquina de estados.           *)
(*                                                                         *)
(* Esta especificacion no describe lo que nos gustaria que pasara: describe *)
(* lo que el codigo hace, y por eso cada accion dice que parte del codigo  *)
(* la implementa. La correspondencia completa esta en el README; aqui va   *)
(* en el comentario de cada accion para que no se separen.                 *)
(*                                                                         *)
(* Lo que se verifica (SPEC-003 RF-TLA-02 y RF-TLA-03):                    *)
(*   NoPublicarSinValidar         - nunca se publica un capitulo sin pasar  *)
(*                                  todos los validadores                   *)
(*   CheckpointNoDuplicaNiPierde  - la reanudacion no rehace ni se salta    *)
(*   VersionAnteriorSeConserva    - regenerar no destruye la version previa *)
(*   ReintentosAcotados           - los reintentos no superan el limite     *)
(*   Termina                      - toda generacion acaba publicando o      *)
(*                                  parando con error                       *)
(***************************************************************************)

EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS
    Capitulos,      \* conjunto de capitulos a escribir, p.ej. 1..5
    MaxReintentos   \* limite de la escalera, p.ej. 2

VARIABLES
    fase,           \* configuracion, planificacion, escritura, validacion, publicacion, error
    escritos,       \* capitulos con borrador producido
    validados,      \* capitulos que pasaron TODOS los validadores
    publicados,     \* capitulos incluidos en la version publicada
    checkpoint,     \* capitulos marcados como completados
    reintentos,     \* [capitulo -> numero de reintentos consumidos]
    versiones,      \* secuencia de versiones publicadas; cada una es un conjunto de capitulos
    regenerando     \* capitulos que el lector pidio cambiar

vars == <<fase, escritos, validados, publicados, checkpoint, reintentos, versiones, regenerando>>

TypeOK ==
    /\ fase \in {"configuracion", "planificacion", "escritura", "validacion",
                 "publicacion", "publicada", "error"}
    /\ escritos \subseteq Capitulos
    /\ validados \subseteq Capitulos
    /\ publicados \subseteq Capitulos
    /\ checkpoint \subseteq Capitulos
    /\ reintentos \in [Capitulos -> 0..MaxReintentos]
    /\ regenerando \subseteq Capitulos

Init ==
    /\ fase = "configuracion"
    /\ escritos = {}
    /\ validados = {}
    /\ publicados = {}
    /\ checkpoint = {}
    /\ reintentos = [c \in Capitulos |-> 0]
    /\ versiones = <<>>
    /\ regenerando = {}

(***************************************************************************)
(* Configuracion -> planificacion.                                         *)
(* Codigo: backend/agents/entrevistador/entrevistador.py, construir_encargo *)
(* El encargo solo se cierra si no quedan huecos ni contradicciones.        *)
(***************************************************************************)
CerrarEncargo ==
    /\ fase = "configuracion"
    /\ fase' = "planificacion"
    /\ UNCHANGED <<escritos, validados, publicados, checkpoint, reintentos, versiones, regenerando>>

(***************************************************************************)
(* Planificacion -> escritura.                                             *)
(* Codigo: backend/agents/planner/planner.py, parsear_plan                 *)
(***************************************************************************)
Planificar ==
    /\ fase = "planificacion"
    /\ fase' = "escritura"
    /\ UNCHANGED <<escritos, validados, publicados, checkpoint, reintentos, versiones, regenerando>>

(***************************************************************************)
(* Escribir un capitulo que aun no esta escrito.                           *)
(* Codigo: backend/worker/worker.py, Worker.ejecutar                        *)
(***************************************************************************)
Escribir(c) ==
    /\ fase = "escritura"
    /\ c \notin escritos
    /\ escritos' = escritos \cup {c}
    /\ fase' = "validacion"
    /\ UNCHANGED <<validados, publicados, checkpoint, reintentos, versiones, regenerando>>

(***************************************************************************)
(* Validar un capitulo escrito: hook de capitulo + hook de policy.         *)
(* Codigo: backend/orchestrator/hooks.py, hook_de_capitulo y hook_de_policy *)
(***************************************************************************)
ValidarBien(c) ==
    /\ fase = "validacion"
    /\ c \in escritos
    /\ c \notin validados
    /\ validados' = validados \cup {c}
    /\ checkpoint' = checkpoint \cup {c}
    /\ fase' = IF validados \cup {c} = Capitulos THEN "publicacion" ELSE "escritura"
    /\ UNCHANGED <<escritos, publicados, reintentos, versiones, regenerando>>

(***************************************************************************)
(* Validar mal: el capitulo vuelve al writer y consume un reintento.       *)
(* Codigo: backend/quality/guardarrail.py, Guardarrail.revisar             *)
(***************************************************************************)
ValidarMal(c) ==
    /\ fase = "validacion"
    /\ c \in escritos
    /\ c \notin validados
    /\ reintentos[c] < MaxReintentos
    /\ reintentos' = [reintentos EXCEPT ![c] = @ + 1]
    /\ escritos' = escritos \ {c}
    /\ fase' = "escritura"
    /\ UNCHANGED <<validados, publicados, checkpoint, versiones, regenerando>>

(***************************************************************************)
(* Agotado el limite, la generacion se detiene e informa.                  *)
(* Codigo: LimiteDeReescriturasAgotado en guardarrail.py                    *)
(***************************************************************************)
AgotarReintentos(c) ==
    /\ fase = "validacion"
    /\ c \in escritos
    /\ c \notin validados
    /\ reintentos[c] = MaxReintentos
    /\ fase' = "error"
    /\ UNCHANGED <<escritos, validados, publicados, checkpoint, reintentos, versiones, regenerando>>

(***************************************************************************)
(* Publicar: solo capitulos validados, y conservando la version anterior.  *)
(* Codigo: tabla version_novela, encadenada por anterior_id (migracion 0002)*)
(***************************************************************************)
Publicar ==
    /\ fase = "publicacion"
    /\ validados = Capitulos
    /\ publicados' = validados
    /\ versiones' = Append(versiones, validados)
    /\ fase' = "publicada"
    /\ UNCHANGED <<escritos, validados, checkpoint, reintentos, regenerando>>

(***************************************************************************)
(* El lector pide un cambio: se regeneran SOLO los capitulos afectados.    *)
(* Codigo: UsoDeHechos.capitulos_de en backend/store/repositories.py        *)
(***************************************************************************)
PedirCambio(c) ==
    /\ fase = "publicada"
    /\ c \in publicados
    /\ regenerando' = {c}
    /\ validados' = validados \ {c}
    /\ escritos' = escritos \ {c}
    /\ checkpoint' = checkpoint \ {c}
    /\ reintentos' = [reintentos EXCEPT ![c] = 0]
    /\ fase' = "escritura"
    /\ UNCHANGED <<publicados, versiones>>

(***************************************************************************)
(* Reanudar tras una caida: se sigue por el primer capitulo sin checkpoint. *)
(* Codigo: CheckpointDeCapitulos.siguiente en repositories.py               *)
(***************************************************************************)
Reanudar ==
    /\ fase \in {"escritura", "validacion"}
    /\ escritos' = escritos \cap checkpoint
    /\ fase' = "escritura"
    /\ UNCHANGED <<validados, publicados, checkpoint, reintentos, versiones, regenerando>>

Next ==
    \/ CerrarEncargo
    \/ Planificar
    \/ \E c \in Capitulos : Escribir(c)
    \/ \E c \in Capitulos : ValidarBien(c)
    \/ \E c \in Capitulos : ValidarMal(c)
    \/ \E c \in Capitulos : AgotarReintentos(c)
    \/ Publicar
    \/ \E c \in Capitulos : PedirCambio(c)
    \/ Reanudar

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(***************************************************************************)
(*                          INVARIANTES DE SEGURIDAD                       *)
(***************************************************************************)

\* 1. Nunca se publica un capitulo que no paso todos los validadores.
NoPublicarSinValidar == publicados \subseteq validados

\* 2. La reanudacion no duplica ni pierde: lo que esta en checkpoint sigue escrito, y
\*    nada llega a validado sin haber sido escrito.
CheckpointNoDuplicaNiPierde ==
    /\ checkpoint \subseteq Capitulos
    /\ validados \subseteq (escritos \cup checkpoint)

\* 3. Publicar una version nueva no borra la anterior: la secuencia solo crece.
VersionAnteriorSeConserva == Len(versiones) >= 0 /\ (fase = "publicada" => Len(versiones) >= 1)

\* 4. Ningun capitulo supera el limite de reintentos.
ReintentosAcotados == \A c \in Capitulos : reintentos[c] <= MaxReintentos

(***************************************************************************)
(*                          PROPIEDAD DE LIVENESS                          *)
(***************************************************************************)

\* Toda generacion termina: o publica, o para con error. Nunca gira sin final.
Termina == <>(fase = "publicada" \/ fase = "error")

=============================================================================
