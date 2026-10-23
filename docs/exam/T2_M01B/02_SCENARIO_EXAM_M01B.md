# 02 — ESCENARIO TÉCNICO DEL EXAMEN T2 · M01B

**Proyecto:** PlanMinUPN — Planeamiento de Minado · 2026-2  
**Archivo:** `02_SCENARIO_EXAM_M01B.md`  
**Versión:** 1.0 — propuesta para revisión y aprobación docente  
**Documento complementario:** [`01_AGENT_EXAM_M01B.md`](01_AGENT_EXAM_M01B.md)  
**Destinatarios:** Copilot/agente autorizado, estudiantes y docente  
**Producto objetivo:** **modelo de bloques geológico preliminar 3D**, con trazabilidad de la geometría, topografía, asignación categórica y limitaciones.  
**Principio:** **Primero minería → después modelo → después algoritmo → después código.**

> **IMPORTANTE PARA EL AGENTE:** Este documento describe el escenario académico y los criterios de avance; **NO** certifica el estado de ningún repositorio concreto. Antes de afirmar que un grupo está alineado, inspecciona su repositorio real y aplica `REPOSITORY_CHECK` y, si es necesario, `ALIGNMENT_RECOVERY`, según `01_AGENT_EXAM_M01B.md`. Las decisiones de ingeniería las toma y justifica el estudiante. **No escribas código antes del gate aprobado de esa etapa.**

---

## 1. Encargo del examen

En el trabajo anterior, los grupos desarrollaron progresivamente **M01 — Validate & Desurvey** y prepararon **M01B**, incluida la auditoría de los datos de exploración y el compositado de ensayes, con avances que **pueden diferir entre repositorios**.

El encargo técnico de T2 es conducir el proyecto, desde su **último estado comprobado**, hacia una representación tridimensional **preliminar** de bloques clasificados geológicamente. El estudiante debe ser capaz de explicar cómo una observación a lo largo de un sondaje puede informar una **celda volumétrica**, bajo qué supuestos y con qué incertidumbre.

La evidencia evaluable no es solo el resultado visual: también comprende el **diagnóstico del repositorio, el plan, las decisiones, las alternativas descartadas, la autorización del código, las pruebas, la validación minera y el registro fiel de la interacción con IA**.

### 1.1 Producto que SÍ se persigue

Una malla tridimensional reproducible que, según las decisiones aprobadas y las limitaciones de los datos, permita:

- identificar cada bloque, sus índices y sus coordenadas/volumen nominal;
- relacionarlo con la superficie topográfica y distinguir aire, roca y situaciones indeterminadas;
- atribuir **provisionalmente** un código litológico o de dominio a bloques de roca **solo donde exista soporte defendible**;
- conservar estados como `UNKNOWN`, `UNASSIGNED`, `OUTSIDE_TOPO_COVERAGE` o equivalentes cuando no sea justificable clasificar;
- inspeccionar los bloques en 3D junto con la información de control disponible (topografía, sondajes y, cuando sea posible, composites);
- comprobar y documentar qué parte del modelo ha sido probada y validada desde el punto de vista minero.

### 1.2 Producto que NO se exige en este examen

No forman parte del alcance obligatorio:

- estimación de ley de Cu, Mo o Au a bloques por NN, IDW o Kriging;
- cálculo definitivo de toneladas, valorización económica de bloques o ley de corte;
- declaración de recursos o reservas minerales;
- pit final, precedencias, fases, secuenciamiento o programa de producción;
- construcción de sólidos geológicos profesionales o interpretación de dominios inexistentes en las fuentes;
- refactorización global del repositorio o sustitución de su arquitectura válida.

> Un modelo con bloques coloreados por una categoría interpolada/transferida **no es automáticamente** un modelo geológico interpretado ni una estimación formal de recursos. La **asignación geológica categórica es una inferencia espacial** y requiere declarar límites, soporte e incertidumbre.

---

## 2. Situación de partida: referencia académica, no presunción de cumplimiento

### 2.1 Trayectoria desarrollada antes de T2

```text
M01 — EXPLORACIÓN Y POSICIONAMIENTO
Fuentes: collar + survey + assay + lithology + density + alteration
              │
              ▼
Carga → validación → desurvey → positioning → visualización/diagnóstico
              │
              ▼
M01B — PREPARACIÓN DE DATOS PARA BLOQUES
Baseline → auditoría de inputs → análisis de assay y lithology
         → decisiones de compositado → compositing → composites
              │
              ▼
================ INICIO TÉCNICO DE T2 ================
              │
        DOMINIOS / LITOLOGÍA PRELIMINAR
              │
        GEOMETRÍA Y TAMAÑO DEL GRID
              │
        TOPOGRAFÍA Y CLASIFICACIÓN ESPACIAL
              │
        ASIGNACIÓN GEOLÓGICA A BLOQUES
              │
        VALIDACIÓN Y VISUALIZADOR 3D
              │
              ▼
MODELO DE BLOQUES GEOLÓGICO PRELIMINAR
```

