{ ... }:
{
  imports = [
    ./hardware-configuration.nix
    ./installation.nix
    ./identity.nix
    ./integration.nix
    ../../modules/base.nix
    ../../modules/users.nix
    ../../modules/parallels.nix
    ../../modules/desktop-hyprland.nix
    ../../modules/developer-apps.nix
    ../../modules/docker.nix
    ../../modules/home-manager.nix
    ../../modules/local-configuration.nix
    ../../modules/shared-folder.nix
  ];

  networking.hostName = "workstation-test";
  # Installation updates only this VM's copy with its actual disk configuration.
  system.stateVersion = "26.05";
}
