import asyncio
import getpass
import json
import os
import time
import sys
import websockets
import math
from common import Map

# For testing purposes this script can be run with the following arguments:
#  -test            runs standalone, printing execution times per level and commulatives (CSV compatible, view documentation/ for examples)
#  -level <level>   allows us to specify until which level we desire to run the script (work both in test and paly modes)
# 
# If no arguments are given, script runs as normal, interacting with the server.

level = 57
async def agent_loop(server_address="localhost:8000", agent_name="93444"):
    async with websockets.connect(f"ws://{server_address}/player") as websocket:
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))
        icm = 0
        last_lvl = 0
        maps = []
        moves = []
        while True and last_lvl <= level:
            try:
                # FIXME - Only problem in the code is inside this loop !!
                state = json.loads(
                    await websocket.recv()
                )
                new_grid = state['grid']

                if moves == [] or new_grid.split(" ")[1] not in maps or icm > maps.index(new_grid.split(" ")[1]):
                    map = Map(new_grid)
                    t = SearchTree(map, 'greedy')
                    maps = t.search()
                    tiles = {'empty': map.empty_tile, 'wall': map.wall_tile}
                    moves = move_translator(maps, state['cursor'], tiles)
                    if state['selected'] != '':
                        moves.insert(0, " ")
                
                icm = maps.index(new_grid.split(" ")[1])
                await websocket.send(
                    json.dumps(
                        {"cmd": "key", "key": moves.pop(0)})
                )
                
                # Can't, for the life of me, figure out what it is !!
            except websockets.exceptions.ConnectionClosedOK:
                print("Server has cleanly disconnected us")
                return


def last_move(last_grid, current_grid):
    for i, j in zip(last_grid, current_grid):
        if i != j:
            if i != 'o':
                return i
            else:
                return j
    return ''

class SearchNode:

    
    def __init__(self, state, parent, depth, cost, heuristic):
        self.state = state
        self.parent = parent
        self.depth = depth
        self.cost = cost
        self.heuristic = heuristic

    
    def __str__(self):
        return "no(" + str(self.state) + "," + str(self.parent) + ")"

    
    def __repr__(self):
        return str(self)


class SearchTree:
    def __init__(self, state, strategy='breadth'):
        root = SearchNode(repr(state).split(" ")[1], None, 0, 0, 0)
        self.open_nodes = [root]
        self.strategy = strategy
        self.solution = None
        self.length = None
        self.visited = [root.state]
        self.grid_size = state.grid_size
        self.player_car = state.player_car
        self.wall_tile = state.wall_tile
        self.empty_tile = state.empty_tile
        self.pieces = state.pieces
        self.movements = state.movements

    
    def get_path(self, node):
        if node.parent == None:
            return [node.state]
        path = self.get_path(node.parent)
        path += [node.state]
        return (path)

    
    def search(self):
        while self.open_nodes != []:
            node = self.open_nodes.pop(0)
            player_car_coor = piece_coordinates(node.state, self.player_car)
            if player_car_coor[-1][0] == self.grid_size-1:
                self.solution = node
                self.length = self.solution.depth
                return self.get_path(self.solution)

            lnewnodes = []
            grid = node.state
            for a in self.actions(grid):
                try:
                    newmap = self.move_repr(grid, a[0], a[1])
                    if newmap not in self.visited:
                        player_car_coor = piece_coordinates(
                            newmap, self.player_car)
                        # Heuristic 1 - Player car distance to the finish
                        heuristic = self.grid_size - player_car_coor[-1][0]
                        cost = 0
                        # Heuristic 2 - Number of blocking car
                        player_lane = newmap[player_car_coor[-1][1]*self.grid_size +
                                             player_car_coor[-1][0]+1:(player_car_coor[-1][1]+1)*self.grid_size]
                        heuristic2 = sum(
                            list(map(lambda i: i != self.empty_tile, player_lane)))

                        newnode = SearchNode(
                            newmap, node, node.depth + 1, cost, heuristic + heuristic2)
                        self.visited.append(newmap)
                        lnewnodes.append(newnode)
                except:
                    pass

            self.add_to_open(lnewnodes)

        return None

    
    def add_to_open(self, lnewnodes):
        if self.strategy == 'breadth':
            self.open_nodes.extend(lnewnodes)
        elif self.strategy == 'depth':
            self.open_nodes[:0] = lnewnodes
        elif self.strategy == 'uniform':
            self.open_nodes = sorted(
                self.open_nodes + lnewnodes, key=lambda node: node.cost)
        elif self.strategy == 'greedy':
            self.open_nodes = sorted(
                self.open_nodes + lnewnodes, key=lambda node: node.heuristic)
        elif self.strategy == 'a*':
            self.open_nodes = sorted(
                self.open_nodes + lnewnodes, key=lambda node: node.cost + node.heuristic)

    
    def actions(self, grid):
        actlist = []
        visited = []
        for val in grid:
            if val not in visited and val != self.empty_tile and val != self.wall_tile:
                visited += [val]
                if not (grid.rfind(val) - grid.index(val)) < self.grid_size:
                    actlist += [(val, (0, -1)), (val, (0, 1))]
                else:
                    actlist += [(val, (-1, 0)), (val, (1, 0))]
        return actlist

    
    def move_repr(self, grid, piece: str, direction):
        """Move piece in direction fiven by a vector."""
        if piece == self.wall_tile:
            raise Exception("Blocked piece")

        piece_coord = piece_coordinates(grid, piece)

        horz = (grid.rfind(piece) - grid.index(piece)) < self.grid_size
        if direction[0] != 0 and not horz:
            raise Exception("Can't move sideways")
        if direction[1] != 0 and horz:
            raise Exception("Can't move up-down")

        def sum(a, b):
            return (a[0] + b[0], a[1] + b[1])

        for pos in piece_coord:
            newp = sum(pos, direction)
            if 0 <= newp[0] < self.grid_size and 0 <= newp[1] < self.grid_size:
                if not grid[newp[1]*self.grid_size+newp[0]] in [piece, self.empty_tile]:
                    raise Exception("Blocked piece")
            else:
                raise Exception("Out of the grid")

        newmap = grid
        for pos in piece_coord:
            newmap = newmap[:(pos[1]*self.grid_size)+pos[0]] + \
                self.empty_tile + newmap[(pos[1]*self.grid_size)+pos[0]+1:]

        for pos in piece_coord:
            new_pos = sum(pos, direction)
            newmap = newmap[:(new_pos[1]*self.grid_size)+new_pos[0]] + \
                piece + newmap[(new_pos[1]*self.grid_size)+new_pos[0]+1:]

        return newmap