**Observación:** el orden de las verificaciones puede adaptarse para inspeccionar insumos antes de implementar; no se permite saltar una decisión de ingeniería necesaria. Los nombres de módulos, paquetes y columnas deben deducirse **del repositorio real**, no de esta figura.

### 2.2 Variaciones legítimas entre grupos

Pueden existir estructuras como `src/m01/`, `src/mod1/` o `src/planminpy/modules/`, diferentes nombres de tablas derivadas y distintos conjuntos de pruebas. No fuerces una reorganización cosmética. Evalúa **capacidades comprobables** y respeta la arquitectura existente.

Los datasets de los grupos pueden variar; por tanto **no presupongas**:

- número de sondajes o registros;
- soporte dominante o longitud final de composite (2 m es una **posible decisión previa de un grupo**, no una orden universal);
- número de contactos litológicos o nombres de códigos;
- presencia de leyes diferentes de Cu con información útil;
- parámetros de estimación geológica, espaciamiento, tamaño de bloque o extensión;
- posición local de `Topopl.csv`, existencia de CRS/EPSG o número de bloques.

Todos esos extremos deben comprobarse o figurar como `UNKNOWN`.

---

## 3. Estado base mínimo del examen: qué debe verificar Copilot

**Objetivo de esta fase:** establecer una base técnica justa, trazable y reproducible **antes** de evaluar decisiones sobre el modelo geológico. Clasifica cada requisito como `VERIFIED`, `PARTIAL`, `MISSING`, `UNKNOWN` o `BLOCKED`; indica la **evidencia real**. Si falta algo necesario, activa recuperación guiada.

### 3.1 Matriz de comprobación

| ID | Capacidad / requisito | Qué debe inspeccionar el agente | Criterio de comprobación |
|---|---|---|---|
| B00 | Contexto y Git | Rama, `git status -sb`, HEAD, modificaciones pendientes, reglas del proyecto, estructura real. | Riesgos y estado actual identificados; no exigir árbol limpio a costa de perder trabajo. |
| B01 | Fuentes oficiales | Assay, collar, survey, lithology, density, alteration, diccionario/manifest si existen; hash si hay manifiesto. | Procedencia, integridad, campos y unidades verificadas, sin alterar `data/raw/`. |
| B02 | M01: carga y validación | Loader/validator o equivalentes, pruebas y diagnósticos existentes. | La capacidad funciona o se explicitan limitaciones verificadas. |
| B03 | M01: desurvey y positioning | Trayectorias y XYZ realmente **generados/disponibles**, relación profundidad–posición. | Información espacial utilizable para M01B; no basta que exista `positioning.py`. |
| B04 | M01: visualización previa | Visualizador y salidas reales, si se implementaron. | Antecedente deseable; su ausencia **no bloquea por sí sola** la geometría si B03 está verificado. Registrar deuda técnica. |
| B05 | Baseline y documentación M01B | `IMP-002` o equivalente real, baseline, decisiones y evidencia. | Estado registrado sin inventar pruebas, rutas ni validaciones. |
| B06 | Auditoría assay–lithology | Intervalos, longitudes, contactos, nulos, duplicados, cobertura, campos y unidades. | Información auditada y anomalías clasificadas como `ERROR/WARNING/INFO`. |
| B07 | Regla de compositado | Longitud objetivo, ponderación de ley por longitud, reglas de residuos y contactos **del grupo**. | Decisión explícita, justificada, documentada y reproducible. |
| B08 | Compositing y salida | Código reutilizable, tests ejecutados, tabla realmente generada, columnas y métricas. | Conservación de longitud cuando corresponda, coherencia de ley ponderada, separación por contactos según regla aprobada. |
| B09 | Topografía común | Fuente oficial localizable, campos XY/Z, cobertura y compatibilidad con sondajes. | Disponible para uso; si no existe o no es compatible, recuperación o `BLOCKED`. |
| B10 | Capacidad de prueba y trazabilidad | Comandos de ejecución y tests, estructura `data/processed/`, `outputs/`, registro IMP. | Pueden comprobarse cambios futuros y preservarse los originales. |

**Dependencias críticas para programar T2:** datos espaciales utilizables (**B01/B03**), base litológica y composites coherentes (**B06–B08**), topografía comprobada para la etapa correspondiente (**B09**) y trazabilidad/pruebas (**B00/B05/B10**). La falta de un visualizador heredado (**B04**) se registra, pero no obliga a detener todo el plan.

**Precisión:** si falta un requisito crítico no es correcto escribir `ESTADO BASE: VERIFICADO`. El agente debe recuperar lo necesario o registrar `RECOVERY_BLOCKED`. Puede continuar **solo con el plan conceptual**, dejando claramente pendientes la generación y la validación de resultados.

### 3.2 Evidencia vs. supuesto

