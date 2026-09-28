# IMP-001 — M01 Validate & Desurvey

## 1. Identificación

- **Implementation ID:** IMP-001
- **Module:** M01 — Validate & Desurvey
- **Date:** 2026-09-26
- **Group:** Grupo 03
- **Participants:** UNKNOWN
- **Status:** IN_PROGRESS

---

## 2. Problema minero

El release de exploración contiene collares, estaciones de survey e intervalos
geológicos y de muestreo referidos a profundidad medida. M01 organizará la
carga y validación de esos datos y, una vez definidas las convenciones
necesarias, calculará la trayectoria espacial de los sondajes y posicionará
los intervalos sobre ella.

## 3. Objetivo

Diseñar e implementar un flujo modular que cargue las fuentes necesarias del
release, valide las entradas según reglas acordadas, calcule una trayectoria
desurveyada y relacione los intervalos disponibles con posiciones espaciales.
El loader y un subconjunto de controles verificables del validator están
implementados y probados. Las convenciones de coordenadas y orientación
fueron indicadas por el docente; se seleccionó mínima curvatura. Se definieron
políticas adicionales para comparar orientaciones en `MD = 0`, manejar survey
incompleto o duplicado, y limitar el posicionamiento a la cobertura disponible.
El validator ya distingue duplicados de survey por orientación a igual
`hole_id` y profundidad; faltan implementar la nueva regla de relevancia
angular y los controles de cobertura para posicionamiento.

## 4. Inputs

| Variable | Significado | Unidad | Origen | Obligatorio | Validación |
|---|---|---|---|---|---|
| `hole_id` | Identificador de sondaje | N/A | `data/raw/collar.csv`, `survey.csv`, `assay.csv`, `lithology.csv`, `density.csv` | Sí para relacionar registros | Unicidad en collar y existencia de referencias secundarias en collar |
| Collar (`x`, `y`, `z`, orientación y profundidad final) | Ubicación, orientación inicial y profundidad final registrada | Según `data_dictionary.csv` | `data/raw/collar.csv` | Sí para desurvey | Campos requeridos, finitud numérica, profundidad positiva y rangos angulares documentados |
| Survey (`depth_m`, `azimuth_deg`, `dip_deg`) | Estaciones de profundidad medida y orientación | Según `data_dictionary.csv` | `data/raw/survey.csv` | Sí para desurvey | Relación con collar, profundidad, orden, duplicados, rangos angulares y estación inicial |
| Intervalos de assay | Intervalos y leyes disponibles | Según `data_dictionary.csv` | `data/raw/assay.csv` | Para posicionar assay | Intervalo, relación con collar, IDs, valores finitos, negativos y ceros descriptivos |
| Intervalos de litología | Intervalos y códigos litológicos disponibles | Según `data_dictionary.csv` | `data/raw/lithology.csv` | Para posicionar litología | Intervalo, relación con collar y registros duplicados |
| Muestras de densidad | Intervalos y densidades disponibles | Según `data_dictionary.csv` | `data/raw/density.csv` | Para posicionar densidad | Intervalo, relación con collar, IDs, densidad positiva y gaps descriptivos |
| Alteración | Archivo disponible, actualmente sin registros | Según `data_dictionary.csv` | `data/raw/alteration.csv` | No determinado; archivo vacío en este release | El loader deberá representar la tabla vacía sin inventar registros |
| Diccionario y manifest | Definiciones de campos y metadatos del release | N/A | `data/raw/data_dictionary.csv`, `release_manifest.json`, `README.md` | Para interpretación y trazabilidad | Pendiente de definir uso dentro del flujo |

## 5. Outputs

| Variable / resultado | Significado | Unidad | Destino |
|---|---|---|---|
| Datos cargados | Tablas fuente necesarias para el flujo M01 | Según diccionario de datos | Entrega interna a los módulos |
| `ValidationReport` | Hallazgos con regla, severidad, tabla, fila lógica, identificadores, campo, valor observado y condición esperada; incluye conteos por severidad | N/A | Entrega interna desde `validator.py` |
| Trayectoria desurveyada | Coordenadas calculadas por sondaje y profundidad medida | Coordenadas/distancia en unidades documentadas; convención pendiente | `data/processed/` por definir |
| Intervalos posicionados | Intervalos vinculados espacialmente con la trayectoria | Según datos fuente y representación acordada | `data/processed/` por definir |
| Visualizaciones y exportaciones | Representaciones/archivos derivados que se acuerden | Depende del formato seleccionado | `outputs/` |

