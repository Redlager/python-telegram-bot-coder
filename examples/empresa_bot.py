import logging
import os
import time
from collections import defaultdict
from typing import Final

from dotenv import load_dotenv
from groq import Groq

# --- Gemini (deshabilitado) ---
# from google import genai
# from google.genai import types

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

load_dotenv()

# --- Gemini (deshabilitado) ---
# gemini_api_key = os.getenv("GEMINI_API_KEY")
# if gemini_api_key:
#     genai_client = genai.Client(api_key=gemini_api_key)
#     ...

SYSTEM_INSTRUCTION = (
    "Eres un asistente de CoderNeural, experto en IA, automatización y desarrollo de software.\n"
    "Responde siempre en español.\n\n"
    "📋 Reglas:\n"
    "- Respuestas muy concisas (máx. 2-3 oraciones).\n"
    "- Directo al punto, sin relleno.\n"
    "- Usa 1-2 emojis máximo.\n"
    "- Tono profesional, claro y orientado a negocio.\n"
    "- Siempre que sea posible, enfoca la respuesta en beneficios (ahorro de tiempo, automatización, eficiencia).\n"
    "- Si el tema es complejo o el usuario muestra interés → sugerir contacto.\n\n"
    "📞 Contacto:\n"
    "- Email: contacto@coderneural.com\n"
    "- WhatsApp: https://wa.me/5493764983924\n\n"
    "📌 Servicios:\n"
    "- Chatbots inteligentes\n"
    "- Automatización de procesos\n"
    "- Integración de APIs\n"
    "- Backend y frontend\n"
    "- Análisis de datos\n"
    "- Inteligencia Artificial"
)

# Configurar Groq
groq_api_key = os.getenv("GROQ_API_KEY")
if groq_api_key:
    groq_client = Groq(api_key=groq_api_key)
    LOGGER.info("Groq configurado correctamente.")
else:
    groq_client = None
    LOGGER.warning("GROQ_API_KEY no configurada. El chat de IA no funcionará.")

# Rate limiting: máx 5 mensajes por usuario cada 60 segundos
RATE_LIMIT_MESSAGES = 5
RATE_LIMIT_WINDOW = 60  # segundos
_user_timestamps: dict[int, list[float]] = defaultdict(list)

PROMPT_INJECTION_TOKENS = (
    "ignora",
    "ignore",
    "olvida",
    "forget",
    "system prompt",
    "instrucciones anteriores",
    "jailbreak",
    "bypass",
    "override",
    "act as",
    "actua como",
    "eres ahora",
    "nuevo rol",
    "pretend",
)


def is_rate_limited(user_id: int) -> tuple[bool, int]:
    """Retorna (True, segundos_restantes) si el usuario superó el límite."""
    now = time.time()
    _user_timestamps[user_id] = [
        t for t in _user_timestamps[user_id] if now - t < RATE_LIMIT_WINDOW
    ]
    if len(_user_timestamps[user_id]) >= RATE_LIMIT_MESSAGES:
        oldest = _user_timestamps[user_id][0]
        seconds_left = int(RATE_LIMIT_WINDOW - (now - oldest)) + 1
        return True, seconds_left
    _user_timestamps[user_id].append(now)
    return False, 0


def has_prompt_injection(text: str) -> bool:
    """Retorna True si el mensaje parece un intento de prompt injection."""
    text_lower = text.lower()
    return any(token in text_lower for token in PROMPT_INJECTION_TOKENS)


INFO: Final[str] = (
    "Somos CoderNeural.\n"
    "Creamos soluciones de IA y automatizacion para empresas.\n"
    "Sitio: https://coderneural.com\n"
    "Instagram: https://www.instagram.com/coderneural"
)

SERVICIOS: Final[str] = (
    "Servicios destacados:\n"
    "- Chatbots y agentes con IA.\n"
    "- Automatizacion de procesos y workflows.\n"
    "- Integraciones API y sistemas a medida.\n"
    "- Analitica y modelos de machine learning.\n"
    "- Consultoria y roadmaps de IA."
)

