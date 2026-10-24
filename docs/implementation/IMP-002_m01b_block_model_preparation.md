# IMP-002 — M01B: Preparación de datos para el modelo de bloques

## 1. Identificación

- **Implementation ID:** IMP-002
- **Module:** M01B — Block Model Preparation (baseline, auditoría de inputs, análisis de assay y compositado)
- **Date:** 2026-10-23
- **Group:** G03
- **Participants:** PENDIENTE DE COMPLETAR por el equipo
- **Status:** IN_PROGRESS (etapa de compositado implementada, probada y validada; faltan etapas posteriores de M01B)

---

## 2. Problema minero

Antes de construir un modelo de bloques geológico preliminar, los datos de exploración deben pasar de observaciones a lo largo del sondaje (intervalos FROM-TO de assay y litología) a un soporte reproducible (composites) que respete los contactos litológicos, pondere la ley por longitud y conserve trazabilidad de metros y de posición espacial.

---

## 3. Objetivo

1. Establecer un baseline verificado antes de iniciar M01B.
2. Auditar qué inputs están realmente disponibles y en qué estado.
3. Caracterizar el assay real del grupo antes de decidir el compositado.
4. Implementar el compositado de Cu a 2.0 m sin cruzar contactos litológicos, con `residual_flag` y posición XYZ, y generar `data/processed/m01b/composites.csv`.

No se implementan en esta etapa dominios, grid, topografía, modelo de bloques ni estimación de leyes.

---

## 4. Inputs

| Variable | Significado | Unidad | Origen | Obligatorio | Validación |
|---|---|---|---|---|---|
| collar.csv | Ubicación y profundidad de cada sondaje | m (x,y,z); deg (az,dip) | data/raw/ (M01) | Sí | Reutilizado de M01, ya validado |
| survey.csv | Orientación de la trayectoria por MD | m; deg | data/raw/ (M01) | Sí | Reutilizado de M01 (desurvey) |
| assay.csv | Intervalos FROM-TO con ley Cu/Mo/Au | m; % (Cu, Mo); g/t (Au) | data/raw/ (M01) | Sí | Auditado (outputs/tables/IMP002_assay_analysis_M01B.md) |
| lithology.csv | Intervalos FROM-TO con código litológico | m; código | data/raw/ (M01) | Sí | Auditado; define los contactos |
| density.csv | Intervalos de densidad | m; t/m3 | data/raw/ (M01) | No (no bloquea M01B) | No procesado todavía |
| alteration.csv | Intervalos de alteración | m; código | data/raw/ (M01) | No | EMPTY — INFO, fuente vacía válida |
| trayectorias XYZ | Posición por MD vía mínima curvatura | m | `src/m01/desurvey.py` (M01) | Sí, para XYZ de composites | Ejecutadas en memoria al compositar |
| topography | Superficie común del curso | UNKNOWN | Entrega del docente | No para compositado; sí para etapas posteriores | **MISSING — no localizada** |

No se inventó información para completar esta tabla. Detalle por fuente en `outputs/tables/IMP002_input_audit_M01B.md`.

---

## 5. Outputs

| Variable / resultado | Significado | Unidad | Destino |
|---|---|---|---|
| composites.csv | 3,632 composites de Cu: `hole_id, from_m, to_m, length_m, mid_m, x, y, z, lith_code, cu_pct, residual_flag, n_pieces` | m; %; coordenadas del proyecto | data/processed/m01b/ |
| baseline_M01B.txt | Estado Git + pruebas antes de M01B | texto | outputs/logs/ |
| IMP002_input_audit_M01B.md | Auditoría de disponibilidad de cada fuente | tabla | outputs/tables/ |
| IMP002_assay_analysis_M01B.md | Estadística real de assay y relación con lithology | tabla/texto | outputs/tables/ |

`composites.csv` es un derivado: no sustituye ni modifica `data/raw/`.

---

## 6. Supuestos

