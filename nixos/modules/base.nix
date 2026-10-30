{ lib, pkgs, ... }:
{
  assertions = [{
    assertion = pkgs.stdenv.hostPlatform.system == "aarch64-linux";
    message = "This prototype supports only ARM64 Parallels guests.";
  }];
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  nixpkgs.config.allowUnfreePredicate = pkg: builtins.elem (lib.getName pkg) [
    "prl-tools" "google-chrome" "vscode" "claude-code"
    "1password" "1password-cli"
  ];
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  fileSystems."/boot".options = lib.mkForce [ "fmask=0077" "dmask=0077" ];
  networking.useNetworkd = true;
  networking.useDHCP = false;
  systemd.network.enable = true;
  systemd.network.networks."10-ethernet" = {
    matchConfig.Type = "ether";
    networkConfig.DHCP = "yes";
  };
  time.timeZone = "Australia/Melbourne";
  i18n.defaultLocale = "en_AU.UTF-8";
  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "no";
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
    };
  };
  environment.systemPackages = with pkgs; [ git neovim curl pciutils ];
}
