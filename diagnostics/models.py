from django.db import models
from cameras.models import Camera

class DiagnosticLog(models.Model):
    LEVEL_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Avertissement'),
        ('ERROR', 'Erreur critique'),
    ]

    CATEGORY_CHOICES = [
        ('NETWORK', 'Réseau & Connectivité'),
        ('STREAM', 'Flux Vidéo'),
        ('PTZ', 'Commandes PTZ'),
        ('AUTH', 'Authentification'),
        ('SYSTEM', 'Système'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='STREAM')
    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    message = models.CharField(max_length=255)
    details = models.TextField(blank=True, default="")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Journal Technique"
        verbose_name_plural = "Journaux Techniques"

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] [{self.level}] {self.message}"