CONTACTO: Final[str] = (
    "Contacto directo:\n"
    "Email: contacto@coderneural.com\n"
    "WhatsApp: +54 9 3764 983924\n"
    "Sitio: https://coderneural.com\n"
    "Instagram: https://www.instagram.com/coderneural"
)

EQUIPO: Final[str] = (
    "Equipo CoderNeural:\n"
    "- Liderazgo y estrategia: Renzo Fedeli.\n"
    "- Ingenieria y data: especialistas en IA, MLOps y automatizacion.\n"
    "- Producto y entrega: foco en integraciones y time-to-value.\n"
    "Conectemos: https://coderneural.com/#contacto"
)

# Contenido del Quiz
QUIZ_INTRO: Final[str] = (
    "🎯 Quiz de Necesidades\n\n"
    "Responde estas preguntas para que identifiquemos la solución perfecta para tu empresa.\n\n"
    "¿Cuál es tu principal desafío?"
)

QUIZ_RECOMMENDATIONS = {
    # Chatbot combinations
    ("chatbot", "si_automatizacion", "backend"): (
        "🤖🔧⚙️ SOLUCIÓN PREMIUM: CHATBOT IA + AUTOMATIZACIÓN + BACKEND\n\n"
        "Recomendación: Solución completa 360°\n"
        "✓ Chatbot entrenado con IA avanzada\n"
        "✓ Automatización de procesos internos\n"
        "✓ Backend robusto e integración API\n\n"
        "Caso de uso:\n"
        "- Empresas que quieren transformación digital completa\n"
        "- Atención al cliente + operaciones + innovación"
    ),
    ("chatbot", "si_automatizacion", "no_backend"): (
        "🤖⚙️ SOLUCIÓN POTENCIADA: CHATBOT + AUTOMATIZACIÓN\n\n"
        "Recomendación: Mejora significativa\n"
        "✓ Chatbot con IA para atención al cliente\n"
        "✓ Automatización de tareas manuales\n"
        "✓ Integración con herramientas existentes\n\n"
        "Caso de uso:\n"
        "- Empresas con buena infraestructura actual\n"
        "- Mejorar + automatizar sin rediseño"
    ),
    ("chatbot", "no_automatizacion", "backend"): (
        "🤖🔧 SOLUCIÓN INTELIGENTE: CHATBOT + BACKEND API\n\n"
        "Recomendación: Atención + Infraestructura\n"
        "✓ Chatbot con IA para soporte 24/7\n"
        "✓ Backend profesional y seguro\n"
        "✓ APIs integradas con tus sistemas\n\n"
        "Caso de uso:\n"
        "- Empresas con procesos manuales estables\n"
        "- Necesitan mejorar atención al cliente"
    ),
    ("chatbot", "no_automatizacion", "no_backend"): (
        "🤖 SOLUCIÓN CHATBOT: IA PARA ATENCIÓN\n\n"
        "Recomendación: Foco en cliente\n"
        "✓ Chatbot inteligente 24/7\n"
        "✓ Respuestas automáticas personalizadas\n"
        "✓ Integración con WhatsApp/Web\n\n"
        "Caso de uso:\n"
        "- Reducir tickets de soporte\n"
        "- Mejorar experiencia del cliente"
    ),
    ("chatbot", "ambos", "backend"): (
        "🤖⚙️🔧 SOLUCIÓN COMPLETA: TODO INTEGRADO\n\n"
        "Recomendación: Transformación total\n"
        "✓ Chatbot IA + Automatización\n"
        "✓ Backend robusto\n"
        "✓ Sistema end-to-end"
    ),
    ("chatbot", "ambos", "no_backend"): (
        "🤖⚙️ SOLUCIÓN HIBRIDA: CHATBOT + AUTOMATIZACIÓN\n\n"
        "Recomendación: Máximo valor sin backend nuevo\n"
        "✓ Chatbot inteligente\n"
        "✓ Automatización total de procesos\n"
        "✓ Aprovecha infraestructura existente"
    ),
    # Automatización combinations
    ("automatizacion", "si_automatizacion", "backend"): (
        "⚙️🔧 SOLUCIÓN OPERATIVA: AUTOMATIZACIÓN + BACKEND\n\n"
        "Recomendación: Operaciones + Tecnología\n"
        "✓ Automatización avanzada de flujos\n"
        "✓ Backend profesional\n"
        "✓ Integración con múltiples APIs\n\n"
        "Caso de uso:\n"
        "- Empresas con procesos complejos\n"
        "- Necesitan infraestructura moderna"
    ),
    ("automatizacion", "si_automatizacion", "no_backend"): (
        "⚙️ SOLUCIÓN EFICIENCIA: AUTOMATIZACIÓN TOTAL\n\n"
        "Recomendación: Máxima automatización\n"
        "✓ Flujos sin intervención manual\n"
        "✓ Reportes automáticos\n"
        "✓ Sincronización de datos"
    ),
    ("automatizacion", "no_automatizacion", "backend"): (
        "🔧⚙️ SOLUCIÓN MODERNA: BACKEND + AUTOMATIZACIÓN\n\n"
        "Recomendación: Infraestructura + Eficiencia\n"
        "✓ Backend moderno y escalable\n"
        "✓ Automatización vía APIs\n"
        "✓ Integraciones futuras fáciles"
    ),
    ("automatizacion", "no_automatizacion", "no_backend"): (
        "⚙️ SOLUCIÓN PROCESOS: AUTOMATIZACIÓN ESENCIAL\n\n"
        "Recomendación: Reducir trabajo manual\n"
        "✓ Automatización de tareas repetitivas\n"
        "✓ Flujos sin intervención\n"
        "✓ Reportes diarios automáticos"
    ),
    ("automatizacion", "ambos", "backend"): (
        "⚙️🔧💼 SOLUCIÓN ENTERPRISE: AUTOMATIZACIÓN TOTAL\n\n"
        "Recomendación: Transformación completa\n"
        "✓ Automatización sin límites\n"
        "✓ Backend escalable\n"
        "✓ Sistema integrado"
    ),
    ("automatizacion", "ambos", "no_backend"): (
        "⚙️ SOLUCIÓN MÁXIMA: AUTOMATIZACIÓN + OPTIMIZACIÓN\n\n"
        "Recomendación: Eficiencia sin límites\n"
        "✓ Automatización total\n"
        "✓ Workflows complejos\n"
        "✓ Optimización máxima"
    ),
    # Backend combinations
    ("backend", "si_automatizacion", "backend"): (
        "🔧⚙️🚀 SOLUCIÓN ARQUITECTURA: BACKEND + AUTOMATIZACIÓN\n\n"
        "Recomendación: Sistema profesional\n"
        "✓ Backend robusto y seguro\n"
        "✓ Automatización integrada\n"
        "✓ APIs profesionales"
    ),
    ("backend", "si_automatizacion", "no_backend"): (
        "🔧⚙️ SOLUCIÓN FUTURA: BACKEND COMO BASE\n\n"
        "Recomendación: Infraestructura + Preparación\n"
        "✓ Backend moderno\n"
        "✓ Preparado para automatización\n"
        "✓ APIs escalables"
    ),
    ("backend", "no_automatizacion", "backend"): (
        "🔧 SOLUCIÓN TÉCNICA: BACKEND ROBUSTO\n\n"
        "Recomendación: Infraestructura sólida\n"
        "✓ Backend enterprise-grade\n"
        "✓ Base de datos optimizada\n"
        "✓ APIs seguras y rápidas"
    ),
    ("backend", "no_automatizacion", "no_backend"): (
        "🔧 SOLUCIÓN API: BACKEND MODERNO\n\n"
        "Recomendación: Sistemas integrados\n"
        "✓ Backend REST/GraphQL\n"
        "✓ Database profesional\n"
        "✓ Seguridad y autenticación"
    ),
    ("backend", "ambos", "backend"): (
        "🔧⚙️💎 SOLUCIÓN EXTREMA: BACKEND + AUTOMATIZACIÓN TOTAL\n\n"
        "Recomendación: Sistema completo\n"
        "✓ Backend profesional\n"
        "✓ Automatización avanzada\n"
        "✓ Cloud ready"
    ),
    ("backend", "ambos", "no_backend"): (
        "🔧⚙️ SOLUCIÓN INTEGRADA: BACKEND MODERNO\n\n"
        "Recomendación: Sistema flexible\n"
        "✓ Backend escalable\n"
        "✓ Preparado para automatización\n"
        "✓ APIs poderosas"
    ),
    # Analytics combinations
    ("analytics", "si_automatizacion", "backend"): (
        "📊⚙️🔧 SOLUCIÓN DATA-DRIVEN: ANALYTICS + TODO\n\n"
        "Recomendación: Decisiones inteligentes\n"
        "✓ Análisis avanzado de datos\n"
        "✓ Automatización de reportes\n"
        "✓ Backend para datos\n"
        "✓ Dashboard interactivos"
    ),
    ("analytics", "si_automatizacion", "no_backend"): (
        "📊⚙️ SOLUCIÓN INSIGHTS: ANÁLISIS + AUTOMATIZACIÓN\n\n"
        "Recomendación: Datos inteligentes\n"
        "✓ Analytics avanzada\n"
        "✓ Reportes automáticos\n"
        "✓ Dashboards en tiempo real"
    ),
    ("analytics", "no_automatizacion", "backend"): (
        "📊🔧 SOLUCIÓN ML: ANÁLISIS + BACKEND\n\n"
        "Recomendación: Datos + Infraestructura\n"
        "✓ Análisis de datos avanzado\n"
        "✓ Modelos de ML\n"
        "✓ Backend para almacenamiento"
    ),
    ("analytics", "no_automatizacion", "no_backend"): (
        "📊 SOLUCIÓN INSIGHTS: ANÁLISIS DE DATOS\n\n"
        "Recomendación: Inteligencia empresarial\n"
        "✓ Análisis exploratorio\n"
        "✓ Visualizaciones interactivas\n"
        "✓ Reportes ejecutivos"
    ),
    ("analytics", "ambos", "backend"): (
        "📊⚙️🔧💼 SOLUCIÓN PREMIUM: DATA + EVERYTHING\n\n"
        "Recomendación: Empresa data-driven total\n"
        "✓ Analytics avanzada\n"
        "✓ Automatización completa\n"
        "✓ Backend enterprise\n"
        "✓ ML integrado"
    ),
    ("analytics", "ambos", "no_backend"): (
        "📊⚙️ SOLUCIÓN SMART: ANÁLISIS + AUTOMATIZACIÓN\n\n"
        "Recomendación: Datos automáticos\n"
        "✓ Analytics con ML\n"
        "✓ Automatización de insights\n"
        "✓ Dashboards automáticos"
    ),
}

