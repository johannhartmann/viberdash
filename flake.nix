{
  description = "ViberDash - A terminal dashboard for Python code quality metrics";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, uv2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;
        
        # For development, we use a manual package set
        pythonEnv = python.withPackages (ps: with ps; [
          # Development tools
          black
          ruff
          mypy
          ipython
          pytest-watch  # Added missing dev dependency
          
          # Project dependencies
          rich
          click
          tomli
          
          # Analysis tools that will be wrapped
          radon
          pylint
          coverage
          pytest
          pytest-cov
          vulture
        ]);
        
        # Load pyproject.toml to get project metadata
        pyprojectToml = builtins.fromTOML (builtins.readFile ./pyproject.toml);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python and environment
            pythonEnv
            
            # UV for end-user installation testing
            uv
            
            # Git for version control
            git
            
            # Additional development tools
            ripgrep
            fd
            bat
            jq
            
            # SQLite for data storage
            sqlite
            
            # For watching file changes (optional)
            watchexec
          ];

          shellHook = ''
            echo "🚀 ViberDash Development Environment"
            echo "──────────────────────────────────"
            echo "Python: ${python.version}"
            echo ""
            echo "Available commands:"
            echo "  python       - Python ${python.version} with all dependencies"
            echo "  pylint       - Code quality checker"
            echo "  radon        - Code complexity analyzer"
            echo "  vulture      - Dead code finder"
            echo "  uv           - For testing end-user installation"
            echo ""
          '';

          # Environment variables
          PYTHONPATH = ".";
          VIBERDASH_DEV = "1";
        };
        
        # Package output for end-user installation
        packages.default = python.pkgs.buildPythonPackage {
          pname = "viberdash";
          version = pyprojectToml.project.version;
          
          src = ./.;
          
          # Use the modern pyproject format
          format = "pyproject";
          
          # Build system dependencies
          nativeBuildInputs = with python.pkgs; [
            hatchling
          ];
          
          # Runtime dependencies from pyproject.toml
          propagatedBuildInputs = with python.pkgs; [
            rich
            click
            tomli
            radon
            pylint
            coverage
            pytest
            pytest-cov
            vulture
          ];
          
          # Optional: include test dependencies
          nativeCheckInputs = with python.pkgs; [
            pytest
            pytest-cov
          ];
          
          # Run tests during build
          checkPhase = ''
            runHook preCheck
            pytest tests/
            runHook postCheck
          '';
          
          meta = with pkgs.lib; {
            description = pyprojectToml.project.description;
            homepage = pyprojectToml.project.urls.Homepage;
            license = licenses.mit;
            maintainers = [];
          };
        };
      });
}