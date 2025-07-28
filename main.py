from typing import Union, Optional
from pydantic import BaseModel

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from servo_controller import get_servo_controller, cleanup_servo_controller
import logging
import atexit
import os


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize servo controller on startup
simulate = os.getenv("SIMULATE_SERVO", "true").lower() == "true"
servo_controller = get_servo_controller(simulate=simulate)

# Register cleanup function
atexit.register(cleanup_servo_controller)


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


class PanTilt(BaseModel):
    pan: float
    tilt: float


@app.post("/api/bot/{name}/look")
def look_bot(name: str, request: Request, pan_tilt: PanTilt):
    """
    Rotate the bot's camera servos to look at a specific direction
    """
    if name not in BOTS:
        raise HTTPException(status_code=404, detail="Bot not found")

    servo_controller.set_pan(round(pan_tilt.pan))
    servo_controller.set_tilt(round(pan_tilt.tilt))

    return {"result": "okay", "message": f"Bot {name} moved successfully"}


# Servo Control Models
class ServoPosition(BaseModel):
    pan: Optional[int] = None
    tilt: Optional[int] = None
    smooth: bool = False


class ServoMovement(BaseModel):
    direction: str  # "left", "right", "up", "down"
    step: Optional[int] = None


# Servo Control API Endpoints
@app.get("/api/servo/position")
def get_servo_position():
    """
    Get current servo positions
    """
    try:
        position = servo_controller.get_position()
        return {"result": "okay", "position": position}
    except Exception as e:
        logging.error(f"Failed to get servo position: {e}")
        raise HTTPException(status_code=500, detail="Failed to get servo position")


@app.post("/api/servo/position")
def set_servo_position(position: ServoPosition):
    """
    Set servo to absolute position
    """
    try:
        success = servo_controller.move_to_position(
            pan=position.pan, tilt=position.tilt, smooth=position.smooth
        )

        if success:
            current_position = servo_controller.get_position()
            return {"result": "okay", "position": current_position}
        else:
            raise HTTPException(status_code=400, detail="Failed to move servos")

    except Exception as e:
        logging.error(f"Failed to set servo position: {e}")
        raise HTTPException(status_code=500, detail="Failed to set servo position")


@app.post("/api/servo/move")
def move_servo(movement: ServoMovement):
    """
    Move servo in a specific direction
    """
    try:
        success = False
        direction = movement.direction.lower()

        if direction == "left":
            success = servo_controller.pan_left(movement.step)
        elif direction == "right":
            success = servo_controller.pan_right(movement.step)
        elif direction == "up":
            success = servo_controller.tilt_up(movement.step)
        elif direction == "down":
            success = servo_controller.tilt_down(movement.step)
        else:
            raise HTTPException(
                status_code=400, detail="Invalid direction. Use: left, right, up, down"
            )

        if success:
            current_position = servo_controller.get_position()
            return {"result": "okay", "position": current_position}
        else:
            raise HTTPException(status_code=400, detail="Failed to move servo")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to move servo: {e}")
        raise HTTPException(status_code=500, detail="Failed to move servo")


@app.post("/api/servo/reset")
def reset_servo_position():
    """
    Reset servos to center position (90 degrees)
    """
    try:
        servo_controller.reset_position()
        position = servo_controller.get_position()
        return {"result": "okay", "position": position}
    except Exception as e:
        logging.error(f"Failed to reset servo position: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset servo position")


@app.get("/api/servo/limits")
def get_servo_limits():
    """
    Get servo movement limits and configuration
    """
    return {
        "result": "okay",
        "limits": {
            "pan": {
                "min": servo_controller.config.SERVO_DOWN_MIN,
                "max": servo_controller.config.SERVO_DOWN_MAX,
                "channel": servo_controller.config.SERVO_DOWN_CH,
            },
            "tilt": {
                "min": servo_controller.config.SERVO_UP_MIN,
                "max": servo_controller.config.SERVO_UP_MAX,
                "channel": servo_controller.config.SERVO_UP_CH,
            },
            "step_size": servo_controller.config.STEP,
            "step_delay": servo_controller.config.STEP_DELAY,
        },
    }