| ID | Supuesto | Justificación | Impacto |
|---|---|---|---|
| SUP-01 | El dataset real del grupo es DS01/EXP03 | Único release presente en `data/raw/` y verificado por hash en T1/IMP-001 | Si cambiara el release, la auditoría y los composites deben rehacerse |
| SUP-02 | Las pruebas se ejecutaron en una sesión de diagnóstico remoto, no en el venv de PyCharm del estudiante | Las versiones de dependencias podrían diferir | Repetir `python -m pytest` en PyCharm para dejar el baseline oficial en el entorno real |
| SUP-03 | Los contactos litológicos de `lithology.csv` son la fuente autoritativa de límites; los códigos se conservan tal cual | No existe diccionario de códigos; la semántica de cada código es UNKNOWN | Un composite hereda el código de su intervalo sin reinterpretarlo |
| SUP-04 | Las ventanas de 2.0 m parten del inicio de cada tramo litológico continuo (no de múltiplos de 2 m desde el collar) | Garantiza que ningún composite cruce un contacto | Tras un contacto en profundidad impar, las ventanas ya no coinciden con las muestras originales; un assay puede repartirse entre dos composites |
| SUP-05 | Tolerancia numérica de 1e-6 m para continuidad, contactos y residuales | Evitar falsos residuales por redondeo de punto flotante | Diferencias menores a 1e-6 m no se consideran huecos ni solapes |

---

## 7. Lógica minera

**Soporte.** Se usa una longitud objetivo de 2.0 m, igual al soporte nativo del assay (99.3% de las muestras ya miden 2.000 m). No se genera resolución que el sondaje no midió.

**Contactos.** Un composite no puede mezclar roca de dos litologías: promediaría la ley de dominios distintos como si fueran uno. Por eso, antes de compositar, cada assay que cruza un contacto se divide exactamente en el contacto y cada pieza hereda el `lith_code` del intervalo que la contiene (25 assays se dividieron, 3,619 → 3,644 segmentos).

**Ley.** La ley de cada composite es el promedio ponderado por longitud:

`Cu_comp = Σ(Cu_i × L_i) / Σ(L_i)`

donde `L_i` es la longitud de la parte del segmento `i` que cae dentro de la ventana. Solo se compone Cu (%): Mo y Au son 0.0 en el 100% de los registros y quedan fuera.

**Tramos continuos y residuales.** Cada sondaje se trata de forma independiente. Un tramo continuo es una cadena de segmentos contiguos con el mismo `lith_code`; un hueco o un cambio de código lo termina. Dentro de cada tramo las ventanas de 2.0 m parten del inicio del tramo. La última ventana puede ser menor a 2.0 m: se conserva como residual con `residual_flag = True`, no se elimina ni se une atravesando un contacto.

**Posición.** XYZ se calcula en el punto medio (`mid_m`) del composite sobre la trayectoria de mínima curvatura de M01, sin extrapolar más allá de la cobertura de la trayectoria.

---

## 8. Diseño computacional

### Módulos / archivos

- `src/m01/compositing.py` — nuevo; sigue la convención existente `src/m01/`.
- `tests/test_m01_compositing.py` — nuevo.

### Funciones / clases principales

- `split_assays_at_contacts(data)` — divide assays en contactos; reporta COMPOSITE-001..004 (litología inválida/solapada, assay inválido, tramo sin litología, assay solapado).
- `composite_segments(segments, target_length_m)` — arma tramos continuos y compone por ventanas ponderando por longitud.
- `position_composites(composites, trajectories)` — XYZ en `mid_m`; COMPOSITE-005 (ERROR, sin XYZ) si queda fuera de cobertura.
- `composite_m01_assays(data, trajectories)` — orquesta las tres anteriores.
- `summarize_compositing(data, result)` — cifras de validación minera.
- `write_composites_csv(composites, path)` y `run_m01b_compositing()` — escritura y ejecución completa (`python -m src.m01.compositing`).

### Dependencias relevantes

Reutiliza `loader.load_m01_data`, `validator.validate_m01_data`, `desurvey.desurvey_m01_data` y `positioning._position_at_depth` (función privada de M01, importada sin modificarla). No se agregaron dependencias externas. `main.py` no se modificó.

