import logging
import subprocess
import time
import i3ipc
import argparse


from typing import Dict, Optional, List, Any
from functools import reduce
from itertools import accumulate
from enum import Enum
from time import sleep


from dataclasses import dataclass, field


@dataclass
class Window:
    run: list | None  # command to run (list of arguments) or None
    geometry: Dict[str, int]  # dict like {"x": 0, "y": 0, "w": 200, "h": 200}
    window_name: str  # name of the window spawned from run command
    workspace: Optional[str | int] = "w_hidden"  # home workspace
    skip_spawn: Optional[bool] = False  # do not spawn this window. Skips spawn step
    skip_init: Optional[bool] = False  # do not init this window (initial state snapshot, position, set mode, etc). Skips init step
    steal_focus: Optional[bool] = False  # should this window steal focus. If multiple set in one layout, last one will steal focus
    restore_to_initial_state: Optional[bool] = False  # if set, window will catch it current state and try to restore to this state instead of hiding

    _initial_state_snapshot: Optional[Any] = None  # internal variable for initial window state to return to

    def __hash__(self):
        return hash(self.window_name)

    def __eq__(self, o):
        if not isinstance(o, Window):
            raise ValueError("compare only with window")
        return self.window_name == o.window_name


@dataclass
class Layout:
    windows: List[Window]
    close_layout_on: Optional[List[str]] = field(default_factory=list())
    # layout_command: str


# Ideally, first layout, which used to showup on empty workspaces
# should not contain any focus stealing windows
# because default layout is shown on workspace with floating windows as well
# and stealing focus in this case can be annoying
# on the other hand, sub-layouts should have focus stealing on apps, that
# actually interactable, because it is usually expected behaviour

LAYOUTS = {
    'exec --no-startup-id  echo "show_system_monitor"': Layout(
        windows=[
            Window(
                run=["/home/myo/sources/system_monitor/run.sh"],
                geometry={"x": 50, "y": 50, "w": 400, "h": 1000},
                window_name="SystemMonitor",
            ),
            Window(
                run=["alacritty", "-T", "w_todo", "-e", "todo_output.sh", "/home/myo/Desk/todo_/todo.md", "22"],
                geometry={"x": 500, "y": 50, "w": 900, "h": 350},
                window_name="w_todo",
            ),
        ],
        close_layout_on=[
            'exec --no-startup-id  echo "show_system_monitor"',
        ]
    ),
    'exec --no-startup-id  echo "show_newsboat"': Layout(
        windows=[
            Window(
                run=["/home/myo/sources/system_monitor/run.sh"],
                geometry={"x": 50, "y": 50, "w": 400, "h": 1000},
                window_name="SystemMonitor",
            ),
            Window(
                run=["alacritty", "-T", "w_todo_short", "-e", "todo_output.sh", "/home/myo/Desk/todo_/todo.md", "3"],
                geometry={"x": 500, "y": 50, "w": 1100, "h": 100},
                window_name="w_todo_short",
            ),
            Window(
                run=["alacritty", "-T", "w_newsboat", "-e", "newsboat"],
                geometry={"x": 500, "y": 175, "w": 1100, "h": 350},
                window_name="w_newsboat",
            ),
            Window(
                run=["alacritty", "-T", "w_termusic", "-e", "termusic"],
                geometry={"x": 500, "y": 550, "w": 1100, "h": 500},
                window_name="w_termusic",
                steal_focus=True,
            ),
        ],
        close_layout_on=[
            'exec --no-startup-id  echo "show_newsboat"',
            # 'exec --no-startup-id  echo "show_system_monitor"',
        ]
    ),
    'exec --no-startup-id  echo "show_todo"': Layout(
        windows=[
            Window(
                run=["/home/myo/sources/system_monitor/run.sh"],
                geometry={"x": 50, "y": 50, "w": 400, "h": 1000},
                window_name="SystemMonitor",
            ),
            
            Window(
                run=["alacritty", "-T", "w_todo_edit", "-e", "helix", "/home/myo/Desk/todo_/todo.md"],
                geometry={"x": 500, "y": 50, "w": 1300, "h": 1000},
                window_name="w_todo_edit",
                steal_focus=True,
            ),
        ],
        close_layout_on=[
            'exec --no-startup-id  echo "show_todo"',
            # 'exec --no-startup-id  echo "show_system_monitor"',
        ]
    ),
}

