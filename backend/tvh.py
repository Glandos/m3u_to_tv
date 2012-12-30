#!/usr/bin/env python
# -*- coding: utf8 -*-

import urllib, urllib2
import json

class AttributedDict(dict):
    def __init__(self, d):
        dict.__init__(self, d)
        for (key, value) in d.items():
            setattr(self, key, value)
    
class IPTVService(AttributedDict):
    def __init__(self, d):
        AttributedDict.__init__(self, d)
    
class Channel(AttributedDict):
    def __init__(self, d):
        AttributedDict.__init__(self, d)
    
    
def decodeTVHObject(d):
    if 'id' in d and d['id'].startswith('iptv_'):
        service = IPTVService(d)
        return service
    elif 'chid' in d:
        return Channel(d)
    return d

class TVHBackend:
    def __init__(self, url):
        self._url = url
        self._iptv_services_url = url + "/iptv/services"
        self._channels_url = url + "/channels"
    
    def create_channel(self, channel = None):
        try:
            response = urllib2.urlopen(self._channels_url, "op=create")
            tvh_channel = json.load(response, object_hook = decodeTVHObject)
            if channel is None:
                return tvh_channel
            return self.update_channels([tvh_channel], [channel])
        except:
            print 'Error while creating channel'
            return False
    
    def send_update(self, url, json_object):
        try:
            data = {'op': 'update', 'entries': '%s' % json.dumps(json_object) }
            response = urllib2.urlopen(url, urllib.urlencode(data))
            return True
        except:
            print 'Error while sending update for %s' % json.dumps(json_object)
            return False
    
    def update_channels(self, tvh_channels, channels):
        updates = []
        for (tvh_channel, channel) in zip(tvh_channels, channels):
            update = {'id' : tvh_channel.chid, # Yes, it is different
                      'name': channel.channel_name,
                      'number': channel.channel_number,
                      'ch_icon': channel.icon_url}
            updates.append(update)
        return self.send_update(self._channels_url, updates)
    
    def update_iptv_services(self, tvh_services, channels):
        updates = []
        for (tvh_service, channel) in zip(tvh_services, channels):
            update = {'id' : tvh_service.id, # Yes, it is different
                      'channelname': channel.channel_name,
                      'interface': channel.channel_url}
            updates.append(update)
        return self.send_update(self._iptv_services_url, updates)
    
    def create_iptv_service(self, channel = None):
        try:
            response = urllib2.urlopen(self._iptv_services_url, "op=create")
            service = json.load(response, object_hook = decodeTVHObject)
            if channel is None:
                return service
            return self.update_iptv_services([service], [channel])
        except:
            print 'Error while creating IPTV service'
            return False
    
    def add_iptv_channels(self, channels):
        # Create empty channels and services
        tvh_channels = [self.create_channel() for i in range(len(channels))]
        services = [self.create_iptv_service() for i in range(len(channels))]
        # Massive updates
        self.update_channels(tvh_channels, channels)
        self.update_iptv_services(services, channels)