"""Fans-text lane (fans lane): YouTube + Anime2You. Re-exports lane entry points."""
from nga.fans.anime2you import run as run_anime2you
from nga.fans.youtube import run as run_youtube

__all__ = ["run_youtube", "run_anime2you"]
