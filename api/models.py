import hashlib
import httplib
import logging
import random
import datetime
import json
import time
import requests
import heapq

from collections import deque
from operator import attrgetter
from django.db import models
from django.db.models import Max

__author__ = 'agusx1211'


class User(models.Model):
    user_name = models.CharField(max_length=60)
    spotify_id = models.CharField(max_length=60, primary_key=True)
    email = models.CharField(max_length=255)

    last_token_spotify = models.CharField(max_length=255)
    "expireDateTokenSpotify = models.IntegerField()"

    account_type = models.CharField(max_length=255)

    def __str__(self):
        return self.spotify_id

    def check_token_spotify(self):
        """Returns is the token is valid for Spotify server."""
        import urllib2
        req = urllib2.Request('https://api.spotify.com/v1/me')
        req.add_header('Authorization', 'Bearer ' + self.last_token_spotify)

        try:
            resp = urllib2.urlopen(req)
        except urllib2.HTTPError, e:
            return False
        except urllib2.URLError, e:
            return False
        except httplib.HTTPException, e:
            return False
        except Exception:
            return False

        content = resp.read()

        spotify_data = json.loads(content)
        return spotify_data["id"] == self.spotify_id

    def join_party(self, party):
        if self not in party.members:
            party.members.append(self)

    def left_party(self, party):
        party.members.remove(self)

    def is_authenticated(self, access_token):
        if access_token == self.last_token_spotify:
            return True
        else:
            self.last_token_spotify = access_token
            result = self.check_token_spotify()
            if result:
                self.save()

            return result

    def get_current_luck(self):
        """Devuelve un valor al azar, que sera usado para calcular
        el orden en el que son reproducidas las canciones en la Party"""
        random.seed(self.email + datetime.datetime.now().strftime("%Y-%m-%d"))
        result = random.randint(0, 9223372036854775806)
        return result


class Party(models.Model):
    id = models.AutoField(primary_key=True)

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owner')
    name = models.CharField(max_length=255)
    members = deque()

    secret = models.CharField(max_length=65, null="True")

    def __str__(self):
        return self.name

    @classmethod
    def create_party(cls, _owner, _name):
        p = cls(owner=_owner, name=_name)

        "Se genera el secret"
        p.secret = hashlib.sha256(
            str(random.randint(0,
                               999999999999)) + " :) " + _owner.user_name + _name + _owner.last_token_spotify).hexdigest()

        return p

    def validate_secret(self, secret):
        return self.secret == secret

    def get_next_track(self):
        try:
            member = self.get_next_user()
            track = Track.get_next_track(self, member)
            track.played = True
            track.played_time = time.time()
            track.save()

            self.save()

            return track
        except IndexError:
            return None

    def get_all_tracks_in_order(self):
        all_tracks = []

    def get_next_user(self):
        return self.members.rotate(1)

    @staticmethod
    def get_parties_with(user):
        return Party.objects.filter(members__in=[user])

    @staticmethod
    def get_parties_from(user):
        return Party.objects.filter(owner=[user])

    def get_total_tracks(self):
        return self.get_all_tracks_in_order()

    def get_last_played_track(self):
        try:
            return Track.objects.filter(party=self, played=True).exclude(played_time=None).latest('played_time')
        except Exception:
            return None


class Track(models.Model):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user')
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='party')

    spotify_track_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    duration_ms = models.IntegerField()
    explicit = models.BooleanField()
    preview_url = models.CharField(max_length=255)
    href = models.CharField(max_length=255)
    popularity = models.IntegerField()
    uri = models.CharField(max_length=255)

    artist_name = models.CharField(max_length=1024)

    played = models.BooleanField()
    played_time = models.IntegerField(null=True, blank=True)

    priority = models.IntegerField()

    def __str__(self):
        return self.name

    def get_party_id(self):
        return self.party.id

    def get_user_id(self):
        return self.user.spotify_id

    @staticmethod
    def create_track(_user, _party, _spotify_track_id, _name, _duration_ms, _explicit, _preview_url, _href, _popularity,
                     _uri, _priority, _artist_name):
        t = Track()

        t.user = _user
        t.party = _party
        t.spotify_track_id = _spotify_track_id
        t.name = _name
        t.duration_ms = _duration_ms
        t.explicit = _explicit
        t.review_url = _preview_url
        t.href = _href
        t.popularity = _popularity
        t.priority = _priority
        t.uri = _uri
        t.played = False
        t.artist_name = _artist_name

        return t

    @staticmethod
    def get_all_tracks(party, user):
        return Track.objects.filter(party=party, user=user, played=False)

    @staticmethod
    def get_all_tracks_sorted(party, user):
        return heapq._heapify_max(Track.get_all_tracks(party, user))

    @staticmethod
    def get_next_track(party, user):
        return heapq._heappop_max(Track.get_all_tracks_sorted(party, user))

    @staticmethod
    def del_all_tracks(party, user):
        Track.get_all_tracks(party, user).delete()

    def __cmp__(self, other):
        return cmp(self.priority, other.priority)
