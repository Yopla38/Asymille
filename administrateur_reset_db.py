import os
import shutil
from pathlib import Path


def reset_database():
    # Chemin du projet
    base_dir = Path(__file__).resolve().parent

    # Supprimer la base de données SQLite
    db_path = base_dir / 'db.sqlite3'
    if db_path.exists():
        os.remove(db_path)
        print("Base de données supprimée.")

    # Supprimer les fichiers de migration
    apps = ['users']  # Ajoutez ici vos autres applications Django
    for app in apps:
        migrations_dir = base_dir / app / 'migrations'
        if migrations_dir.exists():
            # Préserver __init__.py
            init_file = migrations_dir / '__init__.py'
            init_exists = init_file.exists()
            init_content = None
            if init_exists:
                with open(init_file, 'r') as f:
                    init_content = f.read()

            # Supprimer le dossier migrations
            shutil.rmtree(migrations_dir)
            print(f"Dossier migrations de {app} supprimé.")

            # Recréer le dossier migrations
            migrations_dir.mkdir(exist_ok=True)

            # Recréer __init__.py
            if init_exists:
                with open(init_file, 'w') as f:
                    f.write(init_content or '')

    # Exécuter les commandes Django
    os.system('python manage.py makemigrations')
    os.system('python manage.py migrate')

    print("\nBase de données réinitialisée avec succès!")

    # Proposer de créer un superuser
    create_superuser = input("\nVoulez-vous créer un superuser ? (o/n): ")
    if create_superuser.lower() == 'o':
        os.system('python manage.py createsuperuser')


if __name__ == "__main__":
    print("Attention : Cette opération va supprimer toutes les données de la base de données.")
    confirm = input("Êtes-vous sûr de vouloir continuer ? (o/n): ")

    if confirm.lower() == 'o':
        reset_database()
    else:
        print("Opération annulée.")