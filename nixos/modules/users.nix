{ config, lib, pkgs, ... }:
let cfg = config.workstation; in {
  options.workstation = {
    userName = lib.mkOption { type = lib.types.strMatching "[a-z_][a-z0-9_-]*"; default = "developer"; };
    authorizedKeys = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
  };
  config = {
    assertions = [{
      assertion = config.security.sudo.wheelNeedsPassword;
      message = "The workstation must finish provisioning with password-protected sudo.";
    }];
    programs.zsh.enable = true;
    users.mutableUsers = true;
    users.users.${cfg.userName} = {
      isNormalUser = true;
      shell = pkgs.zsh;
      extraGroups = [ "wheel" ];
      openssh.authorizedKeys.keys = cfg.authorizedKeys;
    };
    security.sudo.wheelNeedsPassword = true;
  };
}
