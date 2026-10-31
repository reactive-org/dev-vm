-- Fixed high-resolution Parallels display. Live resolution changes are not used.
local omarchy_monitor_scale = 1.0
local omarchy_gdk_scale = 1

hl.monitor({ output = "", mode = "__DISPLAY_MODE__", position = "0x0", scale = omarchy_monitor_scale })
hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