DEFAULT_RECOMMENDATION: Final[str] = (
    "🚀 Solución Combinada: IA + AUTOMATIZACIÓN + INTEGRACIÓN\n\n"
    "Tu empresa podría beneficiarse de:\n"
    "✓ Chatbot inteligente\n"
    "✓ Automatización de procesos\n"
    "✓ Sistema backend integrado\n"
    "✓ Analytics y reportes\n\n"
    "Esto te permitirá:\n"
    "- Mejorar experiencia del cliente\n"
    "- Optimizar operaciones\n"
    "- Escalar sin aumentar costos\n"
    "- Tomar decisiones basadas en datos\n\n"
    "📞 Contáctanos para una consulta personalizada"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user.first_name or ""
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="Visitar CoderNeural", url="https://coderneural.com"
                )
            ],
            [InlineKeyboardButton(text="WhatsApp", url="https://wa.me/5493764983924")],
            [
                InlineKeyboardButton(
                    text="Contacto web", url="https://coderneural.com/#contacto"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Instagram", url="https://www.instagram.com/coderneural"
                )
            ],
        ]
    )
    await update.message.reply_text(
        f"Hola {user}! Soy el bot de CoderNeural. Usa /info, /servicios, /equipo o /contacto.",
        reply_markup=keyboard,
    )


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(INFO)