## 6. Convenciones y supuestos

Convenciones geométricas comunicadas por el estudiante desde el material del
docente, antes de programar desurvey:

- X representa Easting; Y representa Northing; Z representa elevación, con
  positivo hacia arriba.
- Azimut medido en sentido horario desde el Norte: 0° Norte y 90° Este.
- Dip de 0° horizontal a -90° vertical hacia abajo.

Estas convenciones definen ejes y ángulos, pero no el CRS/EPSG ni cómo
consultar la trayectoria entre estaciones survey o fuera del rango cubierto.
También queda pendiente decidir qué fuente gobierna la orientación inicial en
MD = 0 cuando difieren collar.azimuth_deg/dip_deg y
survey.azimuth_deg/dip_deg.

Para la validación de rango angular se aprobó azimut en `[0°, 360°)` y dip en
`[-90°, 0°]`. El límite de 360° queda excluido porque representa la misma
dirección que 0°; ambos extremos del dip descendente son válidos. Estos rangos
se aplican tanto a collar como a survey.

Reglas adicionales comunicadas para desurvey y positioning:

- En `MD = 0`, comparar azimut y dip de collar y survey. Una diferencia
  relevante debe reportarse como `WARNING` o `ERROR` según una regla aprobada;
  todavía no se especificaron el umbral de relevancia ni la correspondencia
  entre diferencia y severidad. La comparación no decide por sí sola qué
  orientación gobierna.
- Un survey duplicado idéntico es `WARNING`; uno contradictorio es `ERROR`.
  Al implementar debe precisarse qué campos determinan identidad o
  contradicción.
- No completar un survey incompleto inventando estaciones.
- No extrapolar más allá de la última estación survey sin aprobación explícita.
- Si un intervalo excede la trayectoria disponible, generar `ERROR` y no
  calcular XYZ para ese intervalo.

Estas reglas no definen qué constituye un survey completo, qué hacer si falta
una estación survey en `MD = 0`, ni el umbral y la severidad de una diferencia
collar-survey relevante.

## 7. Lógica minera

El collar aporta el anclaje espacial y una orientación registrada; survey
aporta orientaciones a measured depth. Con las convenciones anteriores, un
azimut A y dip D describen la dirección mediante componentes
`(sin(A) * cos(D), cos(A) * cos(D), sin(D))` en los ejes `(X, Y, Z)`, con
ángulos expresados en radianes al evaluar funciones trigonométricas. Se
seleccionó mínima curvatura para calcular el desplazamiento entre estaciones
consecutivas. Dados los vectores unitarios `u1` y `u2` y la separación
`delta_MD`, el dogleg es `beta = acos(clamp(u1 · u2, -1, 1))`, el factor de
razón es `RF = (2 / beta) * tan(beta / 2)` y el desplazamiento es
`delta_MD / 2 * (u1 + u2) * RF`; para dogleg tendiente a cero, el límite de
`RF` es 1. Esta selección no define qué orientación gobierna en `MD = 0`,
cómo calcular puntos interiores para positioning, el tratamiento numérico de
doglegs extremos ni el CRS/EPSG. No se deben inventar estaciones ni extrapolar
más allá del último survey sin aprobación. Un intervalo que exceda la
cobertura disponible genera `ERROR` y no recibe XYZ. No se ha implementado
cálculo espacial.

## 8. Diseño computacional

### Módulos / archivos

Arquitectura aprobada como base:

- `main.py`: orquesta el flujo, sin concentrar lógica minera.
- `src/m01/loader.py`: carga collar, survey, assay, litología, densidad,
  alteración, diccionario, manifest y README. Conserva las columnas de
  `alteration.csv` aunque no tenga filas.
- `src/m01/validator.py`: ejecuta controles aprobados; no corresponde al loader
  aplicar reglas mineras. `validate_m01_data(data)` devuelve un
  `ValidationReport` sin modificar las tablas cargadas.
- `src/m01/desurvey.py`: calculará la trayectoria con mínima curvatura y las
  convenciones aprobadas, tras resolver la orientación inicial en `MD = 0`,
  el tratamiento de survey incompleto y la cobertura disponible.
- `src/m01/positioning.py`: relaciona los intervalos con la trayectoria.
- `src/m01/visualizer.py`: presenta trayectoria y datos posicionados.
- `src/m01/exporter.py`: escribe salidas derivadas en los destinos acordados.
- `tests/`: pruebas de las unidades implementadas.

