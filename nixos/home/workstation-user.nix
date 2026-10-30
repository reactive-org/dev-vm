{ config, lib, nixosConfig, pkgs, ... }:
let cfg = nixosConfig.workstation; in
{
  imports = [ ./shell.nix ./desktop.nix ];
  home.stateVersion = "26.05";
  home.sessionPath = [ "$HOME/.local/bin" ];
  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    NIXOS_OZONE_WL = "1";
    OP_BIOMETRIC_UNLOCK_ENABLED = "true";
  };
  programs.git = {
    enable = true;
    lfs.enable = true;
    includes = map (path: { inherit path; }) cfg.gitIncludes;
  };
  programs.mise.globalConfig.tools = cfg.miseTools;
  home.activation.projectsDirectory = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    run ${pkgs.coreutils}/bin/mkdir -p -- ${lib.escapeShellArg "${config.home.homeDirectory}/${cfg.projectsDirectory}"}
  '';
  programs.claude-code = {
    enable = true;
    package = pkgs.claude-code;
    mutableSettings = true;
  };
  # Identity, private keys, Claude auth and 1Password state stay mutable and
  # are never copied from the host or embedded in this Home Manager source.
  xdg.enable = true;
  xdg.userDirs = { enable = true; createDirectories = true; };
}
