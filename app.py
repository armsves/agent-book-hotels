"""Vercel entrypoint. The Hotels.com session comes from HOTELS_COOKIE."""

from agent.main import create_app

app = create_app()
