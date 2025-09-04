from functools import reduce
from enum import Enum
import subprocess
import time
import i3ipc
from time import sleep


PRESETS = {
    "hidden1": [
        {
            "run": ["alacritty", "-T", "thing"],
            "name": "thing",
            "geometry": {"x": 0, "y": 0, "w": 200, "h": 200},
            "scratch": "hidden1",
        },
    ],
    "hidden2": [
        {
            "run": ["alacritty", "-T", "thing2"],
            "name": "thing2",
            "geometry": {"x": 250, "y": 250, "w": 200, "h": 200},
            "scratch": "hidden2",
        },
    ],
    # 
    # 
    #     {
    #         "run": ["/usr/bin/bash", "/home/myo/.config/i3/watcher/script.sh"],
    #         "name": "SystemMonitor",
    #         "geometry": {"x": 10, "y": 10, "w": 400, "h": 1060},
    #         "scratch": "hidden1",
    #         # "skip_startup": False,
    #     },
    # "hidden2": [
        # {
        #     "run": ["alacritty", "-T", "newsboatterm", "-e", "newsboat"],
        #     "name": "newsboatterm",
        #     "geometry": {"x": 420, "y": 10, "w": 1200, "h": 353},
        #     "scratch": "hidden2",
        #     # "skip_startup": True,
        # },
        # {
        #     "run": ["alacritty", "-T", "termusicoverlay", "-e", "termusic"],
        #     "name": "termusicoverlay",
        #     "geometry": {"x": 420, "y": 373, "w": 1200, "h": 696},
        #     "scratch": "hidden2",
        # },
    # ],
    # "hidden3": [
    #     {
    #         "run": ["alacritty", "-T", "todo", "-e", "helix", "~/Desk/todo_/todo.md"],
    #         "name": "todo",
    #         "geometry": {"x": 420, "y": 10, "w": 1200, "h": 1060},
    #         "scratch": "hidden3",
    #     },
    # ],
}


# TODO: make it enum instead
status = 0
LAST_WORKSPACE = None
ALL_APPS = reduce(
    lambda x, y: x + y, PRESETS.values()
)
ALL_NAMES = [app['name'] for app in ALL_APPS]
button_trigger = None

i3 = i3ipc.Connection()


# ========================================================================================



def spawn(targets=None):
    if not targets:
        targets = PRESETS["hidden1"]
    if not cleanup_unneded_instances(i3.get_tree()):
        for app in targets:
            res = subprocess.Popen(app["run"])
            print(res)


def cleanup_unneded_instances(
    tree,
    scratches=None,
    keep=None,
) -> bool:
    if not scratches:
        scratches = PRESETS.keys()
    if not keep:
        keep = []

    scratches_to_cleanup = [PRESETS[item] for item in scratches if item not in keep]

    if not scratches:
        return

    all_apps = reduce(
        lambda x, y: x + y, scratches
    )

    res = True
    for app in all_apps:
        matching = list(
            filter(
                lambda w: w.name
                and w.name == app['name']
                and w.workspace().name not in PRESETS.keys(),
                tree.leaves(),
            )
        )
        if len(matching) > 0:
            for win in matching[1:]:
                win.command("kill")
            # float_and_resize(matching[0], app["geometry"])
            move_to_scratchpad(matching[0], app["scratch"])
        res = False
    return


def float_and_resize(win, geometry):
    win_id = win.id
    i3.command(f"[con_id={win_id}] floating enable")
    i3.command(f"[con_id={win_id}] resize set {geometry['w']} {geometry['h']}")
    i3.command(f"[con_id={win_id}] move position {geometry['x']} {geometry['y']}")


def move_to_scratchpad(win, scratch):
    if scratch == "scratchpad":
        i3.command(f"[con_id={win.id}] move to {scratch}")
    else:
        i3.command(f"[con_id={win.id}] move to workspace {scratch}")


def showup(tree, ws, show_scratches=None, focus_win=None):
    if not show_scratches:
        show_scratches = ["hidden1"]
        all_apps = PRESETS["hidden1"]
    else:
        all_apps = reduce(
            lambda x, y: x + y, [PRESETS[item] for item in show_scratches]
        )

    if resp_if_needed(
        tree,
        all_apps,
    ):
        tree = i3.get_tree()
    for app in all_apps:
        # if app["skip_startup"] and not app["scratch"] == show_scratch and not FULL_OVERLAY_SPAWN:
        #     return
        matching = list(
            filter(lambda w: w.name and w.name == app["name"], tree.leaves())
        )
        if not matching:
            print("ERR: index out of bounds. Check apps health.")
            return
        win = matching[0]
        float_and_resize(win, app["geometry"])
        win.command(f"move container to workspace {ws.name}")
        if focus_win == app["name"]:
            win.command("focus")


