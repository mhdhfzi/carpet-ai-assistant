"""Serving the built frontend, with cache headers that are safe across deploys."""

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Vite puts a content hash in every file name under assets/, so a changed file gets a new
# name and these can be cached for good.
IMMUTABLE = "public, max-age=31536000, immutable"
# Pages and widget.js keep the same name across deploys: browsers must check for a new
# version every time (a cheap 304 when nothing changed), or visitors see stale pages.
REVALIDATE = "no-cache"


class FrontendFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            hashed = path.replace("\\", "/").startswith("assets/")
            response.headers["Cache-Control"] = IMMUTABLE if hashed else REVALIDATE
        return response