Los formatos concretos de las salidas derivadas y las interfaces entre
módulos siguen pendientes.

### Funciones / clases principales

- `load_collar(path) -> list[CollarRecord]`: lee collar y convierte sus campos
  numéricos documentados.
- `load_m01_data(raw_directory) -> M01Data`: carga las tablas tabulares y los
  metadatos del release para las etapas de M01.
- `LoadedTable`: conserva columnas y registros; representa tablas vacías sin
  perder el esquema del CSV.
- `M01Data`: agrupa fuentes cargadas para consumo por las etapas posteriores.
- `LoaderError`: comunica fallos de lectura, esquema CSV o conversión.
- `validate_m01_data(data: M01Data) -> ValidationReport`: aplica controles
  verificables y produce hallazgos trazables.
- `ValidationFinding`: registra `rule_id`, severidad, tabla, fila lógica,
  identificadores, campo, valor observado y condición esperada; expone las
  propiedades `blocking` y `requires_review`.
- `ValidationReport`: agrupa hallazgos y calcula conteos por severidad y
  `has_errors`.
- `main()`: coordina `load_m01_data()`, `validate_m01_data()` y la impresión
  del reporte; no contiene reglas de validación.
- `print_validation_report(report)`: muestra conteos y agrupa hallazgos por
  regla y severidad, con un ejemplo observado por grupo.

### Dependencias relevantes

No se aprobó añadir dependencias. El loader utilizará el módulo `csv` de la
biblioteca estándar de Python, consistente con `requirements.txt`.

## 9. Etapas de implementación

### Etapa 1 — 2026-09-25 — Inventario de datos

- **Objetivo:** identificar fuentes, campos, tipos, unidades documentadas y
  relaciones disponibles.
- **Trabajo realizado:** se revisaron las instrucciones del repositorio,
  `data/raw/`, el diccionario, el manifest y el README.
- **Resultado:** se identificó el release DS01/EXP03 y sus tablas, incluidas
  las cero filas de alteración.
- **Pendiente:** convertir el inventario en carga y reglas computacionales.

### Etapa 2 — 2026-09-25 — Modelo conceptual y plan de validación

- **Objetivo:** comprender el vínculo entre collar, survey e intervalos y
  proponer controles sin fijar umbrales no documentados.
- **Trabajo realizado:** se describieron las relaciones conceptuales y se
  propusieron familias de validación. Se comparó orientación de collar con
  survey a profundidad cero; en los datos inspeccionados coincidieron los 32
  sondajes.
- **Resultado:** se documentaron decisiones pendientes de convenciones y
  umbrales. El plan quedó sujeto a aprobación antes de convertir sus controles
  en código.
- **Pendiente:** implementar controles verificables sin inventar límites y
  conservar las decisiones de ingeniería pendientes.

### Etapa 3 — 2026-09-25 — Evidencia objetiva para T1

- **Objetivo:** consolidar evidencia reproducible del release sin
  interpretaciones mineras.
- **Trabajo realizado:** se generó el workbook
  `outputs/tables/T1_audit_summary_DS01_EXP03.xlsx`.
- **Resultado:** el workbook incluye metadatos, archivos, esquema, conteos,
  rangos, relaciones y métricas descriptivas; registra que no se encontró un
  validator implementado y no presenta resultados como validaciones pasadas.
- **Pendiente:** desarrollar reglas y reporte del validator.

### Etapa 4 — 2026-09-26 — Diseño de arquitectura y alcance del loader

- **Objetivo:** definir una arquitectura modular mínima antes de escribir
  código.
- **Trabajo realizado:** el equipo aprobó la arquitectura base `loader`,
  `validator`, `desurvey`, `positioning`, `visualizer` y `exporter` bajo
  `src/m01/`, coordinada desde `main.py`. Se aclaró que `loader.py` debe poder
  cargar todas las fuentes necesarias de `data/raw/` para las etapas hasta el
  visualizador, y no solo `collar.csv`.
- **Resultado:** arquitectura y responsabilidades generales acordadas.
- **Pendiente en esta etapa:** ampliar loader a las demás fuentes; precisar
  interfaces, formatos de salida, reglas del validator y convenciones de
  desurvey.

### Etapa 5 — 2026-09-26 — Loader mínimo de collar

- **Objetivo:** implementar la primera unidad verificable de carga antes de
  extender el loader a survey e intervalos.