---

## 9. Etapas de implementación

### Etapa 1 — 2026-10-23

- **Objetivo:** Capturar el baseline antes de M01B.
- **Trabajo realizado:** `git status -sb`, `git rev-parse HEAD`, `python -m pytest -q` registrados en `outputs/logs/baseline_M01B.txt`.
- **Resultado:** Branch `main`, commit `8b3612c36d06b180940b71396dbb87f83706b29c`, 47 tests passed, 0 failed.
- **Pendiente:** Confirmar el baseline corriendo pytest en PyCharm (SUP-02).

### Etapa 2 — 2026-10-23

- **Objetivo:** Auditar los inputs disponibles para M01B.
- **Trabajo realizado:** Inspección de `data/raw/`, `data/PL00/` y de la carpeta `Data/` compartida fuera del repo.
- **Resultado:** Ver `outputs/tables/IMP002_input_audit_M01B.md`. No existe topografía en ninguna ubicación accesible. `desurvey.py` y `positioning.py` estaban implementados y probados con fixtures sintéticos, pero no se habían ejecutado contra el dataset real.
- **Pendiente:** Solicitar la topografía al docente.

### Etapa 3 — 2026-10-23

- **Objetivo:** Caracterizar el assay real antes de compositar.
- **Trabajo realizado:** Estadística de `length_m` y leyes, e intersección assay–lithology (pandas, solo lectura).
- **Resultado:** Ver `outputs/tables/IMP002_assay_analysis_M01B.md`. 99.3% de los assays a 2.0 m; Mo y Au sin variación; 25 assays cruzan contacto; 25 residuales de cierre.
- **Pendiente:** DECISION-01.

### Etapa 4 — 2026-10-23

- **Objetivo:** Implementar el compositado y generar los composites reales.
- **Trabajo realizado:** Se creó `src/m01/compositing.py` y `tests/test_m01_compositing.py` (18 pruebas con datos sintéticos etiquetados). Se ejecutó contra `data/raw/` con `python -m src.m01.compositing`, generando `data/processed/m01b/composites.csv`. Se hizo una verificación independiente con pandas directamente sobre los CSV de origen.
- **Resultado:** 3,632 composites, metros conservados (diferencia 0.0), 0 findings, los 32 sondajes con XYZ. Cifras en sección 13.
- **Pendiente:** Verificar en PyCharm; revisar el código litológico `AIR`; topografía y etapas posteriores de M01B.

### Etapa 5 — 2026-10-24

- **Objetivo:** Incorporar la topografía común, decidir dominios y grid, y clasificar cada bloque frente a la superficie (pasos 2, 6, 7 y 8 del PDF del docente).
- **Trabajo realizado:** Se copió `Topopl.csv` (sin modificar) a `data/raw/topography/` y se auditó (`outputs/tables/IMP002_topography_audit_M01B.md`). Se registraron DECISION-02 (dominios), DECISION-03 (grid) y DECISION-04 (método topográfico). Se creó `src/m01/block_model.py` y `tests/test_m01_block_model.py` (17 pruebas sintéticas etiquetadas). Se ejecutó contra los datos reales y se contrastó con un TIN independiente.
- **Resultado:** 29,952 bloques: ROCK 16,965 (56.6 %), PARTIAL 1,532 (5.1 %), AIR 11,455 (38.2 %), OUTSIDE_TOPO_COVERAGE 0; 0 findings. Detalle en DECISION-03 y DECISION-04.
- **Pendiente:** Validación de bloques, visualización, densidad y tonelaje. Revisión del estudiante de DECISION-03 y DECISION-04.

### Etapa 6 — 2026-10-24

