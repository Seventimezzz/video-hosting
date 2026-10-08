# Один образ для трёх ролей: api (uvicorn), worker (rq) и migrate (alembic +
# init_storage). Чем именно станет контейнер, решает command в docker-compose.yml.
FROM python:3.12-slim

# ffmpeg нужен воркеру для транскодирования. Ставим в отдельном слое до кода:
# он меняется редко и останется в кэше сборки.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# uv берём бинарником из официального образа, а не через pip.
COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /usr/local/bin/uv

WORKDIR /app

# Байткод компилируем при сборке (быстрее старт), пакеты копируем, а не линкуем
# (кэш uv и .venv лежат на разных файловых системах внутри сборки).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Сначала только зависимости. Пока pyproject.toml и uv.lock не менялись, этот
# слой берётся из кэша, и правка кода не вызывает переустановку пакетов.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Потом код и сам проект.
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

# Команды uvicorn/rq/alembic/python берутся из .venv без "uv run".
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
