#!/bin/bash

MAGNETZ_FILE=/tmp/magnetz

# Let the script do its job
python tvshow_downloader.py

if [ -f $MAGNETZ_FILE ]; then

    # Adding the different magnet torrent
    for magnet in $(cat $MAGNETZ_FILE); do
        transmission-remote host:port --auth user:pwd -a "$magnet"
    done;

    rm $MAGNETZ_FILE
fi