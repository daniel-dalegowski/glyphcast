# Builds the `glyphcast` CLI with fontconfig and DejaVu Sans on its PATH --
# the default `font` vocabulary (round symbols, box-drawing diagonals,
# chevrons) is measured against DejaVu Sans, same font family Glyphscape's
# own "symbols" script uses.
{
  lib,
  python3Packages,
  fontconfig,
  makeFontsConf,
  dejavu_fonts,
}:

let
  fontsConf = makeFontsConf { fontDirectories = [ dejavu_fonts ]; };
in
python3Packages.buildPythonApplication {
  pname = "glyphcast";
  version = "0.1.0";
  pyproject = true; # nixpkgs < 24.05: replace with `format = "pyproject";`

  src = ../.;

  build-system = [ python3Packages.setuptools ];

  propagatedBuildInputs = with python3Packages; [
    pillow
    requests
  ];

  makeWrapperArgs = [
    "--prefix"
    "PATH"
    ":"
    (lib.makeBinPath [ fontconfig ])
    "--set"
    "FONTCONFIG_FILE"
    fontsConf
  ];

  # No test suite yet; the pipeline is exercised via `glyphcast render --mock`.
  doCheck = false;

  meta = {
    description = "Hourly weather overlay, composited in Glyphscape's density-ramp glyph language";
    mainProgram = "glyphcast";
    platforms = lib.platforms.linux;
  };
}
