# Copyright 2011 James Tait - All Rights Reserved

"""Definition of the buddycloud channel server."""

import logging
import select
import time
import uuid
import xmpp

from datetime import datetime


NS_PUBSUB_OWNER = '%s#%s' % (xmpp.protocol.NS_PUBSUB, 'owner')
NS_RSM = 'http://jabber.org/protocol/rsm'
NS_ATOM = 'http://www.w3.org/2005/Atom'
NS_THREADS = 'http://purl.org/syndication/thread/1.0'
NS_ACTIVITY_STREAMS = 'http://activitystrea.ms/spec/1.0/'


class ChannelServer:
    """XMPP component for buddycloud channel server."""

    def __init__(self, config):
        self.config = config
        self.connection = None
        self.is_online = False
        self.logger = logging.getLogger('ChannelServer')
        handler = logging.StreamHandler()
        formatter = logging.Formatter(config.get('Logging', 'log_format', raw=True))
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
        self._parse_config(config)
        self.temp_entry_store = {}

    def _parse_config(self, config):
        """"""
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
        self.connection.RegisterHandler('message', self.xmpp_message)
        self.connection.RegisterHandler('presence', self.xmpp_presence)
        self.connection.RegisterHandler(
            'iq', self.xmpp_pubsub_get, typ='get', ns=xmpp.protocol.NS_PUBSUB)
        self.connection.RegisterHandler(
            'iq', self.xmpp_pubsub_set, typ='set', ns=xmpp.protocol.NS_PUBSUB)
        self.connection.RegisterHandler(
            'iq', self.xmpp_register_set, typ='set',
            ns=xmpp.protocol.NS_REGISTER)
        self.disco = xmpp.browser.Browser()
        self.disco.PlugIn(self.connection)
        self.disco.setDiscoHandler(self.xmpp_base_disco, node='', jid=self.jid)

    def xmpp_message(self, conn, event):
        self.logger.debug(event)

    def xmpp_presence(self, conn, event):
        self.logger.debug(event)

    def xmpp_pubsub_get(self, conn, event):
        self.logger.debug('Pubsub request: %s', event)
        tag = event.getTag('pubsub')
        if tag and tag.getNamespace() == xmpp.protocol.NS_PUBSUB:
            node = tag.getTagAttr('items', 'node')
            rsm = tag.getTag('set', namespace=NS_RSM)
            set_size = int(rsm.getTagData('max'))
            channel = self.temp_entry_store.get(node, {})
            self.logger.debug(
                'Got channel entries for node %s: %s', node, channel)
            if channel is None:
                # TODO Channel does not exist - return 404
                return
            reply = event.buildReply('result')
            pubsub = reply.setTag('pubsub',
                    namespace=xmpp.protocol.NS_PUBSUB)
            items = pubsub.setTag('items', attrs={'node': node})
            for channel_item in sorted(channel.items(), key=lambda x: x[1][0],
                    reverse=True)[:set_size]:
                item = items.setTag('item', attrs={'id': channel_item[0]})
                item.addChild(node=channel_item[1][1])
            rsm = pubsub.setTag('set', namespace=NS_RSM)
            if len(channel.items()) > 0:
                rsm.setTagData('first', channel.items()[0][0], attrs={'index': 0})
                rsm.setTagData('last', channel.items()[-1][0])
            rsm.setTagData('count', len(channel.items()))
            conn.send(reply)
            raise xmpp.protocol.NodeProcessed


    def xmpp_pubsub_set(self, conn, event):
        self.logger.debug('Pubsub command: %s', event)
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
            items = self.temp_entry_store.get(node, {})
            items[entry_id] = (datetime.utcnow(), entry)
            self.temp_entry_store[node] = items
            reply = event.buildReply('result')
            pubsub = reply.setTag('pubsub', namespace=xmpp.protocol.NS_PUBSUB)
            publish = pubsub.setTag('publish', attrs={'node': node})
            publish.setTag('item', attrs={'id': entry_id})
            conn.send(reply)
            raise xmpp.protocol.NodeProcessed

    def xmpp_register_set(self, conn, event):
        """"""
        self.logger.debug('Register command: %s', event)
        tag = event.getTag('query')
        if tag and tag.getNamespace() == xmpp.protocol.NS_REGISTER:
            fromjid = event.getFrom().getStripped().__str__()
            # Create /user/<jid>/posts
            # Create /user/<jid>/geo/previous
            # Create /user/<jid>/geo/current
            # Create /user/<jid>/geo/next
            # Create /user/<jid>/subscriptions
            # Create /user/<jid>/status
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
        """"""
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
                        dict(node=x, jid=self.jid) for x in
                            self.temp_entry_store.keys()]
            else:
                channel = self.temp_entry_store.get(node, {})
                if channel and disco_type == 'info':
                    features = [xmpp.protocol.NS_DISCO_INFO,
                            xmpp.protocol.NS_DISCO_ITEMS,
                            xmpp.protocol.NS_PUBSUB,
                            NS_PUBSUB_OWNER]
                    if self.allow_register:
                        features.append(xmpp.protocol.NS_REGISTER)
                    return {
                        'ids': [{'category': 'pubsub', 'type': 'leaf',
                            'name': 'XEP-0060 service'},
                            {'category': 'pubsub', 'type': 'channel',
                                'name': 'buddycloud channel'}],
                        'features': features}

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