- **`IMPLEMENTED`:** existe código que realiza esa función; no demuestra que se ejecutó correctamente.
- **`TESTED`:** hay ejecución y resultado verificables de pruebas relevantes.
- **`GENERATED`:** existe salida derivada genuina de datos oficiales, con comando/proceso identificable.
- **`MINING_VALIDATED`:** se contrastó la salida con criterios geológicos/mineros explicados, no solo con `pytest`.
- **`DOCUMENTED`:** el IMP y/o informes registran decisiones, pruebas y limitaciones reales.

No uses estos estados como sinónimos. Un archivo presente no significa un módulo cerrado.

### 3.3 Recuperación si el estado base no está alineado

En `ALIGNMENT_RECOVERY`, prioriza el faltante mínimo **sin deshacer trabajo ajeno**:

```text
Diagnóstico de solo lectura
       ↓
Evidencia del faltante o contradicción
       ↓
Microteoría + 2–4 alternativas plausibles
       ↓
Estudiante elige, justifica y responde
       ↓
Si exige edición: gate y aprobación específica
       ↓
Recuperar una capacidad a la vez
       ↓
Tests + interpretación + validación pertinente
       ↓
Actualizar evidencia y repetir B00–B10 necesarios
       ↓
BASE_VERIFIED   o   RECOVERY_BLOCKED
```

Ejemplos de recuperación: instalar dependencias **solo con autorización**, corregir una prueba que falla sin refactorizar todo M01, generar derivados verdaderos que faltan, recuperar la topografía desde la fuente oficial **sin inventar archivos**, corregir inconsistencias documentadas de composites o completar evidencia faltante sin reconstruir artificialmente el pasado.

**No ejecutes** `git reset --hard`, `git clean -fd`, `git add .`, `push --force`, cambios de gobernanza o ediciones de fuente para forzar alineación. Evita commits automáticos. Si existe un riesgo de pérdida de trabajo, pregunta con alternativas y consulta al docente.

---

## 4. Inventario técnico que debe construir con el estudiante

Antes de planificar parámetros, el agente identifica el **contrato de datos real**; las siguientes son *categorías esperadas*, no nombres de columna garantizados.

| Insumo | Información requerida o esperada | Comprobación minera y de unidades | Uso previsto |
|---|---|---|---|
| `collar` | ID, coordenadas y profundidad/longitud declarada del sondaje. | Sistema de coordenadas, cota, unidades de longitud; correspondencia con survey. | Extensión y ubicación del modelo. |
| `survey` | MD y orientación de las trayectorias. | Convención de azimut/inclinación, grados, continuidad y cobertura en MD. | Posicionamiento/desurvey. |
| `assay` | Intervalos FROM–TO y leyes disponibles. | Longitudes positivas, unidades de ley, nulos/sentinelas y traslapes. | Evidencia de muestreo/composites; **sin estimar ley a bloques en T2**. |
| `lithology` | Intervalos FROM–TO y códigos categóricos. | Semántica documentada o `UNKNOWN`; contactos, continuidad y traslapes. | Representación litológica y soporte para asignación. |
| `density` | Valores e intervalos o referencias de densidad. | Unidades, cobertura, soporte y asociación por litología, si existe. | Fuente disponible para futuro; **no obliga a calcular tonelaje en T2**. |
| `alteration` | Códigos/intervalos si hay filas. | Un archivo vacío válido puede ser `INFO`; no inventar alteraciones. | Contexto geológico solo si está sustentado. |
| Trayectorias XYZ | Coordenadas 3D por profundidad MD. | Orientación, unidades, continuidad, referencia espacial. | Ubicar contactos y composites. |
| Composites M01B | Intervalos, longitudes, posición y código litológico **si corresponde**. | Conservación, residualidad, contacto, ley ponderada y cobertura. | Observaciones de control de la malla. |
| Topografía (`Topopl.csv` u origen oficial identificado) | Puntos/superficie con coordenadas horizontales y elevación. | Compatibilidad geométrica, cobertura, fuera de huella, CRS si consta. | Relación bloque–superficie: aire/roca/parcial/desconocido. |

**Regla de unidades:** longitudes, coordenadas y elevaciones requieren convención explícita (habitualmente metros **solo si la fuente lo confirma**); leyes deben respetar sus unidades de origen. El eje vertical y el signo de elevación deben definirse y probarse. No asumas EPSG, datum o conversiones que no consten.

**Regla de integración:** el hecho de que la topografía sea compartida y tenga compatibilidad general revisada por el docente **no significa** que el CSV ya esté dentro de cada repo o que cubra toda celda propuesta. Su integración debe respetar la estructura local de `data/raw/` y **nunca sobrescribir** los datos oficiales existentes.

---

## 5. Secuencia obligatoria de decisiones y gates

**El agente no entrega este recorrido como respuestas prefijadas.** Lo usa como mapa interno para guiar al estudiante. En cada hito presenta **concepto teórico → implicancias de alternativas → evidencia/faltantes → 2–4 alternativas → elección y justificación del alumno → retroalimentación → gate cuando corresponda**. Una pregunta principal por turno; no adelantar soluciones.

