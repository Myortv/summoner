from functools import reduce
from enum import Enum
import subprocess
import time
import i3ipc
from time import sleep


APP_CMD = {
    "SystemMonitor": {
        "run": ['bash', "/home/myo/script.sh"],
        "name": "SystemMonitor",
        "geometry": {
            "x": 10, "y": 10, "w": 400, "h": 1060
        },
        "scratch": "hidden1",
        # "skip_startup": False,
    },
    "newsboatterm":{
        "run": ['alacritty', '-T', 'newsboatterm', '-e', 'newsboat'],
        "name": "newsboatterm",
        "geometry": {
            "x": 420, "y": 10, "w": 1200, "h": 353
        },
        "scratch": "hidden2",
        # "skip_startup": True,
    },
    "termusicoverlay":{
        "run": ['alacritty', '-T', 'termusicoverlay', '-e', 'termusic'],
        "name": "termusicoverlay",
        "geometry": {
            "x": 420, "y": 373, "w": 1200, "h": 696
        },
        "scratch": "hidden2",
        # "skip_startup": True,
    },
    "todo":{
        "run": ['alacritty', '-T', 'todo', '-e', 'helix', '~/todo/todo'],
        "name": "todo",
        "geometry": {
            "x": 420, "y": 373, "w": 1200, "h": 696
        },
        "scratch": "hidden3",
        # "skip_startup": True,
    },    
}

def gen_app_list_by_scratches():
    res = dict()
    for item in APP_CMD.values():
        if res.get(item["scratch"]):
            res[item["scratch"]].append(item)
        else:
            res[item["scratch"]] = [item]
    return res
            

APP_NAMES = APP_CMD.keys()
APPS_BY_SCRATCHES = gen_app_list_by_scratches()
SCRATCHES = {item["scratch"] for item in APP_CMD.values()}
LAST_WORKSPACE = None

i3 = i3ipc.Connection()

is_stashed = True

class Status(Enum):
    stashed=0
    hidden1=1
    hidden2=2
    hidden3=3

overlay_status = Status(0)

toggled = False
# stashed_focus_hist = [True, True]

def float_and_resize(win, geometry):
    win_id = win.id
    i3.command(f"[con_id={win_id}] floating enable")
    i3.command(f"[con_id={win_id}] resize set {geometry['w']} {geometry['h']}")
    i3.command(f"[con_id={win_id}] move position {geometry['x']} {geometry['y']}")


def cleanup_unneded_instances(
    tree,
    scratches=None,
) -> bool:
    print("======= cleanup")
    print("scratches", scratches)
    if not scratches:
        scratches = list(SCRATCHES)

    all_apps = reduce(lambda x, y: x + y, [APPS_BY_SCRATCHES[item] for item in scratches])
    print("all apps", all_apps)

    res = True
    for name in APP_NAMES:
        matching = list(filter(lambda w: w.workspace() and w.workspace().name not in SCRATCHES, search(tree, name)))
        if len(matching) > 0:
            for  win in matching[1:]:
                win.command('kill')
            float_and_resize(matching[0], APP_CMD[name]["geometry"])
            move_to_scratchpad(matching[0], APP_CMD[name]['scratch'])
        res = False
    return


def search(tree, name):
    return filter(lambda w: w.name and w.name == name, tree.leaves())
    
def resp_if_needed(tree, targets):
    # dead = gather_dead(
    #     tree,
    #     targets
    # )
    dead = filter(
        lambda app: not all(search(tree, app["name"])), targets
    )
    if dead:
        spawn(dead)
        sleep(0.5)
        return True

def gather_dead(tree, targets):
    res = list()
    for app in targets:
        if not list(search(tree, app["name"])):
            res.append(app)
    return res

    
def cleanup(
    tree,
    name,
) -> bool:
    matching = list(filter(lambda w: w.workspace() and w.workspace().name not in SCRATCHES, search(tree, name)))
    if len(matching) > 0:
        for  win in matching[1:]:
            win.command('kill')
        float_and_resize(matching[0], APP_CMD[name]["geometry"])
        move_to_scratchpad(matching[0], APP_CMD[name]['scratch'])
        global overlay_status
        overlay_status = Status(0)
        return True
    return False

def move_to_scratchpad(win, scratch):
    if scratch == "scratchpad":
        i3.command(f'[con_id={win.id}] move to {scratch}')
    else:
        i3.command(f'[con_id={win.id}] move to workspace {scratch}')
    

def on_window_close(i3conn, event):
    win = event.container
    if not win.name or not win.name in APP_NAMES:
        ws = i3.get_tree().find_focused().workspace()
        if overlay_status == Status.stashed and not ws.nodes:
            showup(i3.get_tree(), ws)
    # resp_if_needed(i3conn.get_tree())
    # if not cleanup_unneded_instances(i3.get_tree()):
    #     spawn()
    #     return

i3.on("window::close", on_window_close)

