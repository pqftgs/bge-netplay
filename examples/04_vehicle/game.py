import time
import netplay
from userinput import InputSystem

import components  # Must be imported for components to register

import random


class Game:
    def __init__(self, owner, mode=netplay.MODE_SERVER):
        self.owner = owner

        ## TODO - load from disk
        self.config = {}
        self.config['master'] = {}
        self.config['master']['hostname'] = ''
        self.config['master']['port'] = 64738

        self.systems = {}

        ## Initialize core systems.  These will tic every logic frame.
        if mode == netplay.MODE_SERVER or mode == netplay.MODE_OFFLINE:
            self.systems['Server'] = netplay.Server(self, mode=mode)
            self.systems['Component'] = netplay.ServerComponentSystem(self)

            server = self.systems['Server']
            server.onConnect = self.Server_onConnect
            server.onDisconnect = self.Server_onDisconnect

        else:
            self.systems['Client'] = netplay.Client(self, server_ip=owner['ip'])
            self.systems['Component'] = netplay.ClientComponentSystem(self)

        self.systems['Input'] = InputSystem(self)

        self.last_time = time.monotonic()

        # Spawn things @ server start
        if mode == netplay.MODE_SERVER or mode == netplay.MODE_OFFLINE:
            """
            c = self.systems['Component']

            p = c.spawnComponent('Player', _pos_z=1.0)
            self.systems['Input'].setTarget(p)

            for i in range(0, 20):
                x = random.uniform(-15.0, 15.0)
                y = random.uniform(-15.0, 15.0)
                c.spawnComponent('Dynamic_Cube', _pos_x=x, _pos_y=y, _pos_z=10.0)

                x = random.uniform(-15.0, 15.0)
                y = random.uniform(-15.0, 15.0)
                c.spawnComponent('Rigid_Cube', _pos_x=x, _pos_y=y, _pos_z=10.0)
            """

    def Server_onConnect(self, client_id):
        # Spawn a player component and give input permission
        c = self.systems['Component']
        p = c.spawnComponent('Car', _pos_z=2.0)
        p.givePermission(client_id)

    def Server_onDisconnect(self, client_id):
        # Find the player component that matches the ID
        c = self.systems['Component']
        for comp in c.active_components_:
            if comp is not None:
                if comp.hasPermission(client_id):
                    # Destroy the player component
                    c.freeComponent(comp)
                    return

    def update(self):
        now = time.monotonic()
        dt = min(now - self.last_time, 0.2)
        self.last_time = now

        # Update the systems
        for system in list(self.systems.values()):
            system.update(dt)


def main(cont):
    owner = cont.owner

    game = owner.get('Game', None)
    if game is None:
        if 'init' in owner:
            return
        owner['init'] = True
        game = Game(owner, mode=owner['mode'])
        owner['Game'] = game

    game.update()
