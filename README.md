# 🎮 dota2-9d10 (Dota 2 Remote Match Accepter)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)

**dota2-9d10** es un monitor de escritorio ultraliviano y bot interactivo de Discord diseñado para jugadores de Dota 2 con tiempos de cola largos. Detecta automáticamente cuándo comienzas a buscar partida, te notifica al celular con una captura en cuanto salta la partida y te permite **pulsar un botón interactivo para aceptarla remotamente**.

---

## ✨ Características Principales

* 📱 **Aceptación Remota con Botón Interactivo:** Recibe el aviso en tu celular y pulsa `[ 🎮 ACEPTAR PARTIDA ]` directamente desde Discord.
* 🛡️ **Seguridad para Servidores Públicos / Party (Whitelist por ID):**
  * Configura qué usuarios de Discord tienen permiso para presionar el botón de Aceptar (`ALLOWED_USER_IDS`).
  * Si otra persona en tu servidor hace clic, Discord le responderá solo a ella con un aviso de acceso denegado y **no ejecutará ninguna acción en tu PC**.
* 🎯 **Precisión Matemática y Clic Único:**
  * Calcula el centro exacto del botón verde sin importar la resolución o modo de pantalla (1366x768, 1080p, 1440p, ventana o pantalla completa).
  * Cuenta con un bloqueo estricto (*mutex*) que garantiza que se envíe **un único clic**, evitando cualquier tipo de spam o doble clic accidental.
* 💬 **Ciclo de Vida en un Solo Mensaje (Cero Spam en el Canal):**
  * Detecta automáticamente cuando el botón de "Jugar Dota" cambia a "Buscando partida..." y envía un mensaje de estado inicial.
  * Cuando salta la partida, **edita ese mismo mensaje** con la captura y los botones.
  * Al aceptar, **edita el mensaje** a *"Partida Aceptada"*.
  * Al entrar al juego, **edita el mensaje** a *"Partida Iniciada"*.
* 🔄 **Manejo Inteligente de Dodgeadas (9/10):**
  * Si alguien rechaza la partida o no carga a tiempo y Dota 2 te devuelve a la cola con prioridad alta, el bot lo detecta, te avisa en el mensaje y **reanuda la vigilancia automáticamente**.
* ⚡ **Impacto Cero en Rendimiento (Ultra-Lightweight):**
  * Consume **~0.0% de CPU** y menos de **45 MB de RAM**.
  * No procesa video en tiempo real a 60 FPS; solo comprueba regiones de interés cada 2 segundos.
* 🛡️ **100% Seguro (Sin riesgo de VAC):**
  * No inyecta DLLs ni lee memoria del proceso `dota2.exe`. Opera exclusivamente a nivel de Windows.
* 💤 **Prevención de Suspensión:** Evita que tu laptop apague la pantalla o se suspenda mientras esperas partida.

---

## 📋 Requisitos Previos

1. **Windows 10 / 11**
2. **Python 3.10 o superior**
3. Una cuenta de **Discord** y la app instalada en tu teléfono.

---

## 🚀 Instalación Rápida

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/SantyPizarro/dota2-9d10.git
   cd dota2-9d10
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Crear archivo `.env`:**
   ```bash
   copy .env.example .env
   ```

---

## 🤖 Guía: Configurar tu Bot de Discord en 5 Minutos

### Paso 1: Crear la Aplicación y el Bot
1. Entra a **[Discord Developer Portal](https://discord.com/developers/applications)**.
2. Haz clic en **"New Application"**, nómbrala (ej: `Dota2 Accepter`) y dale a **Create**.
3. En el menú izquierdo, ve a **"Bot"**:
   * Haz clic en **"Reset Token"** (o "Copy Token") y copia tu **Token**.
   * En **"Privileged Gateway Intents"**, activa:
     * ✅ **Message Content Intent**
   * Guarda los cambios (**Save Changes**).

### Paso 2: Invitar al Bot a tu Servidor
1. En el menú izquierdo, ve a **"OAuth2"** ➡️ **"URL Generator"**.
2. En **"Scopes"**, marca:
   * ✅ `bot`
   * ✅ `applications.commands`
3. En **"Bot Permissions"**, marca:
   * ✅ `Send Messages`
   * ✅ `Embed Links`
   * ✅ `Attach Files`
   * ✅ `Use External Emojis`
4. Copia la URL generada al final, ábrela en tu navegador y autoriza al bot en tu servidor.

### Paso 3: Obtener IDs (Canal y Usuario)
1. En la app de Discord en PC, ve a **Ajustes de Usuario** ⚙️ ➡️ **Avanzado** ➡️ Activa el **Modo Desarrollador**.
2. **ID del Canal:** Haz clic derecho sobre el canal donde irá el bot y selecciona **"Copiar ID de canal"**.
3. **ID de tu Usuario:** Haz clic derecho sobre tu propio perfil/avatar en Discord y selecciona **"Copiar ID de usuario"**.

---

## ⚙️ Configuración del `.env`

Edita el archivo `.env` con tus datos:

```env
# Token del bot
DISCORD_BOT_TOKEN=MTM0NDk...tu_token_aqui...

# ID del canal de Discord
DISCORD_CHANNEL_ID=123456789012345678

# Tu ID de Discord (para menciones directas en la alerta)
DISCORD_USER_ID=111222333444555666

# Lista blanca de usuarios autorizados a presionar "Aceptar" (separados por coma)
# Si estás en party y solo tú (o un amigo) pueden aceptar:
ALLOWED_USER_IDS=111222333444555666

# Intervalo de chequeo en segundos (2.0s recomendado)
CHECK_INTERVAL=2.0

# Pausa automática tras iniciar la partida (en minutos)
AUTO_PAUSE_MINUTES=25
```

---

## 🎮 Cómo Usar

1. **Inicia el programa:**
   ```bash
   python main.py
   ```

2. **Probar desde el celular:**
   * En el canal de Discord, escribe `/test`.
   * Recibirás la alerta de prueba interactiva. Toca **`[ 🎮 ACEPTAR PARTIDA ]`** y comprueba que responda correctamente. Si otra persona del servidor lo presiona, el bot le negará el acceso sin afectar tu PC.

3. **¡A jugar!**
   * Abre Dota 2 y dale a **Buscar Partida**.
   * El bot detectará automáticamente que empezaste a buscar y pondrá el estado en Discord.
   * Ve a la cocina o a donde quieras. En cuanto salga la partida, aceptas desde el celular con un toque. Si hay dodge (9/10), el bot continuará vigilando solo.

---

## 📱 Comandos Disponibles en Discord

| Comando | Descripción |
| :--- | :--- |
| `/status` | Muestra el estado del monitor, proceso de Dota 2 y usuarios autorizados. |
| `/test` | Envía una alerta interactiva de prueba a Discord. |
| `/screen` | Captura la pantalla actual de la laptop y la envía a Discord. |
| `/pause [minutos]` | Pausa temporalmente la vigilancia. |
| `/resume` | Reanuda la vigilancia de inmediato. |

---

## 🛠️ Tests Unitarios

Para validar todos los módulos de seguridad, detección de estados y simulación de clics:
```bash
python -m pytest -v
```

---

## 📜 Licencia

Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
