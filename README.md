# Simulador Dinámico de Redes de Computadoras
**Universidad José Antonio Páez (UJAP) - Facultad de Ingeniería**  
**Escuela de Ingeniería en Computación | Métodos Cuantitativos**

Solución integral y modular en Python que modela y simula una red de computadoras en tiempo real integrando tres áreas fundamentales de los métodos cuantitativos:
1. **Teoría de Líneas de Espera (Colas M/M/1/K):** Proceso de Poisson para arribo de paquetes, tiempos de servicio exponencial ($\mu$) y cálculo integral en tiempo real de $L$, $L_q$, $W$, $W_q$.
2. **Modelos de Inventario y Control de Buffers:** Capacidad finita de almacenamiento ($S$), política de reabastecimiento y control de flujo $(s, Q)$, cómputo de costos de almacenamiento (*Holding Cost*) y penalización por desbordamiento (*Shortage Cost*).
3. **Modelos de Asignación Óptima (Algoritmo Húngaro):** Enrutamiento y balanceo dinámico de carga mediante `scipy.optimize.linear_sum_assignment` sobre una matriz de costos que combina latencia y saturación de buffers.

La visualización gráfica está desarrollada en **Pygame a 60 FPS** bajo una estética **Cyberpunk / Dark Mode**, desacoplada del motor de eventos discretos **SimPy** mediante un puente *thread-safe* bidireccional. Incluye exportación a archivo plano `reporte_simulacion.txt`, diagnóstico automatizado mediante API HTTP y generación del informe formal `informe_tecnico.docx`.

---

## 🚀 Requisitos e Instalación

1. **Clonar o abrir el repositorio:**
   ```bash
   cd c:\Metodos-cuantitativos\Tarea-Simulador-Redes
   ```

