from django.contrib import admin

from .models import Sighting, Pokemon, Trainer

@admin.register(Sighting)
class SightingAdmin(admin.ModelAdmin):
    list_display = ('pokemon_name','google_link','expires_at')
    list_filter = ('pokemon__rare','pokemon__name')
    ordering = ('-expires_at',)

@admin.register(Pokemon)
class PokemonAdmin(admin.ModelAdmin):
    list_display = ('pokedex_id','name','rare')
    list_filter = ('rare',)
    ordering = ('pokedex_id',) 

@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    pass