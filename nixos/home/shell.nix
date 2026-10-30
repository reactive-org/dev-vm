{ config, pkgs, ... }:
{
  programs.zsh = {
    enable = true;
    dotDir = "${config.xdg.configHome}/zsh";
    enableCompletion = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    history = { size = 10000; save = 10000; share = true; ignoreDups = true; };
    oh-my-zsh = {
      enable = true;
      plugins = [ "git" "aws" "ansible" "docker" "gradle" "npm" "terraform" ];
      theme = "";
    };
    shellAliases = {
      vi = "nvim";
      vim = "nvim";
      ll = "ls -lah";
      gs = "git status";
      gd = "git diff";
    };
    initContent = ''
      setopt AUTO_CD
      typeset -g POWERLEVEL9K_DISABLE_CONFIGURATION_WIZARD=true
      typeset -g POWERLEVEL9K_LEFT_PROMPT_ELEMENTS=(dir vcs prompt_char)
      typeset -g POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=(status command_execution_time)
      [[ ! -r "$HOME/.p10k.zsh" ]] || source "$HOME/.p10k.zsh"
    '';
  };
  programs.zsh.plugins = [{
    name = "powerlevel10k";
    src = pkgs.zsh-powerlevel10k;
    file = "share/zsh-powerlevel10k/powerlevel10k.zsh-theme";
  }];
  programs.direnv = { enable = true; enableZshIntegration = true; };
  programs.mise = { enable = true; enableZshIntegration = true; };
  programs.fzf = { enable = true; enableZshIntegration = true; };
  programs.zoxide = { enable = true; enableZshIntegration = true; };
}