### ETAPA P0 — Diagnóstico y plan de implementación (SIN CÓDIGO)

**Problema:** establecer qué falta para convertir información de sondajes en una malla geológica provisional.

**Inputs:** estado real de M01/M01B, registros IMP, outputs, tests, estructura Git.  
**Outputs:** mapa de capacidades, dependencias, riesgos y plan incremental propuesto/defendido por el estudiante.  
**Decisiones:** orden técnico, prerequisitos, alcance mínimo de cada módulo, prioridades de recuperación.  
**Validación:** el plan identifica qué dato produce cada etapa y distingue modelo geológico de estimación de leyes.  
**Gate:** `PLAN_APPROVED` cuando el estudiante justifica el orden; **no autoriza código**.

### ETAPA P1 — Códigos litológicos y dominios preliminares

**Problema minero:** representar qué información geológica es observable en intervalos de sondaje y qué significado puede sostenerse al trasladarla al espacio.

**Teoría a explicar:** litología vs. dominio de estimación, contactos, discretización a intervalos, continuidad y limitaciones de categorías sin diccionario. 

**Decisiones a obtener del alumno:**

- ¿Los códigos litológicos tienen significado documentado o se conserva únicamente su código?
- ¿Cómo respetar los contactos al asociar composites y litología?
- ¿Qué representa un tramo `UNASSIGNED`/ambiguo?
- ¿Qué metodología preliminar permite reconocer unidades sin afirmar que se construyeron sólidos geológicos interpretados?

**Alternativas didácticas que puede discutir (sin seleccionarlas por el alumno):** usar códigos tal cual; agrupar códigos solo con justificación geológica; representar contactos/segmentos y `UNASSIGNED` antes de cualquier agrupación. Mostrar ventajas y riesgos de cada alternativa.

**Inputs:** `lithology`, trayectorias MD→XYZ, composites; diccionario real si existe.  
**Outputs posibles:** intervalos/segmentos litológicos posicionados, catálogo de códigos y reporte de ambigüedades; rutas según arquitectura existente.  
**Pruebas:** no crear intervalos negativos, no atravesar contactos prohibidos, no asignar categorías inexistentes, preservar trazabilidad de la fuente.  
**Validación minera:** contactos coherentes con las perforaciones y limitaciones de interpretación explícitas.  
**Gate:** `P1_DOMAINS` (aprobación independiente antes del primer código de esta etapa).

### ETAPA P2 — Extensión, origen y geometría de la malla

**Problema minero:** delimitar el volumen de estudio y discretizarlo en celdas reproducibles sin perder trazabilidad espacial.

**Parámetros críticos a decidir — NO inventar:**

| Parámetro | Significado | Evidencia que debe pedir el agente | Consecuencia de alternativas |
|---|---|---|---|
| `xmin/xmax`, `ymin/ymax`, `zmin/zmax` | Extensión física de malla. | Distribución XYZ de perforaciones, contactos, cobertura de topografía y márgenes justificados. | Una extensión excesiva genera celdas sin soporte; una pequeña recorta el volumen relevante. |
| `origin_x/y/z` | Punto de referencia del grid. | Convenciones y límites del proyecto. | Desplaza centros y límites; afecta reproducibilidad de índices y comparación entre ejecuciones. |
| Orientación de ejes | Convención geométrica, `z` hacia arriba o equivalente documentado. | Contrato de coordenadas. | Un signo incorrecto invierte la relación con topografía. |
| `dx/dy/dz` | Dimensiones de bloque. | Espaciamiento de datos en planta y profundidad, soporte de composites, propósito didáctico. | Bloques pequeños: más detalle/costo y posible falsa resolución; grandes: menos detalle y pérdida de variación. |
| `nx/ny/nz` | Número de celdas. | Extensiones y dimensiones seleccionadas. | Tamaño de memoria/tiempo; cobertura exacta y ajustes en límites. |
| Margen / padding | Ampliación del grid respecto al soporte observado. | Cobertura espacial; decisión y razón del estudiante. | Más cobertura, pero más zonas posiblemente `UNKNOWN`. |
| ID, índices, centros, esquinas | Convención de almacenamiento del bloque. | Requisitos de geometría y futuras pruebas. | Errores de offset de media celda, solapes o duplicidades. |

**Razonamiento que debe inducir el agente:** comparar **al menos dos geometrías candidatas calculadas con los datos reales**, estimar bloques totales y memoria/costo aproximado, reconocer relación entre espaciamiento de sondajes y soporte de composites, y explicar qué se gana/pierde. No aceptar `dx = dy = dz = longitud de composite` sin un razonamiento espacial adicional.

**Relaciones generales admisibles para enseñanza (no valores elegidos):**

```text
nx = ceil((xmax - xmin) / dx)
ny = ceil((ymax - ymin) / dy)
nz = ceil((zmax - zmin) / dz)
N_bloques = nx * ny * nz
V_nominal = dx * dy * dz
x_centro(i) = origin_x + (i + 0.5) * dx   [análogo para y,z]
```

