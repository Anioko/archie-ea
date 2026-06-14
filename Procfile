web: gunicorn -c gunicorn.conf.py manage:app
worker: celery -A app.tasks worker --loglevel=info --concurrency=2
