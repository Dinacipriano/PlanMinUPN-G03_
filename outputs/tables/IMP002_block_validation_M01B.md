# IMP-002 · Validación del modelo de bloques preliminar (M01B)

Resultado global: **WARNING** (PASS 15, WARNING 6, FAIL 0).

Los controles recalculan las reglas desde los CSV generados. Un PASS indica consistencia interna; no demuestra que la geología sea correcta.

| Control | Área | Descripción | Estado | Observado | Esperado |
|---|---|---|---|---|---|
| GEO-01 | geometría | block_id únicos | PASS | 0 duplicados | 0 |
| GEO-02 | geometría | número de bloques = nx*ny*nz | PASS | 29952 de 29952 | 29952 |
| GEO-03 | geometría | dimensiones y volumen positivos y coherentes | PASS | 0 bloques | 0 |
| GEO-04 | geometría | centro e id coinciden con el índice (ix, iy, iz) | PASS | 0 bloques | 0 |
| TOP-01 | topografía | estados topográficos válidos | PASS | 0 inválidos | 0 |
| TOP-02 | topografía | estado coherente con las cotas de superficie del bloque | PASS | 0 bloques | 0 |
| SUP-01 | soporte | todos los composites caen dentro del grid | PASS | 0 fuera | 0 |
| SUP-02 | soporte | todos los composites tienen XYZ | PASS | 0 sin XYZ | 0 |
| TOP-03 | topografía | ningún composite dentro de un bloque AIR | PASS | 0 composites | 0 |
| TOP-04 | topografía | bloques fuera de cobertura topográfica | PASS | 0 bloques | 0 (si hay, documentar) |
| TOP-05 | topografía | bloques PARTIAL (volumen nominal distinto del volumen de roca) | WARNING | 1532 bloques (5.1 %) | 0 (si hay, documentar como limitación) |
| REC-01 | reconciliación | mismos block_id en blocks_topo y blocks_domains | PASS | 0 diferencias | 0 |
| REC-02 | reconciliación | topo_state igual en ambos archivos | PASS | 0 bloques | 0 |
| DOM-01 | dominios | dominio solo en bloques de roca con soporte; AIR/UNKNOWN sin dominio | PASS | 0 bloques | 0 |
| DOM-02 | dominios | dominios dentro del conjunto aprobado (DECISION-02) | PASS | 0 bloques | 0 |
| DOM-03 | dominios | estado de asignación coherente con la distancia y los radios (DECISION-05) | PASS | 0 bloques | 0 |
| DOM-04 | dominios | bloques con composites: dominio asignado = dominio mayoritario interno | WARNING | 10 de 770 bloques difieren | 0 (diferencias esperables junto a contactos) |
| DOM-05 | dominios | proporción de bloques por dominio frente a proporción de metros compuestados | WARNING | BRX -6.1 pp, DIO +25.6 pp, POR -24.2 pp, REG +4.7 pp | diferencia máxima <= 10 pp (disparador de revisión) |
| UNC-01 | incertidumbre | bloques de roca sin soporte (UNKNOWN) | WARNING | 2600 (14.1 % de la roca) | 0 (si hay, documentar) |
| UNC-02 | incertidumbre | bloques de roca asignados por extrapolación | WARNING | 8897 (48.1 % de la roca) | 0 (si hay, documentar) |
| UNC-03 | incertidumbre | bloques con más de un dominio dentro del primer radio (contactos no modelados) | WARNING | 2362 bloques | 0 (si hay, revisar en secciones) |

## Secciones para inspección minera

Símbolos: `.` aire, `?` UNKNOWN, `D P B R` dominio soportado, `d p b r` dominio extrapolado, `-` fuera de cobertura topográfica. Cota = base de la capa (m).

### Sección oeste-este en iy=12

