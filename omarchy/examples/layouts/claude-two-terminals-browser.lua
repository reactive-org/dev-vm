-- Example per-VM layout: Claude on the right, two Foot terminals on the left,
-- and a floating Chromium window. Pass this file with
-- OMARCHY_LAYOUT_FILE; it is not installed by default.

local function workstation_window(class, size, move)
  o.window({ class = class }, {
    float = true,
    workspace = "1 silent",
    size = size,
    move = move,
    persistent_size = true,
  })
end

-- Claude occupies the full usable height of the right 60%.
workstation_window(
  "^com\\.anthropic\\.Claude$",
  { "(monitor_w*0.60-18)", "(monitor_h-50)" },
  { "(monitor_w*0.40+6)", 38 }
)

-- Dedicated Foot app IDs make the upper and lower left positions stable.
workstation_window(
  "^org\\.omarchy\\.dev-vm-terminal-top$",
  { "(monitor_w*0.40-18)", "(monitor_h*0.50-31)" },
  { 12, 38 }
)
workstation_window(
  "^org\\.omarchy\\.dev-vm-terminal-bottom$",
  { "(monitor_w*0.40-18)", "(monitor_h*0.50-31)" },
  { 12, "(monitor_h*0.50+6)" }
)

-- Chromium overlaps the base layout and remembers manual resizing.
workstation_window(
  "^omarchy-work-browser$",
  { "monitor_w*0.46", "monitor_h*0.62" },
  { "monitor_w*0.27", "monitor_h*0.18" }
)

o.exec_on_start(o.launch_sole(
  "org.omarchy.dev-vm-terminal-top",
  "foot --app-id=org.omarchy.dev-vm-terminal-top --title='Top terminal'"
))
o.exec_on_start(o.launch_sole(
  "org.omarchy.dev-vm-terminal-bottom",
  "foot --app-id=org.omarchy.dev-vm-terminal-bottom --title='Bottom terminal'"
))
o.exec_on_start(o.launch_sole("com.anthropic.Claude", "claude-desktop"))
o.exec_on_start(o.launch_sole(
  "omarchy-work-browser",
  "chromium --class=omarchy-work-browser --new-window"
))
