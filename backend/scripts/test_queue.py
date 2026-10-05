from backend.queue import redis_conn

result = redis_conn.ping()
print(f"Redis ping: {result}")
