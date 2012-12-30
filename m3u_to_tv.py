#!/usr/bin/env python
# -*- coding: utf8 -*-

import bs4
import urlparse
import argparse
import urllib2
import fileinput
import re
from backend.tvh import TVHBackend

playlist_url = 'http://mafreebox.freebox.fr/freeboxtv/playlist.m3u'
channels_description_url = ['http://www.free.fr/adsl/pages/television/services-de-television/acces-a-plus-250-chaines/bouquet-basique.html',
                            'http://www.free.fr/adsl/pages/television/services-de-television/acces-a-plus-250-chaines/themes/theme-17.html']
radio_channel_offset = 10000
available_channel_types = {'hd': 'HD', 'ld': '(bas débit)', 'sd': None, 'radio': None}

class Channel(object):
    def __init__(self):
        self._channel_number = None
        self._channel_name = None
        self._channel_url = None
        self._channel_type = None
        self._icon_url = None
        self._available = False
    
    @property
    def channel_number(self):
        return self._channel_number
    
    @channel_number.setter
    def channel_number(self, value):
        self._channel_number = int(value)
    
    @property
    def channel_name(self):
        return self._channel_name
    
    @channel_name.setter
    def channel_name(self, value):
        self._channel_name = value
    
    @property
    def channel_url(self):
        return self._channel_url
    
    @channel_url.setter
    def channel_url(self, value):
        self._channel_url = value
        if value is None:
            self._channel_type = None
        elif self._channel_number >= radio_channel_offset:
            self._channel_type = 'radio'
        else:
            type = self._channel_url[-2:]
            if type in available_channel_types:
                self._channel_type = type
    
    @property
    def channel_type(self):
        return self._channel_type
    
    @property
    def icon_url(self):
        return self._icon_url
    
    @icon_url.setter
    def icon_url(self, value):
        self._icon_url = value
    
    @property
    def available(self):
        return self._available
    
    @available.setter
    def available(self, value):
        self._available = value
    
    def __str__(self):
        return 'Channel %s: %s at %s (%s)' % (self.channel_number, self.channel_name, self.channel_url, self.channel_type)

class Descriptions(object):
    def __init__(self, urls):
        if getattr(urls, '__iter__', False):
            self._soups = {url: bs4.BeautifulSoup(get_handle(url)) for url in urls}
        else:
            self._soups = {urls: bs4.BeautifulSoup(get_handle(urls))}
    
    def get_icon_url(self, channel):
        for (url, soup) in self._soups.items():
            links = soup.select('a.tv-chaine-' + str(channel.channel_number))
            if len(links) > 0:
                img_src = links[0].img['src']
                if img_src:
                    return urlparse.urljoin(url, img_src)
        return None
    
def get_handle(url):
        handle = None
        try:
            handle = open(url)
        except IOError as e:
            handle = urllib2.urlopen(url)
        return handle
    
def parse_channel_metadata(channel, line, strip_quality_qualifier = False):
    _, _, number_and_name = line.partition(',')
    number, _, name = number_and_name.partition(' - ')
    channel.channel_number = number
    if strip_quality_qualifier:
        qualifiers = available_channel_types.values()
        for qualifier in qualifiers:
            if qualifier is not None and name.endswith(qualifier):
                name = name[:-len(qualifier)].strip()
                break
    channel.channel_name = name

def aggregate_channel(channels, channel):
    if not channels.has_key(channel.channel_number):
        channels[channel.channel_number] = {}
    
    channels[channel.channel_number][channel.channel_type] = channel

def fetch_channel_icons(channels, descriptions):
    for channel_types in channels.viewvalues():
        for channel in channel_types.viewvalues():
            icon_url = descriptions.get_icon_url(channel)
            if icon_url:
                channel.icon_url = icon_url
                channel.available = True

def read_playlist(url):
    playlist_file = get_handle(url)
    channels = {}
    channel = Channel()
    for line in playlist_file:
        line = line.strip()
        if line.startswith('#EXTINF'):
            parse_channel_metadata(channel, line, True)
        elif line.startswith('rtsp'):
            channel.channel_url = line
            aggregate_channel(channels, channel)
            channel = Channel()
    return channels

def update_xmltv(channels, xmltv_file):
    compiled_pattern = re.compile('.*?(?P<prefix>channel \d+ )(?P<name>.*?);')
    channels_by_name = {channel.channel_name: channel for channel in channels}
    for line in fileinput.input(xmltv_file, inplace = 1):
        result = compiled_pattern.match(line)
        if result is not None:
            name = result.group('name')
            if name in channels_by_name:
                channel = channels_by_name[name]
                line = result.group('prefix') + name + ';' + channel.icon_url + '\n'
            print line,

def declare_channels(channels, backend, quality = 'hd', fallback_quality = True,
                     include_radio = False, include_unavailable = False,
                     xmltv_file = None):
    i = 0
    selected_channels = []
    for channel_types in channels.viewvalues():
        channel = None
        if 'radio' in channel_types:
            if include_radio:
                channel = channel_types['radio']
                # Mark channel as available
                channel.available = True
        else:
            if quality in channel_types:
                channel = channel_types[quality]
            elif fallback_quality:
                # Fallback to the first available
                channel = channel_types.itervalues().next()
                print 'Falling back to %s quality for %s' % (channel.channel_type, channel.channel_name)
        if channel is not None and (include_unavailable or channel.available):
            selected_channels.append(channel)
            i += 1
    if xmltv_file is not None:
        print 'Updating XMLTV'
        update_xmltv(selected_channels, xmltv_file)
    backend.add_iptv_channels(selected_channels)
    print '%d channels added to backend' % i
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Read a playlist and feed it to TVHeadend')
    parser.add_argument('--playlist-url', '-p', default = playlist_url)
    parser.add_argument('--backend', '-b', default = 'tvh')
    parser.add_argument('--backend-host', default = 'localhost')
    parser.add_argument('--backend-port', default = '9981') # port is string, it will be in the URL
    parser.add_argument('--descriptions-url', default = channels_description_url, nargs = '*')
    parser.add_argument('--quality', '-q', default = 'hd', choices = ['sd', 'ld', 'hd'])
    parser.add_argument('--no-fallback-quality', action = 'store_true')
    parser.add_argument('--include-radio', action = 'store_true')
    parser.add_argument('--include-without-description', action = 'store_true')
    parser.add_argument('--xmltv-telerama-file', default = None)
    
    args = parser.parse_args()
    
    print 'Reading playlist from %s' % args.playlist_url
    
    channels = read_playlist(args.playlist_url)
    backend = TVHBackend('http://%s:%s' % (args.backend_host, args.backend_port) )
    
    print 'Reading icons from %s' % args.descriptions_url
    descriptions = Descriptions(args.descriptions_url)
    fetch_channel_icons(channels, descriptions)
    
    print 'Adding channels to backend'
    declare_channels(channels, backend, args.quality, not args.no_fallback_quality,
                     args.include_radio, args.include_without_description, args.xmltv_telerama_file)
    