- **Objetivo:** Asignar un dominio preliminar a cada bloque de roca (paso 8, P4), sin estimar ley.
- **Trabajo realizado:** Se creó `src/m01/domain_assignment.py` y `tests/test_m01_domain_assignment.py` (16 pruebas sintéticas etiquetadas). Se validó el radio de búsqueda con validación cruzada dejando un pozo fuera (DECISION-05) y se contrastó el resultado con un cálculo independiente (scipy).
- **Resultado:** 29,952 bloques; 18,497 de roca: 7,000 `ASSIGNED_SUPPORTED`, 8,897 `ASSIGNED_EXTRAPOLATED`, 2,600 `UNKNOWN_NO_SUPPORT`; 11,455 `NOT_ROCK_AIR`; 2,362 bloques con `mixed_flag`. Coincidencia con el cálculo independiente: 100 %.
- **Pendiente:** Validación de bloques (`block_validation`), visualización, densidad y tonelaje; revisión del estudiante de DECISION-03, -04 y -05.

---

## 10. Decisiones

### DECISION-01

**Problema:** ¿Qué longitud de composite y variable primaria usar, y cómo tratar los assays que cruzan contactos litológicos y los residuales?

**Alternativas consideradas:**

- A. Longitud objetivo 2.0 m, igual al soporte nativo dominante.
- B. No componer; usar `length_m` original.
- C. Longitud mayor (por ejemplo 4.0 m).

**Alternativa seleccionada:** A — 2.0 m, variable primaria Cu (%). Reglas: no cruzar contactos litológicos; dividir en el contacto los assays que lo cruzan; promedio ponderado por longitud; conservar residuales con `residual_flag`; no estimar Mo ni Au.

**Procedencia de las reglas:** la elección de la longitud (A) la hizo el estudiante el 2026-10-23. Las reglas de contactos, ponderación y residuales corresponden a las reglas aprobadas en clase para M01B (compartidas por el docente) y fueron contrastadas con los datos reales del grupo antes de aplicarse.

**Justificación (texto original del estudiante, sin editar):**

- Intento 1, evaluado PARCIAL: "Elijo A porque a menor longitud podemos tener muestras mas exactas, ademas agarra mas cruces de contacto."
- Intento 2, tras pista conceptual (ayuda H2): "la opción A no altera la resolución nativa y no genera cruces adicionales"

**Evidencia:** 3,594 de 3,619 assays (99.3%) ya miden 2.000 m; 25 residuales de cierre; 25 assays cruzan contacto (conjunto distinto); Mo y Au = 0.0 en el 100% de los registros.

**Impacto:** el compositado actúa sobre 25 cortes por contacto y 53 residuales; el resto de los datos se conserva casi intacto. Ver limitaciones.

### DECISION-02

**Problema:** ¿Qué dominios preliminares usar para el modelo de bloques geológico (M01B, paso 6)?

**Alternativas consideradas:**

- A. Un dominio por código litológico: `DIO`, `POR`, `BRX`, `REG`; `AIR` fuera del dominio geológico (`UNASSIGNED`).
- B. Dos dominios por comportamiento: `MINERALIZADO` (POR+BRX) y `ESTERIL` (DIO+REG).
- C. Tres dominios: `DIO`, `POR+BRX`, `REG`.

**Alternativa seleccionada:** A.

**Procedencia:** la alternativa A, la evidencia y las alternativas B y C fueron propuestas por el agente de IA (Claude) el 2026-10-24 a pedido del estudiante, como ejemplo guiado de práctica. El estudiante adoptó A y redactó su justificación a partir de una frase modelo entregada por el agente, que adaptó con sus palabras (texto más abajo). No hay regla de dominios entregada por el docente (el grupo parte de cero). Para el examen real el estudiante debe decidir y justificar sin esta ayuda.

**Justificación del estudiante (texto original, sin editar; adaptado de una frase modelo del agente):**

> "Elijo A (un dominio por litología) porque el Cu y la densidad cambian mucho entre los distintos tipos de litología: la litologia POR tiene unas 10 veces el % de Cu de DIO y BRX y casi el doble de POR, así que juntarlas en B o C mezclaría poblaciones distintas. Además A se puede reagrupar después y B o C no."

*Aclaración del agente sobre los datos:* POR tiene unas 10 veces el Cu de DIO (0.515 % frente a 0.050 %), y BRX tiene casi el doble de Cu que POR (1.043 % frente a 0.515 %).

