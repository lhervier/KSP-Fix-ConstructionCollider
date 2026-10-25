"""Plays the protocols of Construction Collider Fix: a leg of a small stand is edited in EVA construction mode, with
the Rotate and Move tools, then released; does it still hold the stand up?

It drives KSP through KSP-Util-MCPServer, a mod that answers HTTP requests on 127.0.0.1, and needs nothing but
Python 3: no AI, no package to install. Start KSP with KSP-Util-MCPServer installed, copy construction-collider.sfs
into a sandbox game, then run:

    python run-colliders.py --folder <your sandbox game> --out out

construction-collider.sfs holds the Construction Tripod on the flat grass west of the space centre, in the
morning: a Mk1 command pod standing on three small nose cones, its legs, surface-attached under its base, their tips
on the ground, so that the pod stands half a metre above it; and its engineer, Bill, on EVA five metres north of it,
the active vessel: only an engineer opens the construction mode. The legs are light enough for one engineer to
edit. The stand rests on its three legs alone: when one of them no longer holds, it leans towards it until the rim
of the pod touches the ground.
Each protocol loads the save first, from the space centre: the game is opened there first when KSP is at its main
menu.

Each protocol edits one leg, its own, so that a run shows which one it touched, and selects it once only:

- rotate-move (the first leg): the Rotate tool; a click on the leg selects it; the Move tool, the leg still
  selected; the Place tool, which releases it;
- move-rotate (the second leg): the same, the Move tool first, then the Rotate tool;
- rotate (the third leg), the control: the Rotate tool; a click on the leg selects it; the Place tool releases it.
  The leg is never switched between tools while selected.

While a leg is selected, it holds nothing, and the stand stays still as long as nothing moves it: the game freezes
neither the stand nor the leg, it just has no reason to move yet. Once the leg is released, the script closes the
construction mode, warps time at 5x on rails for a moment, then back to normal: back off rails, the game puts the
stand under its weight again, and a leg that no longer holds lets it lean. Selecting a second leg, or the same one
again, after that would let the stand lean on the selected leg: that is why each protocol selects once.

The script uses the tools of KSP-Util-MCPServer only. It opens the construction mode and picks its tools as the
mode's buttons do (construction_tool). It clicks the leg with the mouse (mouse_click), as a player does: the camera
is first aimed at the leg, as its Aim Camera button does (aim_camera), and turned to where the leg shows best;
locate_part then gives a point where the game sees the mouse over the leg, found by casting rays from the camera as
the game does to find the part under the mouse. After the warp, the game runs five seconds, then the script reads,
with locate_part again, how many of the leg's colliders are triggers (a trigger collides with nothing), and how far
the pod leans from the vertical.

A screenshot is taken of the stand once the save is loaded, then after the protocol, from the north and from the
east, the interface hidden as F2 hides it and the pointer at the top left corner, out of the way, as a PNG the size
of the window. With Pillow installed, each is also saved 640 pixels wide as a JPEG. The script writes what it read to runs.json.

At the end, the script checks what the fix promises and prints PASS or FAIL for each check, then exits with 0 when
all pass, 1 otherwise. Without the mod, the checks marked (fix) fail: they are the bug.

- each click selects the leg;
- once released, none of the leg's colliders is a trigger (fix in rotate-move and move-rotate);
- after the warp, the pod leans less than 2 degrees from the vertical (fix in rotate-move and move-rotate).

KSP is left running at the end.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

URL = None

# The stand of the save, its pod and its legs, by the name of their part.
STAND = "Construction Tripod"
POD = "mk1pod.v2"
LEG = "standardNoseCone"

# How far the camera stands from a leg to click it, and from the pod for the screenshots, in metres.
LEG_DISTANCE = 3
STAND_DISTANCE = 5

# How long the game warps on rails once a leg is released, and runs after that before the script reads it, in seconds.
WARP = 2.0
SETTLE = 5.0

# How far the pod may lean and still count as upright, in degrees.
UPRIGHT = 2.0


def call(tool_name, **args):
    """Calls one tool of KSP-Util-MCPServer and returns its answer, decoded from JSON when it is JSON."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool_name, "arguments": args}}).encode()
    request = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.loads(response.read())["result"]
    text = result["content"][0].get("text", "") if result["content"] else ""
    if result.get("isError"):
        raise RuntimeError(tool_name + ": " + text)
    try:
        return json.loads(text)
    except ValueError:
        return text


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


