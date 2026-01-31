"""
Build Script - Create Windows Executable

Uses PyInstaller to package the TraderVolt Migrator as a single .exe file.

Usage:
    python build.py
    
Output:
    dist/TraderVoltMigrator.exe
"""

import subprocess
import sys
import os
from pathlib import Path


def main():
    # Ensure we're in the project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("=" * 60)
    print("Building TraderVolt Migrator Windows Executable")
    print("=" * 60)
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"✓ PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=TraderVoltMigrator",
        "--onefile",           # Single executable
        "--windowed",          # No console window (GUI app)
        "--icon=NONE",         # No custom icon (add .ico later if needed)
        "--add-data=.env;.",   # Include .env file
        "--hidden-import=src",
        "--hidden-import=src.gui",
        "--hidden-import=src.gui.app",
        "--hidden-import=src.gui.commands",
        "--hidden-import=src.commands",
        "--hidden-import=src.commands.discover",
        "--hidden-import=src.commands.plan",
        "--hidden-import=src.commands.validate",
        "--hidden-import=src.commands.apply",
        "--hidden-import=src.commands.cleanup",
        "--hidden-import=src.parsers",
        "--hidden-import=src.parsers.htm_parser",
        "--hidden-import=src.parsers.json_parser",
        "--hidden-import=src.models",
        "--hidden-import=src.models.entities",
        "--hidden-import=src.tradervolt_client",
        "--hidden-import=src.tradervolt_client.api",
        "--clean",             # Clean PyInstaller cache
        "run_gui.py"
    ]
    
    print("\nRunning PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = project_root / "dist" / "TraderVoltMigrator.exe"
        print("\n" + "=" * 60)
        print("✓ BUILD SUCCESSFUL!")
        print("=" * 60)
        print(f"\nExecutable: {exe_path}")
        print(f"Size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
        print("\nTo run: double-click TraderVoltMigrator.exe in the dist folder")
    else:
        print("\n✗ BUILD FAILED")
        print("Check the output above for errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
