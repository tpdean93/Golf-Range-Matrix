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
- `custom-cards/golf-club-results-card.js`

Optional global CSS resource:

- `styles/nova-lovelace-background.css`

## Required Helpers

The dashboard card expects these helpers:

- `input_select.golf_active_player`
- `input_select.golf_active_club`
- `input_text.golf_profiles_json`
- `input_text.golf_profile_bags_json`
- `input_text.golf_profile_bags_json_2`
- `input_text.golf_profile_bags_json_3`
- `input_text.golf_profile_bags_json_4`
- `input_text.golf_profile_wedge_matrices_json`
- `input_text.golf_profile_wedge_matrices_json_2`
- `input_text.golf_profile_wedge_matrices_json_3`
- `input_text.golf_profile_wedge_matrices_json_4`
- `input_text.golf_club_metadata_json`
- `input_text.golf_club_metadata_json_2`
- `input_text.golf_club_metadata_json_3`
- `input_text.golf_club_metadata_json_4`
- `input_text.golf_club_metadata_json_5`
- `input_text.golf_club_metadata_json_6`
- `input_text.golf_club_metadata_json_7`
- `input_text.golf_club_metadata_json_8`
- `input_boolean.golf_club_mapping_active`
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
profiles_entity: input_text.golf_profiles_json
profile_bags_entity: input_text.golf_profile_bags_json
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

The card enforces the 14-club max in the UI, supports custom club names, and writes the selected bag to the dynamic profile bag store. The legacy per-player bag helpers can remain configured as a compatibility mirror for the starter profiles.

## Wedge Matrix Card

Use:

```yaml
type: custom:nova-wedge-matrix-card
player_entity: input_select.golf_active_player
club_entity: input_select.golf_active_club
carry_entity: sensor.golf_carry
capture_shots: 5
profiles_entity: input_text.golf_profiles_json
profile_bags_entity: input_text.golf_profile_bags_json
profile_matrices_entity: input_text.golf_profile_wedge_matrices_json
bag_entities:
  Tyler: input_text.golf_tyler_bag
  Kids: input_text.golf_kids_bag
  Guest: input_text.golf_guest_bag
matrix_entities:
  Tyler: input_text.golf_tyler_wedge_matrix
  Kids: input_text.golf_kids_wedge_matrix
  Guest: input_text.golf_guest_wedge_matrix
players:
  - Tyler
  - Kids
  - Guest
swings:
  - Half
  - Waist
  - Shoulder
  - Full
```

The matrix columns are automatically filtered from the selected player's saved bag. It will include wedge-style clubs such as `PW`, `GW`, `SW`, `LW`, `AW`, `UW`, `56 Wedge`, or loft labels like `50`.

To auto-fill a yardage:

1. Click the cell for the saved wedge and swing type.
2. Click `Start` in the 5-shot capture panel.
3. Hit 5 shots. The card watches `sensor.golf_carry`.
4. If one is a bad ball, click `Throw Out Last` before the fifth accepted shot.
5. The cell is filled with the carry average.
6. Click `Save Matrix`.

The matrix stores compact text like:

```text
LW:Half=57/67,Full=74/80;SW:Half=67/80,Full=85/92
```

That keeps it compatible with simple Home Assistant `input_text` helpers while still supporting custom wedge names and yardage ranges.

## Club Results Card

Use:

```yaml
type: custom:golf-club-results-card
player_entity: input_select.golf_active_player
profile_bags_entity: input_text.golf_profile_bags_json
metadata_entity: input_text.golf_club_metadata_json
metadata_chunks: 8
summary_entity_prefix: sensor.golf_summary
```

The card creates one visual result card for each saved club in the selected player's bag. It reads mapped data from MQTT discovery entities such as `sensor.golf_summary_tyler_bag` and stores manual brand, model, and image URL details in the chunked metadata helpers.
