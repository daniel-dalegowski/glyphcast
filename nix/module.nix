# home-manager module for Glyphcast.
#
# Usage, in a home-manager config:
#
#   imports = [ glyphcast.homeManagerModules.default ];
#   programs.glyphcast = {
#     enable = true;
#     settings.latitude = 47.6;
#     settings.longitude = -122.3;
#   };
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.programs.glyphcast;
  tomlFormat = pkgs.formats.toml { };
in
{
  options.programs.glyphcast = {
    enable = lib.mkEnableOption "Glyphcast, an hourly weather overlay for a wallpaper image";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./package.nix { };
      description = "The glyphcast package to use.";
    };

    interval = lib.mkOption {
      type = lib.types.str;
      default = "hourly";
      description = "systemd OnCalendar expression for how often to refresh.";
    };

    settings = lib.mkOption {
      type = tomlFormat.type;
      default = { };
      description = ''
        Settings written to ~/.config/glyphcast/config.toml. At minimum, set
        `latitude`/`longitude`. See the README's Configuration table for the
        full key reference. `base_image`/`output` default to Glyphscape's
        own wallpaper path, so the common case needs no path overrides.
      '';
      example = lib.literalExpression ''
        {
          latitude = 47.6062;
          longitude = -122.3321;
          units = "celsius";
        }
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ];

    xdg.configFile."glyphcast/config.toml".source = tomlFormat.generate "glyphcast-config.toml" cfg.settings;

    systemd.user.services.glyphcast = {
      Unit.Description = "Composite current weather onto the configured wallpaper image";
      Service = {
        Type = "oneshot";
        ExecStart = "${cfg.package}/bin/glyphcast";
      };
    };

    systemd.user.timers.glyphcast = {
      Unit.Description = "Hourly timer for Glyphcast";
      Timer = {
        OnCalendar = cfg.interval;
        Persistent = true;
        OnStartupSec = "1min";
      };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
