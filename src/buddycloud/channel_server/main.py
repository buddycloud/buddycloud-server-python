#! /usr/bin/env python

# Copyright 2011 James Tait - All Rights Reserved

"""Main entry point for buddycloud channel server."""

import ConfigParser
import logging
import os
import signal
import sys

from buddycloud.channel_server.channel_server import ChannelServer
from optparse import OptionParser

def sigHandler(signum, frame):
    """Signal handler."""
    channel_server.offlinemsg = 'Signal handler called with signal %s' % signum
    channel_server.is_online = False

if __name__ == '__main__':
    parser = OptionParser('%prog [options]')
    parser.add_option('--config', dest='config_file',
            default='conf/channel_server.conf',
            help='The configuration file to use.')
    options, args = parser.parse_args()

    if len(args) > 0:
        parser.error('Garbage args after command line.')
    if not os.path.isfile(options.config_file):
        parser.error('Specified config file %s does not exist!' %
                options.config_file)
    config = ConfigParser.ConfigParser()
    config.read(options.config_file)

    logger = logging.getLogger('main')
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.get('Logging', 'log_format', raw=True))
    handler.setFormatter(formatter)
    logger.setLevel(logging.__getattribute__(
        config.get('Logging', 'log_level')))
    logger.addHandler(handler)
    
    channel_server = ChannelServer(config)
    if not channel_server.xmpp_connect():
        logger.fatal('Could not connect to server, or password mismatch!')
        sys.exit(1)
    # Set the signal handlers
    signal.signal(signal.SIGINT, sigHandler)
    signal.signal(signal.SIGTERM, sigHandler)
    channel_server.run()