**Justificación del agente (evidencia):**

1. El Cu separa las litologías: Cu ponderado POR 0.515 %, DIO 0.050 %, BRX 1.043 % (CV 0.06), REG 0.088 %. Fusionar mezclaría poblaciones distintas.
2. El método posterior es por grupo; cada dominio debe ser homogéneo.
3. A es el más fino y reversible: se puede reagrupar en B o C por remapeo; lo inverso exige volver a los datos.
4. Soporte para asignación preliminar: BRX 8 pozos / 258 composites; REG 32 pozos / 108 composites.
5. REG no se fusiona con DIO: densidad media 2.31 frente a 2.70 t/m3 (6 y 135 muestras).

**Evidencia:** `data/raw/lithology.csv`, `data/raw/density.csv` y `data/processed/m01b/composites.csv` (cálculo del 2026-10-24). BRX aparece solo entre 110 y 238 m, siempre dentro de POR (POR→BRX→POR). Alteración: sin registros.

**Limitaciones asociadas:** BRX solo en 8 pozos (continuidad entre pozos interpretada, no medida); REG con solo 6 muestras de densidad; `AIR` (2 intervalos, 3.0 m, 2 composites) con significado UNKNOWN, no se le asigna dominio.

### DECISION-03

**Problema:** ¿Qué tamaño de bloque y extensión de grid usar (paso 7, gate 2)?

**Alternativas consideradas:** 10x10x5 m; 20x20x10 m; 25x25x10 m; 30x30x15 m; 50x50x15 m.

**Alternativa seleccionada:** 25 x 25 x 10 m, origen (242225, 8196100, 3060), 26 x 24 x 48 bloques = 29,952 celdas (huella de los sondajes más un bloque de margen; techo en 3,540 m).

**Procedencia:** propuesta por el agente de IA (Claude) el 2026-10-24; el estudiante la aceptó ("si queda aceptado el grid"). Justificación del estudiante en sus propias palabras: PENDIENTE.

**Evidencia:** espaciamiento de collares por vecino más cercano: mediana 65 m (mín. 20, máx. 140). Con 25x25x10 m cada bloque ocupado recibe en promedio 4.8 composites (10x10x5 m: 2.4; más grueso que el contacto POR/BRX de 18 a 80 m solo a partir de 50 m). 10 m de altura es múltiplo de los 2 m del composite. El soporte real no depende del tamaño de bloque: la fracción de celdas a 50 m o menos de un composite es 25 a 29 % en todas las opciones. Solo el 2.7 % de las celdas del grid contiene composites. Hallazgo GRID-001: la superficie llega a 3,533.8 m dentro del grid, por lo que el techo se subió de 3,510 a 3,540 m (45 a 48 capas; 28,080 a 29,952 celdas).

### DECISION-04

**Problema:** ¿Cómo se evalúa la superficie topográfica y cómo se clasifica cada bloque (aire, roca, parcial, fuera de cobertura)? (paso 8, etapa P3)

**Alternativas consideradas:**

- A. Clasificar solo por el centro del bloque (rápido; puede equivocarse en bloques que la superficie corta).
- B. Evaluar la superficie en las 4 esquinas y el centro de cada columna; ROCK si el tope del bloque no supera la cota mínima, AIR si su base no está bajo la cota máxima, PARTIAL en otro caso.
- C. Calcular la fracción ocupada de cada bloque (exacto, pero con más costo y supuestos).

**Alternativa seleccionada:** B.

**Superficie:** la topografía son curvas de nivel digitalizadas (99.1 % de las cotas enteras). La cota en un punto se obtiene con la ponderación inversa al cuadrado de la distancia del punto más cercano de cada uno de 8 sectores angulares, radio 40 m. Hay cobertura solo si al menos 4 sectores tienen punto y los puntos rodean al lugar (mayor hueco angular menor a 180 grados); si no, el estado es `OUTSIDE_TOPO_COVERAGE` y no se extrapola. Solo se usa la biblioteca estándar de Python, como el resto del repositorio.

