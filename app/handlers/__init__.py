from aiogram import Router

from app.handlers.admin import router as admin_router
from app.handlers.callbacks import (
    fresh_note_callback,
    history_note_callback,
    router as callbacks_router,
)
from app.handlers.fallbacks import router as fallbacks_router
from app.handlers.help import router as help_router
from app.handlers.history import _send_history, history_callback, router as history_router
from app.handlers.menu import router as menu_router
from app.handlers.profile import router as profile_router
from app.handlers.settings import router as settings_router
from app.handlers.start import router as start_router
from app.handlers.system import router as system_router
from app.handlers.voice import router as voice_router


router = Router()
router.include_router(start_router)
router.include_router(system_router)
router.include_router(settings_router)
router.include_router(profile_router)
router.include_router(help_router)
router.include_router(history_router)
router.include_router(admin_router)
router.include_router(voice_router)
router.include_router(callbacks_router)
router.include_router(menu_router)
router.include_router(fallbacks_router)


__all__ = [
    "_send_history",
    "fresh_note_callback",
    "history_callback",
    "history_note_callback",
    "router",
]
