#!/bin/bash

echo "Suppression des migrations..."
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

echo "Suppression de la base de données..."
rm db.sqlite3

echo "Création des nouvelles migrations..."
python manage.py makemigrations

echo "Application des migrations..."
python manage.py migrate

echo "Création du superuser..."
python manage.py createsuperuser

echo "Base de données réinitialisée avec succès!"