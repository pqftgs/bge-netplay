import time
import random
import bge
import netplay
from userinput import InputSystem

import components  # Must be imported for components to register
components

# Limit 255x255
SIZE_X = 10
SIZE_Y = 10
MINES = 10


class Game:
    def __init__(self, owner, mode=netplay.MODE_OFFLINE):
        self.owner = owner

        ## TODO - load from disk
        self.config = {}
        self.config['master'] = {}
        self.config['master']['hostname'] = ''
        self.config['master']['port'] = 64738

        self.systems = {}

        self.timer = None  # We'll store the game timer here

        self.board = None  # We'll store the game board here

        ## Initialize core systems.  These will tic every frame
        if mode == netplay.MODE_SERVER or mode == netplay.MODE_OFFLINE:
            self.systems['Server'] = netplay.Server(self, mode=mode)
            self.systems['Component'] = netplay.ServerComponentSystem(self)

            serversystem = self.systems['Server']
            serversystem.onConnect = self.Server_onConnect
            serversystem.onDisconnect = self.Server_onDisconnect

            """
            # Spawn blocks and add timer
            self.generate()
            """
            components.SPAWN_BOARD(self.systems['Component'],
                    SIZE_X, SIZE_Y, MINES)

            components.SPAWN_TIMER(self.systems['Component'])
        else:
            self.systems['Client'] = netplay.Client(self,
                    server_ip=owner['ip'])
            self.systems['Component'] = netplay.ClientComponentSystem(self)

        self.systems['Input'] = InputSystem(self)

        if mode == netplay.MODE_SERVER or mode == netplay.MODE_OFFLINE:
            c = self.systems['Component']
            #p = c.spawnComponent('Player')
            p = components.SPAWN_PLAYER(c, 'TheHost')
            self.systems['Input'].setTarget(p)

        ## Used to determine frame time delta.
        self.last_time = time.monotonic()

        self.init = True

    def reset(self):
        # Yellow button pressed on server
        print ("Resetting board")

        c = self.systems['Component']
        for comp in c.active_components_:
            if comp is not None:
                if type(comp) is components.Player:
                    comp.setAttribute('current_block_x', 0)
                    comp.setAttribute('current_block_y', 0)

        c.freeComponent(self.board)
        self.board = None
        c.freeComponent(self.timer)
        self.timer = None

        components.SPAWN_BOARD(c, SIZE_X, SIZE_Y, MINES)
        components.SPAWN_TIMER(c)

    def Server_onConnect(self, client_id):
        # Spawn a player component and give input permission
        c = self.systems['Component']
        p = components.SPAWN_PLAYER(c, 'AClient')
        p.givePermission(client_id)

    def Server_onDisconnect(self, client_id):
        # Find the player component that matches the client ID
        c = self.systems['Component']
        for comp in c.active_components_:
            if comp is not None:
                if comp.hasPermission(client_id):
                    # Destroy the player component
                    c.freeComponent(comp)
                    return

    def update(self):
        # Determine delta time
        now = time.monotonic()
        dt = now - self.last_time
        self.last_time = now

        # Update the systems
        for system in list(self.systems.values()):
            system.update(dt)


def resetButton(cont):
    if cont.sensors['click'].positive and cont.sensors['over'].positive:
        owner = cont.owner
        game = owner.get('Game', None)
        if game is not None:
            if game.systems['Component'].hostmode == 'server':
                game.reset()


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


if __name__ == '__main__':
    main(bge.logic.getCurrentController())
