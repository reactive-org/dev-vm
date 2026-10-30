{ config, lib, ... }:
{
  options.workstation = {
    projectsDirectory = lib.mkOption {
      type = lib.types.str;
      default = "Development/Projects";
      description = "Projects directory relative to the workstation user's home.";
    };
    extraPackages = lib.mkOption {
      type = lib.types.listOf lib.types.package;
      default = [];
      description = "Additional durable packages; language runtimes belong to mise.";
    };
    gitIncludes = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [];
      description = "Paths to mutable, separately provisioned Git include files.";
    };
    hyprlandExtraConfig = lib.mkOption {
      type = lib.types.lines;
      default = "";
      description = "Non-secret Hyprland Lua configuration appended to the shared defaults.";
    };
    miseTools = lib.mkOption {
      type = with lib.types; attrsOf (either str (listOf str));
      default = {};
      description = "Opt-in mise runtime versions; install explicitly with mise install.";
    };
  };
  config = {
    assertions = [{
      assertion = builtins.all (part: part != "" && part != "." && part != "..")
        (lib.splitString "/" config.workstation.projectsDirectory);
      message = "workstation.projectsDirectory must be a normalized relative path inside the user's home.";
    }];
    environment.systemPackages = config.workstation.extraPackages;
  };
}