```text
   3530 | ..........................
   3520 | .........................r
   3510 | .........................r
   3500 | ........................rr
   3490 | ........................rr
   3480 | .......................Rrr
   3470 | .......................RRr
   3460 | .......................RRr
   3450 | ......................RRRr
   3440 | ......................DRRr
   3430 | ......................DDDd
   3420 | ......................DDDd
   3410 | .....................DDDDd
   3400 | ....................RRDDDd
   3390 | ....................RRDDDd
   3380 | ...................DRRDDDd
   3370 | ..................DDDDDDDd
   3360 | ..................DDDDDDDd
   3350 | ...............DRRDDDDDDDd
   3340 | .............RpDDRDDDDDDDd
   3330 | ............PRpPDRDDDDDDDd
   3320 | ...........pPRPPPDDDDDDDDd
   3310 | ..........RpPPPPPPDDDDDDDd
   3300 | .........RPPPPPPPPDDDDDDdd
   3290 | ........RRPPPPPPPPDDDDDDdd
   3280 | .......RRPPPPPPPPPPDDDDDdd
   3270 | ..RRRrrRPPPPPPPPPPPPDDDDdd
   3260 | rRRDDdrRPPPPPPPPPPPPDDDDdd
   3250 | dDDDDdrpPPPPPPPPPPPPDDDDdd
   3240 | dDDDDdppPPPPPPPPPPPPDDDDdd
   3230 | dDDDDddpPPPPPPPPPPPPDDDDdd
   3220 | dDDDDddpPPPPPPPPPPPPDDDDdd
   3210 | dDDDDddpPPPPPBPPPPPPDDDDdd
   3200 | dDDDDddpPPPPBBBPPPPPDDDDdd
   3190 | dDDDDddpPPPBBBBPPPPPDDDDdd
   3180 | dDDDDddppPPBBBBPPPPpDDDDdd
   3170 | dDDDDddppPPBBBBPPPPpDDDDdd
   3160 | ddDDDDdppPPBBBPPPPPpDDDDdd
   3150 | ddDDDDdppPBBBBPPPPPdDDDDdd
   3140 | ddDDDDdppBBPBBPPPPPdDDDDdd
   3130 | ddDDDDdppPPPBBPPPPPdDDDDdd
   3120 | ddDDDDdppPPPBBPPPPPdDDDDdd
   3110 | ddDDDDdppPPPBBPPPPpdDDDDdd
   3100 | ddDDDDdppPPPBBPPPPpdDDDDdd
   3090 | ddDDDDdpppPPBBPPPPpdDDDddd
   3080 | ddDDDDdppppPBBPPPppddDDddd
   3070 | ddDDDDdpppppbbpppppdddddd?
   3060 | ddDDDDdppppppbpppppdddddd?
```

### Sección sur-norte en ix=13

```text
   3530 | ........................
   3520 | ........................
   3510 | ........................
   3500 | ........................
   3490 | ........................
   3480 | ........................
   3470 | ........................
   3460 | ........................
   3450 | ........................
   3440 | ........................
   3430 | ........................
   3420 | ........................
   3410 | ........................
   3400 | ........................
   3390 | rrR.....................
   3380 | rrRRRdr.................
   3370 | ddDDDdrR................
   3360 | ddDDDDrRRR..............
   3350 | ddDDDDrRRRR.............
   3340 | ddDDDDrRRDRRR...........
   3330 | ddDDDDrRDDRPRR..........
   3320 | ddDDDDrDDPPPRRR.........
   3310 | ddDDDDdDPPPPPRRRRR......
   3300 | ddDDDDdpPPPPPPPPRDRrRR..
   3290 | ddDDDDdpPPPPPPPPPDDrRRRr
   3280 | ddDDDDdpPPPPPPPPPPDdDDRr
   3270 | ddDDDDdpPPPPPPPPPPPdDDDd
   3260 | ddDDDDdpPPPPPPPPPPPdDDDd
   3250 | ddDDDDdpPPPPPPPPPPPdDDDd
   3240 | ddDDDDdpPPPPPPPPPPPdDDDd
   3230 | ddDDDDdpPPPPPPPPPPpdDDDd
   3220 | ddDDDDdpPPPPPPPPPPpdDDDd
   3210 | ddDDDDdpPPPPBPPPPPpdDDDd
   3200 | ddDDDDdpPPPBBBPPPPpdDDdd
   3190 | ddDDDDdpPPBBBBBPPPpdDDdd
   3180 | ddDDDDdpPPBBBBPPPPpDDDdd
   3170 | ddDDDDdpPPBBBBPPPpdDDDdd
   3160 | ddDDDDdpPPBBBBPPPpdDDDdd
   3150 | ddDDDDdpPPPBBBPPPpdDDDdd
   3140 | ddDDDDdpPPPBBBPPPpdDDDdd
   3130 | ddDDDDdpPPPBBBPPPpdDDDdd
   3120 | ddDDDDdpPPPBBBPPPpdDDDdd
   3110 | ddDDDDdpPPPBBBPPPpdDDDdd
   3100 | dddDDDdpPPPBBBPPppdDDDdd
   3090 | ?ddDDDdppPPBBBPPppdDDDdd
   3080 | ?ddDDDdppppBBBPpppddDDdd
   3070 | ?ddddddppppbbbppppdddddd
   3060 | ?ddddddppppbbbppppdddddd
```
