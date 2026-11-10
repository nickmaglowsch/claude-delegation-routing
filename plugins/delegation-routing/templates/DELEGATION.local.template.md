# DELEGATION — local overrides

Your personal routing choices. Where this file conflicts with `DELEGATION.md`, this file wins. `/delegation-setup` creates it once and never overwrites it, so put your changes here, not in `DELEGATION.md`. That keeps `DELEGATION.md` identical to the plugin template, so plugin updates apply cleanly.

Versioned model IDs still belong in `~/.paseo/orchestration-preferences.json`. This file holds the rules that sit around them. Examples of what goes here:

- Which model counts as your top tier. For example: "The Claude top tier is `opus` at `xhigh` effort; Fable is not used."
- Overriding a `list_models` tier description. For example: "The OpenAI top tier is the everyday workhorse at xhigh, not the tier labelled frontier."
- Which gateway model is your third-family advisor, and at what effort.
- Different fan-out caps, if your quota needs them.
