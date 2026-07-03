from fastapi import APIRouter, Depends, Request

from dml_bot.api.deps import ViewerContext, get_viewer
from dml_bot.api.templating import templates

router = APIRouter()


@router.get("/")
async def shell(request: Request):
    return templates.TemplateResponse(request, "shell.html", {})


@router.get("/api/home")
async def home(request: Request, viewer: ViewerContext = Depends(get_viewer)):
    if viewer.db_user is None and not viewer.is_admin:
        return templates.TemplateResponse(request, "partials/unregistered.html", {"viewer": viewer})
    return templates.TemplateResponse(request, "partials/home.html", {"viewer": viewer})
