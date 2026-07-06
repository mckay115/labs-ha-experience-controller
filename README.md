# Labs Experience Controller for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Validate](https://github.com/mckay115/labs-ha-experience-controller/actions/workflows/validate.yml/badge.svg)](https://github.com/mckay115/labs-ha-experience-controller/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Turn areas into **Spaces** with experiential behavior. A space gently
acknowledges you when you enter, settles into an experience while you're
there (*Watching TV*, *Hanging out*, *Working*), recognizes when you just
pass through, and winds down gracefully when you leave — all from one
config entry instead of a dozen fragile automations.

Part of the Labs ecosystem:
[labs-ha-themes](https://github.com/mckay115/labs-ha-themes) ·
[labs-ha-cards](https://github.com/mckay115/labs-ha-cards)

## How it works

Every space runs a two-layer engine:

**1. Occupancy lifecycle** (automatic):

```
vacant ──presence──▶ waking ──persists──▶ occupied ──presence gone──▶ cooldown ──▶ vacant
   ▲                    │                                                  │
   └── passing through ◀┘ (quick in-and-out)          (presence returns ──▶ occupied)
```

- **Waking** — the space acknowledges you without fully waking: dim a lamp
  to 20%, not blast every light.
- **Passing through** — presence that ends during waking never fully wakes
  the room; run quick-off actions instead.
- **Cool-down** — a graceful wind-down (fade lights) before vacant, with
  instant recovery if you come back.

**2. Experience states** (yours): define states per space with *evidence* —
*Watching TV* when the TV is playing (priority 10), *Hanging out* otherwise
(no evidence = baseline). The highest-priority matching state wins, runs
your enter/exit actions, and shows on a select entity you can override
anytime. States with **hold occupancy** keep the room alive while their
evidence is active — no more lights-off in the middle of a movie because
you sat still.

**Controls**: bind physical buttons, remotes, and switches to space
commands — set a state, cycle states, wake, sleep, resume automatic, or
run custom actions. Like Switch Manager, but space-aware. The easiest way
to add one is **press-to-program**: choose *Add a control by pressing it*,
press the physical button, and the exact button + press type is captured
and mapped — works with modern `event` entities *and* raw bus events
(`zha_event`, `deconz_event`, `hue_event`, Lutron, Z-Wave scene
notifications, and more) from remotes that never become entities.

## Modern sensors welcome

Presence understands classic motion, occupancy and door sensors, mmWave
sensors (FP1/FP2-class `present` / `moving` / `stationary` states),
persons and geo zones, and **numeric counts** — any state above zero is
presence, so ESPresense/Bermuda person counts and zone occupancy work
out of the box. BLE room trackers that report a room name are covered by
the per-space *extra presence states* field.

## Installation

### HACS

1. In HACS, open the overflow menu (⋮) → **Custom repositories**.
2. Add `https://github.com/mckay115/labs-ha-experience-controller` with type **Integration**.
3. Install **Labs Experience Controller** and restart Home Assistant.

### Manual

Copy `custom_components/labs_experience` into your config's
`custom_components` folder and restart.

## Quick start: a living room in two minutes

1. **Settings → Devices & services → Add integration → Labs Experience
   Controller.** Name it *Living Room* and pick its area — presence
   sensors and the room profile fill themselves from the area.
2. **Configure → Experience states → Add common states.** Pick *Hanging
   out*, *Media*, and *Night light*, confirm the TV. Done.
3. Walk in: gentle acknowledgement (night light when dark) → circadian
   ambient (*Hanging out*) — and if the TV is already playing, the room
   recognizes you instantly and goes straight to *Media*. Movies hold the
   room occupied through motionless stretches; leaving fades down and
   turns off. Touch any wall switch and the engine hands you the lights
   without losing the experience state.
4. Optional: **Controls → Add a control by pressing it** — press your
   remote, pick a command, done.

## Room profile & habitat intelligence

Assign what lives in the space — light roles (ambient/task/accent/night),
climate, windows, doors, media, an illuminance sensor — or click **Fill
the room profile from the area** and it's built from the HA registries in
one step (creating a space with an area does this automatically). With a
profile, the space behaves well with *zero* further configuration:

- **Wake** → night-role lights dim on (only when dark), **occupied** →
  ambient on the **circadian curve** (color temperature and brightness
  follow the sun, ~2200 K nights to ~5500 K days, drifting every 5
  minutes), **cool-down** → fade, **vacant** → off. Your own phase/state
  actions always take precedence.
- **Lux intelligence:** a threshold stops lights coming on in bright
  rooms, and an optional **target light level** runs a closed loop —
  initial brightness is estimated from the measured deficit, then nudged
  as daylight changes (deadband + rate-limited, never oscillates).
- **Manual control is sacred:** touch a wall switch, dimmer, app, or
  voice and the space's *lighting authority* flips to **manual** — the
  engine stops adjusting lights but the experience state doesn't move.
  Automation resumes when the room empties, via *Resume automatic*, the
  Lighting select, or an optional timed hold. Control bindings gain
  `lights on/off/brighten/dim` verbs that do the same.
- **Climate (opt-in):** per-state comfort intents (comfort/eco/off),
  eco setback when vacant, and window-pause — a window open past the
  delay saves the thermostat state and pauses; closing restores it.
- **Dayparts:** every space knows morning/day/evening/night (sun +
  configurable times). States can be limited to dayparts — a *Night
  light* baseline that only exists at night — and **controls too**: bind
  the same button twice with different dayparts to do different things at
  different times. The daypart sensor exposes live circadian targets for
  dashboards.

## Modeling a multi-state room

**Priorities are your transition graph.** Give every activity a state, rank
them, and the room moves between them on its own — no per-transition
automations. A den that goes standby → ambient → work → media and back:

| State | Priority | Evidence | Notes |
| --- | --- | --- | --- |
| *(waking)* | — | — | Wake actions = night/background lights on entry |
| Ambient | 0 | none (baseline) | Soft background lighting once you stay |
| Work | 10 | `switch.desk` or `binary_sensor.desk_seat` (any) | Full work lighting while either is active |
| Media | 20 | `media_player.tv` playing | **Hold occupancy on** — motion can't vacate the room until the TV stops |

How an evening plays out: walk in → night lights (waking) → stay → *Ambient*
→ flip the desk switch or sit down → *Work* → TV turns on → *Media* outranks
Work → everyone sits still for two hours → the hold keeps the room occupied
→ TV off → back to *Ambient* (desk is off) → leave → cool-down → vacant.
Dropping evidence always falls back down the priority ladder automatically;
buttons and the select entity can jump anywhere at any time. This exact flow
runs in [`tests/test_scenarios.py`](tests/test_scenarios.py).

Occupancy itself aggregates any number of sensors — motion, mmWave, desk
seats, door contacts, counts — and evidence devices (media players, desks)
assist occupancy through inference + hold, so a quiet movie night never goes
dark.

## What each space gives you

| Entity | Purpose |
| --- | --- |
| `select.<space>_experience` | Current experience. Selecting = manual override (until vacant or *Resume automatic*). |
| `select.<space>_lighting` | Lighting authority: automatic or manual (with a room profile). |
| `sensor.<space>_phase` | `vacant` / `waking` / `occupied` / `cooldown`, with since/presence/override/authority attributes. |
| `sensor.<space>_daypart` | Morning/day/evening/night, with live circadian kelvin/brightness targets. |
| `binary_sensor.<space>_occupied` | On while waking or occupied. |
| `switch.<space>_automation` | Pause/resume this space's engine (survives restarts). |
| `switch.<space>_circadian` | Enable/disable circadian drift (with a room profile). |
| `button.<space>_resume_automatic` | Clear manual overrides and manual lighting/climate authority. |

**Actions (services)** — target the space's select entity:

```yaml
action: labs_experience.set_state
target:
  entity_id: select.living_room_experience
data:
  state: watching_tv   # id or name; wakes the space if vacant
```

`labs_experience.clear_override` returns a space to automatic.

## Building on top: your automations still rule

Everything is a normal entity, so the native automation editor works —
no YAML events needed:

> **When** `select.living_room_experience` becomes *Watching TV* →
> close the blinds.

For advanced flows, every transition also fires a `labs_experience_event`:

```yaml
triggers:
  - trigger: event
    event_type: labs_experience_event
    event_data:
      space: Living Room
      type: state_changed          # or phase_changed / passing_through
      to: watching_tv
```

## Dashboard

A tile card per space makes a simple viewer today:

```yaml
type: vertical-stack
cards:
  - type: tile
    entity: select.living_room_experience
    features:
      - type: select-options
  - type: tile
    entity: sensor.living_room_phase
```

A dedicated space card with a planner/viewer UI is on the roadmap in
[labs-ha-cards](https://github.com/mckay115/labs-ha-cards).

## Tips

- Motion sensors with long built-in off-delays: shorten them and let the
  space's *clear delay* do the debouncing instead.
- Wake actions run day and night — put a sun/time condition inside the
  action sequence for "warm dim at night, nothing at noon".
- *Paused* media ends a hold by default; add `paused` to the state's
  *active states* if popcorn breaks shouldn't count as leaving.

See [DESIGN.md](DESIGN.md) for the full design and roadmap.

## License

[MIT](LICENSE)