def resp_if_needed(tree, targets):
    dead = list(filter(lambda app: not list(filter(lambda w: w.name==app["name"], tree.leaves())), targets))
    if dead:
        spawn(dead)
        sleep(0.5)
        return True


# ========================================================================================


def on_binding(i3conn, event):
    global status, button_trigger
    # 
    # when workpace focused, button_trigger sets to None

    print('~~~~~~~~~~``')
    print(event.binding.command)
    print(status)
    print(button_trigger)
    print('~~~~~~~~~~``')
    match event.binding.command:

        case 'exec --no-startup-id  echo "show_partial_overlay"':
            if status != 0:
                cleanup_unneded_instances(i3.get_tree())
                status = 0
                button_trigger = True
            else:
                status = 1
                cleanup_unneded_instances(i3conn.get_tree(), None, ["hidden1"])
                ws = i3.get_tree().find_focused().workspace()
                showup(i3.get_tree(), ws, ["hidden1"], focus_win="thing")
                button_trigger = True

        case 'exec --no-startup-id  echo "show_overlay_1"':
            if status == 2:
                # cleanup status (current thing opened)
                status = 0
                cleanup_unneded_instances(i3.get_tree(), ["hidden1", "hidden2"])
                button_trigger = True
            else:
                if status != 0:
                    cleanup_unneded_instances(i3conn.get_tree(), None, ["hidden1", "hidden2"])
                status = 2
                ws = i3.get_tree().find_focused().workspace()
                showup(i3.get_tree(), ws, ["hidden1", "hidden2"], "thing2")
                button_trigger = True

        # case 'exec --no-startup-id  echo "show_overlay_2"':
        #     if status == 3:
        #         status = 0
        #         cleanup_unneded_instances(i3.get_tree(), ["hidden1", "hidden3"])
        #         button_trigger = True
        #     else:
        #         if status != 0:
        #             cleanup_unneded_instances(i3conn.get_tree(), None, ["hidden1", "hidden3"])
        #         status = 3
        #         ws = i3.get_tree().find_focused().workspace()
        #         showup(i3.get_tree(), ws, ["hidden1", "hidden3"], "todo")
        #         button_trigger = True

i3.on("binding", on_binding)


def on_window_close(i3conn, event):
    global status
    win = event.container
    if not win.name or not win.name in ALL_NAMES:
        ws = i3.get_tree().find_focused().workspace()
        if status == 0 and not ws.nodes:
            showup(i3.get_tree(), ws, ["hidden1"])
            status = 1
    resp_if_needed(i3conn.get_tree(), ALL_APPS)
    # if not cleanup_unneded_instances(i3.get_tree()):
    #     spawn()
    #     return

i3.on("window::close", on_window_close)



def on_workspace_focus(i3conn, event):
    global LAST_WORKSPACE, status, button_trigger
    ws = event.current
    if ws is None:
        return
    if button_trigger and LAST_WORKSPACE == ws.name:
        button_trigger = None
        LAST_WORKSPACE = ws.name
        return
    if (
        not ws.nodes
        and LAST_WORKSPACE != ws.name
    ):
        showup(i3.get_tree(), ws, ["hidden1"])
        status = 1
    else:
        cleanup_unneded_instances(i3.get_tree())
        status = 0
    LAST_WORKSPACE = ws.name
    
i3.on("workspace::focus", on_workspace_focus)


def on_new_windnow(i3conn, event):
    global status
    win = event.container
    if win.name and win.name in ALL_NAMES:
        if cleanup_unneded_instances(i3.get_tree()):
            return
    if status == 0:
        return
    ws = win.workspace()
    if ws and ws.nodes:
        status = 0
        return cleanup_unneded_instances(i3.get_tree())
    if win.floating != "user_on" and win.floating != "auto_on":
        status = 0
        return cleanup_unneded_instances(i3.get_tree())

i3.on("window::new", on_new_windnow)


def on_window_floating(i3conn, event):
    win = event.container
    ws = i3.get_tree().find_focused().workspace()
    if ws and ws.nodes:
        cleanup_unneded_instances(i3.get_tree())
    elif win.floating == "user_on":
        showup(i3.get_tree(), ws)
    else:
        cleanup_unneded_instances(i3.get_tree())

i3.on("window::floating", on_window_floating)

 
# ========================================================================================

spawn(
    ALL_APPS
)
i3.main()
