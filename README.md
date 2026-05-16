# Task Board

A multi-channel task manager where tasks can be created, updated, and deleted
from three independent channels that all share the same backend state.

---

## Channels

**Web interface**
A browser-based board that shows tasks in two columns (to do / done). Changes
made in other channels appear automatically via a WebSocket connection, so the
page stays up to date without refreshing.

**Telegram bot**
A bot that accepts commands in any Telegram chat. Useful for quick updates from
a phone or when a browser is not available.

**E-mail**
Commands are sent as an e-mail with the command in the subject line. The backend
polls the inbox, processes the command, and sends a reply with the result. The
mail page in the web interface lets you compose and read those messages directly.

---

## External API

Tasks with a location field show current weather information fetched from
Open-Meteo (https://open-meteo.com). No API key is needed. Results are cached
for 30 minutes per location to avoid unnecessary requests.

---

## Conflict resolution

Every task has a version number that increments on each update. When you send an
update, you include the version you last saw. If another channel updated the task
in the meantime, the backend rejects the request with a 409 response. The web
interface shows a dialog explaining that the task was changed elsewhere and
displays the latest version automatically.

---

## Tech stack

- Backend: Python 3.14, FastAPI, uvicorn
- Telegram: python-telegram-bot
- E-mail: aioimaplib (IMAP), aiosmtplib (SMTP)
- HTTP client: httpx
- Configuration: pydantic-settings
- Frontend: plain HTML, CSS, and JavaScript served by nginx
- Dev mail server: GreenMail (runs in Docker, no external mail account needed)
- Packaging: uv
- Containers: Docker + Docker Compose

---

## Prerequisites

- Docker and Docker Compose
- A Telegram bot token (optional, the app runs without it)

To create a Telegram bot: open a chat with @BotFather on Telegram, send
`/newbot`, follow the steps, and copy the token you receive.

---

## Setup

Copy the defaults file to create your local config:

```
cp .env.defaults .env
```

Open `.env` and fill in your Telegram bot token:

```
TELEGRAM_BOT_TOKEN=your_token_here
```

If you leave the token empty the app starts normally but the Telegram channel
will not be active.

---

## Running the app

```
docker compose up --build
```

Wait until all three containers are running.

To stop:

```
docker compose down
```

---

## Using the channels

### Web interface

Open http://localhost:3000. Click "+ Nieuwe taak" to create a task. Hover over
a task card to see the edit and delete buttons. The dot in the top-right corner
shows whether the WebSocket connection is live.

The mail page (http://localhost:3000/mail.html) lets you send commands by e-mail
and shows the inbox with both your commands and the bot's replies.

### Telegram

Start a chat with your bot and send `/start` to see the available commands:

```
/list              - show all tasks
/add <title>       - create a new task
/done <id>         - mark a task as done (first 8 characters of the ID)
/delete <id>       - permanently delete a task
```

Example:

```
/add Fix the deployment pipeline
/list
/done a1b2c3d4
```

### E-mail

Send an e-mail to `test@taskboard.local` with the command in the subject line.
You can do this from the mail page in the web interface or through the GreenMail
UI at http://localhost:8080.

Available commands (subject line):

```
ADD <title>        - create a new task
DONE <id>          - mark a task as done
DELETE <id>        - permanently delete a task
LIST               - list all tasks
```

The bot replies to the same address the command was sent from. Use the first
8 characters of a task ID for DONE and DELETE commands.

---

## Project structure

```
/
  backend/          Python backend (FastAPI)
    api/            REST endpoints and WebSocket
    channels/       Telegram bot and e-mail poller
    integrations/   Weather API and e-mail client
    services/       Business logic layer
    config.py       Settings loaded from .env
    events.py       Internal event bus
    models.py       Task data model
    store.py        In-memory task store
    main.py         App entry point
  frontend/
    index.html      Task board page
    mail.html       Mail client page
    app.js          Board logic
    mail.js         Mail page logic
    style.css       Shared styles
  docker-compose.yml
  .env.defaults     Default configuration (copy to .env)
```