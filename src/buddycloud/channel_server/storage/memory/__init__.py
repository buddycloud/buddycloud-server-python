# Copyright 2011-2012 James Tait - All Rights Reserved

"""Storage module for buddycloud channel server."""

import copy

from datetime import datetime

from buddycloud.channel_server.storage import StorageBackend


class MemoryStorageBackend(StorageBackend):
    """In-memory storage.

    NOTE: This back-end is intended for testing only.  It is full-fat,
    vitamin-free, high-calorie, artificially-preserved, hydrogenated, salt-rich
    badness, totally non-persistent, non-transactional and non-threadsafe and
    definitely not suitable for production use.

    Creates an in-memory dictionary to hold nodes and items.  The dictionary is
    keyed on the node ID, the value being another dictionary whose key is the
    entry ID and whose value is a tuple consisting of a timestamp and the entry
    Node object:

        {'node_id': {'entry_id': (timestamp, entry_node)}}"""

    def __init__(self):
        self.temp_entry_store = {}

    def get_nodes(self):
        """Get a list of all the available PubSub nodes."""
        return self.temp_entry_store.keys()

    def get_node(self, node):
        """Get the requested PubSub node."""
        return copy.deepcopy(self.temp_entry_store.get(node, None))

    def add_item(self, node, item_id, item):
        """Add an item to the requested PubSub node."""
        channel = self.temp_entry_store[node]
        channel[item_id] = (datetime.utcnow(), item)
