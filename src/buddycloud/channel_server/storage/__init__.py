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
    module_config.update({
        'log_format': config.get('Logging', 'log_format', raw=True),
        'log_level': config.get('Logging', 'log_level')})
    storage_module.set_config(**module_config)
    return storage_module


class StorageBackend(object):
    """Base class for storage back-ends."""

    def set_config(self, **kwargs):
        """Set the configuration of this storage back-end."""
        pass

    def create_channel(self, jid):
        """Create a channel for the given JID."""
        raise NotImplementedError()

    def create_node(self, node, jid, node_config):
        """Create a PubSub node with the given configuration."""
        raise NotImplementedError()

    def get_nodes(self):
        """Get a list of all the available PubSub nodes."""
        raise NotImplementedError()

    def get_node(self, node):
        """Get the requested PubSub node."""
        raise NotImplementedError()

    def add_item(self, node, item_id, item):
        """Add an item to the requested PubSub node."""
        raise NotImplementedError()

    def shutdown(self):
        """Shut down the storage module - close any open resources, flush any
        pending data and so on."""
        pass