CURRENT_LAYOUT: None | Layout = None
HIDE_ON_WORKSPACE: None | str = None


i3 = i3ipc.Connection()


def move_window_to_workspace(
    i3_container: i3ipc.Con,
    workspace: Optional[str] = None,
):
    if workspace == "scratchpad":
        i3.command(f"[con_id={i3_container.id}] move to scratchpad")
    else:
        i3.command(f"[con_id={i3_container.id}] move to workspace {workspace}")


def get_dimensions_on_workspace(
    geometry: Dict[str, int],
    workspace: i3ipc.Con,
):
    max_x = workspace.rect.x + workspace.rect.width
    desired_x = geometry['x'] + workspace.rect.x

    if desired_x >= max_x:
        return

    max_y = workspace.rect.y + workspace.rect.height
    desired_y = geometry['y'] + workspace.rect.y

    if desired_y >= max_y:
        return

    width = min(
        geometry['w'],
        max_x - desired_x
    )
    height = min(
        geometry['h'],
        max_y - desired_y,
    )

    if width < 100 or height < 100:
        return


    return {
        "x": desired_x,
        "y": desired_y,
        "w": width,
        "h": height,
    }


def place_window(
    i3_container: i3ipc.Con,
    x,
    y,
):
    win_id = i3_container.id
    i3.command(f"[con_id={win_id}] move position {x} {y}")

def resize_window(
    i3_container: i3ipc.Con,
    w,
    h,
):
    win_id = i3_container.id
    i3.command(f"[con_id={win_id}] resize set {w} {h}")


def float_window(
    i3_container: i3ipc.Con,
):
    i3.command(f"[con_id={i3_container.id}] floating enable")


def focus_window(
    i3_container: i3ipc.Con,
):
    i3.command(f"[con_id={i3_container.id}] focus")


def snapshot_Window(
    i3_container: i3ipc.Con,
):
    rect = i3_container.rect

    return {
        "con_id": i3_container.id,
        "workspace": i3_container.workspace().name,
        "floating": i3_container.floating,
        "fullscreen": i3_container.fullscreen_mode,
        "rect": {
            "x": rect.x,
            "y": rect.y,
            "w": rect.width,
            "h": rect.height,
        },
    }


def restore_Window(
    window: Window,
):
    if not window.restore_to_initial_state:
        return

    state = window._initial_state_snapshot

    i3.command(
        f"[con_id={state['con_id']}] move container to workspace {state['workspace']}"
    )

    if state["floating"] not in {"user_off", "auto_off"}:
        r = state["rect"]
        i3.command(f"[con_id={state['con_id']}] floating enable")
        i3.command(f"[con_id={state['con_id']}] move position {r['x']} px {r['y']} px")
        i3.command(f"[con_id={state['con_id']}] resize set {r['w']} px {r['h']} px")
    else:
        i3.command(f"[con_id={state['con_id']}] floating disable")

    if state["fullscreen"]:
        i3.command(f"[con_id={state['con_id']}] fullscreen enable")


def init_Layout(layout: Layout):
    """set windows initial positions and sizes"""
    tree = i3.get_tree()
    for win in layout.windows:
        if win.skip_init:
            continue
        i3_container = find_window_container(tree, win)
        if not i3_container:
            logging.debug(f'Container for window (window_name={win.window_name}) not found, trying to spawn it')
            continue
        if win.restore_to_initial_state:
            win._initial_state_snapshot = snapshot_Window(i3_container)
            restore_Window(win)
            continue
        resize_window(i3_container, win.geometry['w'], win.geometry['h'])
        move_window_to_workspace(
            i3_container,
            win.workspace,
        )


def spawn_Layout(layout: Layout):
    tree = i3.get_tree()
    for win in layout.windows:
        if win.skip_spawn:
            continue
        i3_container = find_window_container(tree, win)
        if i3_container:
            continue
        spawn([win])
        i3_container = find_window_container(tree, win)
        if not i3_container:
            logging.debug(f'Container for window (window_name={win.window_name}) either not spawned properly or disabled for spawning. Either way, it is not moved to desired workspace')