def showup(tree, ws, show_scratches=None, focus_win=None):
    print('==== showup')
    print('show scratches', show_scratches)
    if not show_scratches:
        show_scratches = ['hidden1']
        all_apps = APPS_BY_SCRATCHES['hidden1']
    else:
        all_apps = reduce(lambda x, y: x + y,[APPS_BY_SCRATCHES[item] for item in show_scratches])
        
    # global overlay_status
    # overlay_status = Status()
    if resp_if_needed(
        tree,
        all_apps,
    ):
        tree = i3.get_tree()
    for app in all_apps:
        # if app["skip_startup"] and not app["scratch"] == show_scratch and not FULL_OVERLAY_SPAWN:
        #     return
        matching = list(filter(lambda w: w.name and w.name == app["name"], tree.leaves()))
        win = matching[0]
        float_and_resize(win, app['geometry'])
        win.command(f'move container to workspace {ws.name}')
        if focus_win == app["name"]:
            win.command('focus')


def on_workspace_focus(i3conn, event):
    print('========== focus ')
    global LAST_WORKSPACE, overlay_status
    ws = event.current
    if ws is None:
        return
    if (
        not ws.nodes
        and ws.name != LAST_WORKSPACE
        and overlay_status == Status.stashed
    ):
        showup(i3.get_tree(), ws)
    else:
        cleanup_unneded_instances(i3.get_tree())
    LAST_WORKSPACE = ws.name
    overlay_shown = False
    overlay_shown2 = False

    
i3.on("workspace::focus", on_workspace_focus)
    

def on_new_windnow(i3conn, event):
    win = event.container
    if win.name and win.name in APP_NAMES:
        if cleanup_unneded_instances(i3.get_tree()):
            return
    if overlay_status == Status.stashed:
        return
    ws = win.workspace()
    if ws and ws.nodes:
        return cleanup_unneded_instances(i3.get_tree())
    if win.floating != "user_on" and win.floating != "auto_on":
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

def clean_other_scratches(tree, keep=None):
    if not keep:
        keep={"hidden1"}
    cleanup_unneded_instances(
        tree,
        list(SCRATCHES - keep)
    )

def on_binding(i3conn, event):
    global overlay_status
    match event.binding.command:
        case 'exec --no-startup-id  echo "show_partial_overlay"':
            if overlay_status == Status.hidden1:
                cleanup_unneded_instances(
                    i3.get_tree(),
                    ["hidden1"]
                )
                overlay_status = Status(0)
            else:
                ws = i3.get_tree().find_focused().workspace()
                showup(i3.get_tree(), ws, ['hidden1'], focus_win="SystemMonitor")
        case 'exec --no-startup-id  echo "show_overlay_1"':
            if overlay_status == Status.hidden2:
                overlay_status = Status(0)
                cleanup_unneded_instances(
                    i3.get_tree(),
                    ["hidden1", 'hidden2']
                )
            else:
                clean_other_scratches(i3conn.get_tree(), {"hidden1", "hidden2"})
                ws = i3.get_tree().find_focused().workspace()
                showup(i3.get_tree(), ws, ['hidden1', 'hidden2'], "SystemMonitor")
        case 'exec --no-startup-id  echo "show_overlay_2"':
            if overlay_status == Status.hidden3:
                overlay_status = Status(0)
                cleanup_unneded_instances(i3.get_tree(), ["hidden1", "hidden3"])
            else:
                clean_other_scratches(i3conn.get_tree(), {"hidden1", "hidden3"})
                ws = i3.get_tree().find_focused().workspace()
                showup(i3.get_tree(), ws, ['hidden1', 'hidden3'], "todo")

i3.on("binding", on_binding)

def spawn(targets=None):
    if not targets:
        targets = APP_CMD.values()
    if not cleanup_unneded_instances(i3.get_tree()):
        for app in targets:
            res = subprocess.Popen(app["run"])
            print(res)




    # # Wait and find its window
    # for _ in range(50):
    #     time.sleep(0.1)
    #     for win in i3.get_tree().leaves():
    #         if APP_MARK in win.marks:
    #             return  # already marked
    #     # Find unmarked new window in focused workspace
    #     new_win = [
    #         w for w in focused_ws.leaves()
    #         if APP_MARK not in w.marks
    #     ]
    #     if new_win:
    #         float_and_resize(new_win[0].id)
    #         return

# def move_to_scratch_if_other_windows():
#     ws = i3.get_tree().find_focused().workspace()
#     app_win = next((w for w in ws.leaves() if APP_MARK in w.marks), None)
#     if not app_win:
#         return
#     others = [w for w in ws.leaves() if w.id != app_win.id]
#     if others:
#         i3.command(f"[con_mark={APP_MARK}] move scratchpad")

# def kill_duplicate_instances():
#     app_windows = [w for w in i3.get_tree().leaves() if APP_MARK in w.marks]
#     if len(app_windows) <= 1:
#         return
#     # Keep one, kill others
#     keep_id = app_windows[0].id
#     for w in app_windows[1:]:
#         i3.command(f"[con_id={w.id}] kill")

# def on_window_new(i3conn, e):
#     move_to_scratch_if_other_windows()
#     kill_duplicate_instances()

# spawn_and_mark_app()

# i3.on("window::new", on_window_new)
# i3.on('workspace::focus', on_workspace_focus)

spawn()
i3.main()