- **Trabajo realizado:** se implementó `load_collar` usando la biblioteca
  estándar `csv`. Convierte a `float` los campos numéricos definidos para
  collar y genera `LoaderError` para archivos/estructuras no legibles o
  conversiones numéricas fallidas. No aplica duplicados, rangos ni relaciones
  mineras.
- **Resultado:** se cargaron los 32 registros del collar real y se agregaron
  cuatro pruebas unitarias.
- **Pendiente en esta etapa:** extender la carga a survey, assay, lithology y
  density, representar alteration vacía y, posteriormente, implementar las
  reglas aprobadas en `validator.py`.

### Etapa 6 — 2026-09-26 — Convenciones de coordenadas y orientación

- **Objetivo:** registrar las convenciones compartidas por el docente antes
  de definir reglas angulares del validator.
- **Trabajo realizado:** se registró X=Easting, Y=Northing, Z=elevación
  positiva hacia arriba; azimut 0° Norte, 90° Este, sentido horario; dip 0°
  horizontal y negativo hacia abajo hasta -90°.
- **Resultado:** las convenciones de ejes y orientación quedan documentadas.
- **Pendiente:** CRS/EPSG, algoritmo de desurvey, interpolación y
  extrapolación siguen sin estar definidos.

### Etapa 7 — 2026-09-26 — Loader de las fuentes de M01

- **Objetivo:** ampliar la carga para incluir las fuentes requeridas a través
  de la visualización, incluyendo survey e intervalos.
- **Trabajo realizado:** `load_m01_data` carga collar, survey, lithology,
  alteration, assay, density y data dictionary, además de manifest JSON y
  README. Los campos numéricos de las tablas de datos se convierten a `float`;
  `LoadedTable` conserva encabezados incluso cuando no hay registros. Se
  añadieron pruebas sobre conteos del release, conversiones, metadatos y
  alteración vacía.
- **Resultado:** `python -m unittest discover -s tests -v` pasó 7 pruebas.
- **Pendiente en esa etapa:** implementar validator con controles
  verificables; desurvey y módulos siguientes permanecían sin implementar.

### Etapa 8 — 2026-09-27 — Validator y pruebas de M01

- **Objetivo:** convertir controles verificables del plan de validación en
  hallazgos trazables, usando las tablas entregadas por el loader.
- **Trabajo realizado:** se implementó `validate_m01_data` y los tipos
  `ValidationFinding` y `ValidationReport`. Se añadieron controles para
  identificadores, campos requeridos y valores finitos, profundidades,
  orientación, relaciones entre tablas, intervalos, valores de assay y
  densidad, campañas del manifest y la tabla de alteración vacía. Survey
  informa de forma descriptiva si la estación más profunda no coincide con
  `final_depth_m`; density informa gaps observados sin umbral. Cada hallazgo
  conserva regla, severidad, tabla, fila lógica del CSV, identificadores,
  campo, valor observado y condición esperada. Las pruebas usan fixtures
  pequeños y una prueba de integración sobre DS01/EXP03.
- **Resultado:** `python -m unittest discover -s tests -v` pasó 19 pruebas
  (7 de loader y 12 de validator). Sobre DS01/EXP03 el validator produjo
  0 ERROR, 1 WARNING por los nombres de campaña del manifest frente a los
  CSV, y 261 INFO: alteración sin registros, valores cero de `mo_pct` y
  `au_gt`, y 258 gaps observados entre intervalos de densidad. Estos son
  resultados computacionales, no una evaluación de suficiencia o calidad
  minera.
- **Pendiente:** definir tolerancias y políticas antes de añadir controles
  de longitud de intervalos, cobertura continua de assay/lithology, cambios
  angulares y plausibilidad espacial o de densidad. No se implementó desurvey.

### Etapa 9 — 2026-09-27 — Orquestación de M01 desde main.py

- **Objetivo:** conectar la carga y validación implementadas al punto de
  entrada, conservando `main.py` como orquestador.
- **Trabajo realizado:** `main()` ahora carga el release predeterminado,
  ejecuta `validate_m01_data` y muestra el resumen por severidad. Los
  hallazgos de salida se agrupan por regla y severidad, con cantidad y un
  ejemplo objetivo para evitar repetir cientos de líneas de hallazgos
  informativos. Se añadieron pruebas de integración y del reporte vacío.
- **Resultado:** `python -m unittest discover -s tests -v` pasó 21 pruebas:
  7 de loader, 12 de validator y 2 de orquestación. La ejecución de `main()`
  sobre DS01/EXP03 informó 0 ERROR, 1 WARNING y 261 INFO; las líneas de
  detalle resumen las reglas involucradas.
