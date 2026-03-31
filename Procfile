web: python manage.py migrate --noinput && python manage.py seed_schemes --min-count 5000 && gunicorn ai_sakhi.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120