Si el número de celdas obliga a cubrir más allá de los máximos, documentar los límites reales del grid o resolver el ajuste de manera explícita; no presentar bordes extrapolados como datos observados.

**Inputs:** coordenadas verificadas, extensión y parámetros aprobados.  
**Outputs posibles:** tabla de grid `block_id, i, j, k, x, y, z, dx, dy, dz, volume_nominal` y metadatos del grid.  
**Pruebas:** IDs únicos, orden e índices, centro/esquinas correctos, dimensiones/volúmenes positivos, número esperado de bloques, reproducibilidad y manejo de tamaños inviables.  
**Validación minera:** resolución defendible frente al soporte real; zonas modeladas vs. observadas diferenciadas.  
**Gate:** `P2_GRID` (independiente).

### ETAPA P3 — Topografía y condición aire/roca

**Problema minero:** reconocer qué parte del volumen de la malla es subsuperficial y qué parte está sobre la superficie disponible.

**Teoría:** superficie topográfica, interpolación/cobertura de XY, referencia vertical, límite aire–roca; diferencia entre **clasificación del centro**, **evaluación de vértices** y **fracción ocupada**.

**Decisiones críticas:**

- fuente oficial y validación de sus campos, cobertura espacial y unidades;
- método para evaluar `z_topo(x,y)` donde hay información **y estrategia al salir de cobertura**;
- criterio de clasificación: centro de celda, vértices o fracción estimada;
- significado inequívoco de `AIR`, `ROCK`, `PARTIAL/MIXED`, `OUTSIDE_TOPO_COVERAGE`, `TOPO_UNKNOWN` o equivalentes;
- cómo reportar bloques cortados por la superficie y qué volumen representa el atributo almacenado.

**Consecuencia de las opciones:** clasificar por el centro es una aproximación rápida y puede equivocarse con celdas que intersectan la superficie; evaluar vértices identifica mejor la posibilidad de intersección, pero no proporciona por sí solo fracción exacta; calcular una fracción exige un método geométrico adicional, con costo y supuestos. **No afirmar `volumen_roca = V_nominal` para celdas mixtas**, ni eliminar sin registro las celdas fuera de cobertura.

**Inputs:** grid, topografía verificable y reglas aprobadas.  
**Outputs posibles:** clasificación topográfica y atributos de cobertura por bloque, dejando explícito el método.  
**Pruebas:** plano horizontal sintético **solo en tests**, casos por encima/debajo, celdas cortadas, puntos fuera de cobertura, signo de elevación.  
**Validación minera:** superposición con topografía y sondajes; revisión de franjas y bordes; no confundir aproximación con volumen real excavable.  
**Gate:** `P3_TOPO` (independiente).

### ETAPA P4 — Asignación geológica categórica a bloques

**Problema minero:** trasladar observaciones de litología en perforaciones a celdas de **roca**, sin inventar interpretación donde no hay soporte.

**Teoría:** información puntual/lineal vs. volumen, inferencia categórica, continuidad geológica, distancia, sesgo de vecindad, extrapolación, ambigüedad cerca de contactos.

**Decisiones críticas:**

- qué elemento actúa como observación geológica (segmentos de `lithology`, composites con código validado, otros derivados justificados);
- qué estrategia se comparará (proximidad/vecino más cercano con limitaciones, reglas condicionadas por unidades geológicas realmente disponibles, o regiones desconocidas); no asumir sólidos inexistentes;
- definición reproducible de distancia y vecindad **con datos reales**, límites de soporte y empatía con geometría de sondajes;
- cómo impedir clasificación incondicional de toda la malla por el único sondaje más cercano;
- prioridad de `AIR`, `OUTSIDE_TOPO_COVERAGE`, `TOPO_UNKNOWN` sobre una asignación geológica automática;
- qué ocurre en bloques sin apoyo suficiente, disputados entre códigos o con contactos cercanos.

**Regla fundamental:** si el soporte es insuficiente, el bloque permanece `UNKNOWN/UNASSIGNED` con causa identificada. Los códigos geológicos deben provenir de datos reales; **no crear litologías por estética de la visualización**.

**Inputs:** observaciones geológicas 3D, grid topográficamente caracterizado, parámetros aprobados.  
**Outputs posibles:** `block_id`, estado topográfico, `lith_code/domain_code` preliminar, distancia/medida de soporte, flag de incertidumbre y causa de no clasificación.  
**Pruebas:** casos controlados de dos códigos y frontera, distancia/soporte, bloque de aire, sin soporte, códigos desconocidos, desempates reproducibles.  
**Validación minera:** cotejo con sondajes y secciones; proporción `UNKNOWN`, continuidad o artefactos, extrapolación, relaciones entre litologías y topografía.  
**Gate:** `P4_GEO_ASSIGN` (independiente).

### ETAPA P5 — Validación computacional + validación minera

**Problema minero:** demostrar qué parte de la malla y su clasificación es reproducible y cuáles son los límites técnicos del modelo.

**Distinguir obligatoriamente:**