- **Pendiente:** `main.py` aún no orquesta desurvey, positioning,
  visualizer ni exporter; esos módulos permanecen fuera del alcance aprobado.

### Etapa 10 — 2026-09-27 — Registro de convenciones geométricas

- **Objetivo:** registrar las convenciones compartidas para la siguiente etapa
  conceptual de desurvey antes de calcular coordenadas.
- **Trabajo realizado:** se precisó en este registro el sistema de ejes
  (`X` Easting, `Y` Northing, `Z` elevación positiva hacia arriba), azimut
  horario desde Norte y dip entre horizontal y vertical hacia abajo. Se
  consignó la relación direccional de componentes para esos ángulos.
- **Resultado:** queda documentada la interpretación de ejes y orientación;
  en esta etapa aún no se había seleccionado ni programado un método de
  desurvey.
- **Pendiente en esta etapa:** decidir la autoridad en `MD = 0`, seleccionar
  y justificar el método geométrico, y definir interpolación, extrapolación y
  CRS/EPSG.

### Etapa 11 — 2026-09-27 — Rangos de azimut y dip en validator

- **Objetivo:** aplicar en collar y survey la regla de rango angular aprobada.
- **Trabajo realizado:** inicialmente se incorporó un intervalo inclusivo que
  no correspondía a la convención descendente presentada después. A partir de
  la aclaración visual del docente se corrigió `validator.py` para aplicar
  azimut en `[0°, 360°)` y dip en `[-90°, 0°]`, y se adaptaron las pruebas de
  límites y valores fuera de rango para collar y survey.
- **Resultado:** la suite pasó 25 pruebas (7 loader, 16 validator y 2 main).
  Al ejecutar `main.py` sobre el release local DS01/EXP03 se observaron
  0 ERROR, 1 WARNING y 261 INFO. No hubo hallazgos de rango angular.
- **Pendiente:** esta regla de rango no decide la autoridad de collar frente a
  survey en `MD = 0` ni el método de desurvey. La política posterior de
  comparación en `MD = 0` queda registrada en DECISION-11.

### Etapa 12 — 2026-09-27 — Selección conceptual de mínima curvatura

- **Objetivo:** seleccionar el método geométrico para calcular la trayectoria
  entre estaciones consecutivas de survey.
- **Trabajo realizado:** el estudiante seleccionó mínima curvatura, método
  indicado en el material del docente. Se documentaron la ecuación del
  dogleg, el factor de razón y el desplazamiento entre estaciones.
- **Resultado:** el método queda seleccionado para la futura implementación.
  En esta etapa solo se registró la lógica; no se escribió ni ejecutó código
  de desurvey.
- **Pendiente:** decidir qué orientación gobierna en `MD = 0`, el umbral y
  severidad de diferencias relevantes, cómo consultar profundidades entre
  estaciones, qué define un survey incompleto, doglegs extremos y CRS/EPSG.
  No se debe extrapolar sin aprobación; los intervalos fuera de la trayectoria
  disponible generan `ERROR` y no reciben XYZ.

### Etapa 13 — 2026-09-27 — Políticas de comparación y cobertura

- **Objetivo:** registrar las reglas recibidas para discrepancias en `MD = 0`,
  duplicados survey y cobertura de la trayectoria.
- **Trabajo realizado:** se documentó comparar azimut/dip entre collar y
  survey en `MD = 0`; emitir `WARNING` o `ERROR` para una diferencia relevante
  según el criterio aprobado; clasificar duplicados idénticos como `WARNING`
  y contradictorios como `ERROR`; no sintetizar estaciones; no extrapolar
  después de la última estación sin aprobación; y rechazar con `ERROR`, sin
  XYZ, intervalos fuera de la trayectoria disponible.
- **Resultado:** las reglas quedaron registradas en DECISION-11. No se modificó
  código y no se ejecutaron pruebas en esta etapa.
- **Pendiente:** definir el umbral y severidad de diferencias angulares, la
  autoridad direccional en `MD = 0`, el criterio de identidad/contradicción de
  duplicados, qué constituye un survey incompleto, la consulta de puntos entre
  estaciones y el CRS/EPSG.

## 10. Decisiones

### DECISION-01

**Problema:** separar responsabilidades para que el flujo M01 sea modular y
`main.py` solo lo orqueste.

**Alternativas consideradas:**

La revisión aprobó una arquitectura modular; no quedó registrada una
comparación formal con otras arquitecturas.

