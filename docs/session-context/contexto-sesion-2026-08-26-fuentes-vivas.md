# Contexto de sesión — Fuentes vivas, etapas y documentación (2026-08-26 al 2026-08-27)

> Complementa a `docs/session-context/contexto-sesion-2026-08-landing-sieej.md` (contexto general del
> proyecto). Cubre la sesión en que las fuentes de producción dejaron de estar bloqueadas y la
> Fase 5 pasó de "todo pendiente" a "casi cerrada". Describe el trabajo de **cada rama creada**,
> no repite un archivo por rama.
>
> **Deja sin efecto la premisa central de `contexto-sesion-2026-08-19-tunel-ssh.md`**: ni
> Airflow ni PostgreSQL necesitan túnel SSH. Ambos responden directo por IP con la VPN activa.
> Ese archivo **no está en `main`**: vive solo en las ramas borrador #36–#39, así que la
> referencia no resuelve hasta que alguna de ellas se mergee o se cierre.

## Punto de partida

La sesión abrió con un `/resume` y la pregunta de cómo recuperar el contexto. El tablero traía
la Fase 5 completa en `[ ]`, con cuatro PR en borrador (#36–#39) atoradas desde el 2026-08-19
por tres bloqueadores: el `sshd` de `iieg-db-etl` rechazaba el reenvío de puertos, no había
credenciales de solo lectura, y el cliente de Airflow apuntaba a una API retirada.

## El hallazgo que reordenó todo

El usuario indicó que Airflow **no** debía consultarse por SSH, sino directo contra
`http://10.13.201.115:8080`. La comprobación invirtió la premisa registrada:

| Destino | Resultado |
|---|---|
| `http://10.13.201.115:8080/api/v2/version` | **200** — Airflow **3.1.1** |
| `http://10.13.201.115:8080/api/v1/dags` | 404 — la API v1 ya no existe |
| `10.13.201.115:22` y `10.13.203.158:49222` (SSH) | timeout |

Es decir: el túnel a Airflow nunca fue necesario, y ese día SSH ni siquiera funcionaba. Más
tarde, con la VPN del usuario activa, **también Postgres resultó alcanzable directo**
(`10.13.203.158:5432`), lo que dejó el túnel sin ningún uso. La premisa de T5.1.1 cambió dos
veces: primero se creyó que todo iba por SSH, luego que solo Postgres, y al final que nada.

## Qué se hizo, rama por rama

### `feature/datalayer-tunel-ssh` (PR #36) y `chore/datalayer-tunel-config` (PR #37)

Se corrigieron para reflejar el acceso directo a Airflow: el script quedó solo para Postgres,
`AIRFLOW_BASE_URL` pasó a la URL directa, y se añadió una nota de corrección al contexto del
2026-08-19 para que la premisa vieja no se heredara. Ambas siguen en borrador: el acceso
directo a Postgres las volvió obsoletas *después* de esa corrección (ver "Pendientes").

### `feature/datalayer-airflow-v3` (PR #42, issue #41) — T5.1.5

Migración del cliente a la API v2 de Airflow 3. El contrato se verificó contra el
`/openapi.json` público del propio servidor, no contra documentación de terceros:

- La seguridad es `OAuth2PasswordBearer`/`HTTPBearer`: **solo JWT**. HTTP Basic se ignora por
  completo (`401 Not authenticated`, sin `WWW-Authenticate`), así que las credenciales correctas
  no habrían bastado sin migrar el cliente.
- `POST /auth/token` con `{"username","password"}` devuelve `access_token`; con `{}` responde
  `400 Username and password must be provided`.
- `order_by=-execution_date` dejó de ser válido: Airflow 3 retiró ese atributo. Se usa
  `-run_after`, y la fecha de la última corrida cae a `run_after` porque `logical_date` es
  nullable (corridas manuales o por asset).
- Variables nuevas: `AIRFLOW_TOKEN` (JWT ya emitido, opcional) y `AIRFLOW_TOKEN_PATH`.

35 pruebas en verde. Contra producción con credenciales falsas el fallo cae exactamente en
`/auth/token` con 401 —protocolo correcto, credenciales incorrectas—, y con las reales devuelve
**53 DAGs**.

### `feature/datalayer-etapas-pipeline` (PR #44, issue #43) — T5.1.6

El cruce reportaba **86 pipelines donde hay 33**. `_normalizar_dag_id()` quitaba el prefijo
`etl_` pero no el sufijo de etapa, así que `etl_denue_update` nunca empataba con la base `denue`
y cada conjunto entraba dos o tres veces. Lo grave no era el conteo inflado: **ninguna** de las
86 entradas tenía DAG y base a la vez, de modo que la landing no habría mostrado estado de
ejecución para ningún pipeline documentado.

Segundo motivo acumulado: los alias de nombre (`ALIAS_HTML_A_BD`) solo se aplicaban a los HTML,
no a los `dag_id`. Por eso `etl_censos_economicos_bootstrap` —plural, como está en Airflow— no
empataba con la base `censo_economico`, en singular.

La corrección: `partir_dag_id()` separa `(pipeline, etapa)` resolviendo alias,
`emparejar_dags()` agrupa y ordena las etapas, `Pipeline.dag` pasó a `Pipeline.etapas:
list[Dag]`, y el catálogo del sitio lista cada etapa con nombre legible en español, su DAG, si
está pausada y el resultado de su última corrida.

| Métrica | Antes | Después |
|---|---|---|
| `pipelines` | 86 | **33** |
| `dags_emparejados` | 53, ninguno unido a su base | **53** |
| `pipelines_sin_html` | 64 | **11** |

### `docs/html-pipelines-faltantes` (PR #45, issue #47) — T5.2

De los 11 pipelines sin ficha, **10 sí tienen README** en `origin/main` de `ETL-SIEEJ`; el único
ausente es `nacimientos_dgis`. `scripts/generar_doc_pipeline.py` genera cada documento
homologado: hereda **literalmente** el `<head>`, los estilos y el script de zoom de un documento
ya publicado, de modo que no puedan divergir del formato.

| Sección | Fuente |
|---|---|
| Descripción, Fuente de datos, Variables de entorno | README del pipeline |
| Tablas (descripción y filas) | Producción: `obj_description` y `COUNT(*)` exacto |
| Vistas y columnas | Producción: `pg_class` / `pg_attribute` |
| DAGs (descripción y programación) | API de Airflow |
| Diagrama entidad-relación | `assets/erd.svg` del pipeline |

Resultado: 22 → **32 documentos**, `pipelines_sin_html` de 11 a **1**.

### `fix/docs-enlace-indice` (PR #46, issue #48) — T5.3

El botón «Índice de pipelines» de cada documento apunta a `index.html`, que `copy-docs.mjs`
excluye a propósito. Defecto **preexistente** —los 22 documentos viejos ya lo traían— que nadie
notó porque nginx lo salva en producción con un 301, mientras `astro dev` responde 404. Se
reescribe el enlace a `/#catalogo` en las copias servidas; los documentos fuente quedan
intactos como paquete autónomo.

## Decisiones y matices que vale la pena recordar

- **Airflow directo, no por túnel.** `AIRFLOW_BASE_URL=http://10.13.201.115:8080`. El túnel SSH
  quedó reducido a Postgres y luego, con la VPN, a nada.
- **La URL literal vive en `.env.example`** porque el repositorio es privado; si eso cambia,
  debe volver a ser un marcador de posición.
- **Credenciales en uso son administrativas, no de solo lectura** (las de Airflow, además, con
  usuario y contraseña idénticos; viven en el `.env`, que no se versiona, y aquí no se
  reproducen). El riesgo se acota porque toda conexión se abre con
  `default_transaction_read_only=on` —comprobado atacándolo: el servidor rechaza `CREATE TABLE`
  y `UPDATE` con SQLSTATE `25006`— y el cliente de Airflow solo hace GET salvo el POST del
  token. Aun así, el `builder` periódico merece un rol de solo lectura propio.
- **`consultar_bd()` es todo-o-nada**: abre una conexión por base y si cualquiera de las 35
  falla, la fuente entera se reporta caída con cero bases. Con una VPN intermitente —se cayó a
  mitad de una corrida— eso es probable. Vale una tarea para tolerar fallas por base.
- **El generador de documentación hereda la plantilla en vez de copiarla a mano.** El `erd.svg`
  del repositorio no trae `viewBox`, que es justo lo que lee el control de zoom: se deriva de
  `width`/`height`.
- **`general-documentation/` no está bajo control de versiones.** Los 10 documentos nuevos y las
  32 navegaciones reescritas viven solo en disco; se respaldó el directorio antes de escribir
  (`html-documents.respaldo-20260827-113528`).
- **Cada documento incrusta la navegación completa**, así que agregar pipelines obliga a
  reescribir la barra lateral y los enlaces anterior/siguiente en todos.

## Errores cometidos en esta sesión, y cómo se repararon

1. **Dos PR sin issue.** #45 y #46 se abrieron directo, rompiendo la convención «una tarea = un
   issue = una rama = una PR». Se abrieron los issues #47 y #48 y se enlazaron con `Closes` en
   los cuerpos de las PR **antes** de mergear, para que GitHub los cierre solo. Lo reparable es
   la trazabilidad; que el issue debía preceder al código no se puede deshacer, y las marcas de
   tiempo lo muestran.
2. **Orden de reparación mal propuesto.** El primer plan mergeaba #45 y #46 antes de abrir sus
   issues, lo que habría dejado un rastro escrito al revés. Se corrigió el orden.
3. **`data/*.json` regenerados fuera de lugar.** Se generaron en ramas ajenas para poder ver el
   sitio. Se decidió **no arrastrarlos**: se descartan y se regeneran sobre
   `feature/datalayer-cruce-vivo` ya rebasada, porque traen el esquema `etapas` que solo existe
   a partir de #44 y porque un dato generado en un estado intermedio del árbol no es
   reproducible.

## Estado al momento de escribir

| Rama | PR | Issue | Estado |
|---|---|---|---|
| `feature/datalayer-airflow-v3` | #42 | #41 | Lista para mergear |
| `feature/datalayer-etapas-pipeline` | #44 | #43 | Lista, apilada sobre #42 |
| `docs/html-pipelines-faltantes` | #45 | #47 | Lista, apilada sobre #44 |
| `fix/docs-enlace-indice` | #46 | #48 | Lista, apilada sobre #45 |
| `feature/datalayer-cruce-vivo` | #38 | #34 | Borrador — el cruce ya corre; falta commitear los JSON |
| `chore/verificacion-cruce-vivo` | #39 | #35 | Borrador — verificado de facto |
| `feature/datalayer-tunel-ssh` | #36 | #32 | Borrador — **obsoleto** por el acceso directo |
| `chore/datalayer-tunel-config` | #37 | #33 | Borrador — por reescribir hacia acceso directo |

El cruce contra producción ya corre completo: las cuatro fuentes en `ok`,
`verificado_contra_produccion: true`, 53 DAGs, 35 bases, 137 vistas y 47 materializadas,
~17 millones de registros, en unos dos minutos.

Esas cifras son del 2026-08-27 y ya envejecieron; se conservan como registro. Medidas de nuevo
el 2026-09-02, con dos pipelines nuevos aguas arriba:

| | 2026-08-27 | 2026-09-02 |
|---|---|---|
| DAGs | 53 | **56** |
| Pipelines | 33 | **35** |
| Vistas | 137 | **141** |
| Materializadas | 47 | **48** |
| Registros | ~17 M | **27.8 M** |
| `pipelines_sin_html` | 1 | **3** |

## Cómo retomar

> Escrito el 2026-08-27. **Las secciones que siguen a ésta lo actualizan**: la revisión de la
> pila del 2026-08-31, las decisiones tomadas y la premisa de despliegue corregida por el
> usuario. Léelas antes de ejecutar estos pasos.

1. Mergear la pila en orden: **#42 → #44 → #45 → #46**.
2. Rebasar `feature/datalayer-cruce-vivo` sobre el nuevo `main`, regenerar los `data/*.json`
   ahí, commitear y mergear #38 → cierra #34.
3. Tablero y borrado de los dos runbooks en #39 → cierra #35.
4. Cerrar #32/#36 por obsoletos y reescribir #33/#37 hacia el acceso directo.
5. Pendiente aguas arriba: **tres** pipelines sin ficha, con bloqueos distintos (al
   2026-09-02).

   | Pipeline | README | `erd.svg` | Base en producción | Qué falta |
   |---|---|---|---|---|
   | `nacimientos_dgis` | no | no | no | el README en `ETL-SIEEJ` |
   | `defunciones_inegi` | sí | sí | **no existe** | desplegar el pipeline |
   | `edafologia` | sí | sí | **no existe** | desplegar el pipeline |

   El generador saca tablas, conteos, vistas y columnas de producción, así que los dos últimos
   no se pueden documentar aunque su README esté listo. Sus nombres ya están curados en
   `NOMBRES`, de modo que generarlos será un solo comando en cuanto se desplieguen.

## Revisión de la pila (2026-08-31)

La revisión se hizo en el orden #45 → #44 → #42 → #46 → #49, empezando por la documentación
HTML. De #45 salieron tres observaciones del usuario sobre `scripts/generar_doc_pipeline.py`,
todas atendidas en esa misma rama:

- **Las rutas estaban incrustadas al disco del autor.** `ETL_REPO_DIR`, `ETL_REPO_REF` y
  `DOCS_HTML_DIR` pasaron a `Settings`; esta última es la misma variable que ya consumía
  `copy-docs.mjs`. Las rutas relativas se resuelven contra la raíz del repositorio y no contra
  el directorio de trabajo, porque en el servidor esto correrá desde un cron.
- **`html-documents/` era material de referencia, no una dependencia.** La constante `DOCS`
  hacía tres trabajos a la vez: plantilla, índice y destino. La plantilla se extrajo a
  `scripts/plantilla/` y se versiona aquí —el generador ya no hereda de un documento que él
  mismo pudo haber escrito—; el índice sigue saliendo del directorio de salida, porque la
  navegación enlaza archivos hermanos y un pipeline sin documento daría un enlace roto; el
  destino es `DOCS_HTML_DIR`.
- **`NOMBRES` se volvía obsoleto.** Peor: `FALTANTES = list(NOMBRES)` lo hacía también la lista
  de trabajo, así que un ETL nuevo no habría aparecido *ni se habría quejado*. Ahora qué falta
  se calcula de `data/inventario.json`, y un pipeline sin nombre curado cae a uno derivado de
  su clave y lo avisa, en vez de reventar con `KeyError` después de haber consultado la base.

Verificación: los 10 documentos de #45 se regeneraron contra producción y salieron idénticos a
los publicados salvo la fecha y el commit nuevo del pie. `--solo-navegacion` sobre los 33
produce cero diferencias byte a byte.

### Lo que destapó el SHA del pie, el mismo día que se agregó

El pie ahora registra el commit de `ETL_REPO_REF` que se documentó. En la primera corrida marcó
`ad3a05f` y en la segunda `83e1081`: el clon de ETL-SIEEJ se había movido. Entre ambos commits
aparecieron **dos pipelines nuevos** y cambió el README de un tercero. Son 35 pipelines en
ETL-SIEEJ contra 32 documentados.

| Pipeline | README | `erd.svg` | Base en producción | Estado |
|---|---|---|---|---|
| `defunciones_inegi` | sí | sí | **no existe** | no se puede documentar aún |
| `edafologia` | sí | sí | **no existe** | no se puede documentar aún |
| `nacimientos_dgis` | no | no | no existe | bloqueado desde antes |

Los dos primeros están en el repositorio pero no desplegados: el generador saca tablas,
conteos, vistas y columnas de producción, así que documentarlos hoy sería publicar la ficha de
algo que no existe. Sus nombres ya quedaron curados en `NOMBRES` —`defunciones_inegi` es
«Defunciones (INEGI)», que el README de ETL-SIEEJ pide distinguir del `defunciones` de la DGIS—
para que su generación sea un solo comando en cuanto se desplieguen.

`intensidad_migratoria` sí se regeneró, y el diff mostró que el documento publicado estaba
**equivocado**, no solo viejo: listaba `view_iim_municipios_jalisco` cuando producción ya la
tiene partida en `_2010` y `_2020`, no mencionaba la materializada `vm_iim_geo`, y nombraba
columnas que ya no existen (`grado_iim`, `fecha`). El costo del cambio es que cuatro
descripciones curadas a mano pasaron a «Sin descripción registrada»: producción no tiene
`COMMENT` en esas tablas y el diccionario del README es una tabla markdown, que el generador no
usa como descripción. La forma de recuperarlas es un `COMMENT ON` en producción —que es de
donde el generador prefiere leerlas, y `vm_iim_geo` ya lo tiene—, no volver a escribirlas en el
HTML.

### Defecto encontrado al regenerar

El generador listaba `spatial_ref_sys`, `geometry_columns` y `geography_columns` como si fueran
del pipeline: son de PostGIS. Habría afectado a todo pipeline geoespacial, `edafologia`
incluido. Se corrigió excluyendo lo que pertenece a una extensión (`pg_depend.deptype = 'e'`)
en vez de una lista de nombres, para que cualquier extensión futura quede fuera sola.

### Decisiones tomadas en la revisión

- **Orden de las etapas: inicial → actualización → incremental.** Es el que el código ya
  producía; el comentario y el tablero decían otro. Se corrigieron los dos textos, no el orden.
- **`airflow_configurado` sigue aceptando usuario/contraseña**, no solo un JWT ya emitido,
  porque así está configurado el Airflow de producción. No es un descuido: es la forma en que
  el servidor autentica hoy, y el cliente se adapta a ella. Revisar si algún día se emiten
  tokens de servicio.
- **Durante una corrida viva se muestra el estado, no una fecha.** `ultima_corrida_fecha` dejó
  de caer a `run_after` —que es cuándo empezó, no cuándo terminó— y los estados se muestran en
  español: «correcta», «con error», «en ejecución», «en cola».
- **Aviso de nomenclatura de DAG**, `dags_fuera_de_convencion`, apoyado en la convención escrita
  en ETL-SIEEJ (`.github/skills/dag-airflow/SKILL.md` y `docs/architecture.md`). Avisa, no
  corrige.

Medición que respaldó las dos primeras, sobre 56 DAG y 151 corridas: 5 corridas con
`logical_date` nulo (las bootstrap manuales, que es por lo que se ordena por `-run_after`), 0
DAG donde el orden por uno difiera del otro, y 0 corridas con `end_date` nulo.

### Decisión pendiente del equipo

Queda **sin abrir a propósito** un issue en `ETL-SIEEJ` para que cada README declare su nombre
corto y el nombre del producto. Hoy esos nombres se curan a mano en el diccionario `NOMBRES` de
este repositorio, que es exactamente lo que se vuelve obsoleto: los README de los dos pipelines
nuevos traen `# defunciones_inegi` y `# edafologia` como título, así que sin curaduría saldrían
«Defunciones Inegi» y «Edafologia», sin acento. Mientras la fuente de los nombres siga fuera del
repositorio que los produce, cada ETL nuevo va a necesitar que alguien se acuerde. **El usuario
quiere discutirlo con su equipo antes de abrirlo**; no se abra el issue sin esa decisión.

### Cómo debe desplegarse la documentación (premisa corregida por el usuario)

Durante la revisión se afirmó que el servidor tendría que montar `general-documentation/` y
apuntarle `DOCS_HTML_DIR_HOST`. **El usuario corrigió esa premisa: `general-documentation/` no
puede vivir en el servidor de pruebas ni en el de producción.** Los HTML se deben **generar**
cada vez que el servicio arranca, y actualizarse después con un cron o equivalente.

El diseño lo permite y ya avanzó hacia allá: al mover la plantilla a `scripts/plantilla/` (punto
2 de la revisión de #45) el generador dejó de depender de ese directorio para su formato, y las
rutas ya se leen del entorno. Lo que falta no es diseño, son **dos huecos de datos**, ambos
aguas arriba de este repositorio, medidos el 2026-09-01 contra producción.

**Hueco 1 — los nombres.** El nombre corto sale de `NOMBRES` (13 entradas) o, para el resto, de
leer los HTML ya publicados. Con el directorio de salida vacío esa segunda fuente no existe:
**22 de los 35 pipelines** caerían a un nombre derivado de la clave, sin acentos ni siglas
(`denue` → «Denue», `censo_economico` → «Censo Economico», `establecimientos_de_salud` →
«Establecimientos De Salud»). Se perderían además las abreviaturas curadas de la barra lateral
—«Estab. de Salud», «Pobreza Multidim.»—, que hoy solo existen dentro de los HTML publicados.

**Hueco 2 — las descripciones.** El generador toma la descripción de cada tabla y vista del
`COMMENT` de producción. De los 372 objetos de las 33 bases, **222 tienen comentario y 150 no**.
Esos 150 saldrían como «Sin descripción registrada», hoy cubiertos por texto curado a mano
dentro del HTML. Ya se vio en pequeño al regenerar `intensidad_migratoria`, donde cuatro
descripciones se convirtieron en ese placeholder. Los peores casos:

| Base | Objetos con comentario |
|---|---|
| `establecimientos_de_salud` | 0 / 26 |
| `centros_educativos` | 0 / 11 |
| `agropecuario_siap`, `inpc`, `marginacion` | 0 / 8 cada una |
| `denue` | 4 / 13 |
| `delitos_fuero_comun` | 23 / 40 |

**Consecuencia:** mientras cualquiera de los dos huecos siga abierto, generar todo en el
servidor produce documentación *peor* que la actual. Los dos se cierran fuera de este
repositorio:

1. Que cada README de `ETL-SIEEJ` declare el nombre corto y el del producto. Es el mismo issue
   que quedó pendiente de discusión con el equipo, y este es su segundo argumento —ya no es
   higiene, es requisito para generar en el servidor.
2. `COMMENT ON` en las migraciones de producción para los 150 objetos que no lo tienen. El
   generador ya los prefiere sobre cualquier otra fuente.

Falta también, menor pero necesario, que el servidor tenga un clon de `ETL-SIEEJ`
(`ETL_REPO_DIR`) con `git fetch` antes de generar: de ahí salen los README y los `erd.svg`.

**Esto es una tarea nueva, no un ajuste a #45.** Por decisión del usuario **no se abrió el
issue**: queda escrito aquí para levantarlo cuando lo decida, junto con la decisión de los
nombres, que es su dependencia.

### Un riesgo de despliegue que se comprobó de paso

Con el esquema actual —origen montado— se probó qué pasa si `DOCS_HTML_DIR` apunta a un
directorio sin documentos: `copy-docs.mjs` copia cero, **el build termina en verde**, y la
landing publica sus 32 botones «Ver documentación» apuntando a archivos que no existen. Nadie
avisa. La causa es que dos piezas leen la misma variable sin coordinarse: el datalayer tiene un
guardián (`generate.py:77`, `_fuente_degradada`) que se niega a sobrescribir el inventario
cuando una fuente empeora —conserva el previo y lo marca `datos_obsoletos`—, mientras
`copy-docs.mjs` no tiene ese guardián. El inventario sigue diciendo 32 documentos y el
directorio servido tiene 0.

Agrava el riesgo el default de `docker-compose.yml`: `${DOCS_HTML_DIR_HOST:-./docs}` cae al
`docs/` del propio repositorio, que es markdown y no tiene ningún HTML. Olvidar la variable no
da un error de configuración; da un sitio que compila bien con todos los botones muertos.

Queda pendiente decidir si `copy-docs.mjs` debe fallar el build cuando el origen está
configurado pero no aporta ningún documento. La degradación con gracia tiene sentido cuando no
hay variable; copiar cero habiendo apuntado a un directorio es un error de despliegue.

### Inconsistencia señalada, no corregida

Los 22 documentos hechos a mano escriben los tipos abreviados (`float8`, `varchar`) y los 10
generados por #45 los escriben completos (`double precision`, `character varying`). Es visible
al comparar cualquier par. No se tocó porque uniformarlos es una decisión de estilo sobre los 32
documentos, no un defecto del generador.

Para levantar el sitio localmente hace falta exportar `DOCS_HTML_DIR`: `copy-docs.mjs` la lee
del entorno y no del `.env`, y sin ella no copia ningún documento.
