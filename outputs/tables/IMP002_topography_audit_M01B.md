# IMP-002 · Auditoría de topografía (M01B) — DS01/EXP03

Fuente: `Topopl.csv` entregado por el docente el 2026-10-24 (no editado).
SHA-256: `1724a97f1fa6f6a059def896d1ba566b1e23d6f78781034bf2e3f53d2d4b1887`

| Verificación | Resultado |
|---|---|
| Filas / columnas | 218,112 puntos; `PID, X, Y, Z` |
| Nulos / PID duplicados / XY duplicados | 0 / 0 / 0 |
| Extensión X | 242090.5 – 243287.7 |
| Extensión Y | 8195892.2 – 8197095.7 |
| Rango Z | 3120.9 – 3596.0 |
| CRS / EPSG | NO consta en el archivo (UNKNOWN). README de `data/raw`: sistema cartesiano local, metros |
| Z con valor entero | 99.1 % (patrón de curvas de nivel digitalizadas) |
| Distancia al vecino más cercano (mediana / p95 / máx) | 0.41 / 3.00 / 18.64 m |
| Collars dentro de la envolvente de la topografía | 32 / 32 |
| Margen collars → borde de topografía (O / E / S / N) | 173 / 452 / 253 / 421 m |
| z_collar − z_topo (TIN lineal): media / desv. / mín / máx | 0.03 / 0.71 / -1.26 / 1.76 m |
| Distancia del collar al punto topográfico más cercano (mediana / máx) | 1.9 / 6.6 m |
| Composites con z_topo evaluable | 3,632 / 3,632 |
| Composites sobre la superficie (z > z_topo) | 4 (máx. 0.83 m) |

Lectura: compatible en XY y Z con los sondajes (no hay desplazamiento ni cambio de signo). La diferencia
collar–superficie (±~2 m) es de orden coherente con puntos de curvas de nivel interpolados; no se corrige.
Pendiente de decisión del estudiante (P3_TOPO): método aire/roca (centro / vértices / fracción) y tratamiento
de la zona fuera de cobertura.