**Procedencia:** decidida e implementada por el agente de IA (Claude) el 2026-10-24 por pedido del estudiante. PENDIENTE de revisión, adopción y justificación del estudiante.

**Evidencia (verificación independiente con TIN lineal de scipy, solo para contrastar):** diferencia de cota en 624 centros de columna: media 0.02 m, desv. 0.31 m, máx. |d| 1.43 m. Estados coinciden en el 99.9 % de una muestra de 3,000 bloques (2 discrepancias, ambas ROCK/PARTIAL en el límite). Los 3,632 composites caen dentro del grid: 3,440 en bloques ROCK, 192 en PARTIAL, 0 en AIR. Resultado: ROCK 16,965; PARTIAL 1,532; AIR 11,455; OUTSIDE_TOPO_COVERAGE 0.

**Limitaciones:** el volumen de un bloque PARTIAL no es el volumen nominal de roca (no se calcula la fracción). La superficie proviene de curvas de nivel y su CRS no consta (UNKNOWN). La coincidencia collar-superficie es de ±2 m. El estado AIR/ROCK no implica geología interpretada.

### DECISION-05

**Problema:** ¿Cómo asignar dominio geológico a un bloque y hasta qué distancia de los datos (paso 8, gate 3: vecindad, radios, fallback)?

**Alternativas consideradas:** (A) un solo radio; (B) dos pasadas: soportada y extrapolada, con `UNKNOWN` más allá; (C) elipsoide con anisotropía vertical. Método: dominio del composite más cercano (distancia 3D, sin ponderar), con `UNKNOWN` fuera de radio.

**Alternativa seleccionada:** B, radios 50 m (`ASSIGNED_SUPPORTED`) y 100 m (`ASSIGNED_EXTRAPOLATED`), isotrópico. Los composites con código `AIR` (2) se excluyen como fuente; no se inventa dominio para `AIR`, aire fuera de topografía ni bloques sin soporte.

**Procedencia:** decidida e implementada por el agente de IA (Claude) el 2026-10-24 por pedido del estudiante. PENDIENTE de revisión, adopción y justificación del estudiante.

**Evidencia (validación cruzada dejando un pozo fuera, 3,630 composites):** predecir la litología con el composite más cercano de otros pozos acierta 98.4 % a 25 m, 92.7 % a 40 m, 90.9 % a 50 m, 87.5 % a 65 m, 82.7 % a 100 m y 75.0 % a 150 m, con una cobertura de 17.5, 42.4, 49.4, 58.2, 70.2 y 100 %. La clase mayoritaria sola (DIO) acierta 46.6 %. La franja de 50 a 100 m acierta unos 63 %, por eso se marca como extrapolada. Un factor de anisotropía vertical de 2 sube el acierto de 87.5 a 88.8 % (65 m), mejora que no justifica la complejidad. Contraste independiente con scipy: estados 100 % iguales, dominios iguales en 15,897 bloques, máxima diferencia de distancia 0.0005 m. De los 770 bloques que contienen composites, el 98.7 % toma el dominio mayoritario interno.

**Limitaciones:**

- Las proporciones no son proporciones geológicas: entre los bloques asignados, DIO 72.2 %, POR 19.2 %, REG 7.6 % y BRX 1.0 %, frente a 46.6 %, 43.4 %, 2.9 % y 7.1 % de los metros compuestados. El vecino más cercano no interpola contactos ni extiende lentes como BRX (8 pozos, 18 a 80 m de espesor), y los bloques entre pozos quedan más cerca de la parte superior de cada pozo.
- El 38 % de los bloques de roca tiene soporte a 50 m o menos; el 14 % queda `UNKNOWN`.
- `mixed_flag` marca 2,362 bloques con más de un dominio dentro de 50 m (cerca de contactos); el contacto no se modela.
- El dominio asignado es una clasificación categórica preliminar, no un modelo geológico interpretado ni de recursos.

---

## 11. Archivos creados o modificados

