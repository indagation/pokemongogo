from django.shortcuts import render
from django.http import HttpResponse
from poke_tracker import *
from tracker.models import *
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from datetime import datetime, timedelta
import html

def get_trainer_access_token(trainer):
    access_token = get_access_token(trainer.login_type, trainer.username, trainer.password)
    if access_token is not None:
        print 'Access token received: {}'.format(access_token)
        trainer.access_token = access_token
        trainer.save()
    return access_token

def attempt_login(current_user):
    try:
        trainer = Trainer.objects.get(user = current_user)        
        access_token = get_trainer_access_token(trainer)

        if access_token is not None:
            api_endpoint = get_api_endpoint(trainer.login_type, access_token)
            if api_endpoint is not None:
                print 'Api endpoint received: {}'.format(access_token)

                trainer.api_endpoint = api_endpoint
                trainer.save()

                profile_response = retrying_get_profile(trainer.login_type, trainer.access_token, trainer.api_endpoint, None)

                if profile_response is None or not profile_response.payload:
                    raise Exception('Could not get profile')

                print '[+] Login successful'

                payload = profile_response.payload[0]
                profile = pokemon_pb2.ResponseEnvelop.ProfilePayload()
                profile.ParseFromString(payload)
                print '[+] Username: {}'.format(profile.profile.username)

                creation_time = datetime.fromtimestamp(int(profile.profile.creation_time) / 1000)
                print '[+] You started playing Pokemon Go on: {}'.format(creation_time.strftime('%Y-%m-%d %H:%M:%S'))

                for curr in profile.profile.currency:
                    print '[+] {}: {}'.format(curr.type, curr.amount)
                return profile_response
    except ObjectDoesNotExist:
        print "We couldn't find your Trainer credentials for PokemonGoGo"        
    else:
        print "You need to setup your Trainer credentials before using PokemonGoGo"
        return None

def search_grids(scan, profile_response):
    steplimit = int(scan.step)
    trainer = scan.trainer
    pokemonsJSON = json.load(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'pokemon.json')))
    print "Going to run step {}".format(steplimit)

    pos = 1
    x = 0
    y = 0
    dx = 0
    dy = -1
    steplimit2 = steplimit**2
    count = 0
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes = 2)
    origin_lat = float(trainer.latitude)
    origin_lon = float(trainer.longitude)

    for step in range(steplimit2):
        #starting at 0 index
        debug('looping: step {} of {}'.format((step+1), steplimit**2))
        #debug('steplimit: {} x: {} y: {} pos: {} dx: {} dy {}'.format(steplimit2, x, y, pos, dx, dy))
        # Scan location math
        if -steplimit2 / 2 < x <= steplimit2 / 2 and -steplimit2 / 2 < y <= steplimit2 / 2:
            current_latitude = x * 0.0025 + origin_lat
            current_longitude = y * 0.0025 + origin_lon
            set_location_coords(current_latitude, current_longitude, 0)
        if x == y or x < 0 and x == -y or x > 0 and x == 1 - y:
            (dx, dy) = (-dy, dx)

        (x, y) = (x + dx, y + dy)

        cutoff = False
        print('Checking for grid at location {} {}'.format(current_latitude, current_longitude))
        try:
            grid = Grid.objects.get(latitude = current_latitude, longitude = current_longitude)
            # print('Grid exists: {}'.format(grid.id))
            # print('Last scanned at: {}'.format(grid.last_scanned_at))
            # print('Cutoff time: {}'.format(cutoff_time))
            if grid.last_scanned_at > cutoff_time:
                cutoff = True
        except ObjectDoesNotExist:
            print "Creating a new grid."
            grid = Grid(latitude = current_latitude, longitude = current_longitude)
            grid.save()

        if cutoff:
            print "Grid has been scanned within the last 2 minutes"
        else:
            grid.last_scanned_at = datetime.now(timezone.utc)
            grid.save()
            print('[+] Searching for Pokemon at location {} {}'.format(current_latitude, current_longitude))
            origin = LatLng.from_degrees(current_latitude, current_longitude)
            step_lat = current_latitude
            step_long = current_longitude
            parent = CellId.from_lat_lng(LatLng.from_degrees(current_latitude, current_longitude)).parent(15)
            h = get_heartbeat(trainer.login_type, trainer.api_endpoint, trainer.access_token, profile_response)
            hs = [h]
            seen = {}

            for child in parent.children():
                latlng = LatLng.from_point(Cell(child).get_center())
                set_location_coords(latlng.lat().degrees, latlng.lng().degrees, 0)
                hs.append(get_heartbeat(trainer.login_type, trainer.api_endpoint, trainer.access_token, profile_response))
            set_location_coords(step_lat, step_long, 0)
            visible = []

            for hh in hs:
                try:
                    for cell in hh.cells:
                        for wild in cell.WildPokemon:
                            hash = wild.SpawnPointId;
                            if hash not in seen.keys() or (seen[hash].TimeTillHiddenMs <= wild.TimeTillHiddenMs):
                                visible.append(wild)    
                            seen[hash] = wild.TimeTillHiddenMs
                except AttributeError:
                    break

            for poke in visible:
                disappear_timestamp = time.time() + poke.TimeTillHiddenMs / 1000
                pokeid = str(poke.pokemon.PokemonId)
                pokename = pokemonsJSON[pokeid]
                spawn_point_id = poke.SpawnPointId
                
                print "Found a {}".format(pokename)
                try:
                    pokemon = Pokemon.objects.get(pokedex_id = poke.pokemon.PokemonId)
                except ObjectDoesNotExist:
                    pokemon = Pokemon(pokedex_id = poke.pokemon.PokemonId, name = pokename)
                    pokemon.save()
                # print pokemon.pokedex_id
                # print spawn_point_id
                expires_at = datetime.fromtimestamp(disappear_timestamp, timezone.utc)
                try:
                    sighting = Sighting.objects.get(spawn_point_id = spawn_point_id )
                    # print "Sighting already exists: {}".format(spawn_point_id, pokemon = pokemon, expires_at = expires_at)
                    # sighting = Sighting.objects.get(spawn_point_id = spawn_point_id, pokemon = pokemon, expires_at = expires_at )
                except ObjectDoesNotExist:
                    # print "Try creating a new sighting"
                    sighting = Sighting(spawn_point_id = spawn_point_id, pokemon = pokemon, latitude = poke.Latitude, longitude = poke.Longitude, expires_at = expires_at )
                    sighting.save()
                # print sighting.id
            count += 1;
            if count >= 10:
                break

        print('Completed: ' + str(
            ((step+1) + pos * .25 - .25) / (steplimit2) * 100) + '%')

    global NEXT_LAT, NEXT_LONG
    if (NEXT_LAT and NEXT_LONG and
            (NEXT_LAT != FLOAT_LAT or NEXT_LONG != FLOAT_LONG)):
        print('Update to next location %f, %f' % (NEXT_LAT, NEXT_LONG))
        set_location_coords(NEXT_LAT, NEXT_LONG, 0)
        NEXT_LAT = 0
        NEXT_LONG = 0
    else:
        set_location_coords(origin_lat, origin_lon, 0) 

