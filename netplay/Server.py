from . import enetwrapper
import struct
enet = enetwrapper.enet

import socket
import threading
import json
import time

from . import constants, Pack


class ServerHeartbeatThread(threading.Thread):
    def __init__(self, game, port, info):
        super().__init__()
        self.port = port
        self.info = info

        self.HOST = game.config['master']['hostname']
        self.PORT = int(game.config['master']['port'])

    def run(self):
        #HOST = '127.0.0.1'
        #PORT = 4000
        HOST = self.HOST
        PORT = self.PORT

        if HOST == '':
            # No master configured
            return

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((HOST, PORT))
        except socket.error as value:
            s.close()
            print ("Could not reach master -", value)
            return

        s.setblocking(0)
        port = self.port
        info = {}
        info['Name'] = 'Server of Bob Johnson'
        data = bytes(json.dumps([port, info]), 'UTF-8')
        data += b'\0'
        s.sendall(data)
        s.close()


class Server:

    def __init__(self, game, mode=constants.MODE_OFFLINE,
            servername='', mapname='', playername='',
            maxclients=10, interface='', port=54303):

        self.mode = mode

        self.game = game
        self.owner = game.owner
        self.maxclients = maxclients
        self.port = port

        info = {}
        info['Name'] = servername
        info['Map'] = mapname
        info['TotalPlayers'] = '1'
        info['MaxPlayers'] = str(maxclients)
        info['PlayerList'] = playername + '\n'

        self.info = info

        # Client ID and enet peer ID are the same
        self.client_list = [None] * maxclients

        # Create the ENet wrapper
        # It should temporarily be moved to a separate thread during
        # blocking operations

        if mode == constants.MODE_OFFLINE:
            self.network = None
            print ("Playing offline")
        elif enet is None:
            # No network support - a compatible enet library was not supplied
            self.network = None
            print ("No compatible enet library found.  Network play disabled.")
        else:
            self.network = enetwrapper.ENetWrapper(server=True,
                maxclients=maxclients, interface=interface, port=port)

            # Notify the master server
            self.nextHeartbeat = time.time() + 30.0
            self.masterThread = ServerHeartbeatThread(self.game, port, info)

            print ("Server started")

    def onConnect(self, peer_id):
        print ("Client connected")

    def onDisconnect(self, peer_id):
        print ("Client disconnected")

    def addClient(self, peer):
        peerID = peer.incomingPeerID
        if self.client_list[peerID] is not None:
            print ("ERROR - client ID in use")
            return

        self.peer = peer
        client = Client(self, peer)
        self.client_list[peerID] = client

        # Just going to throw it at enet all at once and see what happens
        bdata_list = self.owner['Game'].systems['Component'].getGameState(peerID)
        """
        d = Pack.fromDataList(bdata_list)
        packet = self.network.createPacket(d, reliable=True)
        self.network.send(self.peer, packet)
        """
        for bdata in bdata_list:
            packet = self.network.createPacket(bdata)
            self.network.send(self.peer, packet)
        #"""

        self.onConnect(peerID)

    def removeClient(self, peerID):
        # Assumes the peer was already reset (either by disconnect event
        # or a class to Client.disconnect()
        #client = self.client_list[peerID]
        self.client_list[peerID] = None

        self.onDisconnect(peerID)

    def update(self, dt):
        cmgr = self.owner['Game'].systems['Component']

        if self.network is None:
            # Flush queued data
            cmgr.getQueuedData()
            return

        now = time.time()
        if now > self.nextHeartbeat:
            if not self.masterThread.is_alive():
                self.nextHeartbeat = now + 30.0
                self.masterThread = ServerHeartbeatThread(self.game, self.port, self.info)

        backlog = []
        if self.network.threaded:
            backlog = self.network.disableThreading()

        cmgr = self.owner['Game'].systems['Component']

        while True:
            if len(backlog):
                event = backlog.popleft()
            else:
                event = self.network.host.service(0)

            if event.type == 0:
                break

            elif event.type == enet.EVENT_TYPE_CONNECT:
                print (("%s connected" % event.peer.address))
                self.addClient(event.peer)

            elif event.type == enet.EVENT_TYPE_DISCONNECT:
                print (("%s disconnected" % event.peer.address))
                self.removeClient(event.peer.incomingPeerID)

            elif event.type == enet.EVENT_TYPE_RECEIVE:
                peerID = event.peer.incomingPeerID
                bdata = event.packet.data
                #bdata_list = Pack.toDataList(zlib.decompress(event.packet.data))
                #for bdata in bdata_list:
                # Get the component and processor IDs
                header = struct.unpack('!HH', bdata[:4])
                c_id = header[0]
                p_id = header[1]

                component = cmgr.getComponent(c_id)
                if component is not None:
                    if component.hasPermission(peerID):
                        # Strip the IDs and process
                        data = bdata[4:]
                        dp = component._packer.process(p_id, data)

                        if dp.replicate:
                            # Forward the command to other clients
                            k = 0
                            for c in self.client_list:
                                if c is not None and k != peerID:
                                    self.network.send(c.peer, self.network.createPacket(bdata))

                                k += 1
                    else:
                        print ("Client does not have input permission")
                        print (("This is normal if button was changed when",
                            "the client still thought it was alive"))

                else:
                    print (("Invalid component ID %d" % c_id))

        self.sendQueuedData()

    def sendQueuedData(self):
        if self.network is None:
            return

        # Get queued data and ship to clients
        cmgr = self.owner['Game'].systems['Component']
        bdata_list = cmgr.getQueuedData()
        """
        # Ok... I'm going to create per-client packets
        # to reduce packet overhead at the cost of CPU time(?)
        for bdata_packer in bdata_list:
            for bdata in bdata_packer:
                comp = bdata[0]
                reliable = bdata[1]
                ignoreOwner = bdata[2]
                d = bdata[3]

                for c in self.client_list:
                    if c is not None:
                        if not ignoreOwner:
                            if reliable:
                                c.reliable_data.append(d)
                            else:
                                c.unreliable_data.append(d)
                        elif not comp.hasPermission(c.peer.incomingPeerID):
                            if reliable:
                                c.reliable_data.append(d)
                            else:
                                c.unreliable_data.append(d)

        for c in self.client_list:
            if c is not None:
                if len(c.reliable_data):
                    d = Pack.fromDataList(c.reliable_data)
                    c.reliable_data = []
                    packet = self.network.createPacket(d, reliable=True)
                    self.network.send(c.peer, packet)

                if len(c.unreliable_data):
                    d = Pack.fromDataList(c.unreliable_data)
                    c.unreliable_data = []
                    packet = self.network.createPacket(d, reliable=False)
                    self.network.send(c.peer, packet)
        """
        for bdata_packer in bdata_list:
            for bdata in bdata_packer:
                comp = bdata[0]
                reliable = bdata[1]
                ignoreOwner = bdata[2]
                d = bdata[3]

                packet = self.network.createPacket(d, reliable=reliable)
                for c in self.client_list:
                    if c is not None:
                        if not ignoreOwner:
                            self.network.send(c.peer, packet)
                        elif not comp.hasPermission(c.peer.incomingPeerID):
                            self.network.send(c.peer, packet)
        #"""


class Client:

    def __init__(self, server, peer):
        self.server = server
        self.peer = peer

        self.reliable_data = []
        self.unreliable_data = []

    def disconnect(self):
        # Forces disconnect, rather than waiting for timeout
        self.peer.reset()
        self.server.removeClient(self.peer.incomingPeerID)

