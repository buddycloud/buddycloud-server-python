# Copyright 2011-2012 James Tait - All Rights Reserved

"""Definition of the buddycloud channel server."""

import logging
import select
import time
import uuid
import xmpp

from xmpp.simplexml import (
    ustr,
    XML2Node,
)

from buddycloud.channel_server.storage import init_storage


NS_PUBSUB_EVENT = '%s#event' % xmpp.protocol.NS_PUBSUB
NS_PUBSUB_OWNER = '%s#owner' % xmpp.protocol.NS_PUBSUB
NS_RSM = 'http://jabber.org/protocol/rsm'
NS_ATOM = 'http://www.w3.org/2005/Atom'
NS_THREADS = 'http://purl.org/syndication/thread/1.0'
NS_ACTIVITY_STREAMS = 'http://activitystrea.ms/spec/1.0/'

FORM_TYPE_PUBSUB_METADATA = '%s#meta-data' % xmpp.protocol.NS_PUBSUB

PUBSUB_FIELDS = {
    'title': {
        'name': 'pubsub#title',
        'label': 'A short name for the node',
        'typ': 'text-single'
    },
    'description': {
        'name': 'pubsub#description',
        'label': 'A description of the node',
        'typ': 'text-single'
    },
    'accessModel': {
        'name': 'pubsub#access_model',
        'label': 'Who may subscribe and retrieve items',
        'typ': 'text-single'
    },
    'publishModel': {
        'name': 'pubsub#publish_model',
        'label': 'Who may publish items',
        'typ': 'text-single'
    },
    'creationDate': {
        'name': 'pubsub#creation_date',
        'label': 'Creation date',
        'typ': 'text-single'
    },
}

BUDDYCLOUD_FIELDS = {
    'defaultAffiliation': {
        'name': 'buddycloud#default_affiliation',
        'label': 'What role do new subscribers have?',
        'typ': 'text-single'
    },
    'channelType': {
        'name': 'buddycloud#channel_type',
        'label': 'Type of channel',
        'typ': 'text-single'
    },
}