def close_Layout(layout: Optional[Layout] = None):
    global CURRENT_LAYOUT
    global HIDE_ON_WORKSPACE

    if not layout:
        layout = CURRENT_LAYOUT

    if not layout:
        return

    tree = i3.get_tree()
    for win in layout.windows:
        i3_container = find_window_container(tree, win)
        if not i3_container:
            logging.debug(f'Container for window (window_name={win.window_name}) not found')
            continue
        if win.restore_to_initial_state:
            restore_Window(win)
            continue
        move_window_to_workspace(
            i3_container,
            win.workspace,
        )

    CURRENT_LAYOUT = None


def open_Layout(
    layout: Layout,
):
    global CURRENT_LAYOUT
    global HIDE_ON_WORKSPACE

    tree = i3.get_tree()
    ws = tree.find_focused().workspace()
    windows_data = list()
    for win in layout.windows:
        i3_container = find_window_container(tree, win)
        if not i3_container:
            logging.debug(f'Container for window (window_name={win.window_name}) not found')
            continue
        float_window(i3_container)
        move_window_to_workspace(
            i3_container,
            ws.name,
        )                
        dimensions = get_dimensions_on_workspace(
            win.geometry,
            ws,
        )
        if not dimensions:
            logging.debug(f'Container for window (window_name={win.window_name}) can not be fitted in workspace, hiding it')
            move_window_to_workspace(
                i3_container,
                win.workspace,
            )
            continue
        place_window(i3_container, dimensions["x"], dimensions["y"])
        if win.steal_focus:
            focus_window(i3_container)
        windows_data.append(
            {
                "win": win,
                "i3_container": i3_container,
                "x": dimensions['x'],
                "y": dimensions["y"],
                "w": dimensions["w"],
                "h": dimensions["h"],
            }
        )

    sleep(0.005)
    for win in windows_data:
        resize_window(
            win["i3_container"],
            win['w'],
            win['h']
        )

    CURRENT_LAYOUT = layout
    HIDE_ON_WORKSPACE = None


def workspace_empty(ws: i3ipc.Con):
    """checks if all workspace empty, or have only 'floating' windows in it"""
    for w in ws.leaves():
        if w.floating in {"auto_off", "user_off",}:
            return False
    return True


def spawn(targets: List[Window]):
    tree = i3.get_tree()
    for win in filter(lambda target: not find_window_container(tree, target), targets):
        if win.run:
            res = subprocess.Popen(win.run)
            logging.debug(f"window spawned: {res}")


def find_window_container(tree: i3ipc.Con, win: Window) -> i3ipc.Con | None:
    try:
        return next(
            filter(
                lambda i3_con: i3_con.name
                and i3_con.name == win.window_name,
                tree.leaves(),
            )
        )
    except StopIteration:
        return None


def get_layouts_window_titles() -> List[str]:
    all_titles = set()
    for layout in LAYOUTS.values():
        for win in layout.windows:
            all_titles.add(win.window_name)

    return list(all_titles)
            


def get_spawn_targets(
    layouts: List[Layout]
) -> List[Window]:
    """returns filtered out unique spawn targets"""
    all_windows = reduce(
        lambda a, b: a + b.windows,
        layouts,
        list(),
    )
    return list(set(all_windows))


def on_binding(i3conn, event: i3ipc.events.BindingEvent):
    """check binding sended and try to showup windows"""
    global CURRENT_LAYOUT
    global HIDE_ON_WORKSPACE

    tree = i3conn.get_tree()

    layout_to_switch_to = LAYOUTS.get(event.binding.command)
    if not layout_to_switch_to:
        return


    if CURRENT_LAYOUT is None:
        close_Layout()
        spawn_Layout(layout_to_switch_to)
        open_Layout(layout_to_switch_to)
        return

    if CURRENT_LAYOUT == layout_to_switch_to:
        close_Layout()
        HIDE_ON_WORKSPACE = tree.find_focused().workspace().name
        return

    if event.binding.command in CURRENT_LAYOUT.close_layout_on:
        close_Layout()
        HIDE_ON_WORKSPACE = tree.find_focused().workspace().name
        return

    close_Layout()
    open_Layout(layout_to_switch_to)


i3.on("binding", on_binding)


