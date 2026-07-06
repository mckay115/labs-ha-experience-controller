# Labs Experience Controller — Design

## Vision

Home Assistant gives you areas, entities, automations, and scripts — the
raw materials. Making a *room feel alive* with them means hand-wiring the
same brittle mesh in every room: motion → lights automation, clear → delay
→ off automation, TV → scene automation, TV stop → revert automation, a
presence-hold boolean so movies don't go dark, an override boolean so
manual choices stick, and restart-safety glue. Ten automations per room,
none aware of each other.

The Experience Controller makes the *experience* the first-class object.
A **Space** owns its presence model, its lifecycle, its states, its
actions, and its physical controls — configured in the UI, visible as
entities, driven by one engine that handles the fiddly parts (debounce,
timer races, restart adoption, override lifecycles) correctly once.

**Design principles**

1. **The Home Assistant way.** Config entries, areas, devices, entities,
   the standard action editor, translations, diagnostics. No custom DSL,
   no YAML requirement, no parallel concepts where HA already has one.
2. **No lock-in.** All behavior hooks are standard HA action sequences —
   copy/paste YAML to or from any automation. Removing the integration
   leaves your scenes and scripts untouched.
3. **Entities are the API.** The current experience is a `select`, the
   lifecycle a `sensor` — so the native automation editor, templates,
   dashboards, and voice assistants compose with spaces for free.
4. **Sustain, don't surprise.** Evidence can *hold* occupancy but never
   create it; restarts adopt reality without replaying actions; manual
   overrides always win until you leave.

## The layer model (v0.3)

Each layer answers one question; they compose instead of fighting:

| Layer | Question | Values |
|---|---|---|
| Occupancy | Is anyone here? | vacant / waking / occupied / cooldown |
| Activity | What are they doing? | experience states |
| Daypart | What time-of-body is it? | morning / day / evening / night |
| Authority (per facet) | Who's in control? | auto / manual (lighting, climate) |

The key rule: **device-level changes move the Authority layer, never the
Activity layer.** Flipping a wall switch makes lighting `manual` (engine
contexts distinguish our commands from human ones) while the room stays
*Hanging out*. Vacancy always releases manual authority.

**Room profile:** entities assigned to semantic roles (light roles
ambient/task/accent/night, climate, windows, doors, media, appliances,
illuminance) — auto-fillable from the HA area registries. The profile is
what lets the engine offer habitat-science defaults with zero config:
gentle night-light wake, circadian ambient baseline (sun-elevation-driven
kelvin/brightness), lux gating, target-lux closed-loop brightness
(deadband + rate-limited), cool-down fade, off at vacancy, per-state
climate intents, and window-pause with restore.

## Concepts

### Space

