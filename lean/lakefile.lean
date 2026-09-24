import Lake
open Lake DSL

package «mystorymaker» where
  -- Sin opciones: la verificacion tiene que poder correr en una maquina limpia.

lean_lib «MyStoryMaker» where
  roots := #[`MyStoryMaker.Cronologia]

@[default_target]
lean_exe «verificar» where
  root := `Main
