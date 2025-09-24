Installez Django et Django REST Framework :

pip install django djangorestframework psycopg2-binary

Créez un projet Django :

django-admin startproject my_saas_app .

Démarrez une application principale pour la gestion des utilisateurs et des profils :

python manage.py startapp users

sudo apt install postgresql postgresql-contrib


sudo -u postgres psql

CREATE DATABASE my_saas_db;
CREATE USER your_user WITH PASSWORD 'your_password';
ALTER ROLE your_user SET client_encoding TO 'utf8';
ALTER ROLE your_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE your_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE my_saas_db TO your_user;

\q



Pour juste supprimer : 
DROP DATABASE nom_de_votre_base;
CREATE DATABASE nom_de_votre_base;
\q

puis
# Supprimer tous les fichiers de migration (sauf __init__.py)
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

# Recréer les migrations
python manage.py makemigrations users
python manage.py makemigrations

# Appliquer les migrations
python manage.py migrate

# Créer un superuser
python manage.py createsuperuser

sudo -u postgres psql

-- Dans psql:
ALTER USER votre_utilisateur CREATEDB;
ALTER DATABASE nom_de_votre_base OWNER TO votre_utilisateur;
\q




python manage.py runserver
python manage.py migrate
