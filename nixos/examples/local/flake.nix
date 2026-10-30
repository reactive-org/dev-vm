{
  description = "Example private workstation overrides (non-secret only)";
  outputs = { ... }: {
    nixosModules.default = { pkgs, workstationProfiles, ... }: {
      # Select only the profiles you use. Their runtimes remain mise-owned.
      imports = [ workstationProfiles.rails ];
      workstation = {
        extraPackages = [ pkgs.htop ];
        projectsDirectory = "Development/Projects";
        gitIncludes = [ "~/.gitconfig-client" ];
        hyprlandExtraConfig = ''
          hl.window_rule({
            name = "chrome-floating",
            match = { class = "^(google-chrome)$" },
            float = true,
          })
        '';
      };
    };
  };
}
