{
  description = "ARM64 Parallels developer workstation";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.home-manager = {
    url = "github:nix-community/home-manager";
    inputs.nixpkgs.follows = "nixpkgs";
  };
  inputs.llm-agents = {
    url = "github:numtide/llm-agents.nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };
  inputs.local.url = "path:./local";

  outputs = inputs@{ nixpkgs, home-manager, ... }: let
    system = "aarch64-linux";
    workstation = nixpkgs.lib.nixosSystem {
      specialArgs = {
        inherit inputs;
        workstationProfiles = {
          rails = ./profiles/rails.nix;
          java = ./profiles/java.nix;
        };
      };
      modules = [ home-manager.nixosModules.home-manager ./hosts/workstation-test inputs.local.nixosModules.default ];
    };
    pkgs = workstation.pkgs;
    cfg = workstation.config;
    userConfig = pkgs.writeText "workstation.lua"
      cfg.home-manager.users.${cfg.workstation.userName}.xdg.configFile."hypr/workstation.lua".text;
  in {
    nixosConfigurations.workstation-test = workstation;
    checks.${system} = {
      workstation-test = workstation.config.system.build.toplevel;
      hyprland-config = pkgs.runCommand "workstation-hyprland-config" {} ''
      export HOME="$TMPDIR/home"
      export XDG_RUNTIME_DIR="$TMPDIR/runtime"
      mkdir -p "$HOME/.config/hypr" "$XDG_RUNTIME_DIR"
      chmod 700 "$XDG_RUNTIME_DIR"
      cp ${userConfig} "$HOME/.config/hypr/workstation.lua"
      ${cfg.programs.hyprland.package}/bin/Hyprland --verify-config \
        --config ${cfg.environment.etc."xdg/hypr/hyprland.lua".source}
      touch "$out"
      '';
    };
  };
}
