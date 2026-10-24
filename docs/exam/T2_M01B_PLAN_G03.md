# T2 · M01B — Plan de implementación del grupo G03 (NO OFICIAL)

- **Grupo:** G03 · **Dataset:** DS01 / EXP03 · **Fecha:** 2026-10-24
- **Estado de este documento:** salida **no oficial** propuesta (no se conoce una ruta ordenada por la pauta oficial). Pendiente de confirmación del estudiante y del docente.
- **Naturaleza del trabajo:** práctica **guiada por un asistente de IA (Claude, no Copilot)**. El estudiante pidió expresamente que el asistente tomara las decisiones como ejemplo resuelto para aprender de él. Por tanto, el plan NO es un plan defendido de forma independiente por el estudiante. Ver `T2_M01B_EVIDENCE_G03.md`.
- **Producto objetivo:** modelo de bloques geológico **preliminar** visualizable en 3D, sin estimación de leyes.
- **Fuera de alcance (según escenario):** NN/IDW/Kriging, recursos y reservas, valorización, pit y secuenciamiento. Los pasos 9 y 10 del PDF del docente (estimación, densidad, tonelaje) no se implementaron; **el docente debe confirmar** que no se exigen.

## 1. Secuencia de etapas

| # | Etapa | Problema minero | Entradas (unidades) | Salidas | Módulo / archivo |
|---|---|---|---|---|---|
| 0 | Estado base | ¿Puedo confiar en M01 y en el compositado? | M01 y `composites.csv` | pruebas M01 + M01B | `src/m01/*`, `tests/` |
| 1 | Dominios | ¿Qué unidad geológica representa cada intervalo? | `composites.csv` (m, Cu %, `lith_code`) | dominios DIO, POR, BRX, REG | `src/m01/domain_assignment.py` (`DOMAIN_BY_LITH`) |
| 2 | Grid | ¿Con qué resolución y extensión representar el volumen? | colares + composites (m, UTM) | malla 25×25×10 m, 26×24×48 = 29,952 bloques | `src/m01/block_model.py` (`GridSpec`) |
| 3 | Topografía | ¿Qué bloques son aire, roca o parciales? | `Topopl.csv` (puntos de curvas de nivel, m) | `topo_state` por bloque | `block_model.py` (`TopographySurface`) |
| 4 | Asignación | ¿Qué dominio tiene cada bloque de roca y con qué soporte? | bloques ROCK + composites con XYZ | `domain_id`, `assign_status`, distancia, `mixed_flag` | `domain_assignment.py` |
| 5 | Validación | ¿Cumple el modelo controles verificables? | `blocks_topo.csv`, `blocks_domains.csv`, composites | informe con 21 controles | `src/m01/block_validation.py` |
| 6 | Visualizador | ¿Se puede inspeccionar en 3D con la información de control? | CSV + collares + composites + superficie | HTML autocontenido | `src/m01/block_viewer.py` (visor de bloques) y `src/m01/visualizer.py` (visor Plotly de M01) |
| 7 | Orquestación | ¿Se reproduce todo con un comando? | todo lo anterior | `python main.py --stage m01b` | `main.py` |

## 2. Decisiones críticas (quién decidió)

| ID | Decisión | Elegido | Quién | Estado de la justificación del estudiante |
|---|---|---|---|---|
| DECISION-02 | Dominios | A: un dominio por litología (DIO, POR, BRX, REG); `AIR` excluido | Alternativas y elección propuestas por el asistente; el estudiante aceptó y la redactó con sus palabras | Registrada (cita en EVIDENCE) |
| DECISION-03 | Grid | 25 × 25 × 10 m, origen (242225, 8196100, 3060), 26×24×48 | Propuesto por el asistente; aceptado por el estudiante | **PENDIENTE** |
| DECISION-04 | Estado topográfico por bloque | 4 esquinas + centro de cada columna; ROCK / AIR / PARTIAL; sin extrapolar fuera de cobertura | Asistente | **PENDIENTE** de revisión |
| DECISION-05 | Asignación | Bloque al compuesto más cercano en 3D; R1 = 50 m (`ASSIGNED_SUPPORTED`), R2 = 100 m (`ASSIGNED_EXTRAPOLATED`), si no `UNKNOWN_NO_SUPPORT` | Asistente (radios a partir de validación cruzada dejando fuera un sondaje) | **PENDIENTE** de revisión |

El detalle, las alternativas y las limitaciones están en `docs/implementation/IMP-002_m01b_block_model_preparation.md`.

## 3. Validaciones previstas

- **Computacionales:** `python -m unittest discover -s tests -t .` (133 pruebas, ver EVIDENCE) y los 21 controles de `block_validation.py` (GEO, TOP, SUP, REC, DOM, UNC).
- **Mineras (a cargo del estudiante):** interpretación de secciones y del visor 3D, cercanía a contactos, bloques parciales, bloques sin soporte, distancia extrapolada. **PENDIENTE.**

## 4. Riesgos y limitaciones conocidas

- La topografía se interpola desde puntos de curvas de nivel (99.1 % de cotas enteras) con IDW por 8 sectores; no hay TIN oficial.
- CRS de la topografía: EPSG **UNKNOWN**, aceptado como limitación no bloqueante por la «DECISION-06» del docente (no se puede afirmar ubicación global ni transformar a otro CRS); el README de `data/raw` indica sistema cartesiano local en metros. La auditoría muestra 32/32 collares dentro de la envolvente y Δz collar–superficie de −1.26 a +1.76 m (media 0.03 m), coherente con un mismo sistema, pero no es confirmación documental.
- 8,897 bloques (48 % de la roca) son extrapolados entre 50 y 100 m; 2,600 sin soporte; 2,362 con dominios mezclados dentro de 50 m.
- 1,532 bloques parciales (8 % de los 18,497 bloques de roca y parciales) no se subdividen.
- El código litológico `AIR` (3 m en dos intervalos) no tiene significado documentado.
- Un dominio por litología no equivale a un modelo geológico interpretado ni a un modelo de recursos.

## 5. Criterios de avance

Cada etapa avanza solo si sus pruebas pasan y no hay FAIL en la validación; los WARNING quedan registrados, no ocultos. El producto técnico se mantiene en **IN_PROGRESS** hasta que existan la interpretación minera del estudiante y sus justificaciones pendientes.