**Alternativa seleccionada:** B, con `loader.py`, `validator.py`,
`desurvey.py`, `positioning.py`, `visualizer.py` y `exporter.py`.

**Justificación:** arquitectura modular aprobada por el equipo antes de
implementar.

**Impacto:** interfaces explícitas por definir; cada módulo deberá mantener
responsabilidad identificable.

### DECISION-02

**Problema:** alcance de lectura del loader.

**Alternativas consideradas:**

- A. Cargar inicialmente solo collar como alcance final.
- B. Permitir que el loader cargue todas las fuentes requeridas por el flujo
  hasta visualización.

**Alternativa seleccionada:** B. El loader cubrirá las tablas requeridas de
collar, survey, assay, litología y densidad; el archivo vacío de alteración
requiere tratamiento explícito que no invente filas.

**Justificación:** el flujo posterior necesita esas fuentes y el loader debe
servir a las etapas hasta el visualizador.

**Impacto:** se podrá desarrollar y probar el loader incrementalmente sin
limitar su alcance final a collar. La primera unidad verificable puede ser
cargar collar y probarlo; después se ampliará a survey e intervalos, manteniendo
el alcance final acordado.

### DECISION-03

**Problema:** dependencias para cargar CSV.

**Alternativas consideradas:**

La revisión registró el uso del módulo `csv` estándar y que no se añadirán
dependencias; no quedó registrada una comparación formal de librerías.

**Alternativa seleccionada:** B; no agregar dependencias por ahora.

**Justificación:** decisión registrada en la revisión del equipo y consistente
con `requirements.txt`.

**Impacto:** la lectura CSV se implementará con la biblioteca estándar.

### DECISION-04

**Problema:** responsabilidades de validación.

**Alternativas consideradas:**

La revisión asignó las reglas mineras a `validator.py` y no al loader; no
quedó registrada una comparación formal de diseños alternativos.

**Alternativa seleccionada:** B. Las reglas mineras corresponden a
`validator.py`.

**Justificación:** separación de responsabilidades acordada.

**Impacto:** errores de conversión de campos numéricos deben reportarse
explícitamente durante la carga; los controles mineros se ejecutan aparte.

### DECISION-05

**Problema:** campos numéricos que no pueden convertirse durante la carga.

**Alternativa seleccionada:** emitir un error explícito `LoaderError`, sin
asumir ni sustituir un valor.

**Alternativas consideradas:** no quedaron registradas formalmente.

**Justificación:** no inventar datos y hacer visible el error de entrada.

**Impacto:** formato del mensaje y contexto del error se definirán durante la
implementación.

### DECISION-07

**Problema:** convenciones de coordenadas y orientación que se usarán en M01.

**Alternativa seleccionada:** X=Easting, Y=Northing, Z=elevación positiva
hacia arriba; azimut medido en sentido horario desde Norte (0° Norte, 90°
Este); dip de 0° horizontal a -90° vertical hacia abajo.

**Fuente:** material del docente compartido por el estudiante el 2026-09-27.

**Impacto:** fija la interpretación de ejes y rangos angulares. No define el
CRS/EPSG ni cuál registro gobierna en MD = 0 cuando collar y survey no
coinciden.

### DECISION-08

**Problema:** implementar únicamente los controles con condición y severidad
que pueden comprobarse sin introducir umbrales técnicos no aprobados.

**Alternativas consideradas:**

- A. Aplicar límites de tolerancia o plausibilidad no documentados.
- B. Implementar los controles definidos y verificables y mantener pendientes
  los que requieren tolerancias o políticas de cobertura.

**Alternativa seleccionada:** B.

**Justificación:** el plan de validación deja explícitas decisiones pendientes
para tolerancias, cobertura, cambios angulares y rangos de plausibilidad.

**Impacto:** el validator no determina longitud coherente por tolerancia,
cobertura continua de assay/lithology, saltos angulares anómalos ni rangos
locales de coordenadas/elevación/densidad. Los gaps de density se informan
como `INFO`, sin umbral de espaciamiento. El comportamiento previo de
informar cualquier diferencia exacta entre orientación del collar y survey a
profundidad cero como `WARNING` no sustituye la regla posterior de DECISION-11:
falta definir qué diferencia es relevante y cuándo corresponde `ERROR`.

### DECISION-09

**Problema:** rango numérico admitido para azimut y dip en las reglas del
validator.

**Alternativa inicial:** azimut inclusivo `[0°, 360°]` y dip inclusivo
`[-90°, 90°]`.

