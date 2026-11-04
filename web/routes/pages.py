from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse


templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
router = APIRouter(tags=["pages"])


@router.get("/app", response_class=HTMLResponse)
def mini_app(request: Request):
    return templates.TemplateResponse(request=request, name="mini_app.html")


@router.get("/games", response_class=HTMLResponse)
def games_page(request: Request):
    return templates.TemplateResponse(request=request, name="games.html")


@router.get("/games/{game_id}/edit", response_class=HTMLResponse)
def edit_game_page(request: Request, game_id: int):
    return templates.TemplateResponse(
        request=request,
        name="game_edit.html",
        context={"game_id": game_id},
    )
