# SKU Decoder

The SKU Decoder reverse-engineers an existing SKU string back into its component fields, extras, item name, and item description. It lives in the **SKU Decoder** page (`pages.py` → `decoder_page`) and the core logic is in `helpers.py` (`decode_sku`, `_decode_for_category`).

## How it works

### 1. Try every category

For each product category in inventory, the decoder attempts to parse the SKU. All successful parses are ranked; the best match is shown first.

### 2. Strip category suffix (if any)

Some categories append a fixed suffix to every SKU (currently **Hose → `JF`**). The decoder requires the suffix, strips it, then parses the rest.

Defined in `CATEGORY_SUFFIXES` in `helpers.py`. If you add suffixes for new categories in the generator, add them here too.

### 3. Split base vs extras

When a category has extras configured, the generator inserts an **`X` marker** between the base SKU and concatenated extra codes:

```
base + X + extra1 + extra2 + ...
```

The decoder finds the **rightmost** `X` and only treats it as the extras marker if the tail fully parses as a chain of known extra codes. This avoids false splits when a field option itself uses code `X` (e.g. Hose → Fitting → "No Fitting").

### 4. Walk fields in order

Fields are processed in `ordered_fields` order (same as the generator):

- **Dropdown fields** — longest-prefix match against valid options.
- **Text fields** — read characters until the next visible field's code is found downstream. If no downstream code is found, the text field contributes nothing (it does not swallow the whole SKU).
- **Machine field** — identified via `settings.machine_field` (default `Machine`; Hose uses `Application`). At least one machine option must prefix the SKU, or the category is rejected.
- **Machine visibility** — field-level and option-level `machines` tags are respected the same way as in the generator (`filter_for_machine`, `field_visible`).

### 5. Parse extras

After the base is consumed, extra codes are parsed greedily with longest-prefix matching.

### 6. Rank candidates

Each candidate gets a score:

1. Machine field matched (yes/no)
2. Number of concrete field matches
3. Negative length of leftover unmatched characters

A category needs either a machine match **or** at least two concrete field matches to qualify. This filters weak accidental matches.

### 7. Build item name & description

Once the best match is chosen, `build_selection_from_decode` rebuilds the same `sel` / `chosen` structures the generator uses, then calls `generate_mapped_name_and_description` to produce the Tally item name and catalog description from `tally_name` / `description` mappings in Settings.

---

## SKU format reference (encoder ↔ decoder)

| Rule | Generator | Decoder |
|------|-----------|---------|
| Field order | `ordered_fields` | Same |
| Separator | `settings.separator` (usually `""`) | Stripped between segments |
| Extras marker | `sep + "X"` when base and extras both exist | `rfind` + tail validation |
| Category suffix | `get_category_suffix()` appended at end | Stripped before parse |
| Machine selector | `settings.machine_field` | Same |
| Field / option visibility | `machines` tags | Same |
| Text fields | User-entered value in SKU | Lookahead to next field code |
| Item name / description | `generate_mapped_name_and_description` | Same function after rebuild |

---

## Known limitations & issues

### Text fields (CBM custom machines)

Text fields are the hardest case. The decoder guesses how many characters belong to a text segment by scanning for the next field's code. If custom text accidentally contains a valid downstream code as a substring, the split can be wrong.

**Example risk:** Client abbreviation `ABC` where `C` matches a downstream option code.

**Mitigation:** Use distinctive option codes; avoid single-character codes on fields that follow text inputs.

### `X` code collision

`X` is reserved as the extras separator. Field options can still use `X` as a code (Hose Fitting → "No Fitting"), but combining that with extras can be ambiguous in edge cases. The admin UI warns about this. Prefer codes like `NF` or `NA` for new options.

### Extras concatenation order

The generator joins extras in **user selection order**. The decoder parses extras with **greedy longest-prefix** from the start. This is fine when extra codes are prefix-free (current `1`–`7` single-char codes). It can mis-parse if you add codes where one is a prefix of another (e.g. `MS` and `MSX`).

### Partial / incomplete decode

If some fields could not be matched, they appear as **Unmatched portion** in the UI. Item name and description are still built from whatever *was* matched — they may be incomplete. Always check for leftover characters.

### Multiple category matches

Ambiguous SKUs may match more than one category. The highest-scored match is shown; others appear under "Other possible matches". Review these when decoding unfamiliar codes.

### Stale inventory

The decoder reads live inventory from `st.session_state["sku_data"]["inventory"]` (loaded via GitHub storage). If field codes, order, or mappings changed since a SKU was generated, decode can fail or produce wrong breakdowns.

### Missing Tally / Description mappings

Item name and description depend on `tally_name` and `description` values configured per option in Settings. If mappings are empty, the decoder still shows the component breakdown but may show an info message that name/description could not be built.

### Matrix export SKUs

The full-matrix CSV export generates base SKUs only (no extras, no `X` marker). Those decode correctly for field breakdown but will not include extras.

### Categories without suffix registry

Only categories listed in `CATEGORY_SUFFIXES` get suffix handling. A suffix hardcoded only in custom generator logic would not be stripped by the decoder.

---

## Files

| File | Role |
|------|------|
| `helpers.py` | `decode_sku`, `_decode_for_category`, `_split_base_and_extras`, `build_selection_from_decode` |
| `pages.py` | `decoder_page` UI |
| `DECODER.md` | This document |

## Testing tips

1. Generate a SKU in the configurator, copy it, paste into the decoder — should round-trip exactly.
2. Test with extras selected — verify `X` split and extra breakdown.
3. Test Hose SKUs — verify `JF` suffix is stripped and Manufacturer row appears.
4. Test CBM custom-machine SKUs with text fields — watch for unmatched portions.
5. If decode fails, check Settings → field codes and order match the SKU era.
