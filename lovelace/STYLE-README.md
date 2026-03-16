# Lovelace Dashboard Style Guide

This file defines the dashboard styling rules for this repository.
Use it as the default reference whenever adding or editing cards in `lovelace/views/`.

## Goals

- Keep the dashboard visually consistent across all views.
- Make important states readable at a glance.
- Use color as meaning, not decoration.
- Prefer a small set of repeated patterns over one-off card designs.

## Card Types

### Big cards

Use big cards for high-importance items that summarize a system or show one main value.

Examples:
- Electricity
- Internet
- Fridge
- Water heater

Rules:
- Use `custom:button-card`.
- Use `grid_options` with `columns: 6` and `rows: 2`.
- Use fixed height: `108px`.
- Use border radius: `20px`.
- Use padding: `16px`.
- Use shadow: `0 6px 14px rgba(0,0,0,0.20)`.
- Show only one primary value or status line.
- Keep the layout to 2 rows whenever possible.

Preferred layout:
```yaml
styles:
  card:
    - border-radius: 20px
    - padding: 16px
    - height: 108px
    - box-shadow: 0 6px 14px rgba(0,0,0,0.20)
```

### Small cards

Use small cards for simple toggles and quick actions.

Examples:
- Bathroom light
- Kitchen light
- Door light
- LED strip

Rules:
- Use `custom:button-card` for important toggles.
- Use `grid_options` with `columns: 3` and `rows: 1`.
- Use fixed height: `88px`.
- Use border radius: `18px`.
- Use padding: `10px 12px`.
- Use shadow: `0 6px 14px rgba(0,0,0,0.16)`.
- Keep label short, ideally one word.
- Prefer a stacked layout with icon above label.
- Center both icon and label so small cards stay stable with Arabic text.
- Use slightly smaller text and icon sizes to prevent overlap.

Preferred layout:
```yaml
styles:
  card:
    - border-radius: 18px
    - padding: 10px 12px
    - height: 88px
    - box-shadow: 0 6px 14px rgba(0,0,0,0.16)
  grid:
    - grid-template-areas: '"i"' '"n"'
    - grid-template-columns: 1fr
    - grid-template-rows: min-content min-content
    - row-gap: 4px
    - align-items: center
```

### Standard tiles

Use native `tile` cards only for lower-priority controls or where a custom layout is not needed.

Examples:
- Water filter
- Water pump
- Covers
- Simple entity display

Rules:
- Prefer `tile` only when default Home Assistant styling is acceptable.
- If a card needs custom color logic, multiple values, or stronger visual hierarchy, switch to `custom:button-card`.

## Typography

Use the following type hierarchy:

- Big card title: `16px`, `700`
- Big card main value: `17px` to `24px`, `800`
- Big card secondary status: `15px`, `700`
- Small card title: `15px`, `700`

Rules:
- Text color should generally remain white on colored cards.
- Avoid long text labels.
- Keep status text short and direct.

## Color System

Use soft graduated colors instead of harsh blue/red unless there is a strong reason.

### Base palette

- Slate / unknown / inactive:
  - `#546e7a -> #78909c`
- Teal / cold / healthy connection:
  - `#2f7a6d -> #68b0a1`
- Green / normal stable state:
  - `#7da453 -> #a8c66c`
- Amber / warning / elevated condition:
  - `#c49a3a -> #e6c76a`
- Warm neutral / poor internet quality:
  - `#8d6e63 -> #bcaaa4`

Rules:
- Use gradients for major cards.
- Use slate for unavailable or inactive fallback states.
- Avoid bright red unless the state is truly critical.
- Avoid strong blue as the default temperature color.

## State Rules

### Toggle cards

For switches and lights:
- Background changes by `on` / `off`.
- Icon color should clearly indicate power state.
- When `off`, use muted icon color such as `#dfe7ea` or `#cfd8dc`.
- When `on`, use lighter icon tint such as `#fff8e1` or `#f3f8e8`.

### Cover cards

For covers and shutters:
- Prefer `custom:button-card` over plain `tile` on the home view.
- Show the current position percentage when available.
- Combine the percentage with one short state word such as `مفتوح` or `مغلق`.
- Use slate for closed, amber for open, and warm neutral for moving states.
- Use `tap_action: more-info` unless a direct control layout is intentionally designed.

### Temperature cards

Recommended fridge thresholds:
- `<= 0C`: freezing
- `0C to 5C`: normal
- `> 5C`: warning

Recommended colors:
- Freezing: teal
- Normal: green
- Warning: amber
- Unknown: slate

### Internet cards

Show only the main number on the home dashboard.

Rules:
- Home card should prioritize download speed.
- Detailed metrics like upload and ping belong in the dedicated internet view.
- Use graduated state coloring:
  - Good: teal
  - Medium: amber
  - Weak: warm neutral
  - Unknown: slate

## Icon Rules

- Use one clear icon per card.
- Icons should match the real-world object, not just the domain.
- Keep icon size consistent:
  - Big cards: `34px` to `36px`
  - Small cards: `22px`

Examples:
- Internet: `mdi:web`
- Fridge: `mdi:fridge`
- Bathroom light: `mdi:shower`
- Kitchen light: `mdi:ceiling-light`
- Door light: `mdi:coach-lamp`
- LED strip: `mdi:led-strip-variant`
- Cover / shutter: `mdi:window-shutter`

## Spacing And Alignment

Rules:
- Big cards should align with other big cards by using the same height.
- Small cards should align with other small cards by using the same height.
- Avoid cards that grow based on long text when neighboring cards are fixed-size.
- Keep big cards visually balanced with two text rows max.
- Keep small cards to a single compact row.

## Interaction Rules

- Use `tap_action: toggle` for direct control cards.
- Use `tap_action: navigate` for summary cards that open another view.
- Use `hold_action: more-info` on custom cards when useful.

## Naming Rules

- Prefer short Arabic labels on the home view.
- Use one-word labels where possible for small cards.
- Avoid repeating the domain in the name if the icon already explains it.

Examples:
- `حمام` instead of `إضاءة حمام`
- `المطبخ` instead of `إضاءة مطبخ`
- `الباب` instead of `إضاءة باب المنزل`
- `ليد` instead of `ليد المطبخ`

## Reuse First

Before creating a new visual style:
- Check whether the card is a big card or a small card.
- Reuse an existing gradient family.
- Reuse the same padding, radius, and height.
- Reuse icon sizing and text sizing from similar cards.

If a new card does not fit these rules, document why before introducing a new style.

## Suggested Workflow

When adding a new dashboard card:
1. Decide whether it is big, small, or standard tile.
2. Pick the closest existing card pattern.
3. Reuse the same dimensions and typography.
4. Add color logic only if it communicates state.
5. Keep labels short and readable.

## Current Source Of Truth

The current best examples of this style are in:
- `lovelace/views/home.yaml`
- `lovelace/views/temperature.yaml`

Any future dashboard changes should follow this file unless we intentionally revise the style system.
