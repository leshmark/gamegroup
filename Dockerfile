# Docker file for a simple unauthenticated FastAPI app

FROM python:3.10

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./backend /app/

CMD ["fastapi", "run", "main.py", "--port", "80"]