def on_workspace_focus(i3conn: i3ipc.Connection, event: i3ipc.events.IpcBaseEvent):
    global HIDE_ON_WORKSPACE

    tree = i3conn.get_tree()
    focus_workspace = tree.find_focused().workspace()

    current_layout_workspace_is_empty = (
        CURRENT_LAYOUT
        and next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None)
        and workspace_empty(next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None).workspace())
    )
    if current_layout_workspace_is_empty and not workspace_empty(focus_workspace):
        return

    focus_on_same_workspace_as_current_layout = (
        CURRENT_LAYOUT
        and next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None)
        and focus_workspace.name == next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None).workspace().name
    )
    if focus_on_same_workspace_as_current_layout:
        # skip re-focus on the current layout
        return

    hide_button_pressed_on_current_workspace = focus_workspace.name == HIDE_ON_WORKSPACE
    if hide_button_pressed_on_current_workspace:
        return

    if workspace_empty(focus_workspace):
        close_Layout()
        default_layout = list(LAYOUTS.values())[0]
        spawn_Layout(default_layout)
        open_Layout(default_layout)
        return

    close_Layout()

i3.on("workspace::focus", on_workspace_focus)


def default_behavior(i3conn, event: i3ipc.events.IpcBaseEvent):
    tree = i3conn.get_tree()
    focus_workspace = tree.find_focused().workspace()

    if event.container.window_title in get_layouts_window_titles():
        return
    focus_on_same_workspace_as_current_layout = (
        CURRENT_LAYOUT
        and next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None)
        and focus_workspace.name == next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None).workspace().name
    )
    if focus_on_same_workspace_as_current_layout and workspace_empty(focus_workspace):
        return
    elif focus_on_same_workspace_as_current_layout and not workspace_empty(focus_workspace):
        close_Layout()
        return

    if workspace_empty(focus_workspace):
        default_layout = list(LAYOUTS.values())[0]
        spawn_Layout(default_layout)
        open_Layout(default_layout)
    else:
        close_Layout()


i3.on("window::new", default_behavior)
i3.on("window::floating", default_behavior)


def on_close(i3conn, event: i3ipc.events.WindowEvent):
    closed_window = event.container
    tree = i3conn.get_tree()
    focus_workspace = tree.find_focused().workspace()

    focus_on_same_workspace_as_current_layout = (
        CURRENT_LAYOUT
        and next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None)
        and focus_workspace.name == next((find_window_container(tree, win) for win in CURRENT_LAYOUT.windows), None).workspace().name
    )
    if focus_on_same_workspace_as_current_layout and workspace_empty(focus_workspace):
        return

    if closed_window.window_title in get_layouts_window_titles():
        return
    if workspace_empty(focus_workspace):
        default_layout = list(LAYOUTS.values())[0]
        spawn_Layout(default_layout)
        open_Layout(default_layout)
    else:
        close_Layout()

i3.on("window::close", on_close)



def parse_loglevel(loglevel: str):
    map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    return map.get(loglevel, logging.INFO)


def get_cli_args():
    parser = argparse.ArgumentParser(
        prog="Manage and use floating sub-layouts with i3.",
        description=(
            "Manage floating overlay layouts in i3wm. "
            "The script listens to i3 IPC events and keybindings to automatically "
            "spawn, position, float, hide, and restore predefined windows. "
            "Layouts appear on empty workspaces or when triggered, and disappear "
            "when focus or workspace state changes."
            "\n"
            "Edit `LAYOUTS` variable inside of this script, to modify layouts.\n"
            "To make keybindings accessable, add bindsym strings like this:\n"
            'bindsym --release $mod+Ctrl+y exec --no-startup-id  echo "show_system_monitor"\n'
            'Then, use `exec --no-startup-id  echo "show_system_monitor"\n` as key in `LAYOUTS` variable\n'
            "Value should be valid Layout value.\n\n"
            "You can find more in README.md"
        )
    )

    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=[
            "debug",
            "info",
            "warning",
            "error",
        ],
        default="warning",
    )

    return parser.parse_args()


def main():
    args = get_cli_args()

    logging.basicConfig(level=parse_loglevel(args.log_level))

    spawn(
        get_spawn_targets(
            LAYOUTS.values(),
        )
    )

    sleep(1)

    for layout in LAYOUTS.values():
        spawn_Layout(layout)
        init_Layout(layout)

    i3.main()


if __name__ == "__main__":
    main()
