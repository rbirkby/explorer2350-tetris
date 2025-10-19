# Pimoroni Explorer2350 port by Richard Birkby
# Inspired by the Tildagon port by Richard Birkby - https://github.com/rbirkby/TildagonTetris
# Inspired by the Arduino Microview port by Richard Birkby - https://github.com/rbirkby/ArduinoTetris
# Inspired by the Raspberry Pi Pico port by Richard Birkby - https://github.com/rbirkby/picotetris
# Original JavaScript implementation - Jake Gordon - https://github.com/jakesgordon/javascript-tetris
# MIT licenced

import random
import time

from explorer import BLACK, BLUE, CYAN, GREEN, MAGENTA, RED, WHITE, YELLOW, button_c, button_y, button_z, display

###########################################################################
# base helper methods
###########################################################################

last_button_press = 0


# from https://github.com/pimoroni/explorer/blob/main/examples/main.py#L39
def debounce(button, debounce_ms=200):
    """Simple button debounce function."""
    global last_button_press  # noqa: PLW0603
    try:
        value = button.value() == 0
        if value and time.ticks_ms() - last_button_press > debounce_ms:
            last_button_press = time.ticks_ms()
            return True
    except NameError:
        last_button_press = time.ticks_ms()
    return False


WIDTH, HEIGHT = display.get_bounds()
COURT_X_OFFSET = 8
COURT_Y_OFFSET = 2