def get_pokemarkers(trainer):
    sightings = Sighting.objects.filter(expires_at__gte = datetime.now(timezone.utc), pokemon__rare = True, latitude__gte = trainer.min_latitude(), latitude__lte = trainer.max_latitude(), longitude__gte = trainer.min_longitude(), longitude__lte = trainer.max_longitude())

    pokeMarkers = [{
        'icon': icons.dots.red,
        'lat': trainer.latitude,
        'lng': trainer.longitude,
        'infobox': "Start position",
        'type': 'custom',
        'key': 'start-position',
        'icon': '/static/tracker/forts/Pstop.png',
        'disappear_time': -1
    }]

    for sighting in sightings:
        print sighting
        pokemon = {}
        pokemon["id"] = sighting.pokemon.pokedex_id
        pokemon["disappear_time"] = sighting.expires_at
        pokemon["disappear_time_formatted"] = sighting.expires_at.strftime("%H:%M:%S %Z")
        pokemon["lat"] = sighting.latitude
        pokemon["lng"] = sighting.longitude
        pokemon["name"] = sighting.pokemon.name

        LABEL_TMPL = u'''
<div><b>{name}</b><span> - </span><small><a href='http://www.pokemon.com/us/pokedex/{id}' target='_blank' title='View in Pokedex'>#{id}</a></small></div>
<div>Disappears at - {disappear_time_formatted} <span class='label-countdown' disappears-at='{disappear_time}'></span></div>
<div><a href='https://www.google.com/maps/dir/Current+Location/{lat},{lng}' target='_blank' title='View in Maps'>Get Directions</a></div>
'''
        label = LABEL_TMPL.format(**pokemon)
        #  NOTE: `infobox` field doesn't render multiple line string in frontend
        label = label.replace('\n', '')

        pokeMarkers.append({
            'type': 'pokemon',
            'key': pokemon["id"],
            'disappear_time': pokemon['disappear_time'],
            'icon': '/static/tracker/icons/%d.png' % pokemon["id"],
            'lat': pokemon["lat"],
            'lng': pokemon["lng"],
            'infobox': label
        })
    return pokeMarkers

def index(request):
    if request.user.is_authenticated():
        current_user = request.user
        trainer = current_user.trainer
        profile_response = attempt_login(current_user)
        if trainer is None:
            return HttpResponse("You need to register a trainer account before using PokemonGoGo.")
    else:
        return HttpResponse("You need to login before using PokemonGoGo.")

    pokeMarkers = get_pokemarkers(trainer)

    context = {'pokeMarkers': pokeMarkers, 'origin_lat': trainer.latitude, 'origin_lon': trainer.longitude, 'login_status': True, 'trainer': trainer}
    return render(request, 'tracker/fullmap.html', context)

def set_trainer_location(request):
    current_user = request.user
    try:
        trainer = Trainer.objects.get(user = current_user)    
        lat_lon = request.GET.get('q', '')
        if lat_lon != "":
            origin_lat, origin_lon = [float(x) for x in lat_lon.split(",")]
        else:
            origin_lat = 42.3732099
            origin_lon = -71.1539969
        trainer.latitude = origin_lat
        trainer.longitude = origin_lon
        trainer.save()
    except ObjectDoesNotExist:
        print "We couldn't find your Trainer credentials for PokemonGoGo"        


def scan(request):
    if request.user.is_authenticated():
        current_user = request.user    
        trainer = current_user.trainer
        profile_response = attempt_login(current_user)
        step = request.GET.get('step', '')
        if step != "":
            cutoff_time = datetime.now(timezone.utc) - timedelta(seconds = 30)
            try:
                scan = Scan.objects.get(trainer = trainer, created_at__gte = cutoff_time)
                return HttpResponse("You are only allowed to scan every 30 seconds")
            except ObjectDoesNotExist:
                scan = Scan(trainer = trainer, latitude = trainer.latitude, longitude = trainer.longitude, step = step)
                scan.save()
                search_grids(scan, profile_response)
                return HttpResponse("Your scan has been completed")
        else:
            return HttpResponse("You must enter a distance to scan")
    else:
        return HttpResponse("You need to login before using PokemonGoGo.")     




