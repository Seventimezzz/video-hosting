from redis import Redis
from rq import Queue

from backend.config import settings

redis_conn = Redis.from_url(settings.redis_url)
video_queue = Queue("video_processing", connection=redis_conn)
