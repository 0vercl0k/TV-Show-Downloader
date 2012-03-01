#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
#    movie_rss.py - movie_rss Get your favorites TV Show automaticaly
#    Copyright (C) 2012 Axel "0vercl0k" Souchet - http://www.twitter.com/0vercl0k
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys
from feedparser import parse
from urllib import urlencode
import urllib2
import sqlite3
import time
import datetime
import re
import os

class FileDownloader:
	@staticmethod
	def download(link, where):
		name = link[link.rfind('/')+1:]
		u = urllib2.urlopen(link)
		f = open(os.path.sep.join([where, name]), 'wb')
		f.write(u.read())
		f.close()

class Episode:
	"""class describing an episode"""
	def __init__(self, name):
		self.name = name
		self.info = {}

		if name.lower().find('720p') != -1:
			self.info['is_hd'] = 1
		else:
			self.info['is_hd'] = 0

		r = re.findall(name, '([0-9]{1,2})x([0-9]{1,2})')
		if len(r) == 0:
			self.info['season'] = 1337
			self.info['episode'] = 1337
		else:
			self.info['season'] = r[0]
			self.info['episode'] = r[1]
	
	def get_name(self):
		return self.name

	def get_season(self):
		return self.info['season']
	
	def get_episode_number(self):
		return self.info['episode']

	def is_an_hd_episode(self):
		return self.info['is_hd']

class DownloadHistory:
	def __init__(self, log_file):
		try:
			self.log = open(log_file, 'a')
		except Exception, e:
			raise e
		self.header_put = False

	def __write_header(self):
		self.log.write('\n---- LOG : %s -----\n' % datetime.datetime.fromtimestamp(time.time()).strftime('%d/%m/%Y %H:%M'))

	def add_an_entry(self, name):
		if self.header_put == False:
			self.__write_header()
			self.header_put = True
		self.log.write('Downloaded : %s\n' % name)

	def __del__(self):
		try:
			self.log.close()
		except:
			pass

class TVShows_Manager:
	"""This class manages your favorite TV Shows download"""
	def __init__(self, favorite_tv_show, dir_down = '/tmp', log_file = '/home/overclok/.logz_dl'):
		self.fav = favorite_tv_show
		self.co = sqlite3.connect('./tvshows.db')
		self.c = self.co.cursor()
		self.logger = DownloadHistory(log_file)
		self.dir_down = dir_down

		# initialize the tables
		for show in self.fav:
			# Create the table if it doesn't exist yet
			self.c.execute('''
				CREATE TABLE 
				IF NOT EXISTS "%s" 
				(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					name TEXT,
					season INTEGER,
					episode INTEGER,
					is_hd INTEGER,
					date INTEGER
				)''' % show['name'])
			self.co.commit()

	def __parse_eztv(self, tv_show):
		params = urlencode({
			'show_name' : tv_show,
			'mode' : 'rss'
		})

		f = parse('http://www.ezrss.it/search/index.php?' + params)
		if f.bozo == 1:
			raise f.bozo_exception
		return f.entries[0]

	def __is_episode_already_downloaded(self, tv_show, ep_name):
		self.c.execute('SELECT count(*) FROM "%s" WHERE name = ?' % tv_show, (ep_name, ))
		row = self.c.fetchone()
		if row[0] == 0:
			return False
		return True

	def __get_last_episode(self, tv_show, hd = False):
		try:
			last_ep = self.__parse_eztv(tv_show)
			is_already_downloaded = self.__is_episode_already_downloaded(tv_show, last_ep.title)
			if is_already_downloaded == True:
				return None
			return last_ep
		except Exception, e:
			print 'An error occured buddy: ' + str(e)

	def checkout(self):
		nb_files_down = 0
		for show in self.fav:
			# trying to retrieve the last episode
			last_ep = self.__get_last_episode(show['name'])
			if last_ep != None:

				episode = Episode(last_ep.title)

				# if we want only an hd one or not
				if show['hd'] != episode.is_an_hd_episode():
					continue

				print 'It seems you haven\'t downloaded that one : ' + last_ep.links[0].href
				print '-> Downloading in %s..' % self.dir_down,
				
				is_download_ok = True
				try:
					FileDownloader.download(last_ep.links[0].href, self.dir_down)
				except Exception, e:
					print ' FAIL, exception : %s\n' % str(e)
					is_download_ok = False
				
				if is_download_ok == True:
					print 'OK\n'
					self.logger.add_an_entry(episode.get_name())

					attrs = (
						episode.get_name(),
						episode.get_season(),
						episode.get_episode_number(),
						episode.is_an_hd_episode(),
						time.time()
					)
					self.c.execute('INSERT INTO "%s" VALUES(NULL, ?, ?, ?, ?, ?)' % show['name'], attrs)
					self.co.commit()
					nb_files_down += 1

		return nb_files_down

	def __del__(self):
		self.co.close()

def main(argc, argv):
	# I RECOMMEND YOU:
	# 1] create a little bash script to start this script

	#!/bin/bash
	#WATCH_DIR=/downloads_stuff/watch-dir
	#python movie_rss.py
	#for i in $(ls $WATCH_DIR); do
	#        transmission-remote --auth overclok:pwd -a $WATCH_DIR/$i
	#        rm $WATCH_DIR/$i
	#done;

	# 2] add a crontab to launch the whole process as you want
	# crontab -e
	# 0 * * * * ~/utils/run_movie_rss.sh

	# 3] add to your ~/.bashrc something like:
	# echo "HERE ARE THE LAST DOWNLOADS:"
	# tail -20 ~/.logz_dl

	# I assume your serie exist there : http://www.ezrss.it/shows/ (and verify eztv team releases 720p files for your serie)
	fav_tv_show = [
		{'name' : 'The Walking Dead', 'hd' : True },
		{'name' : 'Game Of Thrones', 'hd' : True },
		{'name' : 'Californication', 'hd' : False},
		{'name' : 'Spartacus', 'hd': True},
		{'name' : 'True Blood', 'hd' : True}
	]

	shows_manager = TVShows_Manager(fav_tv_show, '/downloads_stuff/watch-dir')
	print '%d files downloaded.' % shows_manager.checkout()
	return 1

if __name__ == '__main__':
	sys.exit(main(len(sys.argv), sys.argv))
