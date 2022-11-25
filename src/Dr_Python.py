"""
Starting Template

Once you have learned how to use classes, you can begin your program with this
template.

If Python and Arcade are installed, this example can be run from the command line with:
python -m arcade.examples.starting_template
"""

import arcade

ZOOM_FACTOR = 2
SCREEN_WIDTH = int(1920/ZOOM_FACTOR)
SCREEN_HEIGHT = int(1352/ZOOM_FACTOR)
SCREEN_TITLE = "Dr Python"
MOVEMENT_SPEED = 5

class MyGame(arcade.Window):
    """
    Main application class.

    NOTE: Go ahead and delete the methods you don't need.
    If you do need a method, delete the 'pass' and replace it
    with your own code. Don't leave 'pass' in this program.
    """

    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        self.background = None
        arcade.set_background_color(arcade.color.AMAZON)
        self.center_window()
        self.player_list = None
        self.wall_list = None
        # If you have sprite lists, you should create them here,
        # and set them to None

    def setup(self):
        """ Set up the game and initialize the variables. """

        # Load the background image. Do this in the setup so we don't keep reloading it all the time.
        # Image from:
        # https://wallpaper-gallery.net/single/free-background-images/free-background-images-22.html
        self.background = arcade.load_texture("../art/background.png")
        self.player_list = arcade.SpriteList()
        self.wall_list = arcade.SpriteList()
        self.player_sprite = arcade.Sprite("../art/pill-cel_cel.png", 1)
        self.player_sprite.scale = 1/ZOOM_FACTOR
        self.player_sprite.center_x=988/ZOOM_FACTOR
        self.player_sprite.center_y = 1000/ZOOM_FACTOR
        self.player_list.append(self.player_sprite)

    def on_key_press(self, key, modifiers):
        """Called whenever a key is pressed. """
        print(self.player_sprite.bottom)

        if key == arcade.key.UP:
            self.player_sprite.change_y = MOVEMENT_SPEED
        elif key == arcade.key.DOWN:
            self.player_sprite.change_y = -MOVEMENT_SPEED
        elif key == arcade.key.LEFT:
            self.player_sprite.change_x = -MOVEMENT_SPEED
        elif key == arcade.key.RIGHT:
            self.player_sprite.change_x = MOVEMENT_SPEED

    def on_key_release(self, key, modifiers):
        """Called when the user releases a key. """

        if key == arcade.key.UP or key == arcade.key.DOWN:
            self.player_sprite.change_y = 0
        elif key == arcade.key.LEFT or key == arcade.key.RIGHT:
            self.player_sprite.change_x = 0


    def on_update(self, delta_time):
        """ Movement and game logic """
        # Move the player
        if self.player_sprite.left <= 718/ZOOM_FACTOR:
            self.player_sprite.change_x = 0
            self.player_sprite.left = 719/ZOOM_FACTOR
        if self.player_sprite.right >= 1258 / ZOOM_FACTOR:
            self.player_sprite.change_x = 0
            self.player_sprite.right = 1257 / ZOOM_FACTOR
        if self.player_sprite.bottom <= 400 / ZOOM_FACTOR:
            self.player_sprite.change_y = 0
            self.player_sprite.bottom = 396 / ZOOM_FACTOR

        self.player_list.update()

    def on_draw(self):
        """
        Render the screen.
        """

        # This command should happen before we start drawing. It will clear
        # the screen to the background color, and erase what we drew last frame.
        self.clear()
        # Draw the background texture
        arcade.draw_lrwh_rectangle_textured(0, 0,
                                            SCREEN_WIDTH, SCREEN_HEIGHT,
                                            self.background)
        self.wall_list.draw()
        self.player_list.draw()
        # Call draw() on all your sprite lists below


def main():
    """ Main function """
    game = MyGame(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    game.setup()
    arcade.run()


if __name__ == "__main__":
    main()