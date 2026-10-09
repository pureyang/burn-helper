# /system/main.py for the Claude Buddy badge.
#
# Boots straight into the claude_buddy app. Pressing HOME inside it leaves a
# flag so the next boot shows the stock launcher instead; pressing HOME in any
# other app comes back to claude_buddy. If the app folder is missing this
# behaves exactly like the stock main.py.
import os

MENU_FLAG = "/state/.buddy_menu"
BUDDY = "/system/apps/claude_buddy"


def _menu_requested():
    try:
        os.stat(MENU_FLAG)
    except OSError:
        return False
    try:
        os.remove(MENU_FLAG)
    except OSError:
        pass
    return True


# Eat the wakeup button press to prevent it leaking into the app
badge.poll()

if not _menu_requested() and is_dir(BUDDY):
    launch(BUDDY)

app_to_launch = launch("/system/apps/menu")

# Stopping in Thonny can cause launch("/system/apps/menu") to return None
if app_to_launch is not None:
    # Don't pass menu button presses into the newly launched app
    while badge.pressed() or badge.held() or badge.released():
        badge.poll()
    launch(app_to_launch)

# Catch any exit and reset back to the launcher
reset()