################
# Game constants
################
DIR = {"UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3, "MIN": 0, "MAX": 3}
speed = {"start": 0.6, "decrement": 0.005, "min": 0.1}
nx = 15  # width of tetris court (in blocks)
ny = 15  # height of tetris court (in blocks)
nu = 3  # width/height of upcoming preview (in blocks)


class Tetris:
    ###########################################
    # game variables (initialized during reset)
    ###########################################
    dx = (0.6 * WIDTH) / nx  # pixel size of a single tetris block
    dy = (0.75 * HEIGHT) / ny
    blocks = []  # 2 dimensional array (nx*ny) representing tetris court - either empty block or occupied by a 'piece'
    playing = True  # true|false - game is in progress
    dt = 0  # time since starting this game
    current = None  # the current and next piece
    next_piece = None
    score = 0  # the current score
    vscore = 0  # the currently displayed score (it catches up to score in small chunks - like a spinning slot machine)
    rows = 0  # number of completed rows in the current game
    step = 0  # how long before current piece drops by 1 row
    lost = False
    notification = None

    ###########################################################################
    # tetris pieces
    #
    # blocks: each element represents a rotation of the piece (0, 90, 180, 270)
    #         each element is a 16 bit integer where the 16 bits represent
    #         a 4x4 set of blocks, e.g. j.blocks[0] = 0x44C0
    #
    #             0100 = 0x4 << 3 = 0x4000
    #             0100 = 0x4 << 2 = 0x0400
    #             1100 = 0xC << 1 = 0x00C0
    #             0000 = 0x0 << 0 = 0x0000
    #                               ------
    #                               0x44C0
    #
    ###########################################################################

    i = {"size": 4, "blocks": [0x0F00, 0x2222, 0x00F0, 0x4444], "color": CYAN}
    j = {"size": 3, "blocks": [0x44C0, 0x8E00, 0x6440, 0x0E20], "color": BLUE}
    l = {"size": 3, "blocks": [0x4460, 0x0E80, 0xC440, 0x2E00], "color": MAGENTA}
    o = {"size": 2, "blocks": [0xCC00, 0xCC00, 0xCC00, 0xCC00], "color": MAGENTA}
    s = {"size": 3, "blocks": [0x06C0, 0x8C40, 0x6C00, 0x4620], "color": GREEN}
    t = {"size": 3, "blocks": [0x0E40, 0x4C40, 0x4E00, 0x4640], "color": YELLOW}
    z = {"size": 3, "blocks": [0x0C60, 0x4C80, 0xC600, 0x2640], "color": RED}

    ##################################################
    # do the bit manipulation and iterate through each
    # occupied block (x,y) for a given piece
    ##################################################

    def each_block(self, piece_type, x, y, direction, fn):
        """Execute a function for each block in a piece."""
        blocks = piece_type["blocks"][direction]
        bit = 0x8000
        row = 0
        col = 0
        while bit > 0:
            if blocks & bit:
                fn(x + col, y + row)
            bit = bit >> 1
            col += 1
            if col == 4:
                col = 0
                row += 1

    ######################################################
    # check if a piece can fit into a position in the grid
    ######################################################

    def occupied(self, piece_type, x, y, direction):
        """Check if a piece is occupying a position in the grid."""
        result = False

        def is_occupied(x, y):
            if (x < 0) or (x >= nx) or (y < 0) or (y >= ny) or self.get_block(x, y):
                nonlocal result
                result = True

        self.each_block(piece_type, x, y, direction, is_occupied)
        return result

    def unoccupied(self, piece_type, x, y, direction):
        return not self.occupied(piece_type, x, y, direction)

    ##########################################
    # start with 4 instances of each piece and
    # pick randomly until the 'bag is empty'
    ##########################################

    def random_piece(self):
        pieces = [
            self.i,
            self.i,
            self.i,
            self.i,
            self.j,
            self.j,
            self.j,
            self.j,
            self.l,
            self.l,
            self.l,
            self.l,
            self.o,
            self.o,
            self.o,
            self.o,
            self.s,
            self.s,
            self.s,
            self.s,
            self.t,
            self.t,
            self.t,
            self.t,
            self.z,
            self.z,
            self.z,
            self.z,
        ]
        idx = random.randint(0, len(pieces) - 1)
        piece = pieces[idx]
        return {
            "type": piece,
            "dir": DIR["UP"],
            "x": random.randint(0, nx - piece["size"]),
            "y": 0,
            "color": piece["color"],
        }

    ##################################
    # GAME LOOP
    ##################################

    def setup(self):
        display.set_backlight(1)
        display.set_pen(BLACK)

        display.clear()
        display.update()

        self.reset()

    def loop(self):
        ticks = time.ticks_ms()

        if debounce(button_c):
            self.on_left_button()
        if debounce(button_z):
            self.on_right_button()
        if debounce(button_y):
            self.on_rotate_button()

        if ticks % 60 == 0:
            self.draw()

            if self.playing and (ticks % 300 == 0):
                self.drop()

                if self.lost:
                    self.draw()
                    time.sleep(1000)

    def on_left_button(self):
        if self.lost:
            self.reset()

        self.move(DIR["LEFT"])

    def on_right_button(self):
        if self.lost:
            self.reset()

        self.move(DIR["RIGHT"])

    def on_rotate_button(self):
        if self.lost:
            self.reset()

        self.rotate()

    ##################################
    # GAME LOGIC
    ##################################

    def play(self):
        self.playing = True

    def lose(self):
        self.playing = False
        self.lost = True

    def set_visual_score(self, n=None):
        self.vscore = n if n is not None else self.score

    def set_score(self, n):
        self.score = n
        self.set_visual_score(n)

    def add_score(self, n):
        self.score += n

    def clear_score(self):
        self.set_score(0)

    def clear_rows(self):
        self.set_rows(0)

    def set_rows(self, n):
        self.rows = n
        # step = max(speed['min'], speed['start'] - (speed['decrement'] * rows))
        self.step = 500

    def add_rows(self, n):
        self.set_rows(self.rows + n)

    def get_block(self, x, y):
        if self.blocks and x < len(self.blocks) and y < len(self.blocks[x]):
            return self.blocks[x][y]
        return None

    def set_block(self, x, y, piece_type):
        if x >= len(self.blocks):
            self.blocks.extend([[] for _ in range(x - len(self.blocks) + 1)])
        if y >= len(self.blocks[x]):
            self.blocks[x].extend([None for _ in range(y - len(self.blocks[x]) + 1)])
        self.blocks[x][y] = piece_type

    def clear_blocks(self):
        self.blocks.clear()

    def reset(self):
        self.dt = 0
        self.clear_blocks()
        self.clear_rows()
        self.clear_score()
        self.current = self.random_piece()
        self.next_piece = self.random_piece()
        self.lost = False
        self.notification = None

    def move(self, direction):
        assert self.current is not None

        x = self.current["x"]
        y = self.current["y"]
        if direction == DIR["RIGHT"]:
            x += 1
        elif direction == DIR["LEFT"]:
            x -= 1
        elif direction == DIR["DOWN"]:
            y += 1
        if self.unoccupied(self.current["type"], x, y, self.current["dir"]):
            self.current["x"] = x
            self.current["y"] = y
            return True

        return False

    def rotate(self):
        assert self.current is not None

        newdir = DIR["MIN"] if self.current["dir"] == DIR["MAX"] else self.current["dir"] + 1
        if self.unoccupied(self.current["type"], self.current["x"], self.current["y"], newdir):
            self.current["dir"] = newdir

    def drop(self):
        if not self.move(DIR["DOWN"]):
            self.add_score(10)
            self.drop_piece()
            self.remove_lines()
            self.current = self.next_piece
            self.next_piece = self.random_piece()

            assert self.current is not None

            if self.occupied(self.current["type"], self.current["x"], self.current["y"], self.current["dir"]):
                self.lose()

    def drop_piece(self):
        assert self.current is not None

        self.each_block(
            self.current["type"],
            self.current["x"],
            self.current["y"],
            self.current["dir"],
            lambda x, y: self.set_block(x, y, self.current["type"] if self.current is not None else None),
        )

    def remove_lines(self):
        """Check for and remove completed lines."""
        n = 0
        for y in range(ny - 1, -1, -1):
            complete = True
            for x in range(nx):
                if not self.get_block(x, y):
                    complete = False
                    break
            if complete:
                self.remove_line(y)
                y += 1
                n += 1
        if n > 0:
            self.add_rows(n)
            self.add_score(100 * 2 ** (n - 1))

    def remove_line(self, n):
        for y in range(n, 0, -1):
            for x in range(nx):
                self.set_block(x, y, self.get_block(x, y - 1))

    ##################################
    # RENDERING
    ##################################

    def draw(self):
        self.draw_court()
        self.draw_next()
        self.draw_score()
        self.draw_rows()
        self.remove_lines()

        display.update()

    def draw_court(self):
        """Draw the tetris court and the current piece."""
        assert self.current is not None
        display.set_pen(BLACK)
        display.clear()

        if self.playing:
            self.draw_piece(
                self.current["type"],
                self.current["x"] + COURT_X_OFFSET,
                self.current["y"] + COURT_Y_OFFSET,
                self.current["dir"],
            )

        display.set_pen(WHITE)

        for y in range(ny):
            for x in range(nx):
                block = self.get_block(x, y)
                if block:
                    self.draw_block(x + COURT_X_OFFSET, y + COURT_Y_OFFSET, block["color"])

        display.set_pen(GREEN)
        left = int(COURT_X_OFFSET * self.dx)
        top = int(COURT_Y_OFFSET * self.dy)
        right = int((COURT_X_OFFSET + nx) * self.dx)
        bottom = int((ny + COURT_Y_OFFSET) * self.dy)

        display.line(left, top, left, bottom)
        display.line(left, bottom, right, bottom)
        display.line(right, bottom, right, top)
        display.line(right, top, left, top)

    def draw_next(self):
        assert self.next_piece is not None
        direction = DIR["RIGHT"] if self.next_piece["type"] in (self.z, self.i, self.s, self.z, self.t) else DIR["UP"]
        self.draw_piece(self.next_piece["type"], 1, 6, direction)

    def draw_score(self):
        display.set_pen(WHITE)
        display.text(str(self.score), int(self.dx / 2), int(self.dy / 2), 240, 3)

    def draw_rows(self):
        display.set_pen(WHITE)
        display.text(str(self.rows), int(self.dx / 2), 30)

    def draw_piece(self, piece_type, x, y, direction):
        self.each_block(piece_type, x, y, direction, lambda x, y: self.draw_block(x, y, piece_type["color"]))

    def draw_block(self, x, y, color):
        display.set_pen(color)
        display.rectangle(int(x * self.dx), int(y * self.dy), int(self.dx), int(self.dy))


_game = Tetris()

_game.setup()
while True:
    _game.loop()
