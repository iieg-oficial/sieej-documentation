### Archivos de contexto de sesión

Viven en `docs/session-context/` y se nombran:

```
contexto-sesion-<AAAA-MM-DD>-<tema-en-kebab-case>.md
```

El tema **no es opcional**: es lo que evita que dos sesiones del mismo día se pisen al llegar a
`main` o al servidor. Con solo la fecha, la segunda sobrescribe a la primera sin que nadie lo
note, y se pierde el registro. El tema además hace legible el directorio: se sabe de qué trata
cada archivo sin abrirlo.

- La fecha es la del **inicio** de la sesión. Si abarca varios días, el título del documento lo
  dice (`(2026-08-26 al 2026-08-27)`), el nombre no.
- El tema es corto y describe el trabajo, no la rama: `visor-diagramas`, `fuentes-vivas`,
  `tunel-ssh`.
- Un contexto general de proyecto, sin día concreto, usa el mes: `contexto-sesion-2026-08-landing-sieej.md`.
- **Nunca se sobrescribe uno existente.** Si hay que corregir una sesión pasada, se edita ese
  archivo dejando constancia de la corrección, o se escribe uno nuevo que la deje sin efecto y
  lo diga explícitamente.
- Al renombrar uno, hay que actualizar las referencias cruzadas: estos documentos se citan entre
  sí.
- Revisar el archivo contra la regla de [credenciales](credenciales.md) antes de commitear.
