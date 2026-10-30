local main = "ALT + SUPER"

hl.config({
    input = {
        kb_layout = "us",
        follow_mouse = 1,
        touchpad = { natural_scroll = true },
    },
    general = { gaps_in = 4, gaps_out = 8, border_size = 2, layout = "dwindle" },
    decoration = { rounding = 6 },
    animations = { enabled = false },
    misc = { disable_hyprland_logo = true, disable_splash_rendering = true },
})

local applications = {
    Return = "kitty",
    Space = "fuzzel",
    B = "google-chrome-stable",
    ["SHIFT + B"] = "firefox",
    C = "code",
    E = "nautilus",
    L = "swaylock -f -c 111111",
    P = "cliphist list | fuzzel --dmenu | cliphist decode | wl-copy",
    ["SHIFT + S"] = [[grim -g "$(slurp)" - | wl-copy]],
}
for key, command in pairs(applications) do
    hl.bind(main .. " + " .. key, hl.dsp.exec_cmd(command))
end
hl.bind(main .. " + Q", hl.dsp.window.close())
hl.bind(main .. " + F", hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }))
hl.bind(main .. " + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind(main .. " + SHIFT + E", hl.dsp.exit())

for _, direction in ipairs({ "left", "right", "up", "down" }) do
    hl.bind(main .. " + " .. direction, hl.dsp.focus({ direction = direction }))
    hl.bind(main .. " + SHIFT + " .. direction, hl.dsp.window.move({ direction = direction }))
end
for workspace = 1, 9 do
    hl.bind(main .. " + " .. workspace, hl.dsp.focus({ workspace = workspace }))
    hl.bind(main .. " + SHIFT + " .. workspace, hl.dsp.window.move({ workspace = workspace }))
end
hl.bind(main .. " + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind(main .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
