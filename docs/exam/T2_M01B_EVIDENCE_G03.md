# T2 · M01B — Registro cronológico de evidencia, grupo G03 (NO OFICIAL)

- **Estado de este registro:** propuesto, no oficial. Pendiente de confirmación del estudiante.
- **Fecha de la sesión:** 2026-10-24 · **Dataset:** DS01 / EXP03 · **Estudiante:** Luis (G03).
- **Asistente utilizado:** Claude (Anthropic) mediante sesión remota con acceso a la carpeta del repositorio. **No se usó Copilot.**

## 0. Aviso de alcance (leer primero)

Esta sesión **no siguió el protocolo de evaluación del examen** (`01_AGENT_EXAM_M01B.md`): el asistente no formuló un checkpoint por etapa con alternativas, ni esperó la defensa del estudiante antes de implementar. Por pedido expreso del estudiante ("Necesito que tomes las decisiones tu, a partir de ello voy a poder realizar el ejemplo, elige la opción y dame el porque"), el asistente propuso, decidió e implementó, y el estudiante revisó y aceptó. Por eso:

- Los **gates P1 a P6 se registran `PENDING` en el sentido del examen** (no hay defensa independiente del estudiante). Lo único aprobado es la ejecución técnica por instrucción del estudiante.
- Las **ayudas máximas** son `H3` en todas las etapas: la solución fue entregada, no descubierta por el estudiante.
- Las respuestas del estudiante citadas abajo provienen del registro de la sesión; quedan como **TRANSCRIPCIÓN A CONFIRMAR** por el estudiante. No se reconstruyó ninguna respuesta.
- Este material sirve como **ejemplo resuelto de estudio**, no como evidencia de dominio del estudiante.

## 1. Estado base y evidencia consultada

| Evidencia | Resultado |
|---|---|
| Commit `e13d595` (2026-10-23) | Baseline, auditoría de inputs y compositado a 2.0 m de Cu para DS01/EXP03 |
| Commit `b77f84d` (2026-10-24) | Topografía común `Topopl.csv` y su auditoría |
| Commit `00be54b` (2026-10-24) | Grid 25×25×10 m, estado topográfico y asignación de dominios |
| Pruebas | `python -m unittest discover -s tests -t .`: 133 pruebas OK en sesión remota (10.5 s). **No ejecutadas por el estudiante en su `.venv` de PyCharm: NOT_RUN en su entorno.** |
| Reproducibilidad | `python main.py --stage m01b` regenera `composites.csv`, `blocks_topo.csv` y `blocks_domains.csv` sin diferencias respecto de los commits |
| Autor Git | Los commits aparecen como `Dinacipriano`; el estudiante no ha confirmado que sea su identidad |

Pendiente: commits de la validación, el visor, `main.py`, las pruebas nuevas y IMP-002 actualizado (ver sección 5).

## 2. Checkpoints reales de la interacción

### CHECKPOINT 1 — Disponibilidad de la topografía
- Modo: ALIGNMENT_RECOVERY (informal)
- Pregunta del estudiante (cita): "me comentan que topografía no ha entregado a nadie el archivo el profesor, se puede continuar sin ello?"
- Después: "El profesor acaba de pasar estos dos archivos, uno es la topografía, podemos avanzar ya con esto?"
- Acción: se incorporó `data/raw/topography/Topopl.csv` y se auditó (`outputs/tables/IMP002_topography_audit_M01B.md`).
- Gate: no aplica. Validación computacional: PASS (auditoría). Validación minera: PENDING. CRS: UNKNOWN.

### CHECKPOINT 2 — Dominios (DECISION-02)
- Alternativas: A. un dominio por litología. B. y C. agrupaciones de litologías (ver IMP-002).
- Elección y alternativas propuestas por: el asistente. Antes el estudiante pidió: "dame un ejemplo de frase de justificación que sería correcto para adaptarlo".
- Justificación del estudiante (cita, adaptada de una frase modelo del asistente): "Elijo A (un dominio por litología) porque el Cu y la densidad cambian mucho entre los distintos tipos de litología: la litologia POR tiene unas 10 veces el % de Cu de DIO y BRX y casi el doble de POR, así que juntarlas en B o C mezclaría poblaciones distintas. Además A se puede reagrupar después y B o C no."
- Nota del asistente (verificada con `composites.csv`, Cu % medio ponderado por longitud de composite): BRX 1.043 (258 composites), POR 0.515 (1,574), REG 0.088 (108), DIO 0.050 (1,690). La razón POR/DIO es ≈ 10, como afirma el estudiante, pero BRX **no** tiene menos Cu que POR: tiene cerca del doble. La frase debe corregirse (p. ej., POR ≈ 10 veces DIO y ≈ 6 veces REG, y BRX ≈ 2 veces POR). La afirmación sobre la densidad no se verificó: no se evaluó ningún dato de densidad en esta sesión. La conclusión (A separa poblaciones distintas) se mantiene.
- Evaluación conversacional: PARCIAL. Ayuda máxima: H3. Gate: PENDING.

### CHECKPOINT 3 — Significado de "aire" y del código `AIR`
- Pregunta del estudiante (cita): "Aire no sería lo que está encima del collar y que en realidad no representa datos reales? ya que los taladros son hacia abajo, el aire no representa nada? no estoy seguro si estoy en lo correcto"
- Aclaración del asistente: hay dos conceptos distintos. (1) Aire del modelo = bloques sobre la superficie topográfica. (2) Código litológico `AIR` en el archivo de litología = 2 intervalos, 3 m en total, de significado no documentado; se excluyó como fuente de dominio. La intuición del estudiante es correcta para (1); no se confirmó para (2).
- Evaluación conversacional: PARCIAL. Ayuda máxima: H2. Gate: no aplica.

