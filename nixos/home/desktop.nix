{ config, nixosConfig, pkgs, ... }:
{
  programs.kitty = {
    enable = true;
    font = { name = "JetBrains Mono"; size = 13; };
    settings = {
      linux_display_server = "wayland";
      hide_window_decorations = true;
      enable_audio_bell = false;
    };
    keybindings = {
      "ctrl+shift+c" = "copy_to_clipboard";
      "ctrl+shift+v" = "paste_from_clipboard";
      "ctrl+shift+t" = "launch --type=tab --cwd=${config.home.homeDirectory}";
      "ctrl+shift+enter" = "launch --cwd=${config.home.homeDirectory}";
      "ctrl+shift+n" = "launch --type=os-window --cwd=${config.home.homeDirectory}";
    };
  };
  programs.fuzzel = {
    enable = true;
    settings = {
      main = { font = "JetBrains Mono:size=12"; terminal = "${pkgs.kitty}/bin/kitty"; width = 40; lines = 12; };
      border = { width = 1; radius = 6; };
    };
  };
  programs.waybar = {
    enable = true;
    systemd = { enable = true; targets = [ "graphical-session.target" ]; };
    settings.mainBar = {
      layer = "top";
      position = "top";
      height = 30;
      spacing = 12;
      modules-left = [ "hyprland/workspaces" ];
      modules-right = [ "tray" "cpu" "memory" "network" "pulseaudio" "clock" ];
      "hyprland/workspaces".disable-scroll = true;
      tray.spacing = 8;
      cpu.format = "cpu {usage}%";
      memory.format = "mem {}%";
      network = { format-ethernet = "net {ipaddr}"; format-wifi = "wifi {signalStrength}%"; format-disconnected = "offline"; };
      pulseaudio = { format = "vol {volume}%"; format-muted = "muted"; };
      clock = { format = "{:%H:%M}"; tooltip-format = "{:%A, %d %B %Y}"; };
    };
    style = ''
      * { font-family: "JetBrains Mono"; font-size: 12px; }
      window#waybar { background: #161616; color: #dddddd; }
      #workspaces button { padding: 0 8px; color: #888888; }
      #workspaces button.active { color: #ffffff; }
      #cpu, #memory, #network, #pulseaudio, #clock { padding: 0 8px; }
    '';
  };
  services.mako = {
    enable = true;
    settings = {
      font = "JetBrains Mono 11";
      default-timeout = 5000;
      border-size = 1;
      border-radius = 6;
      padding = "10";
      margin = "8";
    };
  };
  services.cliphist = {
    enable = true;
    allowImages = true;
    systemdTargets = [ "graphical-session.target" ];
  };
  gtk = { enable = true; font = { name = "JetBrains Mono"; size = 11; }; };
  xdg.configFile."hypr/workstation.lua".text =
    builtins.readFile ./hyprland.lua + "\n" + nixosConfig.workstation.hyprlandExtraConfig;
  xdg.mimeApps = {
    enable = true;
    defaultApplications = {
      "text/html" = [ "google-chrome.desktop" ];
      "x-scheme-handler/http" = [ "google-chrome.desktop" ];
      "x-scheme-handler/https" = [ "google-chrome.desktop" ];
      "x-scheme-handler/claude" = [ "com.anthropic.Claude.desktop" ];
      "inode/directory" = [ "org.gnome.Nautilus.desktop" ];
    };
  };
  systemd.user.services.onepassword = {
    Unit = { Description = "1Password background application"; PartOf = [ "graphical-session.target" ]; After = [ "graphical-session.target" ]; };
    Service.ExecStart = "${nixosConfig.programs._1password-gui.package}/bin/1password --silent";
    Install.WantedBy = [ "graphical-session.target" ];
  };
}
