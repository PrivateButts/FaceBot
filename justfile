# https://just.systems

default:
    echo 'Hello, world!'


# Get the tw cli from https://github.com/tailwindlabs/tailwindcss/releases/tag/v4.1.11
setup:
    uv sync
    tailwindcss -i ./static/index.css -o ./static/index.built.css

dev:
    uv run fastapi dev --host 0.0.0.0 main.py

serve:
    just dev & \
    just proxy & \
    sleep 5 && just kiosk

proxy:
    tailscale serve --https 8001 http://localhost:8000

kiosk:
    export XDG_SESSION_TYPE=wayland && chromium --disable-notifications --disable-session-crashed-bubble --disable-translate --kiosk 'https://facebot.dachshund-lizard.ts.net:8001/bot'


gen:
    uv run openapi-generator-cli generate \
        -i http://localhost:8000/openapi.json \
        -g javascript \
        -o ./gen/js
    cd ./gen/js && npm install && npm run build
    cp -r ./gen/js/dist/* ./static/js/api/