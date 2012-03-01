#!/bin/bash

WATCH_DIR=/downloads_stuff/watch-dir
DIR=$(pwd)

cd ~/utils
# Let the script do its job
python movie_rss.py

# Adding manually the different torrent (yeah the watch-dir doesn't seem to work correctly)
for i in $(ls $WATCH_DIR); do
	transmission-remote --auth user:pwd -a $WATCH_DIR/$i
	rm $WATCH_DIR/$i
done;

cd $DIR
