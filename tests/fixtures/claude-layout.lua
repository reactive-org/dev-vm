-- Exercise native layout keybinding decisions without opening real windows.
local windows, workspace, commands, ordinary = {}, { id = 1 }, {}, 0
local shortcut
o = {
  window = function() end,
  exec_on_start = function() end,
  shell_quote = function(value) return "'" .. value .. "'" end,
  launch_sole = function(_, command) return command end,
  launch_terminal = function() return function() ordinary = ordinary + 1 end end,
  rebind = function(keys, _, callback)
    assert(keys == "SUPER + RETURN")
    shortcut = callback
  end,
  bind_expressions = {},
}
hl = {
  get_active_workspace = function() return workspace end,
  get_windows = function() return windows end,
  get_active_window = function() return { pid = 123 } end,
  exec_cmd = function(command) table.insert(commands, command) end,
}
dofile(assert(arg[1], "layout path required"))

local top = "org.omarchy.dev-vm-terminal-top"
local bottom = "org.omarchy.dev-vm-terminal-bottom"
shortcut()
assert(commands[#commands]:find("--app-id=" .. top, 1, true))
assert(commands[#commands]:find('$(omarchy-cmd-terminal-cwd 123)', 1, true))
windows = { { class = top }, { class = "foot" } }
shortcut()
assert(commands[#commands]:find("--app-id=" .. bottom, 1, true))
windows = { { class = bottom } }
shortcut()
assert(commands[#commands]:find("--app-id=" .. top, 1, true))
windows = { { class = top }, { class = bottom } }
shortcut()
assert(#commands == 3 and ordinary == 1)
workspace, windows = { id = 2 }, {}
shortcut()
assert(#commands == 3 and ordinary == 2)
workspace = nil
shortcut()
assert(#commands == 3 and ordinary == 3)
assert(o.bind_expressions[shortcut] == "o.launch_workstation_terminal")
print("PASS layout terminal recovery, occupied slots, ordinary terminals and workspaces")