def index_to_coordinate(charIndex: int, gridSize: int):
    return (int(charIndex % int(math.sqrt(gridSize))), int(charIndex / int(math.sqrt(gridSize))))



def piece_coordinates(grid: str, piece: str):
    return [index_to_coordinate(i, len(grid)) for i in range(len(grid)) if grid[i] == piece]



def move_translator(map_array, cursor, tiles):
    moves = []
    oldPiece = ''
    for old, new in zip(map_array, map_array[1:]):
        newPiece = [i for i, j in zip(old, new) if (i != j and i != tiles['empty'])]
        oldCoord = (int(old.rfind(newPiece[0]) % int(math.sqrt(len(old)))),
                    int(old.rfind(newPiece[0]) / int(math.sqrt(len(old)))))
        newCoord = (int(new.rfind(newPiece[0]) % int(math.sqrt(len(new)))),
                    int(new.rfind(newPiece[0]) / int(math.sqrt(len(new)))))

        dif = []
        # From cursor to piece
        dif.append((oldCoord[0] - cursor[0], oldCoord[1] - cursor[1]))
        # From origin to destiny
        dif.append((newCoord[0] - oldCoord[0], newCoord[1] - oldCoord[1]))

        i = 0
        for (x, y) in dif:
            # If new piece is to be processed and cursor already on top of it -> selects it
            if oldPiece != newPiece and i == 0 and oldPiece != '':
                moves.append(' ')

            if x > 0:
                moves += ('d' * (x))
            elif x < 0:
                moves += ('a' * abs(x))

            if y > 0:
                moves += ('s' * (y))
            elif y < 0:
                moves += ('w' * abs(y))

            if oldPiece != newPiece and i == 0:
                moves.append(' ')

            i += 1

        oldPiece = newPiece
        cursor = newCoord

    return moves



def testing(level):
    with open("levels.txt", "r") as f:
        overall_t = time.time()
        i = 1
        for line in f:
            s = time.time()
            map_grid = Map(line)
            t = SearchTree(map_grid, 'a*')
            maps = t.search()
            tiles = {'empty': map_grid.empty_tile, 'wall': map_grid.wall_tile}
            moves = move_translator(maps, (5,2), tiles)
            print("Level", i)
            [print(m) for m in maps]
            print(moves)
            print(line.split(" ")[0], time.time() - s,
                  time.time()-overall_t, sep=",")
            print()
            if int(level) == i:
                break
            i += 1
        overall = time.time()-overall_t
        print("Overall time", overall, sep=",")
        print("Average time", overall/level, sep=",")


if len(sys.argv) != 1:
    try:
        test = False
        for i in range(1, len(sys.argv)):
            if sys.argv[i] == '-test':
                test = True
            elif sys.argv[i] == '-level':
                level = int(sys.argv[i+1])
        if test:
            testing(level)
            exit()
    except SystemExit:
        exit()
        pass
    except Exception:
        raise Exception("Invalid arguments")

# DO NOT CHANGE THE LINES BELLOW
# You can change the default values using the command line, example:
# $ NAME='arrumador' python3 client.py
loop = asyncio.get_event_loop()
SERVER = os.environ.get("SERVER", "localhost")
PORT = os.environ.get("PORT", "8000")
NAME = os.environ.get("NAME", getpass.getuser())
loop.run_until_complete(agent_loop(f"{SERVER}:{PORT}", NAME))
