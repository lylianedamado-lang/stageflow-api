import logging

from fastapi import FastAPI

from app.api.routes import applications, auth, offers, users
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.middlewares.request_id import RequestIDMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "API interne de gestion des offres de stage, des candidatures "
        "et des validations pédagogiques du Master DSIA."
    ),
    openapi_tags=[
        {"name": "auth", "description": "Inscription et connexion."},
        {"name": "users", "description": "Profil et administration des comptes."},
        {"name": "offers", "description": "Cycle de vie des offres de stage."},
        {"name": "applications", "description": "Dépôt et arbitrage des candidatures."},
        {"name": "health", "description": "Supervision."},
    ],
)

# L'ordre compte : le dernier ajoute est le premier éxécuté.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(offers.router)
app.include_router(applications.router)


@app.get("/health", tags=["health"], summary="Sonde de disponibilité de l'API.")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
