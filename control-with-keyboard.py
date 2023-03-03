# -*- coding: UTF-8 -*-

import olympe
import subprocess
import time
from olympe.messages.ardrone3.Piloting import takeoff, landing, PCMD
from pynput.keyboard import Listener, Key, KeyCode
from collections import defaultdict
from enum import Enum

# DRONE_IP = "192.168.42.1" # Real drone IP address
DRONE_IP = "10.202.0.1" # Simulated drone IP address

class Ctrl(Enum):
    (
        QUIT,
        takeoff,
        landing,
        mv_l,
        mv_right,
        mv_fwd,
        mv_BACKWARD,
        mv_UP,
        mv_DOWN,
        turn_left,
        turn_right,
    ) = range(11)


QWERTY_CTRL_KEYS = {
    Ctrl.QUIT: Key.esc,
    Ctrl.takeoff: "t",
    Ctrl.landing: "l",
    Ctrl.mv_l: "a",
    Ctrl.mv_right: "d",
    Ctrl.mv_fwd: "w",
    Ctrl.mv_BACKWARD: "s",
    Ctrl.mv_UP: Key.up,
    Ctrl.mv_DOWN: Key.down,
    Ctrl.turn_left: Key.left,
    Ctrl.turn_right: Key.right,
}

AZERTY_CTRL_KEYS = QWERTY_CTRL_KEYS.copy()
AZERTY_CTRL_KEYS.update(
    {
        Ctrl.mv_l: "q",
        Ctrl.mv_right: "d",
        Ctrl.mv_fwd: "z",
        Ctrl.mv_BACKWARD: "s",
    }
)


class KeyboardCtrl(Listener):
    def __init__(self, ctrl_keys=None):
        self._ctrl_keys = self._get_ctrl_keys(ctrl_keys)
        self._key_pressed = defaultdict(lambda: False)
        self._last_action_ts = defaultdict(lambda: 0.0)
        super().__init__(on_press=self._on_press, on_release=self._on_release)
        self.start()

    def _on_press(self, key):
        if isinstance(key, KeyCode):
            self._key_pressed[key.char] = True
        elif isinstance(key, Key):
            self._key_pressed[key] = True
        if self._key_pressed[self._ctrl_keys[Ctrl.QUIT]]:
            return False
        else:
            return True

    def _on_release(self, key):
        if isinstance(key, KeyCode):
            self._key_pressed[key.char] = False
        elif isinstance(key, Key):
            self._key_pressed[key] = False
        return True

    def quit(self):
        return not self.running or self._key_pressed[self._ctrl_keys[Ctrl.QUIT]]

    def _axis(self, left_key, right_key):
        return 100 * (
            int(self._key_pressed[right_key]) - int(self._key_pressed[left_key])
        )

    def roll(self):
        return self._axis(
            self._ctrl_keys[Ctrl.mv_l],
            self._ctrl_keys[Ctrl.mv_right]
        )

    def pitch(self):
        return self._axis(
            self._ctrl_keys[Ctrl.mv_BACKWARD],
            self._ctrl_keys[Ctrl.mv_fwd]
        )

    def yaw(self):
        return self._axis(
            self._ctrl_keys[Ctrl.turn_left],
            self._ctrl_keys[Ctrl.turn_right]
        )

    def throttle(self):
        return self._axis(
            self._ctrl_keys[Ctrl.mv_DOWN],
            self._ctrl_keys[Ctrl.mv_UP]
        )

    def has_piloting_cmd(self):
        return (
            bool(self.roll())
            or bool(self.pitch())
            or bool(self.yaw())
            or bool(self.throttle())
        )

    def _rate_limit_cmd(self, ctrl, delay):
        now = time.time()
        if self._last_action_ts[ctrl] > (now - delay):
            return False
        elif self._key_pressed[self._ctrl_keys[ctrl]]:
            self._last_action_ts[ctrl] = now
            return True
        else:
            return False

    def takeoff(self):
        return self._rate_limit_cmd(Ctrl.takeoff, 2.0)

    def landing(self):
        return self._rate_limit_cmd(Ctrl.landing, 2.0)

    def _get_ctrl_keys(self, ctrl_keys):
        # Get the default ctrl keys based on the current keyboard layout:
        if ctrl_keys is None:
            ctrl_keys = QWERTY_CTRL_KEYS
            try:
                # Olympe currently only support Linux
                # and the following only works on *nix/X11...
                keyboard_variant = (
                    subprocess.check_output(
                        "setxkbmap -query | grep 'variant:'|"
                        "cut -d ':' -f2 | tr -d ' '",
                        shell=True,
                    )
                    .decode()
                    .strip()
                )
            except subprocess.CalledProcessError:
                pass
            else:
                if keyboard_variant == "azerty":
                    ctrl_keys = AZERTY_CTRL_KEYS
        return ctrl_keys


if __name__ == "__main__":
    with olympe.Drone(DRONE_IP) as drone:
        drone.connect()
        control = KeyboardCtrl()
        while not control.quit():
            if control.takeoff():
                drone(takeoff())
            elif control.landing():
                drone(landing())
            if control.has_piloting_cmd():
                drone(
                    PCMD(
                        1,
                        control.roll(),
                        control.pitch(),
                        control.yaw(),
                        control.throttle(),
                        timestampAndSeqNum=0,
                    )
                )
            else:
                drone(PCMD(0, 0, 0, 0, 0, timestampAndSeqNum=0))
            time.sleep(0.05)