**Corrección:** la convención geométrica y la aclaración posterior del material
del docente establecen azimut `[0°, 360°)` y dip `[-90°, 0°]`.

**Fuente:** imagen compartida por el estudiante el 2026-09-27, tras revisar las
indicaciones de implementación del docente.

**Impacto:** collar y survey fuera de estos intervalos producen hallazgos
`ERROR`. La decisión de rango mantiene el dip descendente negativo y no
determina qué fuente gobierna en `MD = 0` ni el método de desurvey.

**Nota de trazabilidad:** en la conversación del docente, la regla se refiere
como `DECISION-03`; en este registro local ese identificador ya corresponde a
la decisión de no añadir dependencias CSV. Se conserva `DECISION-09` en este
IMP para evitar duplicar identificadores.

### DECISION-10

**Problema:** método geométrico para calcular desplazamientos entre estaciones
consecutivas de survey.

**Alternativas mencionadas en el material:** tangencial, balanceado y mínima
curvatura.

**Alternativa seleccionada:** mínima curvatura.

**Justificación:** selección expresa del estudiante siguiendo el método
mostrado en el material del docente.

**Lógica:** para direcciones unitarias `u1` y `u2` al inicio y fin del tramo,
`beta = acos(clamp(u1 · u2, -1, 1))`,
`RF = (2 / beta) * tan(beta / 2)` y
`delta_xyz = delta_MD / 2 * (u1 + u2) * RF`. Si `beta` tiende a cero, se usa
el límite `RF = 1`.

**Impacto:** selecciona cómo calcular desplazamientos entre estaciones, pero
no decide qué orientación gobierna en `MD = 0`, cómo consultar posiciones
entre estaciones, tratamiento numérico de doglegs extremos ni CRS/EPSG. No se
debe extrapolar más allá del último survey sin aprobación explícita. El método
no está implementado ni probado.

### DECISION-11

**Problema:** definir políticas de entrada y cobertura para desurvey y
positioning.

**Reglas comunicadas por el estudiante:**

- Comparar azimut y dip de collar con survey en `MD = 0`; una diferencia
  relevante es `WARNING` o `ERROR` según una regla aprobada.
- Un duplicado survey idéntico es `WARNING`; uno contradictorio es `ERROR`.
- No inventar estaciones para completar surveys incompletos.
- No extrapolar después de la última estación survey sin aprobación explícita.
- Si un intervalo queda fuera de la trayectoria disponible, registrar `ERROR`
  y no generar XYZ para ese intervalo.

**Impacto:** estas reglas limitan los resultados posicionables a la cobertura
real de la trayectoria y prohíben crear estaciones observadas artificiales.
Antes de implementarlas se debe precisar el umbral/severidad de diferencias
relevantes en `MD = 0`, qué campos determinan duplicidad/contradicción, qué
casos definen un survey incompleto y cómo tratar un sondaje sin estación en
`MD = 0`. No se selecciona aquí una fuente de orientación dominante.

### DECISION-06

**Problema:** protección de archivos fuente.

**Alternativa seleccionada:** `data/raw/` permanece inmutable; las
transformaciones se guardarán fuera de esa carpeta.

**Justificación:** regla de gobernanza del curso.

**Impacto:** loader solo leerá los archivos originales.

## 11. Archivos creados o modificados

```text
src/m01/__init__.py
src/m01/loader.py
src/m01/validator.py
main.py
tests/__init__.py
tests/test_m01_loader.py
tests/test_m01_validator.py
tests/test_main.py
tests/test_m01_validator.py
docs/implementation/IMP-001_m01_validate_desurvey.md
outputs/tables/T1_audit_summary_DS01_EXP03.xlsx
```

`data/raw/` no fue modificado.

## 12. Pruebas realizadas

### Comandos ejecutados

```text
Set-Location .\PlanMinUPN-G03_; python -m unittest discover -s tests -v
```

### Resultado real

- **Status:** PASS
- **Tests passed:** 25 (7 loader, 16 validator, 2 main)
- **Tests failed:** 0
- La ejecución incluyó fixtures pequeños de validación y una prueba sobre
  los datos reales cargados desde `data/raw/`.
- La corrida de validator sobre DS01/EXP03 produjo 0 ERROR, 1 WARNING y
  261 INFO; los hallazgos quedan descritos en la Etapa 8.
- `main.py` sobre el release produjo el mismo resumen, con detalle agrupado
  por regla para la consola.

Comando ejecutado desde la raíz del repositorio:

