-- prlcp exposes a tiny Wayland surface to broker host clipboard offers. Keep
-- it out of the tiled layout, but do not block focus: Wayland requires an input
-- serial from a focused surface before a client can publish a selection.
o.window({ title = "^Parallels Shared Clipboard$" }, {
  float = true,
  border_size = 0,
  size = { 1, 1 },
  move = { "(monitor_w-1)", "(monitor_h-1)" },
})

-- Parallels publishes its complete mode list shortly after Hyprland starts.
-- Reload the fixed monitor configuration once, then capture the final state.
o.launch_on_start(os.getenv("HOME") .. "/.local/bin/dev-vm-display-init")
o.launch_on_start(os.getenv("HOME") .. "/.local/bin/dev-vm-session-check")
