# Arthur duck-footed walk — 27 Nov 2026

- Cause: Tripo modelled his boots turned out about 25-30 degrees (sole direction from the boot
  geometry), while Manny's feet turn out about 6.5 degrees. Shared animations keep each body's rest
  offset, so his walk turned his toes out by the extra 20 degrees.
- Fix: turned each lower leg about its own axis in the rest pose (left -18.6, right +24 degrees)
  so the soles point 6.4 / -6.6 degrees, applied that as the new rest pose, re-set bone
  orientations to Manny's (0.0 degrees difference). Boot shafts are round, so the twist doesn't show.
- Re-exported and re-imported the same clean way (2 material slots, 3 LODs, root scale 1).
- Backup before the change: `Arthur_rigged_before_feet.blend`. Image: `img/arthur_feet.png`.
- Pipeline rule added: compare foot (sole) direction with the archetype's at rest, along with
  the arm angle, before binding.