```text
python -m unittest discover -s tests -v
```

## 13. Validación minera

- [ ] Unidades consistentes.
- [ ] Signos económicos correctos cuando corresponda.
- [ ] Magnitudes razonables.
- [ ] Restricciones operacionales respetadas.
- [ ] Casos extremos revisados.
- [ ] Caso manual independiente revisado cuando es posible.

### Evidencia / comentario

El loader se verificó mediante conteos, conversiones y conservación de los
encabezados de la tabla vacía de alteración. El validator no emitió errores
para el release en esta ejecución; registró la diferencia de nombres de
campaña como warning y reportó observaciones informativas. Los valores
angulares cargados cumplen los rangos corregidos. Este resultado no determina
suficiencia o aptitud minera. No se calculó una trayectoria desurveyada. La
mínima curvatura está seleccionada, pero aún no implementada; permanecen
pendientes el CRS/EPSG, las reglas completas para `MD = 0` y el cálculo de
puntos dentro de segmentos survey.

## 14. Limitaciones y pendientes

### LIMITATION-01

El loader y un subconjunto de controles documentados que no requieren
umbrales pendientes están implementados. No están implementados `desurvey.py`,
`positioning.py`, `visualizer.py` o `exporter.py`.

### LIMITATION-02

El método de mínima curvatura está seleccionado, pero aún no implementado.
Faltan el CRS/EPSG, la orientación inicial que gobierna en `MD = 0`, el umbral
y severidad para diferencias angulares relevantes, la consulta de puntos entre
estaciones, la definición de survey incompleto y el manejo numérico de doglegs
extremos. La prohibición de extrapolar sin aprobación explícita y el error sin
XYZ para intervalos fuera de la trayectoria disponible ya están definidos,
pero no implementados.

### FUTURE-01

Definir tolerancias para comparar `length_m` con `to_m - from_m` y el umbral
angular que hace relevante una diferencia entre orientación del collar y
survey a profundidad cero; aprobar también qué severidad corresponde a cada
caso.

### FUTURE-02

Definir qué tablas requieren continuidad de intervalos, qué cambio angular
requiere revisión y qué rangos de plausibilidad corresponden a coordenadas,
elevación y densidad. Los gaps de density ya se registran descriptivamente
como `INFO`.

### FUTURE-03

Confirmar el significado analítico de valores assay cero/negativos y la
convención que relaciona `campaigns` del manifest con `campaign_id` de los CSV.

### FUTURE-04

Seleccionar y documentar qué orientación gobierna en MD = 0 y qué hacer si no
existe una estación survey en cero. En la comparación descriptiva previa del
release, los 32 pares collar/survey en profundidad cero coincidieron en azimut
y dip; este hecho observado no sustituye la decisión para datos futuros que
presenten discrepancias. Definir qué campos determinan un duplicado
idéntico/contradictorio y qué situaciones constituyen un survey incompleto.

### FUTURE-05

Definir el cálculo de posiciones entre estaciones para positioning, el manejo
numérico del caso de dogleg extremo y el CRS/EPSG antes de implementar y
validar la trayectoria. No extrapolar después de la última estación sin
aprobación explícita; los intervalos que excedan la cobertura disponible
deben recibir `ERROR` y no generar XYZ.

## 15. Uso del agente de IA

- [x] Explicación conceptual.
- [x] Arquitectura.
- [ ] Algoritmo.
- [x] Implementación.
- [x] Pruebas.
- [x] Depuración.
- [x] Revisión de unidades.
- [x] Documentación.

Comentario: asistencia para inventario y explicación de datos, propuesta de
arquitectura, revisión de relaciones y unidades, plan de validación y
consolidación objetiva de evidencia T1; implementación acotada del loader y
validator y elaboración/ejecución de pruebas; documentación de la selección
de mínima curvatura. No se implementó desurvey ni se interpretaron los
hallazgos como conclusiones mineras.

## 16. Checklist de cierre

- [x] Problema minero documentado.
- [ ] Inputs documentados.
- [ ] Unidades verificadas.
- [x] Supuestos identificados.
- [ ] Lógica minera documentada.
- [ ] Implementación terminada.
- [x] Pruebas ejecutadas o justificadas como NOT RUN.
- [x] Validación computacional realizada para loader y validator.
- [ ] Validación minera realizada.
- [x] Archivos modificados registrados.
- [x] Limitaciones registradas.
- [x] Registro actualizado.

**El estado permanece `IN_PROGRESS`; M01 no está cerrado.**
