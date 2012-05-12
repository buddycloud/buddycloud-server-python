# Copyright 2012 James Tait - All Rights Reserved

"""Storm object model for buddycloud channel server."""


from storm.base import Storm
from storm.locals import (
    DateTime,
    Reference,
    ReferenceSet,
    Store,
    Unicode,
)


class Node(Storm):
    """A PubSub node."""
    __storm_table__ = u'nodes'

    node = Unicode(primary=True, allow_none=False)
    config = ReferenceSet(node, 'NodeConfig.node')
    items = ReferenceSet(node, 'Item.node')
    subscriptions = ReferenceSet(node, 'Subscription.node')
    affiliations = ReferenceSet(node, 'Affiliation.node')

    def __init__(self, node):
        super(Node, self).__init__()
        self.node = unicode(node)


class NodeConfig(Storm):
    """Configuration of a PubSub node."""
    __storm_table__ = u'node_config'
    __storm_primary__ = (u'node', u'key')

    node = Unicode(allow_none=False)
    node_obj = Reference(node, Node.node)
    key = Unicode(allow_none=False)
    value = Unicode()
    updated = DateTime()

    def __init__(self, node, key, value):
        super(NodeConfig, self).__init__()
        self.node = node
        self.key = key
        self.value = value


class Item(Storm):
    """An Item in a PubSub node."""
    __storm_table__ = u'items'
    __storm_primary__ = (u'node', u'id')

    node = Unicode(allow_none=False)
    node_obj = Reference(node, Node.node)
    id = Unicode(allow_none=False)
    updated = DateTime()
    xml = Unicode()

    def __init__(self, node, id, updated, xml):
        super(Item, self).__init__()
        self.node = node
        self.id = id
        self.updated = updated
        self.xml = xml


class Affiliation(Storm):
    """Node affiliation."""
    __storm_table__ = u'affiliations'
    __storm_primary__ = (u'node', u'user')

    node = Unicode(allow_none=False)
    node_obj = Reference(node, Node.node)
    user = Unicode(allow_none=False)
    affiliation = Unicode()
    updated = DateTime()

    def __init__(self, node, user, affiliation, updated):
        super(Affiliation, self).__init__()
        self.node = node
        self.user = user
        self.affiliation = affiliation
        self.updated = updated


class Subscription(Storm):
    """Node subscription."""
    __storm_table__ = u'subscriptions'
    __storm_primary__ = (u'node', u'user')

    node = Unicode(allow_none=False)
    node_obj = Reference(node, Node.node)
    user = Unicode(allow_none=False)
    listener = Unicode()
    subscription = Unicode()
    updated = DateTime()

    def __init__(self, node, user, listener, subscription, updated):
        super(Subscription, self).__init__()
        self.node = node
        self.user = user
        self.listener = listener
        self.subscription = subscription
        self.updated = updated
