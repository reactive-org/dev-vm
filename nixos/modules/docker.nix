{ config, pkgs, ... }:
{
  virtualisation.docker.enable = true;
  users.users.${config.workstation.userName}.extraGroups = [ "docker" ];
  environment.systemPackages = [ pkgs.docker-buildx pkgs.docker-compose ];
}
