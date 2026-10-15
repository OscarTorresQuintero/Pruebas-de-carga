# Informe de Rendimiento — Laboratorio de Resiliencia y Chaos Engineering

**Aprendiz:** Oscar Torres Quintero
**Programa:** Análisis y Desarrollo de Software (ADSO) — 3293689
**Ficha:**
**Fecha:** 15 de octubre de 2026
**Repositorio:** https://github.com/OscarTorresQuintero/Pruebas-de-carga

## 1. Entorno de prueba

- API Flask con dos endpoints: `GET /health` (respuesta ligera) y `POST /procesar` (trabajo de CPU simulado con 50.000 iteraciones de SHA-256).
- Locust 2.46.7 con dos tipos de usuario en proporción 1:1: `UsuarioNavegador` (GET /health) y `UsuarioComprador` (POST /procesar), con espera de 1 a 3 segundos entre peticiones.
- Docker Desktop en Windows. Cada contenedor de la API limitado a **0.20 CPU** y **128 MB de RAM**.

## 2. Tabla comparativa de resultados

| Fase | Servidor / Arquitectura | Límite CPU | Usuarios concurrentes | RPS logrados | Latencia P95 (ms) | % Errores |
|------|-------------------------|------------|-----------------------|--------------|-------------------|-----------|
| Fase 1 | Flask Dev (app.run) | 0.20 cores | 50 | 12.5 | 2300 | 0% |
| Fase 2 | Gunicorn (4 workers) | 0.20 cores | 50 | 13.7 | 2300 | 0% |
| Fase 3 | Nginx + 3 réplicas | 0.20 c/u | 150 | 38.6 | ~5500 * | 0% (antes de la caída) |

\* Valor aproximado leído de la gráfica de Locust.

## 3. Observaciones por fase

### Fase 1 — Flask uniproceso
- La CPU del contenedor llegó a su límite (19.78 %) en los primeros 10–15 segundos, durante la subida de usuarios (50 usuarios a 5 por segundo).
- La latencia P95 fue de 2300 ms y el tiempo máximo de 3146 ms. Incluso `/health`, que tiene un tiempo mínimo de 8 ms, pasó a tardar cerca de 2 segundos, porque todas las peticiones hacen fila por la misma CPU.
- En aproximadamente 7 minutos de prueba (5093 peticiones) no se presentaron errores ni timeouts: la API se volvió lenta pero no se cayó.
- Memoria: 24.8 MiB de 128 MiB (19 %). El cuello de botella fue la CPU, no la memoria.

![Fase 1 - Statistics de Locust](fase1_locust_statistics.png)

![Fase 1 - docker stats durante la prueba](fase1_docker_stats.png)

### Fase 2 — Gunicorn con 4 workers
- El RPS subió de 12.5 a 13.7 (cerca de 10 %) y el P95 se mantuvo en 2300 ms, sin errores.
- La CPU siguió en su límite (19.33 %), pero la memoria pasó de 24.8 MiB a 87.35 MiB (68 % del límite), porque cada worker es un proceso de Python independiente.
- Conclusión: agregar procesos dentro del mismo contenedor no aumenta la capacidad cuando la CPU está limitada; solo aumenta el consumo de memoria.

![Fase 2 - Statistics de Locust](fase2_locust_statistics.png)

![Fase 2 - docker stats durante la prueba](fase2_docker_stats.png)

### Fase 3 — Nginx + 3 réplicas y Chaos Test
- Con las 3 réplicas activas, Nginx repartió el tráfico de forma equilibrada (cada réplica recibió entre 212 kB y 222 kB) y cada una trabajó cerca de su límite (16–20 % de CPU).
- Se alcanzaron cerca de 38 RPS con 150 usuarios, unas 3 veces el resultado de las fases 1 y 2, sin errores.
- **Caída de la réplica:** a las 4:44:50 p.m. se ejecutó `docker stop nuevacarpeta-api-backend-2`. Locust registró errores durante unos 5 segundos (pico de ~6 fallos/s), que corresponden a las peticiones que estaban en curso dentro de la réplica apagada. Después los errores volvieron a 0.
- **Tráfico en las 2 réplicas sobrevivientes:** Nginx dejó de enviar peticiones a la réplica caída y repartió todo el tráfico entre las réplicas 1 y 3. El RPS bajó de ~38 a ~25–28 (cerca de 2/3, la misma proporción de CPU que quedó disponible) y la latencia subió un poco, pero el servicio siguió disponible.
- Nota: a las 4:45:40 p.m. la prueba se reinició manualmente; la caída a 0 RPS en ese momento no corresponde a una falla.
- Nota técnica: al usar `http://localhost` como Host en Locust, las peticiones no llegaban a Nginx y terminaban en timeout (~40 s). Al cambiar a `http://127.0.0.1` funcionó correctamente. En Windows, `localhost` puede resolverse primero por IPv6 y no comportarse igual que la dirección IPv4.

![Fase 3 - Réplicas en reposo antes de la prueba](fase3_docker_stats_reposo.png)

![Fase 3 - Carga balanceada entre las 3 réplicas](fase3_docker_stats_balanceo.png)

![Fase 3 - Locust con las 3 réplicas activas (38.6 RPS, 0% fallos)](fase3_locust_charts_3replicas.png)

## 4. Captura de pantalla — Fase 3 en el momento de la caída

![Locust Fase 3 durante la caída de la réplica](fase3_chaos_charts.png)

## 5. Análisis técnico

En un servidor uniproceso como el de desarrollo de Flask, todas las peticiones compiten por un solo intérprete de Python que además está limitado a 0.20 CPU, así que en cuanto llegan más peticiones de las que puede procesar, se forman filas y la latencia crece. En las pruebas se vio que pasar a Gunicorn con 4 workers dentro del mismo contenedor casi no mejoró el resultado (de 12.5 a 13.7 RPS), porque los 4 procesos se repartían la misma cuota de 0.20 CPU, y en cambio la memoria se multiplicó por 3.5. Es decir, el multiproceso permite atender varias peticiones al mismo tiempo y aprovechar mejor la CPU disponible, pero no crea CPU nueva.

El salto real se logra al combinar procesos con un balanceador de carga y varias réplicas: cada réplica es un contenedor con su propio límite de 0.20 CPU, por lo que las 3 réplicas suman 0.60 CPU y Nginx reparte las peticiones entre ellas. Por eso se obtuvieron cerca de 38 RPS, unas 3 veces más que con un solo contenedor, respetando el mismo límite de hardware por instancia. Además, esta arquitectura aporta tolerancia a fallos: al apagar una réplica, solo se perdieron las peticiones que estaban en curso en ella durante unos segundos, y el sistema siguió respondiendo con las 2 réplicas restantes, con una capacidad proporcional a la CPU que quedó disponible. Un servidor uniproceso, en cambio, es un punto único de falla: si se cae, el servicio se cae por completo.
