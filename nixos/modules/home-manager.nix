{ config, ... }:
{
  home-manager = {
    useGlobalPkgs = true;
    useUserPackages = true;
    # Preserve any unmanaged dotfile rather than silently overwriting it.
    backupFileExtension = "before-home-manager";
    users.${config.workstation.userName} = import ../home/workstation-user.nix;
  };
}
