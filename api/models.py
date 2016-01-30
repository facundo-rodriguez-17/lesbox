from __future__ import unicode_literals
import hashlib
import httplib
import logging
from operator import attrgetter
import random
import datetime
from django.db import models
import json
import time
import requests

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
        auth_header = 'Bearer %s' % self.last_token_spotify
        res = requests.get('https://api.spotify.com/v1/me',
                           headers={"HTTP_AUTHORIZATION": auth_header})
        if res.status_code == 200:
            spotify_data = json.loads(res.content)
            return spotify_data["id"] == self.spotifyId
        else:
            return False

    def join_party(self, party):
        party.members.add(self)

    def left_party(self, party):
        party.members.remove(self)

    def is_authenticated(self, access_token):
        if access_token == self.last_token_spotify:
            return True
        else:
            return self.check_token_spotify()

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
    members = models.ManyToManyField(User, related_name='members')

    current_user = models.ForeignKey(User, related_name='current_user', null="True")

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

    def get_members_in_order(self):
        return sorted(self.members.all(), key=lambda t: t.get_current_luck())

    def get_members_in_order_next_user(self):
        next_member = self.get_next_user()

        members_sorted = self.get_members_in_order()

        def get_distance_to(user):
            distance = members_sorted.index(user) - members_sorted.index(next_member)
            if distance < 0:
                distance += len(members_sorted)

            return distance

        return sorted(members_sorted, key=lambda t: get_distance_to(t))

    def get_next_track(self):
        try:
            track = self.get_all_tracks_in_order()[0]
            track.played = True
            track.save()
            self.current_user = self.get_next_user()
            self.save()
            return track
        except IndexError:
            return None

    def get_all_tracks_in_order(self):
        members = self.get_members_in_order_next_user()
        members_tracks = dict()

        next_user = self.get_next_user()

        biggest_playlist = 1

        result_tracks = []

        for member in members:
            members_tracks[member] = Track.get_all_tracks_sorted(self, member)
            if len(members_tracks[member]) > biggest_playlist:
                biggest_playlist = len(members_tracks[member]) + 2

        for x in range(0, biggest_playlist):
            for y in range(0, len(members)):
                try:
                    result_track = members_tracks[members[y]][x]
                    if result_track is not None:
                        result_tracks.append(result_track)

                except IndexError:
                    pass

        return result_tracks

    def get_next_user(self):
        if self.current_user is not None:
            if len(self.get_members_in_order()) > self.get_members_in_order().index(self.current_user) - 1:
                return self.get_members_in_order()[self.get_members_in_order().index(self.current_user) - 1]
            else:
                return self.get_members_in_order()[0]
        else:
            self.current_user = self.get_members_in_order()[0]
            return self.current_user

    @staticmethod
    def get_parties_with(user):
        return Party.objects.filter(members__in=[user])

    @staticmethod
    def get_parties_from(user):
        return Party.objects.filter(owner=[user])

    def get_total_tracks(self):
        return self.get_all_tracks_in_order()


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

    priority = models.IntegerField()

    def __str__(self):
        return self.name

    def get_party_id(self):
        return self.party.id

    def get_user_id(self):
        return self.user.spotifyId

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
        return sorted(Track.get_all_tracks(party, user), key=attrgetter('priority'))

    @staticmethod
    def get_last_priority(party, user):
        all_tracks = Track.get_all_tracks(party, user)
        if len(all_tracks) > 0:
            return all_tracks[len(all_tracks) - 1].priority
        else:
            return 1

    @staticmethod
    def del_all_tracks(party, user):
        Track.get_all_tracks(party, user).delete()

    """
    @staticmethod
    def get_all_party_tracks_sorted(party):
        theatrical_party = party

        total_tracks = []
        users_tracks = dict()

        members = theatrical_party.get_members_in_order()

        for member in members:
            users_tracks[member.spotify_id] = Track.get_all_tracks_sorted(theatrical_party, member)

        finish = False

        while not finish:
            all_checked = False
            loop_count = 0

            while not all_checked:
                current_user = theatrical_party.get_next_user()

                next_user_tracks = []

                for user_track in users_tracks[current_user.spotify_id]:
                    if not user_track.played:
                        next_user_tracks.append(user_track)

                if loop_count > len(theatrical_party.get_members_in_order()):
                    all_checked = True
                    finish = True

                if len(next_user_tracks) > 0:
                    next_track = next_user_tracks[0]
                    total_tracks.append(next_track)

                    next_track.played = True

                    theatrical_party.current_user = theatrical_party.get_next_user()
                    all_checked = True

                else:
                    loop_count += 1

        for total_track in total_tracks:
            total_track.played = False

        return total_tracks"""
