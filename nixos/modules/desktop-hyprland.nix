{ config, pkgs, ... }:
let
  hyprlandConfig = pkgs.writeText "hyprland.lua" ''
    hl.monitor({ output = "", mode = "2560x1600@59.99", position = "auto", scale = 1 })
    dofile(os.getenv("HOME") .. "/.config/hypr/workstation.lua")
    hl.on("hyprland.start", function()
      hl.exec_cmd("uwsm finalize")
      hl.exec_cmd("kitty")
    end)
  '';
  # UWSM requires a readable entry point; NixOS capability wrappers are
  # deliberately execute-only. Keep the wrapper and invoke it via this script.
  hyprlandSession = pkgs.writeShellScript "workstation-hyprland" ''
    exec ${config.programs.hyprland.package}/bin/start-hyprland --path /run/wrappers/bin/Hyprland -- --config /etc/xdg/hypr/hyprland.lua
  '';
in {
  programs.hyprland = { enable = true; withUWSM = true; };
  services.greetd = {
    enable = true;
    settings.default_session = {
      command = "/etc/greetd/workstation-login";
      user = "greeter";
    };
  };
  # greetd deliberately survives rebuilds. Keep its command stable so future
  # logins resolve the current launcher rather than an old store generation.
  environment.etc."greetd/workstation-login".source = pkgs.writeShellScript "workstation-login" ''
    exec ${pkgs.greetd}/bin/agreety --cmd '${pkgs.uwsm}/bin/uwsm start -D Hyprland -- /etc/greetd/workstation-session'
  '';
  environment.etc."greetd/workstation-session".source = hyprlandSession;
  environment.etc."xdg/hypr/hyprland.lua".source = hyprlandConfig;
  environment.systemPackages = with pkgs; [ kitty wl-clipboard nautilus grim slurp swaylock ];
  fonts.packages = with pkgs; [ jetbrains-mono meslo-lgs-nf ];
  security.pam.services.swaylock = {};
  security.polkit.enable = true;
  systemd.user.services.hyprpolkitagent = {
    description = "Hyprland authentication agent";
    wantedBy = [ "graphical-session.target" ];
    after = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    serviceConfig.ExecStart = "${pkgs.hyprpolkitagent}/libexec/hyprpolkitagent";
  };
  services.gvfs.enable = true;
  programs.dconf.enable = true;
  xdg.portal.extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
  services.pipewire = { enable = true; pulse.enable = true; alsa.enable = true; };
  security.rtkit.enable = true;
}