One config entry = one space, usually bound to an HA area (the area also
places the space's device). A space has presence sources, four timings,
phase actions, experience states, and controls. All configuration lives in
`entry.options`; changing options reloads the entry.

### Occupancy lifecycle (phases)

```
             presence            wake_duration
  VACANT ───────────────▶ WAKING ─────────────▶ OCCUPIED
    ▲                        │ presence gone        │ presence gone
    │   pass_through_delay   │                      │ clear_delay
    ├────◀───────────────────┘                      ▼
    │         (passing_through event)           COOLDOWN
    │              cooldown_duration                │
    └───────────────◀───────────────────────────────┘
                       (presence returns ⇒ OCCUPIED, experience re-enters)
```

| Phase | Meaning | Action hook |
| --- | --- | --- |
| `waking` | Presence detected; acknowledge gently | `wake_actions` |
| `occupied` | Presence persisted; experiences apply | per-state enter/exit |
| `cooldown` | Presence gone; wind down gracefully | `cooldown_actions` |
| `vacant` | Nobody here | `vacant_actions` (or `pass_through_actions`) |

Zero durations skip phases: `wake_duration: 0` occupies instantly,
`cooldown_duration: 0` goes straight to vacant.

**Presence model.** A space is present when *any* presence entity is
active. Active means: classic binary states (`on`, `home`, `occupied`,
`detected`), mmWave presence states (`present`, `moving`, `stationary`),
any numeric state > 0 (zone counts, ESPresense/Bermuda person counts,
mmWave target counts), or any state listed in the space's
`presence_match` (BLE room trackers reporting a room name). Multiple
sensor types aggregate naturally: momentary motion triggers the wake,
sustained mmWave occupancy keeps it alive.

### Experience states

User-defined, active only while occupied.

| Field | Purpose |
| --- | --- |
| `name`, `icon`, `id` (slug) | Identity; id is stable across renames |
| `priority` | Highest matching state wins |
| `evidence_entities` + `evidence_mode` (any/all) | What indicates this experience |
| `active_states` | Which entity states count as evidence (default `on,playing,buffering,home,occupied,open,detected`) |
| `hold_occupancy` | Evidence keeps the space occupied without presence (movie night) |
| `enter_actions` / `exit_actions` | Standard HA action sequences, run as restart-mode scripts |

**Inference:** on any evidence change while occupied, pick the
highest-priority state whose evidence matches. A state with no evidence is
your baseline (always matches). If no user baseline exists, an implicit
*Occupied* state fills in. Time-of-day or person-based variants belong
*inside* action sequences as conditions/choose blocks — one state, adaptive
behavior.

**Manual override:** selecting a state on the select entity (or
`set_state`, or a control) pins it until the space goes vacant, *Resume
automatic* is pressed, or `clear_override` is called. The `set_state`
service and controls also wake a vacant space — walking in and hitting
"movie time" just works.

### Controls

Switch-Manager-style bindings, but space-aware. Two binding kinds:
**entity** (modern `event` entities from remotes, or plain
switch/sensor/button entities, with a trigger like `single`, `double`,
`on`, `any`) and **bus event** (raw `zha_event` / `deconz_event` /
`hue_event` / Lutron / Z-Wave notification events from remotes that never
become entities, matched on a captured data subset). Both map to a
command:

`set_state` · `cycle_states` · `resume_automatic` · `wake` ·
`make_vacant` · `toggle_automation` · `run_actions` (custom sequence)

Semantics: commands respect the space (cycling from vacant wakes into the
first state; `wake` without presence behaves like a pass-through if nobody
arrives). `toggle_automation` works even while paused so a button can
always un-pause its room.

**Press-to-program:** the options flow's *Add a control by pressing it*
listens (30 s) for the next press — watching every `event` entity and the
known controller bus event types — then prefills the binding with exactly
what fired; the user only picks the command. Bus captures keep the scalar
event-data keys as the match signature, so the same button and press type
match while transient payload fields are ignored.

### Events & services

`labs_experience_event` fires for every transition with
`type` (`phase_changed` | `state_changed` | `passing_through`),
`entry_id`, `space`, `from`, `to` (+ names). Services:
`labs_experience.set_state`, `labs_experience.clear_override` — both
target the space's select entity.

### Entities per space

`select.*_experience`, `sensor.*_phase` (enum), `binary_sensor.*_occupied`,
`switch.*_automation` (pause engine; restored across restarts),
`button.*_resume_automatic`. One device per space, suggested into the
linked area. Diagnostics export the full config and engine snapshot.

## Engine implementation

`SpaceEngine` (one per entry, in `entry.runtime_data`) is purely
event-driven: one `async_track_state_change_event` subscription over
presence ∪ evidence ∪ control entities, plus `async_call_later` timers
(wake / clear / cooldown). Entities subscribe to the engine
coordinator-style. Key behaviors:

- **Restart adoption:** on start/reload the engine reads current presence
  and adopts `occupied`/`vacant` *without running actions* — no light
  flashes after a restart.
- **Hold sync:** a `_sync_clear_timer` keeps the clear countdown consistent
  whenever presence, evidence, or overrides change; holds cancel the
  countdown, releasing a hold restarts it.
- **Cooldown recovery:** presence during cooldown re-enters the picked
  experience (re-running enter actions to undo the wind-down).
- **Scripts:** action sequences are validated once, cached, and run in
  restart mode so rapid transitions never queue stale actions.

Requires HA ≥ 2024.12 (`entry.runtime_data`, modern `OptionsFlow`).

## Prior art

- **Magic Areas** — pioneered area states (occupied/extended/sleep) with
  aggregated sensors. Labs differs: arbitrary *named* experiences with
  evidence inference and per-state action sequences, a wake/acknowledge
  phase, and physical controls; behavior lives in HA actions instead of
  feature toggles.
- **Switch Manager** — great button→action binding via blueprints. Labs
  controls are simpler (no per-device blueprints yet) but space-aware:
  the same button does the right thing for *this room's* state.
- **Presence-hold booleans / Wasp-in-a-box blueprints** — replaced by
  `hold_occupancy` and the lifecycle engine.

### Shared ambiance (v0.5)

Open floor plans need spaces that are *passive* participants in a
neighbor's activity. An `AmbianceRule` watches any entity (typically the
neighbor's experience select) and, while matching, overlays this space's
lighting: brightness cap, vacant glow, wake level. Highest priority wins;
manual authority always beats ambiance; occupancy stays local per zone.
Because the trigger is a plain entity, the same mechanism handles bedtime
toggles, alarm states, and future whole-home modes.

### Spaces panel (v0.5)

A native sidebar panel (custom web component served by the integration,
HA websocket + services only): area-grouped live overview, expandable
lifecycle flow strip and priority state ladder with live evidence chips
and one-tap state testing, deep links into the native options flow. State
definitions are published as recorder-excluded attributes on the
experience select — the panel's (and future cards') data contract.

## Roadmap

1. **Visual flow editor (labs-ha-cards):** the panel's next act — a
   node/edge canvas over the same select-attribute data contract: phases
   and states as nodes, evidence/controls/ambiance as typed edges, drag
   to retune priorities and timings (writing back through the options
   flow API), live tokens moving as rooms transition. The Spaces panel
   ships the read/test surface; the editor makes it authorable.
2. **Explicit transition rules:** optional guards ("*Sleeping* can only be
   entered from *Winding down*", "never auto-leave *Movie* before 30 min"),
   turning inference into a real state machine when wanted.
3. **Controller blueprints:** per-device control packs (Hue dimmer, IKEA
   Styrbar, Aqara cube) that pre-fill event types — full Switch Manager
   parity.
4. **Person-aware experiences:** evidence conditioned on *who* is present;
   per-person action variants.
5. **Space relationships:** hallway pass-through pre-wakes adjacent
   spaces; whole-home modes (Night, Away, Guests) gating all spaces.
6. **Time-layered defaults:** first-class morning/day/evening/night action
   variants so conditions inside sequences become optional.
7. **Occupancy intelligence:** learned clear delays per state/time from
   history; presence prediction.
8. **Logbook & trace integration:** human-readable "Living Room →
   Watching TV (TV started playing)" entries with cause chains.
