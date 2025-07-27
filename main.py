from typing import Union
from pydantic import BaseModel

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html.j2")


@app.get("/bot/{name}")
def read_bot(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="bot.html.j2",
        context={"bot_name": request.path_params["name"]},
    )


@app.get("/client/{name}")
def read_client(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="client.html.j2",
        context={"bot_name": request.path_params["name"]},
    )


class Bot(BaseModel):
    name: str
    peer_id: str


BOTS: dict[str, Bot] = {}


@app.get("/api/bot/{name}")
def get_bot(name: str, request: Request):
    """
    Get the bot by name
    """
    if name in BOTS:
        return {"result": "okay", "bot": BOTS[name]}
    else:
        return {"result": "not found", "bot": None}


@app.put("/api/bot/{name}")
def update_bot(name: str, request: Request, bot: Bot):
    """
    Update the bot
    """
    if name in BOTS:
        BOTS[name] = bot
    else:
        BOTS[name] = bot
    print(f"Updated bot: {name} with peer_id: {bot.peer_id}")
    return {"result": "okay", "bot": bot}
