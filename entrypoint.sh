#!/bin/sh
set -e

python manage.py migrate --noinput

python manage.py shell -c "
from accounts.models import User
if not User.objects.filter(is_superuser=False).exists():
    import subprocess
    subprocess.run(['python', 'manage.py', 'seed_data'], check=True)
if not User.objects.filter(email='admin@bfn.test').exists():
    User.objects.create_superuser(
        email='admin@bfn.test', password='Admin99!',
        first_name='Admin', last_name='User'
    )
    print('Admin created: admin@bfn.test / Admin99!')
"

if [ "${DEBUG}" = "True" ]; then
    exec python manage.py runserver 0.0.0.0:8000
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
