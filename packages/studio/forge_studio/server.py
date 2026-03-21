"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title="Forge Studio", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from forge_studio.routes.upload import router as upload_router
    from forge_studio.routes.plugins import router as plugins_router
    app.include_router(upload_router, prefix="/api")
    app.include_router(plugins_router, prefix="/api")

    # Register plugins
    from forge_studio.plugins import register_plugin
    from forge_studio.plugins.script_forge_plugin import ScriptForgePlugin
    register_plugin(ScriptForgePlugin())

    return app
