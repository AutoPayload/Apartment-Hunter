FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=America/Costa_Rica
WORKDIR /app

COPY scraper/pyproject.toml ./
COPY scraper/hunter ./hunter
RUN pip install --no-cache-dir .

# Optional: JavaScript rendering for adapters with needs_js = True.
ARG WITH_PLAYWRIGHT=0
RUN if [ "$WITH_PLAYWRIGHT" = "1" ]; then \
      pip install --no-cache-dir "playwright>=1.45" && playwright install --with-deps chromium; \
    fi

RUN useradd --create-home hunter
USER hunter
WORKDIR /home/hunter
ENTRYPOINT ["hunter"]
CMD ["schedule"]