```text
src/m01/compositing.py                                (nuevo)
tests/test_m01_compositing.py                         (nuevo)
data/processed/m01b/composites.csv                    (nuevo, derivado)
docs/implementation/IMP-002_m01b_block_model_preparation.md  (nuevo)
outputs/logs/baseline_M01B.txt                        (nuevo)
outputs/tables/IMP002_input_audit_M01B.md             (nuevo)
outputs/tables/IMP002_assay_analysis_M01B.md          (nuevo)
data/raw/topography/Topopl.csv                        (nuevo, material oficial sin modificar)
outputs/tables/IMP002_topography_audit_M01B.md        (nuevo)
src/m01/block_model.py                                (nuevo)
tests/test_m01_block_model.py                         (nuevo)
data/processed/m01b/blocks_topo.csv                   (nuevo, derivado)
src/m01/domain_assignment.py                          (nuevo)
tests/test_m01_domain_assignment.py                   (nuevo)
data/processed/m01b/blocks_domains.csv                (nuevo, derivado)
docs/exam/T2_M01B/01_AGENT_EXAM_M01B.md               (nuevo, material oficial sin modificar)
docs/exam/T2_M01B/02_SCENARIO_EXAM_M01B.md            (nuevo, material oficial sin modificar)
```

Los archivos originales de `data/raw/` no fueron modificados; se agregó la carpeta `data/raw/topography/` con `Topopl.csv` sin cambios. Ningún archivo de gobernanza fue modificado. `main.py`, `loader.py`, `validator.py`, `desurvey.py` y `positioning.py` no fueron modificados.

---

## 12. Pruebas realizadas

### Comandos ejecutados

```text
python -m pytest tests/test_m01_compositing.py -v
python -m pytest -q
python -m src.m01.compositing
```

### Resultado real

- **Status:** PASS (ejecutado en sesión de diagnóstico remoto; ver SUP-02)
- **Tests passed:** 65 en total (47 previos + 18 nuevos de compositado)
- **Tests failed:** 0
- **Etapa 5 (2026-10-24):** 82 pruebas en total (65 previas + 17 de `block_model`), 0 fallos, ejecutadas con `python -m unittest discover` en sesión de diagnóstico remoto; también `python -m src.m01.block_model` sobre los datos reales.
- **Etapa 6 (2026-10-24):** 98 pruebas en total (82 + 16 de `domain_assignment`), 0 fallos, con `python -m unittest discover` en sesión de diagnóstico remoto; también `python -m src.m01.domain_assignment` sobre los datos reales.

Las 18 pruebas nuevas usan datos sintéticos pequeños, solo en tests, y cubren: dos assays de 1 m que forman un composite de 2 m; ley ponderada por longitud; assay de 2 m conservado; residual terminal; contacto dentro de un assay; ningún composite cruza un contacto; conservación de metros; `from_m < to_m` y longitud positiva; independencia entre sondajes; hueco que corta el tramo; assay con tramo sin litología, solapado o inválido; XYZ en un pozo vertical; composite fuera de cobertura sin XYZ; escritura del CSV.

---

## 13. Validación minera

- [x] Unidades consistentes (m para profundidades, % para Cu; según `data_dictionary.csv`).
- [ ] Signos económicos correctos cuando corresponda. (No aplica en esta etapa)
- [x] Magnitudes razonables.
- [x] Restricciones operacionales respetadas (sin extrapolar trayectoria, sin modificar `data/raw/`).
- [x] Casos extremos revisados (residuales, cortes por contacto, código `AIR`).
- [x] Caso independiente revisado: se recalcularon metros, media de Cu y ausencia de cruces de contacto con pandas directamente desde `data/raw/`, sin usar el módulo.

### Evidencia / comentario

