import bge
import mathutils
import logging
from . import packer


class NetComponent:
    obj = None

    def __init__(self, owner):
        net = bge.logic.netplay
        # Weirdass workaround for network-enabled objects in the editor
        if owner is None:
            if self.obj is not None:
                owner = bge.logic.getCurrentScene().addObject(self.obj)
                owner['_component'] = self
        elif not net.server and not '_component' in owner:
            logging.warning("{}: You shouldn't directly add network-enabled objects on clients.".format(owner.name))
            owner.endObject()
            return

        self.owner = owner

        self.start()

        if net.server:
            # On the server we spawn components by placing objects in the editor
            # or spawning with scene.addObject
            self.permissions = []
            net.assignComponentID(self)
            self.start_server()

            buff = self.serialize()
            for c in net.clients:
                if c is not None:
                    c.send_reliable(buff)

        else:
            # Clients can only get new network objects from the server
            self.permission = False
            # Setup function defined by serialize will run after construction
            self.start_client()

    def givePermission(self, peer_id):
        if peer_id in self.permissions:
            logging.warning('Client already has access to this component')
            return

        self.permissions.append(peer_id)

        # Notify the client
        table = packer.Table('_permission')
        table.set('id', self.net_id)
        table.set('state', 1)

        buff = packer.to_bytes(table)
        bge.logic.netplay.clients[peer_id].send_reliable(buff)

    def takePermission(self, peer_id):
        if peer_id not in self.permissions:
            # Didn't have permission
            logging.warning('Client did not have access to this component')
            return

        self.permissions.remove(peer_id)

        # Notify the client
        table = packer.Table('_permission')
        table.set('id', self.net_id)
        table.set('state', 0)

        buff = packer.to_bytes(table)
        bge.logic.netplay.clients[peer_id].send_reliable(buff)

    def _permission(self, table):
        if bge.logic.netplay.server:
            logging.warning('Permission flag is not used on the server')
            return

        self.permission = bool(table.get('state'))

    def start(self):
        """
        Called on both client and server
        """
        return

    def start_server(self):
        return

    def update(self):
        """
        Called before update_client and update_server
        """
        return

    def update_client(self):
        return

    def update_server(self):
        return

    def _add_object(self, table):
        print ("Why is this being called")
        # The table is created by self.serialize on the server
        pos = [table.get('x'), table.get('y'), table.get('z')]
        rot = mathutils.Euler((table.get('rot_x'),
                              table.get('rot_y'),
                              table.get('rot_z')))

        self.owner.worldPosition = pos
        self.owner.worldOrientation = rot

    def serialize(self):
        # Runs on the server when the object is spawned or a client connects

        # Builtin table, see definition in host.py
        table = packer.Table('_add_object')

        # Always need to serialize the component ID
        table.set('id', self.net_id)

        # Everything else can be whatever
        pos = self.owner.worldPosition
        table.set('x', pos[0])
        table.set('y', pos[1])
        table.set('z', pos[2])

        rot = self.owner.worldOrientation.to_euler()
        table.set('rot_x', rot[0])
        table.set('rot_y', rot[1])
        table.set('rot_z', rot[2])

        return packer.to_bytes(table)