class ChannelServer(object):
    """XMPP component for buddycloud channel server."""

    def __init__(self, config):
        self.config = config
        self.connection = None
        self.is_online = False
        self.logger = logging.getLogger('ChannelServer')
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            config.get('Logging', 'log_format', raw=True))
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(
            logging.__getattribute__(self.config.get('Logging', 'log_level')))
        # Component config section
        self.jid = None
        self.allow_register = False
        self.component_binding = False
        self.use_route_wrap = False
        # MainServer config section
        self.main_server = None
        # Auth config section
        self.sasl_username = None
        self.secret = None
        # Storage section
        self.storage = init_storage(config)
        # Do the set-up
        self._parse_config(config)

    def _parse_config(self, config):
        """Parse the configuration and set up the component."""
        self.jid = config.get('Component', 'jid')
        self.allow_register = config.getboolean('Component', 'allow_register')
        self.component_binding = config.getboolean(
            'Component', 'component_binding')
        self.route_wrap = config.getboolean('Component', 'route_wrap')
        self.main_server = (
            config.get('MainServer', 'host'), config.get('MainServer', 'port'))
        self.sasl_username = config.get('Auth', 'sasl_username')
        self.secret = config.get('Auth', 'secret')
        self.logger.debug('Configuration: %s',
            dict(((prop, self.__dict__.get(prop)) for prop in (
                'jid', 'allow_register', 'component_binding', 'route_wrap',
                'main_server', 'sasl_username', 'secret'))))

    def register_handlers(self):
        """Register handlers for the various XMPP stanzas."""
        self.connection.RegisterHandler('message', self.xmpp_message)
        self.connection.RegisterHandler('presence', self.xmpp_presence)
        self.connection.RegisterHandler(
            'iq', self.xmpp_pubsub_get, typ='get', ns=xmpp.protocol.NS_PUBSUB)
        self.connection.RegisterHandler(
            'iq', self.xmpp_pubsub_get, typ='get', ns=NS_PUBSUB_OWNER)
        self.connection.RegisterHandler(
            'iq', self.xmpp_pubsub_set, typ='set', ns=xmpp.protocol.NS_PUBSUB)
        self.connection.RegisterHandler(
            'iq', self.xmpp_register_set, typ='set',
            ns=xmpp.protocol.NS_REGISTER)
        self.disco = xmpp.browser.Browser()
        self.disco.PlugIn(self.connection)
        self.disco.setDiscoHandler(self.xmpp_base_disco, node='', jid=self.jid)

    def xmpp_message(self, conn, event):
        """Callback to handle XMPP message stanzas."""
        self.logger.debug(event)

    def xmpp_presence(self, conn, event):
        """Callback to handle XMPP presence stanzas."""
        self.logger.debug(event)

    def xmpp_pubsub_get(self, conn, event):
        """Callback to handle XMPP PubSub queries."""
        self.logger.debug('Pubsub request: %s', ustr(event))
        tag = event.getTag('pubsub')
        if tag and (tag.getNamespace() == xmpp.protocol.NS_PUBSUB or
                tag.getNamespace() == NS_PUBSUB_OWNER):
            child = tag.getChildren()[0]
            op = child.getName()
            node = child.getAttr('node')
            #rsm = tag.getTag('set', namespace=NS_RSM)
            #set_size = int(rsm.getTagData('max'))
            channel = self.storage.get_node(node)
            self.logger.debug(
                'Got channel entries for node %s: %s', node, channel)
            if channel is None:
                conn.send(xmpp.protocol.Error(event, xmpp.ERR_ITEM_NOT_FOUND)) 
                raise xmpp.protocol.NodeProcessed
            reply = event.buildReply('result')
            if op == u'items':
                pubsub = reply.setTag('pubsub',
                        namespace=xmpp.protocol.NS_PUBSUB)
                items = pubsub.setTag('items', attrs={'node': node})
                for channel_item in sorted(
                        channel.items, key=lambda x: x.updated, reverse=True):
                    item = items.setTag('item', attrs={'id': channel_item.id})
                    item.addChild(node=XML2Node(channel_item.xml))
            elif op == u'subscriptions':
                pubsub = reply.setTag('pubsub',
                        namespace=NS_PUBSUB_OWNER)
                subscriptions = pubsub.setTag(
                    u'subscriptions', attrs={u'node': node})
                for channel_item in channel.subscriptions:
                    subscriptions.setTag(u'subscription', attrs={
                        u'jid': channel_item.user,
                        u'subscription': channel_item.subscription})
            elif op == u'affiliations':
                pubsub = reply.setTag('pubsub',
                        namespace=NS_PUBSUB_OWNER)
                affiliations = pubsub.setTag(u'affiliations')
                for channel_item in channel.affiliations:
                    affiliations.setTag(u'affiliation', attrs={
                        u'jid': channel_item.user,
                        u'affiliation': channel_item.affiliation
                    })
            #rsm = pubsub.setTag('set', namespace=NS_RSM)
            #if len(resultset) > 0:
            #    rsm.setTagData('first', resultset[0].id if op == u'items' else
            #        resultset[0].user, attrs={'index': 0})
            #    rsm.setTagData('last', resultset[-1].id if op == u'items' else
            #        resultset[-1].jid)
            #rsm.setTagData('count', len(resultset))
            conn.send(reply)
            raise xmpp.protocol.NodeProcessed

    def xmpp_pubsub_set(self, conn, event):
        """Callback to handle XMPP PubSub commands."""
        self.logger.debug('Pubsub command: %s', event)
        self.logger.debug('Decoded event Node: %s', ustr(event))
        tag = event.getTag('pubsub')
        if tag and tag.getNamespace() == xmpp.protocol.NS_PUBSUB:
            publish = tag.getTag('publish')
            node = publish.getAttr('node')
            jid = publish.getAttr('jid')
            # TODO Check the sending JID can post to the JID/node
            entry = publish.getTag('item').getTag('entry')
            entry_id = str(uuid.uuid4())
            author = entry.getTag('author')
            author.setTagData('uri', 'acct:%s' % author.getTagData('name'))
            entry.setTagData('id', entry_id)
            entry.setTagData('published', entry.getTagData('updated'))
            entry.setTag('link', attrs={'rel': 'self', 'href':
                'xmpp:%s?pubsub;action=retrieve;node=%s;item=%s' % (self.jid,
                    node, entry_id)})
            self.storage.add_item(node, entry_id, ustr(entry))
            reply = event.buildReply('result')
            pubsub = reply.setTag('pubsub', namespace=xmpp.protocol.NS_PUBSUB)
            publish = pubsub.setTag('publish', attrs={'node': node})
            publish.setTag('item', attrs={'id': entry_id})
            conn.send(reply)
            for subscription in self.storage.get_node(node).subscriptions:
                message = xmpp.protocol.Message(
                    typ='headline', frm=self.jid, to=subscription.user)
                event = message.setTag('event', namespace=NS_PUBSUB_EVENT)
                items = event.setTag('items', attrs={'node': node})
                item = items.setTag('item', attrs={'id': entry_id})
                item.addChild(node=entry)
                conn.send(message)
            raise xmpp.protocol.NodeProcessed

    def xmpp_register_set(self, conn, event):
        """Callback to handle XMPP register commands."""
        self.logger.debug('Register command: %s', event)
        if event.getTo().getDomain() != self.jid:
            conn.send(xmpp.protocol.Error(event, xmpp.ERR_NOT_ALLOWED)) 
            raise xmpp.protocol.NodeProcessed
        tag = event.getTag('query')
        if tag and tag.getNamespace() == xmpp.protocol.NS_REGISTER:
            fromjid = event.getFrom().getStripped()
            node = self.storage.get_node(u'/user/%s/posts' % fromjid)
            if node:
                error = xmpp.protocol.Error(event, xmpp.ERR_CONFLICT)
                error.addChild(node=tag)
                conn.send(error)
                raise xmpp.protocol.NodeProcessed
            self.storage.create_channel(fromjid)
            reply = event.buildReply('result')
            conn.send(reply)
            raise xmpp.protocol.NodeProcessed

    def xmpp_connect(self):
        """Connect to the XMPP server."""
        self.connection = xmpp.client.Component(self.jid, self.main_server[0],
            self.main_server[1], debug=['always', 'nodebuilder'] if
            self.logger.level == logging.DEBUG else [],
            sasl=self.sasl_username is None,
            bind=self.component_binding, route=self.route_wrap)

        connected = self.connection.connect(
            (self.main_server[0], self.main_server[1]))
        self.logger.info('connected: %s', connected)
        while not connected:
            time.sleep(5)
            connected = self.connection.connect(
                (self.main_server[0], self.main_server[1]))
            self.logger.info('connected: %s', connected)
        self.register_handlers()
        self.logger.info('trying auth')
        connected = self.connection.auth(
            self.sasl_username or self.jid, self.secret)
        self.logger.info('auth return: %s', connected)
        self.is_online = True
        return connected

    def xmpp_disconnect(self):
        """Disconnect from the XMPP server."""
        time.sleep(5)
        if not self.connection.reconnectAndReauth():
            time.sleep(5)
            self.xmpp_connect()

    def xmpp_base_disco(self, conn, event, disco_type):
        """Callback to handle XMPP Disco requests."""
        self.logger.debug('Disco event: %s', event)
        fromjid = event.getFrom().getStripped().__str__()
        to = event.getTo()
        node = event.getQuerynode()
        if to == self.jid:
            if node is None:
                if disco_type == 'info':
                    features = [xmpp.protocol.NS_DISCO_INFO,
                            xmpp.protocol.NS_DISCO_ITEMS,
                            xmpp.protocol.NS_PUBSUB,
                            NS_PUBSUB_OWNER]
                    if self.allow_register:
                        features.append(xmpp.protocol.NS_REGISTER)
                    return {
                        'ids': [{'category': 'pubsub', 'type': 'service',
                            'name': 'XEP-0060 service'},
                            {'category': 'pubsub', 'type': 'channels',
                                'name': 'Channels service'},
                            {'category': 'pubsub', 'type': 'inbox',
                                'name': 'Channels inbox service'}],
                        'features': features}
                elif disco_type == 'items':
                    return [
                        dict(node=x.node, jid=self.jid) for x in
                            self.storage.get_nodes()]
            else:
                channel = self.storage.get_node(node)
                if channel and disco_type == 'info':
                    features = [xmpp.protocol.NS_DISCO_INFO,
                            xmpp.protocol.NS_DISCO_ITEMS,
                            xmpp.protocol.NS_PUBSUB,
                            NS_PUBSUB_OWNER]
                    if self.allow_register:
                        features.append(xmpp.protocol.NS_REGISTER)
                    fields = [
                        xmpp.protocol.DataField(name='FORM_TYPE', typ='hidden',
                            value=FORM_TYPE_PUBSUB_METADATA)]
                    for c in channel.config:
                        if c.key in BUDDYCLOUD_FIELDS:
                            fields.append(xmpp.protocol.DataField(
                                **dict(BUDDYCLOUD_FIELDS[c.key].items() +
                                    [('value', c.value)])))
                        elif c.key in PUBSUB_FIELDS:
                            fields.append(xmpp.protocol.DataField(
                                **dict(PUBSUB_FIELDS[c.key].items() +
                                    [('value', c.value)])))
                    return {
                        'ids': [{'category': 'pubsub', 'type': 'leaf',
                            'name': 'XEP-0060 service'},
                            {'category': 'pubsub', 'type': 'channel',
                                'name': 'buddycloud channel'}],
                        'features': features,
                        # TODO Populate this from the node configuration
                        'xdata': xmpp.protocol.DataForm(
                            typ='result', data=fields)}

    def run(self):
        """Main event loop."""
        while self.is_online:
            try:
                self.connection.Process(1)
            except IOError:
                self.xmpp_disconnect()
            except xmpp.protocol.UnsupportedStanzaType, err:
                self.logger.warn('Unsupported stanza type received: %s', err)
            except select.error:
                break
            if not self.connection.isConnected():
                self.xmpp_disconnect()
        self.connection.disconnect()
        self.storage.shutdown()