| Comprobación computacional | Validación minera |
|---|---|
| Estructura de tabla, tipos, IDs e índices. | Interpretación de soporte real y coherencia espacial. |
| Centros, dimensiones, volúmenes y límites. | Tamaño de bloque y extensión razonables para datos disponibles. |
| Clasificación topográfica en tests controlados. | Ubicación real de aire/roca y celdas parciales frente a topografía. |
| Reglas reproducibles de asignación categórica. | Contactos, extrapolación, continuidad y bloques sin soporte. |
| Reejecución con mismos inputs/parámetros. | Reconocimiento explícito de incertidumbres y de lo que NO se modeló. |

**Diagnósticos sugeridos (no números prescritos):** celdas totales, número/porcentaje por estado topográfico, celdas clasificadas/`UNKNOWN`, recuentos por código, distancias a observaciones (donde aplique), áreas sin cobertura, secciones por coordenada, distribución por profundidad y casos de revisión cerca de contactos.

Clasifica hallazgos `ERROR/WARNING/INFO` con criterios documentados. Si falla una invariante importante, no se declara `READY_FOR_REVIEW` hasta corregirla o explicar y aprobar un alcance parcial. En todo caso, pedir al estudiante **interpretar qué significa el test y qué no demuestra**.

**Gate:** `P5_VALIDATION` para aceptar evidencias reales; una suite verde **no equivale** a validación geológica.

### ETAPA P6 — Visualizador 3D y síntesis técnica

**Problema minero:** hacer auditable la distribución de bloques y su relación con superficie y perforaciones.

**Capas recomendadas, sujetas a datos y capacidades reales del repo:**

1. topografía (solo donde existe cobertura justificable);
2. sondajes/trayectorias y contactos o composites de control;
3. bloques de roca clasificados por `lith_code`/dominio preliminar;
4. celdas `UNKNOWN/UNASSIGNED` distinguibles, al menos por filtro/leyenda;
5. superficie/celdas parciales y límites de la malla;
6. ejes, escala, unidades, leyenda y filtros/cortes que eviten ocultamiento por bloques externos.

**Decisiones a defender:** qué visualización sirve para auditar la geometría; color por código, no por ley Cu si no se estimó; criterio de filtrado para no saturar memoria; si se usa una herramienta 3D existente en el repo o es necesaria una dependencia nueva (esta última requiere justificación y aprobación).

**Outputs posibles:** visualizador/figura/HTML real dentro de `outputs/` y tabla derivada en `data/processed/`, según arquitectura.  
**Pruebas:** geometría y categorías correctas, malla representada con filtros claros, manejo de datos ausentes y error controlado.  
**Validación minera:** comparación visual con perforaciones y superficie, revisión de secciones, coherencia de clases y límites; documentar artefactos y simplificaciones.  
**Gate:** `P6_VISUALIZER` más reporte de revisión. El cierre del módulo exige también documentación IMP, no solo una imagen convincente.

---

## 6. Parámetros críticos: lista de decisiones que NUNCA debe preseleccionar el agente

El estudiante debe declarar/confirmar los siguientes parámetros **antes de autorizar el código que los utiliza**:

| Grupo | Parámetro/criterio | Fuente de la decisión | Riesgo si se adivina |
|---|---|---|---|
| Información | Campos verdaderos, nombres de códigos, unidades, convenciones XYZ/MD. | Diccionario, archivos y M01. | Integración incorrecta de profundidades/coordenadas. |
| Dominios | Relación litología–dominio, contacto, ambigüedades y categorías `UNASSIGNED`. | Registros geológicos y justificación. | Pérdida o invención de información geológica. |
| Grid | Extensión X/Y/Z, origen, ejes y alineación. | Soporte 3D + cobertura topográfica. | Vacíos de cobertura o volumen arbitrario. |
| Grid | `dx/dy/dz`, `nx/ny/nz`, padding y límite práctico de ejecución. | Espaciamiento del dataset, análisis de sensibilidad básico, recursos disponibles. | Falsa resolución, alto costo, falta de detalle. |
| Topografía | Método de evaluación, cobertura y tratamiento de celdas parciales. | `Topopl.csv` oficial u otro equivalente comprobado. | Aire confundido con roca, errores de volumen. |
| Asignación | Observaciones, método, distancia/radio/vecindad y reglas de desempate. | Geología disponible + pruebas de alternativas. | Extrapolación indiscriminada o sesgo. |
| Sin soporte | Flags, categorías desconocidas y criterio de no asignación. | Calidad/cobertura real de datos. | Geología ficticia. |
| Validación | Métricas, tolerancias y evidencias de revisión. | Requisitos mineros, tests y decisiones previas. | Declarar validez sin sustento. |
| Visualización | Capas, cortes, leyendas, filtros, librerías y formato. | Capacidad real y finalidad de auditoría. | Figura bonita pero engañosa o no reproducible. |

