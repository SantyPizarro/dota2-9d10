# 🎮 dota2-9d10 (Dota 2 Remote Match Accepter)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)

**dota2-9d10** es un monitor de escritorio ultraliviano y bot interactivo de Discord diseñado para jugadores de Dota 2 con tiempos de cola largos. Te envía una notificación instantánea con captura de pantalla a tu celular a través de Discord en cuanto salta una partida y te permite **pulsar un botón interactivo para aceptarla remotamente**.

---

## ✨ Características Principales

* 📱 **Aceptación Remota con Botón Interactivo:** Recibe el aviso en tu celular y pulsa `[ 🎮 ACEPTAR PARTIDA ]` directamente desde Discord.
* ⚡ **Impacto Cero en Rendimiento (Ultra-Lightweight):**
  * Consume **~0.0% de CPU** y menos de **45 MB de RAM**.
  * No procesa video en tiempo real a 60 FPS; solo comprueba una pequeña región central de la pantalla cada 2 segundos.
* 🛡️ **100% Seguro (Sin riesgo de VAC):**
  * No inyecta DLLs, no lee la memoria del proceso `dota2.exe` ni altera archivos del juego.
  * Funciona exclusivamente a nivel de sistema operativo (captura de pantalla estándar de Windows y simulación de clics del ratón).
* 💤 **Prevención de Suspensión:** Evita automáticamente que la laptop apague la pantalla o entre en suspensión mientras estás en la cola de emparejamiento.
* ⏸️ **Auto-Pausa Inteligente:** Al aceptar una partida, el bot se auto-pausa para no consumir recursos durante el juego.
* 🧪 **Comandos de Prueba Integrados:** Prueba todo el flujo desde tu celular antes de buscar partida con el comando `/test`.

---

## 📋 Requisitos Previos

1. **Windows 10 / 11**
2. **Python 3.10 o superior** (asegúrate de marcar *"Add Python to PATH"* durante la instalación).
3. Una cuenta de **Discord** y la app móvil instalada en tu celular.

---

## 🚀 Instalación Rápida

1. **Clonar o descargar el repositorio:**
   ```bash
   git clone https://github.com/SantyPizarro/dota2-9d10.git
   cd dota2-9d10
   ```

2. **Instalar las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Crear tu archivo de configuración `.env`:**
   Copia el archivo de ejemplo `.env.example` y renómbralo a `.env`:
   ```bash
   copy .env.example .env
   ```

---

## 🤖 Guía: Configurar tu Bot de Discord en 5 Minutos

### Paso 1: Crear la Aplicación y el Bot en Discord
1. Ve al [Discord Developer Portal](https://discord.com/developers/applications).
2. Inicia sesión con tu cuenta de Discord y haz clic en el botón azul **"New Application"** (arriba a la derecha).
3. Ponle un nombre a tu aplicación (ej: `Dota2 Notifier`) y acepta los términos.
4. En el menú lateral izquierdo, entra en la sección **"Bot"**:
   * *(Opcional)* Puedes subirle una foto de perfil del logo de Dota 2.
   * Haz clic en el botón **"Reset Token"** (o "Copy Token") para generar el Token del bot.
   * **Copia este Token** (lo necesitarás para tu archivo `.env`).
   * Desplázate hacia abajo hasta **"Privileged Gateway Intents"** y activa:
     * ✅ **Message Content Intent**
   * Guarda los cambios con el botón verde abajo.

### Paso 2: Invitar al Bot a tu Servidor de Discord
1. En el menú lateral izquierdo, ve a **OAuth2** ➡️ **URL Generator**.
2. En la sección **"Scopes"**, marca:
   * ✅ `bot`
   * ✅ `applications.commands`
3. En la sección **"Bot Permissions"** que aparece abajo, marca:
   * ✅ `Send Messages`
   * ✅ `Embed Links`
   * ✅ `Attach Files`
   * ✅ `Use External Emojis`
4. Al final de la página verás un enlace generado (**Generated URL**). Haz clic en **Copy**.
5. Pega ese enlace en tu navegador, selecciona tu servidor privado de Discord (si no tienes uno, crea un servidor personal en Discord en 10 segundos donde solo estés tú) y dale a **Autorizar**.

### Paso 3: Obtener el ID del Canal
1. En la aplicación de Discord (PC), ve a **Ajustes de Usuario** ⚙️ ➡️ **Avanzado** ➡️ Activa el **Modo Desarrollador**.
2. Haz clic derecho sobre el canal de texto de tu servidor donde quieras recibir las alertas (ej. `#general` o crea uno llamado `#dota2-alertas`) y selecciona **"Copiar ID de canal"**.

---

## ⚙️ Configurar el archivo `.env`

Abre el archivo `.env` con cualquier editor de texto (como Bloc de Notas o VS Code) y pega tus datos:

```env
# Token copiado del Developer Portal
DISCORD_BOT_TOKEN=MTM0NDk...tu_token_aqui...

# ID del canal copiado de Discord
DISCORD_CHANNEL_ID=123456789012345678

# (Opcional) Tu ID de usuario si quieres que te mencione con @tu_usuario
DISCORD_USER_ID=

# Intervalo de chequeo en segundos (2.0s recomendado)
CHECK_INTERVAL=2.0

# Pausa automática tras aceptar (en minutos)
AUTO_PAUSE_MINUTES=25
```

---

## 🎮 Cómo Usar

1. **Inicia el programa:**
   ```bash
   python main.py
   ```
   Verás un mensaje en la consola:
   ```text
   [INFO] Bot conectado como Dota2 Notifier#1234
   [INFO] Comandos Slash sincronizados.
   [INFO] Iniciando ciclo de vigilancia (chequeo cada 2.0s)...
   ```

2. **Probar que todo funcione:**
   * Abre Discord en tu celular.
   * En el canal donde está el bot, escribe `/test`.
   * El bot te enviará una notificación interactiva de prueba con una captura y dos botones:
     > 🧪 **ALERTA DE PRUEBA (TEST)**  
     > `[ 🎮 ACEPTAR PARTIDA ]` `[ ❌ Ignorar / No Aceptar ]`
   * Presiona el botón verde `[ 🎮 ACEPTAR PARTIDA ]` desde tu teléfono y verifica que la laptop ejecute la acción.

3. **¡Listo para jugar!**
   * Abre Dota 2 en tu laptop.
   * Dale a **Buscar Partida**.
   * Ve a la cocina o a hacer tus quehaceres con el celular en mano.
   * En cuanto encuentre partida, tu celular sonará y vibrará. ¡Tocas **Aceptar** y caminas a tu PC!

---

## 📱 Comandos Disponibles en Discord

| Comando | Descripción |
| :--- | :--- |
| `/status` | Muestra el estado del monitor y si el proceso de Dota 2 está abierto. |
| `/test` | Envía una alerta de prueba con captura y botón interactivo. |
| `/screen` | Toma una captura de pantalla actual de la laptop y te la envía a Discord. |
| `/pause [minutos]` | Pausa la vigilancia durante el tiempo especificado (por defecto 25m). |
| `/resume` | Reanuda la vigilancia inmediatamente. |

---

## 🛠️ Ejecutar Tests Unitarios

Para verificar que todos los algoritmos de detección y vistas interactivas funcionan correctamente:
```bash
python -m pytest -v
```

---

## 📜 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