| Métrica | Valor |
|---|---|
| Assays originales | 3,619 (32 sondajes) |
| Metros originales | 7,214.872 m |
| Segmentos tras cortar en contactos | 3,644 (3,619 + 25 cortes) |
| Composites | 3,632 |
| Metros compositados | 7,214.872 m (diferencia 0.0) |
| Composites de 2.0 m | 3,579 |
| Composites residuales | 53 (26 en el cierre del sondaje, 27 originados por un contacto) |
| Distribución de longitudes | 2.0 m: 3,579; 1.0 m: 28; resto: 25 valores entre 0.06 y 1.999 m |
| Media Cu ponderada, antes (assay) | 0.322974 % |
| Media Cu ponderada, después (composites) | 0.322974 % |
| Composites por `lith_code` | DIO 1,690; POR 1,574; BRX 258; REG 108; AIR 2 |
| Composites sin XYZ | 0 |
| Findings de compositado | 0 |

Verificación independiente: 0 composites cruzan un contacto o tienen código distinto al de su intervalo litológico; 0 huecos entre composites consecutivos de un mismo sondaje; ningún `mid_m` supera `final_depth_m`; ningún composite queda por encima de la cota del collar.

---

## 14. Limitaciones y pendientes

### LIMITATION-01

No existe archivo de topografía accesible (ni en `data/raw/`, `data/PL00/` ni en la carpeta `Data/` compartida). No bloquea el compositado; bloquea las etapas que clasifican aire/roca.

### LIMITATION-02

Como el soporte nativo ya es 2.0 m, el compositado casi no regulariza ni suaviza el dato: su efecto real se concentra en los 25 cortes por contacto y en los residuales.

### LIMITATION-03

53 composites (1.5% de 3,632) son residuales menores a 2.0 m: 26 en el cierre del sondaje y 27 por contactos. Tienen menos soporte que el resto; `residual_flag` permite filtrarlos o ponderarlos en etapas posteriores. Por SUP-04, tras un contacto en profundidad impar las ventanas dejan de coincidir con las muestras originales y un assay puede repartirse entre dos composites.

### LIMITATION-04

El código litológico `AIR` aparece en 2 intervalos (CA-C02-007, 1.0–2.0 m; CA-C03-003, 0.0–2.0 m), ambos en el tope del sondaje, y tienen ley Cu medida. No hay diccionario de códigos, por lo que su significado es UNKNOWN. Se conserva como está; debe revisarse antes de usarlo en cualquier clasificación aire/roca.

### LIMITATION-05

`positioning._position_at_depth` es una función privada de M01 que `compositing.py` importa. Si M01 la renombra, el compositado debe actualizarse.

### FUTURE-01

Etapas posteriores de M01B (dominios, grid, topografía, asignación a bloques) no están implementadas ni decididas.

### FUTURE-02

Repetir `python -m pytest` y `python -m src.m01.compositing` en el entorno PyCharm del estudiante para dejar la evidencia en el entorno real.

---

## 15. Uso del agente de IA

- [x] Explicación conceptual.
- [x] Arquitectura.
- [x] Algoritmo.
- [x] Implementación.
- [x] Pruebas.
- [ ] Depuración.
- [x] Revisión de unidades.
- [x] Documentación.

**Comentario:** Se usó Claude (sesión con acceso remoto al repositorio) para el baseline, la auditoría de inputs, el análisis de assay, la implementación de `compositing.py`, la escritura de las pruebas y esta documentación. La elección de la longitud de composite (alternativa A) fue del estudiante; las reglas de contactos, ponderación y residuales provienen de las reglas aprobadas en clase.

---

## 16. Checklist de cierre

- [x] Problema minero documentado.
- [x] Inputs documentados.
- [x] Unidades verificadas.
- [x] Supuestos identificados.
- [x] Lógica minera documentada.
- [x] Implementación terminada (etapa de compositado).
- [x] Pruebas ejecutadas.
- [x] Validación computacional realizada.
- [x] Validación minera realizada (etapa de compositado).
- [x] Archivos modificados registrados.
- [x] Limitaciones registradas.
- [x] Registro actualizado.

**Estado: IN_PROGRESS.** El compositado cumple su checklist, pero M01B no se cierra: faltan la verificación en el entorno PyCharm, la topografía y las etapas posteriores. No corresponde `CLOSED`.