async def servicios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(SERVICIOS)


async def contacto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="WhatsApp", url="https://wa.me/5493764983924")],
            [InlineKeyboardButton(text="Sitio", url="https://coderneural.com")],
            [
                InlineKeyboardButton(
                    text="Contacto web", url="https://coderneural.com/#contacto"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Instagram", url="https://www.instagram.com/coderneural"
                )
            ],
        ]
    )
    await update.message.reply_text(CONTACTO, reply_markup=keyboard)


async def equipo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(EQUIPO)


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia el quiz de necesidades"""
    # Inicializar respuestas del usuario
    context.user_data["quiz_answers"] = []

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="🤖 Chatbot con IA", callback_data="quiz_chatbot"
                )
            ],
            [InlineKeyboardButton(text="⚙️ Automatización", callback_data="quiz_auto")],
            [InlineKeyboardButton(text="🔧 Backend/API", callback_data="quiz_backend")],
            [
                InlineKeyboardButton(
                    text="📊 Análisis de datos", callback_data="quiz_analytics"
                )
            ],
        ]
    )
    await update.message.reply_text(QUIZ_INTRO, reply_markup=keyboard)


async def quiz_answer1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja primera respuesta del quiz"""
    query = update.callback_query
    await query.answer()

    # Reinicializar respuestas si es necesario (después del reset)
    if "quiz_answers" not in context.user_data:
        context.user_data["quiz_answers"] = []

    # Guardar respuesta
    answer_map = {
        "quiz_chatbot": "chatbot",
        "quiz_auto": "automatizacion",
        "quiz_backend": "backend",
        "quiz_analytics": "analytics",
    }
    context.user_data["quiz_answers"].append(answer_map.get(query.data))

    # Segunda pregunta
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Sí, mucho", callback_data="quiz_yes_auto")],
            [
                InlineKeyboardButton(
                    text="No, deseo backend", callback_data="quiz_no_auto"
                )
            ],
            [InlineKeyboardButton(text="Ambos", callback_data="quiz_both")],
        ]
    )
    await query.edit_message_text(
        text="¿Necesitas automatizar procesos internos?", reply_markup=keyboard
    )


