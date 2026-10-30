{ pkgs, ... }:
{
  hardware.parallels.enable = true;
  # Match the host build without moving the pinned desktop/toolchain input.
  hardware.parallels.package = pkgs.prl-tools.overrideAttrs {
    version = "27.1.0-58756";
    src = pkgs.fetchurl {
      url = "https://download.parallels.com/desktop/v27/27.1.0-58756/ParallelsDesktop-27.1.0-58756.dmg";
      hash = "sha256-3sh18YutPqbpLgLNXIe5pr9gMGx2z6RnWe7/3RJq7Vc=";
    };
  };
  # The matching 27.1.0 controller passed focused Kitty and host/guest copying.
  # Retry an early startup failure if UWSM has not exported the display yet.
  systemd.user.services.prlcc = {
    after = [ "graphical-session.target" ];
    partOf = [ "graphical-session.target" ];
    serviceConfig = {
      Restart = "on-failure";
      RestartSec = 2;
    };
  };
}
