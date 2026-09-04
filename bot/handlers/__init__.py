import sys
from aiogram import Router

sys.stdout.write("HANDLERS: importing start\n"); sys.stdout.flush()
from bot.handlers import start
sys.stdout.write("HANDLERS: importing idea\n"); sys.stdout.flush()
from bot.handlers import idea
sys.stdout.write("HANDLERS: importing voice\n"); sys.stdout.flush()
from bot.handlers import voice
sys.stdout.write("HANDLERS: importing review\n"); sys.stdout.flush()
from bot.handlers import review
sys.stdout.write("HANDLERS: importing stats\n"); sys.stdout.flush()
from bot.handlers import stats
sys.stdout.write("HANDLERS: importing rubric\n"); sys.stdout.flush()
from bot.handlers import rubric
sys.stdout.write("HANDLERS: importing plan\n"); sys.stdout.flush()
from bot.handlers import plan
sys.stdout.write("HANDLERS: importing month_plan\n"); sys.stdout.flush()
from bot.handlers import month_plan
sys.stdout.write("HANDLERS: importing photo_post\n"); sys.stdout.flush()
from bot.handlers import photo_post
sys.stdout.write("HANDLERS: all done\n"); sys.stdout.flush()


def setup_routers() -> Router:
    root = Router()
    root.include_router(start.router)
    root.include_router(idea.router)
    root.include_router(voice.router)
    root.include_router(review.router)
    root.include_router(stats.router)
    root.include_router(rubric.router)
    root.include_router(plan.router)
    root.include_router(month_plan.router)
    root.include_router(photo_post.router)
    return root