async def quiz_answer2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja segunda respuesta y muestra resultado"""
    query = update.callback_query
    await query.answer()

    # Guardar segunda respuesta
    answer_map = {
        "quiz_yes_auto": "si_automatizacion",
        "quiz_no_auto": "no_automatizacion",
        "quiz_both": "ambos",
    }
    context.user_data["quiz_answers"].append(answer_map.get(query.data))

    # Tercera pregunta
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="Sí, backend robusto", callback_data="quiz_yes_backend"
                )
            ],
            [
                InlineKeyboardButton(
                    text="No, solo aplicación", callback_data="quiz_no_backend"
                )
            ],
        ]
    )
    await query.edit_message_text(
        text="¿Necesitas integración con APIs externas o backend personalizado?",
        reply_markup=keyboard,
    )


async def quiz_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra resultado personalizado del quiz"""
    query = update.callback_query
    await query.answer()

    # Guardar tercera respuesta
    answer_map = {
        "quiz_yes_backend": "backend",
        "quiz_no_backend": "no_backend",
    }
    context.user_data["quiz_answers"].append(answer_map.get(query.data))

    # Generar key para buscar recomendación
    answers_tuple = tuple(context.user_data["quiz_answers"])

    # DEBUG: Mostrar qué combinación buscamos
    LOGGER.info(f"Quiz resultado - Combinación seleccionada: {answers_tuple}")

    recommendation = QUIZ_RECOMMENDATIONS.get(answers_tuple, DEFAULT_RECOMMENDATION)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="📞 Contactar", url="https://wa.me/5493764983924"
                )
            ],
            [InlineKeyboardButton(text="🌐 Más info", url="https://coderneural.com")],
            [InlineKeyboardButton(text="🔙 Volver", callback_data="quiz_reset")],
        ]
    )

    await query.edit_message_text(text=recommendation, reply_markup=keyboard)


