# Copyright 2011-2012 James Tait - All Rights Reserved

"""Storage module for buddycloud channel server."""


def init_storage(config):
    """Initialise the storage module."""
    backend = config.get('Storage', 'backend')
    module_config = dict(config.items('%s-storage' % backend, raw=True))
    module_name, class_name = module_config.pop('class').rsplit('.', 1)
    module = __import__(module_name, fromlist=class_name)
    class_ = getattr(module, class_name)
    storage_module = class_()
    storage_module.set_config(**module_config)
    return storage_module


class StorageModule(object):
    """Base class for storage modules."""

    def set_config(self, **kwargs):
        """Set the configuration of this storage module."""
        pass

    def get_nodes(self):
        """Get a list of all the available PubSub nodes."""
        raise NotImplemented

    def get_node(self, node):
        """Get the requested PubSub node."""
        raise NotImplemented

    def set_node(self, node, items):
        """Set the requested PubSub node."""
        raise NotImplemented

    def shutdown(self):
        """Shut down the storage module - close any open resources, flush any
        pending data and so on."""
        pass


class MemoryStorageModule(StorageModule):
    """In-memory storage."""

    def __init__(self):
        self.temp_entry_store = {}

    def get_nodes(self):
        """Get a list of all the available PubSub nodes."""
        return self.temp_entry_store.keys()

    def get_node(self, node):
        """Get the requested PubSub node."""
        return self.temp_entry_store.get(node, {})

    def set_node(self, node, items):
        """Set the requested PubSub node."""
        self.temp_entry_store[node] = items