> **Regla de alternativas:** el agente siempre presenta **2–4 opciones con ventajas y límites** y pregunta cuál es defendible **para el repositorio del estudiante**. Varias estrategias pueden ser técnicamente aceptables. Nunca convierte esta tabla en una respuesta automática ni introduce valores numéricos sin evidencia.

---

## 7. Contrato mínimo del modelo de bloques geológico

Los campos concretos deben ajustarse a la estructura del proyecto, pero el resultado debe poder responder **qué celda es, dónde está, qué volumen nominal tiene, cuál es su relación con la topografía, qué categoría preliminar se le atribuye y por qué**.

**Esquema conceptual (nombres orientativos, no CSV obligatorio):**

```text
block_id
index_i, index_j, index_k
center_x, center_y, center_z
dx, dy, dz
nominal_volume
topo_status                 # ROCK / AIR / PARTIAL / OUTSIDE_TOPO_COVERAGE / TOPO_UNKNOWN
lith_code_or_domain_code    # valor de fuente, si asignado y sustentado
assignment_status           # ASSIGNED / UNKNOWN / UNASSIGNED / NOT_APPLICABLE
support_distance_or_count   # si el método lo define
uncertainty_or_review_flag  # según definición aprobada
```

**Dos precauciones de diseño:**

1. Un bloque `AIR` no es simplemente un bloque de roca `UNKNOWN`: tiene una condición geométrica diferente. No deben confundirse en tabla ni visualización.
2. `nominal_volume` es volumen de la celda, **no** volumen neto de roca dentro de un bloque topográficamente cortado. Para determinar este último se requiere una regla/fracción de ocupación aparte; si no se implementó, declararlo.

**Ubicaciones orientativas** (nunca forzar nombres si el repo ya tiene convención):

```text
src/<paquete-real>/...                  módulos nuevos y reutilizables

tests/test_<modulo_real>.py             tests controlados y reproducibles

data/processed/<convencion-real>/       tablas derivadas

outputs/tables/                        diagnósticos y conteos
outputs/figures/                       3D o cortes/figuras
outputs/reports/                       informe de validación

docs/implementation/IMP-002_*.md       registro incremental del desarrollo M01B
docs/exam/T2_M01B_PLAN_<GRUPO>.md      plan del examen, si aprobado
docs/exam/T2_M01B_EVIDENCE_<GRUPO>.md  interacción y gates, si aprobado
```

El registro de implementación debe actualizarse **durante** el desarrollo; no reconstruir pasos inexistentes al finalizar. Si el alcance de los nuevos módulos exige un IMP separado conforme a la gobernanza, crearlo con la plantilla **sin modificar la plantilla protegida**.

---

## 8. Protocolo didáctico ligado a este escenario

Este documento **no sustituye** el contrato del `01_AGENT_EXAM_M01B.md`. Para cada decisión de P0–P6:

1. Explica **qué representa técnicamente** la decisión minera, incluyendo conceptos relevantes de geometría/geología.
2. Compara consecuencias de **2–4 alternativas plausibles**; muestra ventajas y limitaciones sin indicar cuál escoger.
3. Identifica evidencia y faltantes específicos del repositorio.
4. Formula **una pregunta principal**, exige **elección + justificación + evidencia + una limitación** y espera respuesta.
5. Evalúa `CORRECTA`, `PARCIAL` o `REQUIERE_REVISIÓN`; si hace falta, ofrece pista escalonada (`H0–H3`) y una nueva pregunta con alternativas.
6. Registra fielmente las respuestas originales, sin corregirlas retrospectivamente.
7. Al quedar técnicamente definido el alcance, muestra el gate y di **«Estamos listos para codificar esta etapa»**. Solicita aprobación **A/B/C**, espera respuesta y autoriza exclusivamente esa etapa.
8. Después de implementar, solicita interpretar pruebas, validar desde la minería, actualizar el IMP y cerrar **solo el checkpoint demostrado**.

El agente **no** debe asumir que un alumno comprende un concepto porque eligió una letra: exige relación causal, dato real, riesgo e implicancia.

---

## 9. Comprobaciones para declarar avance por etapa

| Checkpoint | Evidencia mínima de aceptación técnica | Si falta evidencia |
|---|---|---|
| `BASE_VERIFIED` | B00–B10 críticos revisados, datos espaciales/composites/topografía utilizables y documentación del estado. | `ALIGNMENT_RECOVERY` o `RECOVERY_BLOCKED`. |
| `PLAN_APPROVED` | Plan construido mediante respuestas defendidas; decisiones/gates y dependencias explícitas. | Mantener `EVALUATION_PLAN`. |
| `P1_DOMAINS` | Códigos/contactos y ambigüedades registrados; geología disponible realmente representada. | `PARTIAL/NEEDS_WORK`; no suponer sólidos. |
| `P2_GRID` | Grid reproducible, índices/centros/volúmenes verificables y tamaño defendido. | No avanzar a clasificación topográfica definitiva. |
| `P3_TOPO` | Cobertura y regla aire/roca documentada y probada; parciales/afuera tratados. | No atribuir geología a aire ni fuera de cobertura. |
| `P4_GEO_ASSIGN` | Método categórico explícito; bloques con y sin soporte distinguibles; validación espacial. | Modelo geológico `PARTIAL` o clasificación `UNKNOWN`. |
| `P5_VALIDATION` | Pruebas y revisión minera separadas, diagnóstico y limitaciones. | No declarar `MINING_VALIDATED`. |
| `P6_VISUALIZER` | Figura o vista real, auditable, con capas/leyenda/escala/cobertura y revisión. | Producto visible no demostrado. |
| `READY_FOR_REVIEW` | Resultado técnico existente, IMP/evidencia actualizados, resultados y límites reportados. | `IN_PROGRESS`/`PARTIAL`. |
| `CLOSED` | Implementación **+** pruebas **+** validación minera **+** documentación **+** registro IMP, según reglas del repo. | **Nunca cerrar** solo por `pytest` o por una captura. |

