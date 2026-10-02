#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python create_admin.py
python manage.py shell -c "from employees.demo import generate_demo_data; print(generate_demo_data(10, 4, 40, 7))"
