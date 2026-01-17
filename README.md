# About Summoner

This is a daemon script, that manages summoning layouts.
By summoning layouts, I mean, showing set of floating windows on top of your workspace windows in floating mode.


You don't need to know python and be deeply into programming to configure and use Summoner, but it is still just a script and i don't plan to support any external configs.

It's features:

1. Summon layout on empty workspaces on workspace switch
2. Summon layouts with keybindings
3. Spawn processes to use for layouts
4. Or use already running windows as parts of the layout
5. Restore window position after using this window in layout summon
6. Support multihead setups


# Running
#### It is not standalone package
For now, it is not a package, and you'll need to manage dependencies on your own. Summoner has only one dependecny - i3ipc.
You can either run
```bash
. ./setup.sh
```
or
```bash
python -m venv venv
. ./venv/bin/activate
pip install -r req.txt
```

To run script, you'll need your envrinment activated. You can either do:
```bash
. ./run.sh
```
or
```bash
. ./venv/bin/activate
python summoner.py
```

Tho, you'll probably want to run it inside of i3 config. After placing summoner into the `.config/i3/summoner`:

```bash
exec_always --no-startup-id ~/.config/i3/summoner/run.sh
```


# Configuration
## Simply showing windows on empty workspaces
If you want to use Summoner only to summon layout on empty workspace, you only need to setup your initial layout.
Open script and find `LAYOUTS` variable.
Edit it to be something like this:


```python
LAYOUTS = {
    '############': Layout(
        windows=[
            Window(
                run=["alacritty", "-T", "cmatrix1", "-e", "cmatrix"],
                geometry={"x": 350, "y": 150, "w": 250, "h": 500},
                window_name="cmatrix1",
            ),
            Window(
                run=None,
                geometry={"x": 900, "y": 300, "w": 250, "h": 500},
                window_name="cmatrix2",
                workspace="1"
                skip_spawn=True,
                skip_init=True,
                steal_focus=True,
            ),
        ]
    ),
```
|---|---|
|`run`|  Either None (explicitly) or list of cli args to run |
| `geometry` |  dict in format {"x": 0, "y": 0, "w": 0, "h": 0}, where `x`, `y` is top left of your workspace (output) `w` is window width and `h` is window height. Note that window should be at least 100/100 in size, or window will be counted as too small and not displayed (it still will be spawned) |
| `window_name` | name of the window. Note that it should be unique, and you need to either set it in `run` somewhere, depending on what you run, or by hand, when you run with `skip_spawn` |
| `workspace` | home workspace window will hide itself at. Default as "w_hidden" |
| `skip_spawn` | skipping spawn step of setup. This means you started your process yourself, or plan to start it later |
| `skip_init` | skipping init step of setup. This means, you don't touch window (don't store it's initial values, don't float it, don't resize, don't move it to hidden workspace, etc) |
| `steal_focus` | make this window steal focus from whatever focus was beforehand |
| `restore_to_initial_state` | record initial state of window (init step, don't skip it). When window should be hided, it will try to go to it's initial state. Note that it does not save any layout data, only simple workspace/floated/focused |


## Summoning windows with key presses
If you want to bring out full potential of Summoner and make it summon floating windows right in your face, on top of your current tiling layout, you need to do as follows:

### Edit i3 config
Unfortunately, you need to edit i3 config for it to work. You need to bind some keystrokes for Summoner to catch. Hopefully, it is pretty easy to do.
Just add string like this in your config:
```bash
bindsym --release $mod+Ctrl+y exec --no-startup-id  echo "show_system_monitor"
```

In the i3, whole exec line, including exec will be caught as binding:
```bash
exec --no-startup-id  echo "show_system_monitor"
```

### Edit Summoner

Now, we'll need to edit script file itself. Notice how we had bunch of hashes as the key for `LAYOUTS` in the first example. It was like this because it did not really mattered what value we put there, it will still work. You can even put `ur_mom` in here, but i will be carefull not to cause buffer overflow.
Anyway, now, key for the `LAYOUTS` dictionary will play it's role.

We need to set key to our binded command, including exec and everything after. Like this:
```python
LAYOUTS = {
    'exec --no-startup-id  echo "show_system_monitor"': Layout(
        windows=[
            ...
        ],
    ),
}

```

And, we will need to setup, how our layout is closed:
```python
LAYOUTS = {
    'exec --no-startup-id  echo "show_system_monitor"': Layout(
        ...,
        close_layout_on=[
            'exec --no-startup-id  echo "show_system_monitor"',
        ],            
    ),
}

```

Why this separation?

So we can have scenario like this then:

> .configs/i3/config
```bash
bindsym --release $mod+Ctrl+y exec --no-startup-id  echo "show_system_monitor"
bindsym --release $mod+Ctrl+u exec --no-startup-id  echo "show_newsboat"
bindsym --release $mod+Ctrl+i exec --no-startup-id  echo "show_newsboat_and_system_monitor"

```

> Summoner.py
```python

LAYOUTS = {
    'show_system_monitor': Layout(
        windows=[
            Window(
                run=["system_monitor.sh"],
                ...
            ),
        ],
        close_layout_on=[
            'exec --no-startup-id  echo "show_system_monitor"',
        ]
    ),
    'exec --no-startup-id  echo "show_newsboat"': Layout(
        windows=[
            Window(
                run=["alacritty", "-T", "w_newsboat", "-e", "newsboat"],
                window_name="w_newsboat",
            ),
        ],
        close_layout_on=[
            'exec --no-startup-id  echo "show_system_monitor"',
            'exec --no-startup-id  echo "show_newsboat"',
        ]
    ),
    'exec --no-startup-id  echo "show_newsboat_and_system_monitor"': Layout(
        windows=[
            Window(
                run=["alacritty", "-T", "w_newsboat", "-e", "newsboat"],
                window_name="w_newsboat",
            ),
        ],
        close_layout_on=[
            'exec --no-startup-id  echo "show_newsboat_and_system_monitor"',
        ]
    ),
}

```

In this case, if we hit firts key combination (mod+ctrl+y) will bring out system_monitor, then, if we hit second combination (mod+ctrl+u), we will summon newsboat. Otherwise, we would first close system monitor, and only after this we will be able to bring out system_monitor.
Then, inside of "newsboat" layout, we can close whole layout either hitting system_monitor combination, or newsboat combination
And, after navigating into the show_newsboat_and_system_monitor (mod+ctrl+i), we will be able to close this layout only with show_newsboat_and_system_monitor combination.
Hitting system_monitor or newsboat combinations (mod+ctrl+y/mod+ctrl+u), we will not close whole overlay, but navigate back to each layout respectfully.

So, this system, gives as ability to do some simple "navigation" between layouts, saving some keystrokes, and sanity.


## Restorable windows
As you couldve seen, `Window` have `restore_to_initial_state`. It makes it possible (while still very crude) to bring window back, from where it was taken to show on the layouts.
Initially, this feature was intended to be used shile streaming, to summon chat on screen, from secondary monitor, to the main one, which is captured by obs, and then brought back.
Hope it will be usable with any other usecases.


## Multihead
Summoner supports multihead (tho, only tested in 2 monitor setup by me). General behaviour of summoned layouts will be the same as in the single monitor setup, but in case one of the monitor workspaces considered "empty", when you move focus form "empty" monitor, to monitor with windows opened, current layout will "stick" to the empty monitor (otherwise it wouldve just hid itself)



# Contribution
This repo does not accepts contributions outright. If you want to contribute, hit me up on discord (@myortv) or email (myortv@proton.me) (email is worse, i rarely check it) and i'll either merge your patches or give you access to git ssh.
If you found any bugs, hit me up on discord (@myortv) or email (myortv@proton.me)
If you have any feature requests, hit me up on discord (@myortv) or email (myortv@proton.me)
If you are hop femboy in my area, hit me up on discord (@myortv) or email (myortv@proton.me)
