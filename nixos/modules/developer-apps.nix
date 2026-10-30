{ config, inputs, pkgs, ... }:
let
  upstreamClaude = inputs.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.claude-desktop;
  # Retain upstream's official ARM64 repackaging and FHS runtime, but omit
  # Cowork's firmware and virtiofsd. This workstation does not run Cowork VMs.
  claudeDesktop = pkgs.buildFHSEnv (upstreamClaude.args // {
    targetPkgs = _: with pkgs; [
      upstreamClaude.unwrapped gcc-unwrapped.lib libglvnd mesa libgbm
      vulkan-loader systemdMinimal
    ];
  });
in {
  environment.systemPackages = with pkgs; [
    firefox google-chrome vscode mise gh claudeDesktop
    bat btop direnv fd fzf git-lfs jq lazygit ripgrep shellcheck starship
    tmux tree zoxide unzip zip wget gnumake
  ];
  programs._1password.enable = true;
  programs._1password-gui = {
    enable = true;
    polkitPolicyOwners = [ config.workstation.userName ];
  };
  services.gnome.gnome-keyring.enable = true;
}