**El agente no asigna la nota del examen** ni decide penalizaciones por recuperación. La pauta y rúbrica aprobadas por el docente son la fuente para calificación.

---

## 10. Evidencias que debe dejar el grupo

Durante el trabajo, los alumnos deben poder mostrar:

- diagnóstico y estado inicial del repositorio, con rutas/comandos reales;
- recuperación ejecutada si existió, y estado base comprobado o bloqueos explicados;
- plan incremental y mapa de decisiones producido mediante preguntas;
- comparación técnica de alternativas para extensión, origen, tamaño de bloque, topografía, asignación y soporte;
- registro original de respuestas del estudiante, retroalimentación y nivel de ayuda usado;
- gates y autorizaciones explícitas para cada modificación con código;
- archivos realmente creados/modificados, tests ejecutados con resultados y revisión minera;
- modelo 3D y diagnóstico del resultado **solo si realmente se generaron**;
- `IMP-002` u otros IMP pertinentes actualizados; situación Git comprobada y limitaciones.

**Recomendación de trazabilidad:**

```text
docs/exam/T2_M01B_PLAN_<GRUPO>.md
docs/exam/T2_M01B_EVIDENCE_<GRUPO>.md
```

Estas rutas son **propuestas** hasta que la pauta estudiantil las establezca; no sustituir registros de implementación exigidos por la gobernanza. El agente debe escribir evidencia incremental con autorización y capacidad real de persistencia. Si no puede recuperar fielmente el historial conversacional, debe reconocerlo y solicitar copias literales **sin inventarlas**.

---

## 11. Primer mensaje esperado después del Prompt 0

Después de leer `01_AGENT_EXAM_M01B.md`, este escenario y las reglas oficiales, el agente inicia **solo** con inspección de lectura. Aún no realiza código ni propone medidas definitivas del grid.

**Plantilla de comportamiento (no completar con hechos no verificados):**

```text
PROTOCOLO: EXAM_T2_M01B v1.0
MODO: REPOSITORY_CHECK
ETAPA: DIAGNÓSTICO DEL ESTADO BASE

FUENTES LEÍDAS:
<rutas efectivamente accesibles>

ESTADO REAL:
<rama, estado Git, estructura observada>

MATRIZ BASE:
<B00...B10: VERIFIED / PARTIAL / MISSING / UNKNOWN / BLOCKED>

HALLAZGO PRIORITARIO:
<hecho verificable o «pendiente de inspección»>

CONCEPTO:
<por qué importa este requisito para el modelo geológico>

ALTERNATIVAS:
A. <opción plausible y sus implicancias>
B. <opción plausible y sus implicancias>
C. <opción plausible, cuando corresponda>

TU DECISIÓN:
¿Cuál eliges y cómo la justificas con evidencia real del repositorio?

ESTADO:
PENDIENTE DE RESPUESTA — SIN CÓDIGO
```

Si faltan documentos, acceso al repo o campos críticos, informar el límite y preguntar con alternativas cómo aportar evidencia. **No declarar activación completa del protocolo si no se leyó `01_AGENT_EXAM_M01B.md`.**

---

## 12. Regla final para estudiante y agente

**El examen evalúa quién dirige y justifica el trabajo, no cuánto código produce Copilot.** El estudiante debe explicar, comparar, decidir, aprobar, probar e interpretar. Copilot enseña conceptos y sus implicancias, exige justificación, propone alternativas y ayuda a programar **únicamente después de un gate aprobado**.

Ante duda sobre una celda, dominio, tamaño, cobertura o código, la respuesta correcta del **proceso** no es inventar: **identificar evidencia faltante, conservar la incertidumbre y justificar el siguiente chequeo**. Un resultado parcial técnicamente defendible es preferible a un modelo completo pero no verificable.

**Documento vinculado:** `01_AGENT_EXAM_M01B.md` — normas de interacción, niveles de ayuda y autorizaciones.  
**Documentos siguientes propuestos:** `03_PAUTA_ESTUDIANTE_T2_M01B.docx` y `04_RUBRICA_DOCENTE_T2_M01B.xlsx`.
