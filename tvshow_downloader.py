#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
#    tvshow_downloader.py - A python script to manage the download of your favorites TV Shows
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
import ConfigParser

class TVShowConfigurationParser:
	'''
	This class rules the configuration file.
	If the file doesn't exist, it'll create it.

	Here is the an example configuration file:
	[global]
	magnet_file = bla
	log_file = bla

	[seriename]
	hd = True

	The global section is required to launch the script.
	'''
	def __init__(self, conf_file = './tvshow_downloader.cfg'):
		self.global_conf = {}
		self.series      = []

		parser = ConfigParser.ConfigParser()
		
		# we create the file if it doesn't exist: too kind yeah.
		if len(parser.read(conf_file)) == 0:
			parser.add_section('global')
			parser.set('global', 'magnet_file', '/tmp/magnetz')
			parser.set('global', 'log_file', '~/.logz_dl')
			parser.write(open('./tvshow_downloader.cfg', 'w'))

		try:
			# let me extract the required fields
			self.global_conf['magnet_file'] = parser.get('global', 'magnet_file')
			self.global_conf['log_file'] = parser.get('global', 'log_file')

			# maybe you haven't add yet your serie
			if len(parser.sections()) == 1:
				return

			# each others sections are reserved to describe a serie
			for section in parser.sections():
				if section != 'global':
					self.series.append({
						'name' : section,
						'hd' : parser.getboolean(section, 'hd')
					})
		except:
			raise Exception('Your configuration file sucks.')
	
	def get_log_file(self):
		return self.global_conf['log_file']
	
	def get_magnet_file(self):
		return self.global_conf['magnet_file']
	
	def get_series(self):
		return self.series

class Episode:
	'''
	Extract some useful information about an episode:
		* Is it an HD one ?
		* In which seasons the episode is ?
		* What is the episode number ?
	
	BTW, the eztv episodes are always named according to this way:
		seriename [0-9]{1,2}x[0-9]{1,2} [ quality ] -- Spartacus 2x5 [HDTV - ASAP]
	'''
	def __init__(self, name):
		self.name = name
		self.info = {}

		self.info['is_hd'] = 1 if name.lower().find('720p') != -1 else 0

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
	'''
	A little class to keep a writing trace of the differents downloads,
	it can be cool to see in your bash the latest downloaded files.
	'''
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
	'''
	THE TVShows_Manager !

	It checks the latest episode of a serie:
		-> if this one is in the database, ok you already see it
		-> else, I write the magnet link in a specific file -- like that you can add it in your torrent manager

	The database is a very basic sqlite3 base, with a table for each serie
	'''
	def __init__(self, favorite_tv_show, log_file, magnets_file):
		self.fav          = favorite_tv_show
		self.co           = sqlite3.connect('./tvshow_downloader.db')
		self.c            = self.co.cursor()
		self.logger       = DownloadHistory(log_file)
		self.magnets_file = magnets_file

		# initialize the tables
		for show in self.fav:
			# create the table if it doesn't exist yet
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
		'''
		Parse the eztv website, and raise an exception if something goes wrong
		'''
		params = urlencode({
			'show_name' : tv_show,
			'mode' : 'rss'
		})

		f = parse('http://www.ezrss.it/search/index.php?' + params)
		if f.bozo == 1: # BTW why the exception flag is called 'bozo' ? #wtf
			raise f.bozo_exception

		# we want only the latest entry -- because I assume you launch the script at least one time each day
		return f.entries[0]

	def __is_episode_already_downloaded(self, tv_show, ep_name):
		'''
		Check if an episode is already in the database
		'''
		self.c.execute('SELECT count(*) FROM "%s" WHERE name = ?' % tv_show, (ep_name, ))
		row = self.c.fetchone()
		if row[0] == 0:
			return False
		return True

	def __get_last_episode(self, tv_show, hd = False):
		'''
		Retrives the latest un-downloaded episode of a specific tv show
		'''
		try:
			last_ep = self.__parse_eztv(tv_show)
			is_already_downloaded = self.__is_episode_already_downloaded(tv_show, last_ep.title)
			if is_already_downloaded == True:
				return None
			return last_ep
		except Exception, e:
			print 'An error occured buddy: ' + str(e)

	def checkout(self):
		'''
		Find the latest episode for each your serie and write their magnet URI into a specific file
		'''
		file_magnets = open(self.magnets_file, 'w')
		nb_files_down = 0

		for show in self.fav:
			# trying to retrieve the latest episode
			last_ep = self.__get_last_episode(show['name'])
			if last_ep != None:

				episode = Episode(last_ep.title)

				# if we want only an hd one or not
				if show['hd'] != episode.is_an_hd_episode():
					continue

				print 'It seems you haven\'t downloaded that one : ' + last_ep.magneturi
				self.logger.add_an_entry(episode.get_name())
				file_magnets.write(last_ep.magneturi + '\n')

				attrs = (
					episode.get_name(),
					episode.get_season(),
					episode.get_episode_number(),
					episode.is_an_hd_episode(),
					time.time()
				)
				# OK, now I assume you'll start the torrent soon ; we don't want to re-download this file again
				self.c.execute('INSERT INTO "%s" VALUES(NULL, ?, ?, ?, ?, ?)' % show['name'], attrs)
				self.co.commit()
				nb_files_down += 1

		file_magnets.close()
		return nb_files_down

	def __del__(self):
		self.co.close()

def main(argc, argv):
	'''
	I RECOMMEND YOU:
	1] create a little bash script to start this script -- see run_tvshow_downloader.sh
	
	2] add a crontab to launch the whole process when you want
		crontab -e
		0 * * * * run_tvshow_downloader.sh
	
	3] add to your ~/.bashrc something like:
		echo "HERE ARE THE LATEST DOWNLOADS:"
		tail -20 ~/.logz_dl

	Don't forgot to check if you serie exists there:
		http://www.ezrss.it/shows/ (and verify eztv team releases 720p files for your series)
	'''

	try:
		# try to parse the configuration file
		conf_manager = TVShowConfigurationParser()
	except Exception, e:
		print 'Your configuration file seems to sucks, here is the exception:'
		print str(e)

	# OK, get ready to checkout!
	shows_manager = TVShows_Manager(
		conf_manager.get_series(),
		conf_manager.get_log_file(),
		conf_manager.get_magnet_file()
	)

	print '%d magnets added.' % shows_manager.checkout()
	return 1

if __name__ == '__main__':
	sys.exit(main(len(sys.argv), sys.argv))
