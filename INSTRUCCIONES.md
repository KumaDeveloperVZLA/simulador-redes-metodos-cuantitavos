# Especificaciones del Proyecto: Simulador Dinámico de Redes de Computadoras

Actúa como un Ingeniero de Software Senior especialista en Simulación de Eventos Discretos, Métodos Cuantitativos y Desarrollo de GUI con Pygame. 

Diseña e implementa una solución modular y completa en Python bajo el paradigma de Programación Orientada a Objetos (POO) para un **Simulador Dinámico de Redes de Computadoras**, integrando visualización gráfica, modelado matemático y análisis automático vía API.

---

### 1. ARQUITECTURA DE SOFTWARE Y DEPENDENCIAS
Estructura el proyecto con separación limpia de responsabilidades (evita código espagueti en un solo archivo o bloque masivo):
* **Librerías principales:** `pygame`, `simpy`, `numpy`, `scipy` (`linear_sum_assignment`), `requests`, `threading` / `queue`.
* **Sincronización SimPy ↔ Pygame:**
  * SimPy opera por avance de eventos (`env.now`), mientras que Pygame corre en un game loop a 60 FPS con delta time real. 
  * Implementa un puente desacoplado: ejecuta pasos discretos de SimPy controlados (`env.step()` o micro-avances en el loop) o mediante un worker thread comunicando el estado de buffers, paquetes activos y métricas hacia la GUI vía estructuras thread-safe.
  * Garantiza que la interfaz no se congele durante pausas, caídas de enlaces o la llamada HTTP final.

---

### 2. ESPECIFICACIONES MATEMÁTICAS Y TÉCNICAS

#### A. Teoría de Colas (Líneas de Espera)
* **Generación:** Proceso de Poisson con tasa $\lambda$ configurable en tiempo de ejecución. Intervalos entre llegadas: `random.expovariate(lambd)`.
* **Servicio:** Cada router/enlace procesa paquetes con distribución exponencial de tasa $\mu$.
* **Métricas en tiempo real:**
  * $L_q$: Promedio ponderado en el tiempo de paquetes esperando en cola.
  * $L$: Promedio ponderado en el tiempo de paquetes totales en el sistema (cola + servicio).
  * $W_q$: Tiempo medio real de espera en cola por paquete completado.
  * $W$: Tiempo medio total en el sistema (espera + transmisión) por paquete completado.

#### B. Gestión de Inventario (Buffer Control)
* **Capacidad Finita ($S$):** Límite estricto de paquetes en el buffer de cada router. Si un paquete llega y el buffer está lleno, se descarta por *Buffer Overflow* (Packet Loss).
* **Política de Reabastecimiento / Control de Flujo $(s, Q)$:**
  * Monitorear el nivel del buffer. Si desciende por debajo del umbral mínimo $s$, enviar señal de control de flujo para solicitar un lote $Q$ de paquetes o habilitar admisión de tráfico de entrada.
* **Modelo de Costos Dinámicos:**
  * **Holding Cost ($H$):** Costo por unidad de tiempo por paquete retenido en el buffer/RAM (acumular integralmente según $L_q \cdot H \cdot \Delta t$).
  * **Shortage / Ruptura:** Penalización monetaria fija por cada paquete descartado por desbordamiento.
  * Computar el **Costo Global del Sistema** acumulado ($Costo\ Almacenamiento + Costo\ Ruptura$).

#### C. Asignación Óptima (Algoritmo Húngaro)
* En intervalos discretos $\Delta t$, recopilar $N$ flujos/paquetes pendientes y $M$ enlaces/nodos disponibles.
* Construir la matriz de costos dinámicos:
  $$C_{ij} = \text{Latencia Actual del Enlace}_{ij} + \alpha \cdot (\text{Saturación del Buffer}_j)$$
  *(donde Saturación = Buffer Actual / $S$, y $\alpha$ es un factor de ponderación calibrado).*
* Balancear la matriz si $N \neq M$ con valores dummy (penalizaciones altas).
* Resolver la asignación 1 a 1 óptima usando `scipy.optimize.linear_sum_assignment` y redirigir los flujos en tiempo real.

---

### 3. DISEÑO DE LA INTERFAZ GRÁFICA (Pygame)
La interfaz debe ser profesional, intuitiva y visualmente atractiva (paleta tipo Dark Mode/Cyberpunk, fuentes nítidas, paneles delimitados):
* **Topología de Red:**
  * Nodos (routers/switches) con radio visible e indicadores circulares de saturación:
    * **Verde:** < 50% de ocupación.
    * **Amarillo:** 50% - 80%.
    * **Rojo:** > 80% (Alerta de posible overflow).
  * Enlaces dinámicos (líneas con grosor/color variable según estado activo/caído y latencia).
  * Paquetes animados viajando interpoladamente (LERP) a lo largo de las coordenadas de los enlaces en tiempo real.
* **Dashboard / HUD (Sidebar lateral o barra superior):**
  * Cronómetro de simulación transcurrida.
  * Parámetros activos ($\lambda, \mu, S, s, Q$).
  * Métricas en vivo: $L, L_q, W, W_q$, paquetes procesados, paquetes perdidos y % de pérdida.
  * Costo acumulado desglosado (Almacenamiento, Ruptura, Total).
* **Interactividad y Controles:**
  * Teclado o botones en pantalla:
    * `UP`/`DOWN` o `+/-`: Aumentar/disminuir $\lambda$ dinámicamente.
    * `ESPACIO`: Pausar / Reanudar simulación.
    * Click sobre un enlace: Alternar su estado (simular fallo/caída imprevista del enlace).
    * `E` o `ESC`: Detener simulación, compilar reporte y disparar la llamada API.

---

### 4. EXPORTACIÓN Y LLAMADA A API EXTERNA
* Al finalizar la simulación, generar automáticamente `reporte_simulacion.txt` respetando estrictamente este formato:
```text
==================================================
           REPORTE DE SIMULACIÓN DE RED           
==================================================
Tiempo Total de Simulación: [T] s
Tasa de Llegada (lambda): [λ] paquetes/s
Tasa de Servicio (mu): [μ] paquetes/s
Capacidad de Buffer (S): [S] paquetes
Umbral Reabastecimiento (s): [s] paquetes
--------------------------------------------------
METRICAS OBTENIDAS:
Paquetes Procesados: [N_proc]
Paquetes Perdidos (Overflow): [N_loss]
Tasa de Pérdida: [X.XX]%
Tiempo Medio en Cola (Wq): [X.XX] s
Promedio Paquetes en Sistema (L): [X.XX]
Costo Total de Almacenamiento: $[X.XX]
Costo Total de Penalización (Ruptura): $[X.XX]
--------------------------------------------------
Costo Global del Sistema: $[X.XX]
==================================================
```
