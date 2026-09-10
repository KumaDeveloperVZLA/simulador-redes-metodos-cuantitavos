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
