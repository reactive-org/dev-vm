{ config, lib, pkgs, ... }:
let
  cfg = config.workstation;
in {
  options.workstation.sharedFolder = {
    enable = lib.mkEnableOption "the explicit Parallels Shared folder at /mnt/shared";
    shareName = lib.mkOption {
      type = lib.types.strMatching "[A-Za-z0-9_-]+";
      default = "Shared";
    };
  };
  config = lib.mkIf cfg.sharedFolder.enable {
    # Parallels requests allow_other internally. This guest-wide FUSE policy
    # is required for its unprivileged helper and was explicitly approved.
    programs.fuse.userAllowOther = true;
    systemd.tmpfiles.rules = [ "d /mnt/shared 0755 ${cfg.userName} ${config.users.users.${cfg.userName}.group} -" ];
    systemd.services.workstation-shared-folder = {
      description = "Explicit Parallels host folder at /mnt/shared";
      wantedBy = [ "multi-user.target" ];
      requires = [ "prltoolsd.service" ];
      after = [ "prltoolsd.service" ];
      path = [ "/run/wrappers" pkgs.fuse3 ];
      serviceConfig = {
        User = cfg.userName;
        Group = config.users.users.${cfg.userName}.group;
        UMask = "0022";
        ExecStart = "${config.hardware.parallels.package}/bin/prl_fsd /mnt/shared -f -onosuid,nodev,noatime,fsname=${cfg.sharedFolder.shareName},subtype=prl_fsd --share --sf=${cfg.sharedFolder.shareName}";
        Restart = "on-failure";
        RestartSec = 5;
      };
    };
  };
}
