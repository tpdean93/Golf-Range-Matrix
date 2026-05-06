# Home Assistant Setup

This project is meant to stay separate from your HOA app repo. Home Assistant remains the control surface, while the logger runs locally on the HA box, lab PC, or any machine that can reach the MQTT broker.

## Custom Card Resources

Package these files as Lovelace module resources:

- `custom-cards/nova-shot-tracer-card.js`
- `custom-cards/golf-metric-panel-card.js`
- `custom-cards/golf-shot-history-card.js`
- `custom-cards/golf-session-control-card.js`
- `custom-cards/nova-bag-builder-card.js`
- `custom-cards/nova-wedge-matrix-card.js`

Optional global CSS resource:

- `styles/nova-lovelace-background.css`

## Required Helpers

The dashboard card expects these helpers:

- `input_select.golf_active_player`
- `input_select.golf_active_club`
- `input_text.golf_tyler_bag`
- `input_text.golf_kids_bag`
- `input_text.golf_guest_bag`
- `input_text.golf_tyler_wedge_matrix`
- `input_text.golf_kids_wedge_matrix`
- `input_text.golf_guest_wedge_matrix`

Optional session/logger helpers:

- `input_boolean.golf_recording_enabled`
- `input_boolean.golf_bag_test_active`
- `input_select.golf_session_mode`
- `input_text.golf_session_id`
- `input_number.golf_bag_test_shots_per_club`
- `input_number.golf_bag_test_club_index`
- `input_number.golf_bag_test_shot_count`
- `input_text.golf_last_context_json`

## Bag Builder Card

Use:

```yaml
type: custom:nova-bag-builder-card
player_entity: input_select.golf_active_player
club_entity: input_select.golf_active_club
max_clubs: 14
bag_entities:
  Tyler: input_text.golf_tyler_bag
  Kids: input_text.golf_kids_bag
  Guest: input_text.golf_guest_bag
players:
  - Tyler
  - Kids
  - Guest
catalog:
  - Driver
  - 3 Wood
  - 5 Wood
  - 7 Wood
  - 3 Hybrid
  - 4 Hybrid
  - 5 Hybrid
  - 4 Iron
  - 5 Iron
  - 6 Iron
  - 7 Iron
  - 8 Iron
  - 9 Iron
  - PW
  - GW
  - 52 Wedge
  - 56 Wedge
  - 60 Wedge
  - Putter
```

The card enforces the 14-club max in the UI, supports custom club names, and writes the selected bag to the active player's `input_text`.

## Wedge Matrix Card

Use:

```yaml
type: custom:nova-wedge-matrix-card
player_entity: input_select.golf_active_player
matrix_entities:
  Tyler: input_text.golf_tyler_wedge_matrix
  Kids: input_text.golf_kids_wedge_matrix
  Guest: input_text.golf_guest_wedge_matrix
players:
  - Tyler
  - Kids
  - Guest
wedges:
  - LW
  - SW
  - GW
  - PW
swings:
  - Half
  - Waist
  - Shoulder
  - Full
```

The matrix stores compact text like:

```text
LW:Half=57/67,Full=74/80;SW:Half=67/80,Full=85/92
```

That keeps it compatible with simple Home Assistant `input_text` helpers while still supporting custom wedge names and yardage ranges.
