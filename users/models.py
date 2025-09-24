from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
import stripe



class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)


class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stripe_payment_id = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)


class FitSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Données de base
    expression = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict, verbose_name="Données brutes")  # Pour stocker les données du tableau
    data = models.JSONField(default=dict)  # Pour stocker les données traitées
    fit_report = models.TextField(blank=True)

    # Configuration du graphique
    plot_config = models.JSONField(default=dict)
    custom_objects = models.JSONField(default=list)
    template = models.JSONField(default=dict)

    # Configuration supplémentaire
    active_page = models.IntegerField(default=0)
    column_headers = models.JSONField(default=list)  # Pour stocker les en-têtes des colonnes

    # Sauvegarde des intervales de FIT
    fit_range = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Session {self.name or self.id} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"

    def save_data_state(self, data_dict):
        """Sauvegarde l'état complet des données"""
        if isinstance(data_dict, dict):
            self.raw_data = data_dict
            self.column_headers = data_dict.get('headers', ['X', 'Y'])
            if 'active_page' in data_dict:
                self.active_page = data_dict['active_page']
        self.save()

    def get_data_state(self):
        """Récupère l'état complet des données"""
        return {
            'headers': self.column_headers,
            'pages': self.raw_data.get('pages', []),
            'active_page': self.active_page
        }