class Run:
    """One protocol played: what the script read, its screenshots and its checks."""

    def __init__(self, out, leg):
        self.out = out
        self.steps = []
        self.checks = []
        parts = call("list_parts", vessel=STAND)
        self.pod = next(p["id"] for p in parts if p["name"] == POD)
        legs = [p["id"] for p in parts if p["name"] == LEG]
        self.leg = legs[leg]
        log("leg", leg + 1, "of", len(legs), "id", self.leg)

    def check(self, label, passed):
        """Records one check of what the fix promises."""
        self.checks.append({"check": label, "passed": bool(passed)})
        log("PASS" if passed else "FAIL", label)

    def tool(self, name):
        """Picks a tool of the construction mode, as its button does."""
        answer = call("construction_tool", tool=name)
        self.steps.append({"tool": name, "toolInUse": answer["tool"], "selectedPart": answer["selectedPart"]})
        log("tool", name, "->", answer["tool"], "selected", answer["selectedPart"])
        return answer

    def click_leg(self):
        """Clicks the leg as a player does, the camera turned to it first. Returns whether the click selects it."""
        call("aim_camera", part=self.leg)
        call("set_camera", distance=LEG_DISTANCE)
        seen = call("locate_part", part=self.leg, find_view=True)
        point = seen["point"]
        if point is None:
            raise RuntimeError("the leg does not show anywhere the camera was turned")
        call("mouse_click", x=point["x"], y=point["y"])
        time.sleep(0.5)
        selected = call("construction_tool")["selectedPart"]
        self.steps.append({"click": "leg", "x": point["x"], "y": point["y"], "selectedPart": selected})
        log("click on the leg at %d, %d, selected %s" % (point["x"], point["y"], selected))
        return selected == self.leg

    def read(self, name):
        """Reads the leg's colliders and how far the pod leans."""
        leg = call("locate_part", part=self.leg)
        pod = call("locate_part", part=self.pod)
        step = {"step": name, "colliders": leg["colliders"], "triggers": leg["triggers"], "tilt": pod["tilt"]}
        self.steps.append(step)
        log(name, "leg colliders %d, triggers %d, pod leaning %.1f degrees" % (
            leg["colliders"], leg["triggers"], pod["tilt"]))
        return step

    def shot(self, name, heading):
        """Takes a screenshot of the stand from a heading, the camera low, aimed at the pod, the interface hidden."""
        call("aim_camera", part=self.pod)
        call("set_camera", distance=STAND_DISTANCE, heading=heading, pitch=15)
        # The part under the pointer shows highlighted: the pointer goes to a corner first.
        call("mouse_move", x=1, y=1)
        call("set_ui", visible=False)
        time.sleep(0.5)
        path = os.path.abspath(os.path.join(self.out, name + ".png"))
        call("screenshot", path=path, return_image=False)
        call("set_ui", visible=True)
        save_jpeg(path, os.path.join(self.out, "small", name + ".jpg"))


def save_jpeg(source, target):
    """Saves a screenshot 640 pixels wide as a JPEG. Does nothing without Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return
    image = Image.open(source).convert("RGB")
    image = image.resize((640, round(image.height * 640 / image.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    image.save(target, quality=88)


def start(options, out, leg):
    """Loads the save into flight, from the space centre, and lets the stand settle. Returns the run."""
    scene = call("get_state")["scene"]
    if scene == "MAINMENU":
        call("open_game", folder=options.folder)
    elif scene not in ("SPACECENTER", "FLIGHT"):
        call("go_to_scene", scene="SPACECENTER")
    # Right after the game opens, the server may not take the load yet: try again a few seconds later.
    for attempt in range(3):
        try:
            call("load_save", folder=options.folder, save=options.save)
            break
        except Exception as e:
            if attempt == 2:
                raise
            log("load_save failed, trying again:", e)
            time.sleep(5)
    time.sleep(3)
    run = Run(out, leg)
    run.read("loaded")
    run.shot("0-loaded", 0)
    call("construction_tool", panel="open")
    return run


def finish(run, fixed):
    """Lets the stand settle under its weight once the leg is released, reads it, takes the screenshots, and checks
    it. fixed says whether the checks are what the fix promises."""
    call("construction_tool", panel="close")
    # Off rails again, the game puts the stand under its weight: the warp at 5x, the first rate on rails.
    call("set_warp", rate_index=1)
    time.sleep(WARP)
    call("set_warp", rate_index=0)
    time.sleep(SETTLE)
    after = run.read("released")
    run.shot("1-released-from-north", 0)
    run.shot("2-released-from-east", 90)
    mark = "(fix) " if fixed else ""
    run.check(mark + "once released, none of the leg's colliders is a trigger", after["triggers"] == 0)
    run.check(mark + "after the warp, the pod leans less than %g degrees" % UPRIGHT, after["tilt"] < UPRIGHT)


def switched(options, out, leg, first, second):
    """Selects the leg with one tool, switches to the other, then releases it with the Place tool."""
    run = start(options, out, leg)
    run.tool(first)
    run.check("the click with the %s tool selects the leg" % first.capitalize(), run.click_leg())
    run.tool(second)
    run.tool("place")
    finish(run, True)
    return run


def rotate_move(options, out):
    return switched(options, out, 0, "rotate", "move")


def move_rotate(options, out):
    return switched(options, out, 1, "move", "rotate")


def rotate(options, out):
    run = start(options, out, 2)
    run.tool("rotate")
    run.check("the click with the Rotate tool selects the leg", run.click_leg())
    run.tool("place")
    finish(run, False)
    return run


PROTOCOLS = {"rotate-move": rotate_move, "move-rotate": move_rotate, "rotate": rotate}


def main():
    global URL
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", required=True, help="the sandbox game under saves/ the save was copied into")
    parser.add_argument("--save", default="construction-collider", help="the save, without .sfs")
    parser.add_argument("--protocol", choices=list(PROTOCOLS) + ["all"], default="all")
    parser.add_argument("--out", required=True, help="the folder for runs.json and the screenshots")
    parser.add_argument("--port", type=int, default=8770, help="the port of KSP-Util-MCPServer")
    options = parser.parse_args()
    URL = "http://127.0.0.1:%d/mcp/" % options.port

    names = list(PROTOCOLS) if options.protocol == "all" else [options.protocol]
    runs = {}
    for name in names:
        out = os.path.join(options.out, name)
        os.makedirs(out, exist_ok=True)
        log("protocol", name)
        run = PROTOCOLS[name](options, out)
        runs[name] = {"steps": run.steps, "checks": run.checks}
    with open(os.path.join(options.out, "runs.json"), "w", newline="\n") as f:
        json.dump(runs, f, indent=1)

    failed = [(name, c["check"]) for name, run in runs.items() for c in run["checks"] if not c["passed"]]
    total = sum(len(run["checks"]) for run in runs.values())
    print()
    for name, run in runs.items():
        for c in run["checks"]:
            print("%-4s %-11s %s" % ("PASS" if c["passed"] else "FAIL", name, c["check"]))
    print("%d of %d checks passed" % (total - len(failed), total))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
