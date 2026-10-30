{ pkgs, ... }:
{
  workstation.extraPackages = with pkgs; [ gcc gnumake pkg-config libyaml libffi openssl postgresql sqlite redis ];
  workstation.miseTools = { ruby = "3.4"; node = "lts"; };
}
