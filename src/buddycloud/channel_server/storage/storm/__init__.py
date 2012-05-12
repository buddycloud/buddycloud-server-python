# Copyright 2012 James Tait - All Rights Reserved

"""Storm storage module for buddycloud channel server."""

import copy 
import logging

from datetime import datetime

from storm.locals import (
    create_database,
    Store,
)

from buddycloud.channel_server.storage import StorageBackend
from buddycloud.channel_server.storage.storm.model import (
    Affiliation,
    Item,
    Node,
    NodeConfig,
    Subscription,
)


DEFAULT_CONFIG = {
    u'accessModel': u'open',
    u'defaultAffiliation': u'member',
    u'publishModel': u'publishers',
}


class StormStorageBackend(StorageBackend):
    """Storage back-end based on the Storm ORM framework."""

    def __init__(self):
        self.store = None

    def set_config(self, **kwargs):
        """Set the configuration of this back-end."""
        uri = kwargs['uri']
        database = create_database(uri)
        self.store = Store(database)
        self.logger = logging.getLogger('StormStorageBackend')
        handler = logging.StreamHandler()
        formatter = logging.Formatter(kwargs['log_format'])
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(
            logging.__getattribute__(kwargs['log_level']))

    def create_node(self, node, jid, node_config):
        """Create a PubSub node with the given configuration.

        Creates the Node, NodeConfig, Affiliation and Subscription model for
        the given node.
        """
        self.logger.debug('Creating node %s for jid %s with config %s' %
            (node, jid, node_config))
        new_node = Node(node)
        self.store.add(new_node)
        config = copy.deepcopy(DEFAULT_CONFIG)
        config.update(node_config)
        for key, value in config.items():
            new_node_config = NodeConfig(node, key, value)
            new_node_config.updated = datetime.utcnow()
            self.store.add(new_node_config)
        affiliation = Affiliation(node, jid, u'owner', datetime.utcnow())
        self.store.add(affiliation)
        subscription = Subscription(node, jid, jid, u'subscribed',
                datetime.utcnow())
        self.store.add(subscription)

    def create_channel(self, jid):
        """Create a channel for the given JID.

        Creates all the required PubSub nodes that constitute a channel, with
        the appropriate permissions.
        """
        self.logger.debug('Creating channel for %s' % jid)
        creation_date = unicode(datetime.utcnow().isoformat())
        self.create_node(u'/user/%s/posts' % jid, jid,
            {u'channelType': u'personal',
                u'creationDate': creation_date,
                u'defaultAffiliation': u'publisher',
                u'description': u'buddycloud channel for %s' % jid,
                u'title': jid})
        self.create_node(u'/user/%s/geo/current' % jid, jid,
            {u'creationDate': creation_date,
                u'description': u'Where %s is at now' % jid,
                u'title': u'%s Current Location' % jid})
        self.create_node(u'/user/%s/geo/next' % jid, jid,
            {u'creationDate': creation_date,
                u'description': u'Where %s intends to go' % jid,
                u'title': u'%s Next Location' % jid})
        self.create_node(u'/user/%s/geo/previous' % jid, jid,
            {u'creationDate': creation_date,
                u'description': u'Where %s has been before' % jid,
                u'title': u'%s Previous Location' % jid})
        self.create_node(u'/user/%s/status' % jid, jid,
            {u'creationDate': creation_date,
                u'description': u'M000D',
                u'title': u'%s status updates' % jid})
        self.create_node(u'/user/%s/subscriptions' % jid, jid,
            {u'creationDate': creation_date,
                u'description': u'Browse my interests',
                u'title': u'%s subscriptions' % jid})
        self.store.commit()

    def get_node(self, node):
        """Get the requested PubSub node."""
        self.logger.debug('Getting node %s' % node)
        the_node = self.store.get(Node, node)
        self.logger.debug('Returning node %s' % the_node)
        return the_node

    def get_nodes(self):
        """Get a list of all the available PubSub nodes."""
        self.logger.debug('Getting list of available nodes.')
        node_list = self.store.find(Node)
        self.logger.debug('Returning list of available node %s' % node_list)
        return node_list

    def add_item(self, node, item_id, item):
        """Add an item to the requested PubSub node."""
        new_item = Item(node, unicode(item_id), datetime.utcnow(), item)
        self.store.add(new_item)
        self.store.commit()

    def shutdown(self):
        """Shut down this storage module - flush, commit and close the
        store."""
        self.store.flush()
        self.store.commit()
        self.store.close()