async def quiz_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reinicia el quiz"""
    query = update.callback_query
    await query.answer()

    # Reinicializar completamente
    context.user_data["quiz_answers"] = []

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="🤖 Chatbot con IA", callback_data="quiz_chatbot"
                )
            ],
            [InlineKeyboardButton(text="⚙️ Automatización", callback_data="quiz_auto")],
            [InlineKeyboardButton(text="🔧 Backend/API", callback_data="quiz_backend")],
            [
                InlineKeyboardButton(
                    text="📊 Análisis de datos", callback_data="quiz_analytics"
                )
            ],
        ]
    )
    await query.edit_message_text(text=QUIZ_INTRO, reply_markup=keyboard)


async def sugerir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja mensajes de texto con IA de Groq"""
    text = (update.message.text or "").lower()

    # Detectar despedidas
    farewell_tokens = ("chau", "adios", "adiós", "bye", "nos vemos", "hasta luego")
    if any(token in text for token in farewell_tokens):
        await update.message.reply_text(
            "Gracias por pasar. Cuando quieras saber mas usa /info, /servicios, /equipo o /contacto."
        )
        return

    # Rate limiting
    user_id = update.effective_user.id
    limited, seconds_left = is_rate_limited(user_id)
    if limited:
        await update.message.reply_text(
            f"⏳ Demasiados mensajes seguidos. Espera {seconds_left} segundos e intenta de nuevo."
        )
        return

    # Detectar prompt injection
    if has_prompt_injection(update.message.text or ""):
        LOGGER.warning(f"Posible prompt injection del usuario {user_id}")
        await update.message.reply_text(
            "❌ Ese tipo de mensaje no está permitido. Usa /info, /servicios o /contacto."
        )
        return

    # Si no hay cliente de Groq, mostrar opciones genéricas
    if not groq_client:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="Info", url="https://coderneural.com")],
                [
                    InlineKeyboardButton(
                        text="Servicios", url="https://coderneural.com/#servicios"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Equipo", url="https://coderneural.com/#sobre-mi"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Contacto", url="https://coderneural.com/#contacto"
                    )
                ],
            ]
        )
        await update.message.reply_text(
            "Te comparto opciones: usa /info, /servicios, /equipo o /contacto.",
            reply_markup=keyboard,
        )
        return

    # Usar Groq para responder
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": update.message.text},
            ],
            temperature=0.7,
            max_completion_tokens=150,
        )
        respuesta = completion.choices[0].message.content or ""

        # Limitar a 500 caracteres para mantener respuestas concisas
        if len(respuesta) > 500:
            respuesta = respuesta[:497] + "..."

        await update.message.reply_text(respuesta)
    except Exception as e:
        LOGGER.error(f"Error al usar Groq: {e}")
        await update.message.reply_text(
            "Perdón, tuve un problema. Intenta con /info, /servicios, /equipo o /contacto."
        )


async def on_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.warning("Error manejado: %s (update=%s)", context.error, update)


def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    print("Token obtenido:", "Sí" if token else "No")
    if not token:
        raise RuntimeError(
            "Define la variable de entorno TELEGRAM_TOKEN con el token de BotFather"
        )

    application = (
        Application.builder()
        .token(token)
        .get_updates_read_timeout(60)  # Aumentado de 30 a 60
        .get_updates_write_timeout(60)  # Aumentado de 30 a 60
        .get_updates_connect_timeout(60)  # Añadido: timeout de conexión
        .get_updates_pool_timeout(60)  # Añadido: timeout del pool
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("servicios", servicios))
    application.add_handler(CommandHandler("contacto", contacto))
    application.add_handler(CommandHandler("equipo", equipo))
    # application.add_handler(CommandHandler("quiz", quiz))  # Quiz deshabilitado temporalmente

    # Handlers para el quiz
    application.add_handler(
        CallbackQueryHandler(
            quiz_answer1, pattern="^quiz_(chatbot|auto|backend|analytics)$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(quiz_answer2, pattern="^quiz_(yes_auto|no_auto|both)$")
    )
    application.add_handler(
        CallbackQueryHandler(quiz_result, pattern="^quiz_(yes_backend|no_backend)$")
    )
    application.add_handler(CallbackQueryHandler(quiz_reset, pattern="^quiz_reset$"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sugerir))
    application.add_error_handler(on_error)

    LOGGER.info("Bot iniciado. Ctrl+C para salir.")
    application.run_polling()


if __name__ == "__main__":
    main()