### CHECKPOINT 4 — Grid (DECISION-03)
- Pregunta del estudiante (cita): "y hay otro grid que sea mejor y que contenga mayor cantidad de los datos?"
- Respuesta del asistente: se comparó contra otras geometrías; el grid inicial de 45 capas (techo 3,510 m) quedó bajo la superficie (máx. 3,533.8 m) y se subió a 48 capas (techo 3,540 m) tras la advertencia GRID-001.
- Decisión del estudiante (cita): "si queda aceptado el grid"
- Justificación propia del estudiante: **PENDIENTE**.
- Gate: PENDING. Ayuda máxima: H3.

### CHECKPOINT 5 — Estado topográfico y asignación (DECISION-04 y DECISION-05)
- Instrucciones del estudiante (citas): "si prosigue", "si sigue porfavor".
- Las decisiones, el método (4 esquinas + centro; vecino más cercano en 3D con radios 50/100 m) y la implementación fueron del asistente. El estudiante **no** ha revisado ni adoptado estas decisiones: **PENDIENTE**.
- Gate: PENDING. Ayuda máxima: H3.

### CHECKPOINT 6 — Alcance
- Pregunta del estudiante (cita): "tenemos que hacer solo hasta donde indique el ejemplo de examen, que nos falta?"
- Resultado: se confirmó que estimación, densidad y tonelaje (pasos 9 y 10 del PDF) no se piden en el escenario; **el docente debe confirmarlo**.

### CHECKPOINT 7 — Validación y visor
- Instrucciones del estudiante (citas): "si prosigue"; "sigue con el visualizador, luego subimos esta etapa, las interpretaciones para el final tambien".
- Archivos: `src/m01/block_validation.py`, `src/m01/visualizer.py`, `outputs/tables/IMP002_block_validation_M01B.md`, `outputs/figures/IMP002_block_model_3d_M01B.html`.
- Validación computacional: PASS (sin FAIL). Validación minera: **PENDING** (interpretación del estudiante).

## 3. Resultados verificados del modelo (sesión remota)

| Elemento | Valor |
|---|---|
| Compositado | 3,632 composites de 2 m; 53 residuales; diferencia de metros 0 |
| Bloques | 29,952 (ROCK 16,965; PARTIAL 1,532; AIR 11,455; OUTSIDE 0) |
| Roca y parciales | 18,497 |
| Dominios | ASSIGNED_SUPPORTED 7,000; ASSIGNED_EXTRAPOLATED 8,897; UNKNOWN_NO_SUPPORT 2,600; mixtos 2,362 |
| Validación de bloques | WARNING global: 15 PASS, 6 WARNING (TOP-05, DOM-04, DOM-05, UNC-01, UNC-02, UNC-03), 0 FAIL |
| Visor | 18,497 bloques, 32 sondajes, 3,632 composites; 11,455 bloques de aire omitidos |

Los WARNING no son errores del código: señalan limitaciones reales del modelo (bloques parciales, extrapolación, ausencia de soporte, mezcla de dominios).

## 4. Archivos creados o modificados en la sesión

Nuevos: `src/m01/block_model.py`, `domain_assignment.py`, `block_validation.py`, `visualizer.py`; sus pruebas `tests/test_m01_*.py` y `tests/test_main_m01b.py`; `data/processed/m01b/blocks_topo.csv`, `blocks_domains.csv`; el informe y el HTML de salida; `data/raw/topography/Topopl.csv` (entregado por el docente, sin modificar); este registro y el plan.
Modificados: `main.py` (selector `--stage`), `docs/implementation/IMP-002_m01b_block_model_preparation.md`.
No modificados: `loader.py`, `validator.py`, `desurvey.py`, `positioning.py`, compositado y `data/raw/`.

## 5. Estado Git (verificado en la sesión)

- Último commit en `main`: `00be54b`.
- **Sin versionar al momento de escribir:** `src/m01/block_validation.py`, `src/m01/visualizer.py`, las tres pruebas nuevas, el informe de validación, el HTML, `main.py` e IMP-002 modificados, y estos dos documentos.
- El resto de archivos con ` M` en `git status` son diferencias de fin de línea (CRLF/LF), sin cambios de contenido.
- Los commits y el push los realiza el estudiante en PyCharm; no se declaran como hechos hasta que existan.

## 6. Pendientes del estudiante (no completados por el asistente)

1. Justificaciones propias de DECISION-03, DECISION-04 y DECISION-05.
2. Interpretación minera de las secciones del informe de validación y del visor 3D (¿qué rasgo no puede ser geología real y por qué?).
3. Respuesta a la pregunta final del examen: limitación dominante entre A (dominios), B (grid), C (asignación/extrapolación) y D (topografía/parciales), con evidencia propia.
4. Ejecutar `python -m unittest discover -s tests -t .` en su `.venv`.
5. Confirmar identidad de autor Git y completar participantes en IMP-002.
6. Consultar al docente: CRS de la topografía, significado del código `AIR` y si estimación/densidad/tonelaje son requeridos.

## 7. Estado del producto técnico

**IN_PROGRESS.** Implementado, probado y con controles automáticos; sin validación minera del estudiante. No corresponde `READY_FOR_REVIEW` ni `CLOSED`.
