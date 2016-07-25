from django.db import models
from django.contrib.auth.models import User
from django.utils.html import format_html
import decimal

class Pokemon(models.Model):
    pokedex_id = models.IntegerField()
    name = models.CharField(max_length=30)
    rare = models.BooleanField(default = True)

class Sighting(models.Model):
    pokemon = models.ForeignKey(Pokemon, on_delete=models.CASCADE)
    spawn_point_id = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    sighted_at = models.DateTimeField(auto_now_add=True, blank=True)
    expires_at = models.DateTimeField(blank=True)
    def pokemon_name(self):
        return self.pokemon.name
    pokemon_name.short_description = 'Pokemon Name'
    def google_link(self):
        return format_html(
            '<a href="http://maps.google.com/?q={},{}" target="_blank">Go to pokemon</a>',
            self.latitude,
            self.longitude
        )    
    google_link.short_description = 'Google Map'

class Grid(models.Model):
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    last_scanned_at = models.DateTimeField(auto_now=True, blank=True)

class Trainer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    login_type = models.CharField(max_length=10)
    username = models.CharField(max_length=30)
    password = models.CharField(max_length=30)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    access_token = models.CharField(max_length=200)
    api_endpoint = models.CharField(max_length=200)
    def min_latitude(self):
        return float(self.latitude) - 0.01
    def max_latitude(self):
        return float(self.latitude) + 0.01
    def min_longitude(self):
        return float(self.longitude) - 0.01
    def max_longitude(self):
        return float(self.longitude) + 0.01

class Scan(models.Model):
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    step = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True, blank=True)       
   