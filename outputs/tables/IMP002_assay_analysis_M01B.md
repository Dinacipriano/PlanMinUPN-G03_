# Análisis de assay previo al compositado — evidencia real

Generado: 2026-10-23, sesión de diagnóstico. Calculado directamente de `data/raw/assay.csv` y `data/raw/lithology.csv` con pandas (lectura únicamente).

## 1. Estado general

- 3,619 registros de assay, 32 hole_id distintos.
- 0 intervalos inválidos (`from_m >= to_m`).
- 0 valores nulos en cu_pct, mo_pct, au_gt.

## 2. Distribución de length_m (assay)

| Estadístico | Valor (m) |
|---|---|
| count | 3619 |
| mean | 1.9936 |
| std | 0.0891 |
| min | 0.0603 |
| P10 / P25 / P50 / P75 / P90 | 2.000 (los cinco) |
| max | 2.000 |

- **3,594 de 3,619 registros (99.3%) tienen length_m = 2.000 m exacto.**
- Los 25 registros restantes son residuales de cierre de sondaje (último tramo antes del fondo, con longitud menor a 2.0 m porque `final_depth_m` no cae en un múltiplo exacto de 2). Ejemplos: `CA-C01-001` 188.0–189.88 m (1.88 m); `CA-C02-004` 294.0–294.108 m (0.108 m).
- No existen residuales "intermedios" fuera del cierre de sondaje — todos los 25 casos corresponden al último intervalo de su hole_id respectivo.

## 3. Variables de ley disponibles

| Variable | count | missing | min | P25 | median | mean | P75 | P90 | P95 | P99 | max |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cu_pct | 3619 | 0 | 0.0191 | 0.0431 | 0.1618 | 0.3240 | 0.5810 | 0.8891 | 1.0121 | 1.1097 | 1.2066 |
| mo_pct | 3619 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0 (100% ceros)** |
| au_gt | 3619 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0 (100% ceros)** |

**mo_pct y au_gt no tienen ninguna variación en todo el dataset — no son utilizables como variable de compositado o de análisis en este grupo.** Cu (%) es la única ley con información real.

## 4. Relación con lithology (contactos)

- `lithology.csv`: 95 intervalos, 32 hole_id, códigos REG(36) DIO(27) POR(22) BRX(8) AIR(2).
- **25 de 3,619 intervalos de assay (0.7%) cruzan un contacto litológico** (el contacto cae estrictamente entre `from_m` y `to_m` del assay). Ejemplos: `CA-C01-007` 52–54 m cruza contacto en 53 m; `CA-C02-004` 6–8 m cruza contacto en 7 m.
- Este conjunto de 25 NO es el mismo conjunto que los 25 residuales terminales de la sección 2 — son dos fenómenos distintos (verificado fila por fila).

## 5. Alternativas de longitud de composite — evidencia, sin elegir

(Para que el equipo decida con fundamento — no es una recomendación cerrada.)

**A. 2.0 m, igual al soporte nativo dominante.**
- Evidencia: 99.3% de las muestras ya están a 2.0 m exactos.
- Ventaja: el compositado sería casi una operación de "paso" (passthrough) para la mayoría de los datos; mínima alteración de la información original.
- Desventaja: los 25 residuales de cierre seguirían siendo sub-2m, y los 25 cruces de contacto igual necesitan dividirse — ninguna longitud evita esos dos casos.

**B. Mantener length_m original (no componer).**
- Evidencia: dado que casi todo ya está a soporte uniforme, un compositado "real" aporta poco salvo resolver los 25+25 casos especiales.
- Desventaja: no resuelve de forma sistemática el cruce de contactos ni deja un residual_flag explícito.

**C. Longitud mayor (ej. 4.0 m) para reducir el número de muestras antes del grid.**
- Evidencia: el P90/P75/P50 de longitud ya es 2.0 m; agrandar el soporte implicaría agregar información real, perdiendo resolución frente a lo que el sondaje efectivamente midió.
- Desventaja: pérdida de detalle sin que exista un motivo de soporte/costo que lo justifique en este dataset (a diferencia de un caso con muestras muy cortas e irregulares).

Este documento no fija la decisión; la decisión tomada (alternativa A) y su justificación están en DECISION-01 de `docs/implementation/IMP-002_m01b_block_model_preparation.md`.
