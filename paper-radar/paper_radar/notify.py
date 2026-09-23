"""Optional digests. Each channel turns on only when its environment variables are set.

* Slack    SLACK_WEBHOOK_URL
* Discord  DISCORD_WEBHOOK_URL
* Telegram TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
* Email    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, EMAIL_TO, EMAIL_FROM (optional)
"""

from __future__ import annotations

import html
import os
import smtplib
from email.message import EmailMessage
from typing import Callable

from .config import Config
from .http import post_json
from .scoring import Decision, rank


def _lines(config: Config, day: str, decisions: list[Decision], markdown: str) -> list[str]:
    ranked = rank(decisions)
    must = [d for d in ranked if d.band == "must_read"]
    maybe = [d for d in ranked if d.band == "maybe"]
    head = f"{config.title} · {day}: read {len(decisions):,} papers → {len(must) + len(maybe)} shortlisted → {len(must)} must-read"
    lines = [head]
    for d in must[:10]:
        title = d.paper.title
        if markdown == "slack":
            lines.append(f"• {round(d.relevance * 100)}% <{d.paper.url}|{title}>")
        elif markdown == "html":
            lines.append(f'• {round(d.relevance * 100)}% <a href="{html.escape(d.paper.url)}">{html.escape(title)}</a>')
        else:
            lines.append(f"• {round(d.relevance * 100)}% {title} {d.paper.url}")
        if d.summary:
            lines.append(f"   {html.escape(d.summary) if markdown == 'html' else d.summary}")
    if config.output.site_url:
        lines.append(f"Full list: {config.output.site_url}")
    return lines


def send_all(
    config: Config,
    day: str,
    decisions: list[Decision],
    *,
    env: dict[str, str] | None = None,
    poster: Callable[..., object] = post_json,
    log: Callable[[str], None] = print,
) -> list[str]:
    env = dict(os.environ if env is None else env)
    if not any(d.band == "must_read" for d in decisions) and env.get("NOTIFY_ONLY_IF_MUST_READ") == "1":
        return []
    sent: list[str] = []

    def attempt(name: str, fn: Callable[[], object]) -> None:
        try:
            fn()
            sent.append(name)
        except Exception as error:  # notifications never fail the run
            log(f"  ! {name} notification failed: {error}")

    if env.get("SLACK_WEBHOOK_URL"):
        text = "\n".join(_lines(config, day, decisions, "slack"))
        attempt("slack", lambda: poster(env["SLACK_WEBHOOK_URL"], {"text": text}))
    if env.get("DISCORD_WEBHOOK_URL"):
        text = "\n".join(_lines(config, day, decisions, "plain"))[:1990]
        attempt("discord", lambda: poster(env["DISCORD_WEBHOOK_URL"], {"content": text}))
    if env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"):
        text = "\n".join(_lines(config, day, decisions, "html"))[:4000]
        url = f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/sendMessage"
        payload = {"chat_id": env["TELEGRAM_CHAT_ID"], "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        attempt("telegram", lambda: poster(url, payload))
    if env.get("SMTP_HOST") and env.get("EMAIL_TO"):
        attempt("email", lambda: _email(config, day, decisions, env))
    return sent


def _email(config: Config, day: str, decisions: list[Decision], env: dict[str, str]) -> None:
    lines = _lines(config, day, decisions, "html")
    message = EmailMessage()
    message["Subject"] = lines[0]
    message["From"] = env.get("EMAIL_FROM") or env.get("SMTP_USER") or "paper-radar@localhost"
    message["To"] = env["EMAIL_TO"]
    message.set_content("\n".join(_lines(config, day, decisions, "plain")))
    message.add_alternative("<br>".join(lines), subtype="html")
    port = int(env.get("SMTP_PORT") or 587)
    with smtplib.SMTP(env["SMTP_HOST"], port, timeout=30) as smtp:
        if port != 25:
            smtp.starttls()
        if env.get("SMTP_USER"):
            smtp.login(env["SMTP_USER"], env.get("SMTP_PASSWORD", ""))
        smtp.send_message(message)
