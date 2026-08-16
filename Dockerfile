FROM python:3.11-slim

WORKDIR /app

# Dépendances système minimales (utile si scikit-learn/xgboost sont activés plus tard)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY training ./training

EXPOSE 8001

# Un seul worker par conteneur : on scale horizontalement via docker-compose/replicas
# plutôt qu'avec plusieurs workers uvicorn dans le même conteneur.
# Port 8001 choisi pour matcher ML_SERVICE_URL déjà codé dans le docker-compose
# du backend NestJS (http://ml-service:8001).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
