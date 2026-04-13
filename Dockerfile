FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "portfolio_chat_agent.app:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "src"]
