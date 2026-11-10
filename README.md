# Telegram Signal Bot — Railway Deployment

This repository packages the supplied `AI.py` Telegram bot for Railway. Existing
signal, indicator, candle, chart and Telegram handler logic is retained; the
Telegram token is read from an environment variable.

## Deploy on Railway

1. Create a GitHub repository and upload/push **all files in this folder**.
2. In Railway, create a project and choose **Deploy from GitHub repo**.
3. Open the deployed service → **Variables** and add:
   - `BOT_TOKEN` = your Telegram BotFather token
4. Deploy/redeploy the service. Check **Deployments → View Logs**.
5. Open your Telegram bot and send `/start`.

The process starts the bot using Telegram long polling. Do not run a second
instance with the same token at the same time.

## Optional variables

- `TELEGRAM_BOT_TOKEN`: fallback alias if `BOT_TOKEN` is not set.
- `BOT_TOKEN` always takes priority over a token in `bot_config.json`.

## Important notes

- A Telegram token was embedded in the uploaded source file. It has been
  removed from this repository. **Revoke/regenerate that exposed token with
  @BotFather before deployment**, then use only the new token as Railway's
  `BOT_TOKEN` variable.
- The bot uses the configured candle API endpoint from its existing source.
  Railway deployment does not guarantee that this external API is reachable
  or currently operating.
- Railway's normal container filesystem may be ephemeral. The bot stores
  `bot_config.json`, `users.json`, `users_data.json`, and `user_stats.json`
  locally. Attach a Railway Volume and configure the service to use a persistent
  mount if you need these JSON files to survive redeploys/restarts; otherwise
  data may be lost.
- Do not commit `.env`, `bot_config.json`, user data, or real bot tokens.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export BOT_TOKEN="your-new-token"  # Windows PowerShell: $env:BOT_TOKEN="your-new-token"
python AI.py
```