2. **Crear y activar el entorno virtual:**
   ```bash
   python -m venv .venv
   # En Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # O en CMD:
   .venv\Scripts\activate.bat
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

*(Opcional)* Si deseas usar una API externa en lugar del motor experto integrado, crea un archivo `.env` en la raíz con tu clave:
```env
GEMINI_API_KEY=tu_clave_aqui
# O bien:
OPENAI_API_KEY=tu_clave_aqui
```

---

## 🎮 Modos de Ejecución

### 1. Modo Interactivo con Interfaz Gráfica (Pygame a 60 FPS)
```bash
python main.py
```
Abre la ventana interactiva Cyberpunk (1280x768) con la red en vivo.

#### Controles Interactivos:
- **`ESPACIO`**: Pausar / Reanudar la simulación en cualquier momento.
- **`FLECHA ARRIBA` / `+`**: Incrementar la tasa de llegada de paquetes ($\lambda$).
- **`FLECHA ABAJO` / `-`**: Reducir la tasa de llegada ($\lambda$).
- **Click izquierdo sobre un Enlace**: Alternar su estado (*OFFLINE* / *Activo*), simulando caídas imprevistas de enlaces para forzar al Algoritmo Húngaro a balancear hacia rutas alternas.
- **Click en botones del HUD**: Ajustar parámetros, pausar o exportar.
- **`E` o `ESC`**: Detener la simulación, compilar métricas finales, generar `reporte_simulacion.txt`, consultar la API de análisis y generar `informe_tecnico.docx`.

---

### 2. Modo Headless (Evaluación Rápida por Línea de Comandos)
```bash
python main.py --headless --duration 30
```
Ejecuta la simulación durante el tiempo indicado (ej. 30 segundos) sin abrir la ventana de Pygame, mostrando el avance en consola y generando automáticamente todos los archivos de entrega.

---

## 🧪 Pruebas Automatizadas

Para ejecutar el conjunto de pruebas unitarias y de integración de los modelos cuantitativos:
```bash
python -m unittest tests/test_simulation.py
```

---

## 🧮 Decisiones de Modelado (supuestos explícitos)

Estas son las convenciones que gobiernan los números del reporte. Conviene citarlas en la
defensa del informe, porque determinan cómo deben leerse las métricas.

### Separación entre espera en cola y servicio
El paquete **abandona el buffer en el instante en que comienza su servicio**, no cuando
termina. Por lo tanto:
- $W_q$ mide únicamente la espera en cola y $L_q$ cuenta solo a los paquetes que esperan.
- El tiempo de servicio exponencial se acumula aparte (`Packet.total_service_time`), de modo
  que se preserva la relación $W = W_q + 1/\mu + \text{latencia de tránsito}$ por salto.
- Los valores reportados de $W_q$ y $W$ son **acumulados sobre todos los saltos** del paquete
  (ingreso + núcleo), no por nodo: por eso son aproximadamente el doble del $W_q$ que predice
  un M/M/1 aislado con la misma $\rho$.

### Enrutamiento orientado al destino
Cada paquete nace con un `destination_id` y **ese destino gobierna la ruta**: en cada salto
solo se consideran los enlaces operativos desde los cuales el nodo destino sigue siendo
alcanzable (la tabla de alcanzabilidad se recalcula ante cada caída o restauración de enlace).
Entre los enlaces válidos se elige el de menor costo $C_{ij}$, de manera que el balanceo de
carga opera **dentro** del conjunto de rutas correctas.

Si una falla de enlaces deja al paquete sin ninguna ruta hacia su destino, se permite un
desvío de emergencia por cualquier enlace operativo; esas entregas se contabilizan aparte
como *entregas en egress alterno* y se informan en el reporte.

### Política $(s, Q)$ con lotes efectivos
El lote $Q$ **se consume realmente**, no es una bandera informativa:
- Cada admisión en un buffer descuenta una unidad del lote vigente.
- Cuando la ocupación baja hasta el umbral $s$ y el lote se agotó, el nodo emite la señal de
  control de flujo y autoriza un lote nuevo de $Q$ paquetes (libera su canal de entrada).
- Mientras el lote esté agotado y la ocupación siga por encima de $s$, el canal permanece
  cerrado: el nodo **rechaza** nuevas llegadas y ejerce contrapresión (*backpressure*) sobre
  sus vecinos, que retienen el paquete en su propio buffer en lugar de reenviarlo.

Consecuencia cuantitativa: la ocupación de un buffer nunca supera $s + Q$. Con la
configuración por defecto ($S = 50$, $s = 10$, $Q = 15$) resulta $s + Q = 25 < S$, así que el
control de flujo **previene por construcción el desbordamiento** y la pérdida se materializa
como rechazo controlado en la admisión. Los paquetes rechazados se contabilizan como tráfico
perdido (el modelo no reintenta el envío) y penalizan el costo de ruptura igual que un
*overflow*. Para observar desbordamientos reales basta configurar $S < s + Q$ en `src/config.py`.

### Algoritmo Húngaro
Cada $\Delta t$ (`HUNGARIAN_INTERVAL`, 0.1 s, del orden del tiempo de servicio $1/\mu$) se
plantea **un único problema global**: los $N$ paquetes que están en cabeza de cola en todos los
routers -uno por cada enlace de salida operativo, que son los únicos que el nodo alcanza a
despachar dentro de $\Delta t$- frente a los $M$ enlaces operativos de toda la topología.
Los pares no admisibles (enlace que no nace del nodo donde espera el paquete, ruta que no
conduce al destino, o vecino con el canal cerrado) reciben el costo ficticio y quedan fuera
de la solución. Cada asignación **caduca al vencer $\Delta t$**; pasada esa ventana el nodo
decide por costo mínimo, porque la fotografía de saturación que resolvió la matriz ya no
describe la red.

### Reporte de $\lambda$
$\lambda$ y $\mu$ pueden ajustarse en caliente durante la sesión gráfica. El reporte publica
la **media ponderada en el tiempo** de la corrida -no el último valor tecleado- y deja
constancia del recorrido (inicial → final y rango) en el bloque complementario, de modo que
el archivo entregado nunca sea internamente contradictorio.

---

## 📂 Estructura del Proyecto

```
Tarea-Simulador-Redes/
├── main.py                      # Punto de entrada (interactivo o headless)
├── requirements.txt             # Dependencias fijadas del proyecto
├── reporte_simulacion.txt       # Entregable 2: Reporte con formato estricto y análisis API
├── informe_tecnico.docx         # Entregable 3: Informe formal de ingeniería con desarrollo matemático
├── assets/
│   └── screenshot_simulator.png # Captura de alta resolución de la simulación gráfica
├── tests/
│   └── test_simulation.py      # Pruebas unitarias de colas, inventario y algoritmo húngaro
└── src/
    ├── config.py                # Parámetros por defecto, topología de red y paleta Cyberpunk
    ├── models/
    │   ├── packet.py            # Paquetes de datos, timestamps y animación LERP
    │   ├── node.py              # Routers con buffer finito S, umbral s, lote Q y semaforización
    │   └── link.py              # Enlaces dinámicos, latencias y detección de clicks
    ├── simulation/
    │   ├── engine.py            # Motor SimPy con Poisson, servicio exponencial y enrutamiento
    │   ├── metrics.py           # Cómputo integral de L, Lq, W, Wq, holding costs y ruptura
    │   ├── hungarian.py         # Asignación óptima Kuhn-Munkres (scipy.optimize)
    │   └── bridge.py            # Puente desacoplado y thread-safe SimPy ↔ Pygame
    ├── gui/
    │   ├── renderer.py          # Renderizado de nodos (<50%, 50-80%, >80%), enlaces y paquetes
    │   ├── hud.py               # Panel lateral de instrumentos, métricas en vivo y controles
    │   └── app.py               # Game loop de Pygame, teclado/mouse y ciclo de apagado
    └── reporting/
        ├── exporter.py          # Formateador exacto del reporte en texto plano (.txt)
        ├── api_client.py        # Módulo HTTP con prompt analítico y fallback experto
        └── doc_generator.py     # Generador del documento Word (.docx) formal
```

---

## 📋 Entregables Cumplidos

1. **Código Fuente (`.py`)**: Arquitectura POO modular y extensamente comentada que integra SimPy, Pygame, NumPy, SciPy y Requests.
2. **Reporte de Simulación (`reporte_simulacion.txt`)**: Archivo de salida estructurado conforme a la plantilla oficial de la cátedra con el diagnóstico analítico de la API anexado.
3. **Informe Técnico (`informe_tecnico.docx`)**: Documento Word institucional con portada UJAP, formulación matemática completa, explicación del puente multihilo, tabla de resultados empíricos, dictamen de la API y capturas de la interfaz en ejecución.
