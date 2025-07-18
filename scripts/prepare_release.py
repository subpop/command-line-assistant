#!/usr/bin/env python3
"""Script to manage release process for Command Line Assistant."""

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Define the project root relative to this script
PROJECT_ROOT = Path(__file__).parent.parent

# Files that need version updates
VERSION_FILES = {
    "constants": PROJECT_ROOT / "command_line_assistant" / "constants.py",
    "selinux": PROJECT_ROOT / "data" / "release" / "selinux" / "clad.te",
    "spec": PROJECT_ROOT / "packaging" / "command-line-assistant.spec",
    "pyproject": PROJECT_ROOT / "pyproject.toml",
    "docs": PROJECT_ROOT / "docs" / "source" / "conf.py",
    "makefile": PROJECT_ROOT / "Makefile",
    "containerfile": PROJECT_ROOT / "Containerfile",
}


def update_makefile_version(new_version: str) -> None:
    """Update version in Makefile.

    Arguments:
        new_version (str): New version to set
    """
    with VERSION_FILES["makefile"].open("r") as f:
        content = f.read()

    updated = re.sub(r"VERSION := [\d.]+", f"VERSION := {new_version}", content)

    with VERSION_FILES["makefile"].open("w") as f:
        f.write(updated)


def is_in_virtualenv() -> bool:
    """Check if running inside a virtual environment.

    Returns:
        bool: True if in a virtual environment, False otherwise
    """
    # Check for the presence of the VIRTUAL_ENV environment variable
    # which is set by most virtual environment tools (venv, virtualenv)
    return "VIRTUAL_ENV" in os.environ


def run_make_man() -> None:
    """Run 'make man' to update man pages with new version."""
    print("\nUpdating man pages...")
    try:
        subprocess.run(
            ["make", "man"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error updating man pages: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise RuntimeError("Failed to update man pages") from e


def update_pyproject_version(new_version: str) -> None:
    """Update version in pyproject.toml.

    Arguments:
        new_version (str): New version to set
    """
    with VERSION_FILES["pyproject"].open("r") as f:
        content = f.read()

    updated = re.sub(r'version = "[\d.]+"', f'version = "{new_version}"', content)

    with VERSION_FILES["pyproject"].open("w") as f:
        f.write(updated)


def update_containerfile_version(new_version: str) -> None:
    """Update version in Containerfile.

    Arguments:
        new_version (str): New version to set
    """
    with VERSION_FILES["containerfile"].open("r") as f:
        content = f.read()

    updated = re.sub(r"VERSION=[\d.]+", f"VERSION={new_version}", content)

    with VERSION_FILES["containerfile"].open("w") as f:
        f.write(updated)


def update_docs_version(new_version: str) -> None:
    """Update version in docs/source/conf.py.

    Arguments:
        new_version (str): New version to set
    """
    with VERSION_FILES["docs"].open("r") as f:
        content = f.read()

    updated = re.sub(
        r'release = version = "[\d.]+"', f'release = version = "{new_version}"', content
    )

    with VERSION_FILES["docs"].open("w") as f:
        f.write(updated)


def update_selinux_version(new_version: str) -> None:
    """Update version in SELinux policy module.

    Arguments:
        new_version (str): New version to set
    """
    with VERSION_FILES["selinux"].open("r") as f:
        content = f.read()

    updated = re.sub(
        r"policy_module\(clad, [\d.]+\)", f"policy_module(clad, {new_version})", content
    )

    with VERSION_FILES["selinux"].open("w") as f:
        f.write(updated)


def update_constants_version(new_version: str) -> None:
    """Update version in constants.py.

    Arguments:
        new_version (str): New version to set
    """
    with VERSION_FILES["constants"].open("r") as f:
        content = f.read()

    updated = re.sub(r'VERSION = "[\d.]+"', f'VERSION = "{new_version}"', content)

    with VERSION_FILES["constants"].open("w") as f:
        f.write(updated)


def parse_current_version() -> str:
    """Parse current version from constants.py.

    Returns:
        str: Current version string
    """
    with VERSION_FILES["constants"].open() as f:
        content = f.read()
        match = re.search(r'VERSION = "([\d.]+)"', content)
        if not match:
            raise ValueError("Could not find current version in constants.py")
        return match.group(1)


def parse_github_changelog(changelog_path: Path) -> List[str]:
    """Parse GitHub-generated changelog markdown file.

    Arguments:
        changelog_path (Path): Path to the changelog markdown file

    Returns:
        List[str]: List of changelog entries formatted for RPM spec
    """
    changelog_entries = []

    with changelog_path.open() as f:
        content = f.read()

    # Find all bullet points that match the GitHub PR format
    matches = re.finditer(
        r"^\* (?:\[([^\]]+)\])?\s*(.+?)\s+(?:by @[\w-]+)?\s+in\s+https://github\.com/.+?/pull/\d+\s*$",
        content,
        re.MULTILINE,
    )

    for match in matches:
        message = match.group(2)  # Captures the actual change message
        entry = f"- {message}"
        changelog_entries.append(entry)

    return changelog_entries


def validate_version(version: str) -> bool:
    """Validate version string format.

    Arguments:
        version (str): Version string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return bool(re.match(r"^\d+\.\d+\.\d+$", version))


def format_rpm_changelog(entries: List[str]) -> str:
    """Format changelog entries for RPM spec file.

    Arguments:
        entries (List[str]): List of changelog entries

    Returns:
        str: Formatted changelog text
    """
    # Add proper indentation for RPM spec
    return "\n".join(f"  {entry}" for entry in entries)


def update_spec_file(new_version: str, changelog_entry: Optional[str] = None) -> None:
    """Update version and changelog in spec file.

    Arguments:
        new_version (str): New version to set
        changelog_entry (Optional[str]): Changelog entry to add
    """
    with VERSION_FILES["spec"].open("r") as f:
        content = f.read()

    # Update version
    content = re.sub(r"Version:\s+[\d.]+", f"Version:        {new_version}", content)

    # Add changelog entry if provided
    if changelog_entry:
        today = datetime.datetime.now().strftime("%a %b %d %Y")
        new_entry = f"""
%changelog
* {today} Command Line Assistant Team <lightspeed-dev@redhat.com> - {new_version}-1
{changelog_entry}

"""
        content = re.sub(r"(%changelog\n)", rf"\g<1>{new_entry}", content)

    with VERSION_FILES["spec"].open("w") as f:
        f.write(content)


def checkout_to_prepare_release_branch(version: str) -> None:
    try:
        subprocess.run(
            ["git", "checkout", "-b", f"prepare-release-{version}"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error checking out to new branch: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise RuntimeError("Failed to create prepare release branch") from e


def update_changelogs(changelog: Path) -> str:
    # Parse changelog if provided
    changelog_entry = ""
    print("\nParsing changelog...")
    changelog_entries = parse_github_changelog(changelog)
    if changelog_entries:
        changelog_entry = format_rpm_changelog(changelog_entries)
        print("✓ Changelog parsed successfully")
    else:
        print("Warning: No changelog entries found in the provided file")

    return changelog_entry


def main() -> int:
    """Main function.

    Returns:
        int: Exit code
    """
    # Check if running in a virtual environment
    if not is_in_virtualenv():
        print(
            "Error: This script must be run from within a virtual environment.",
            file=sys.stderr,
        )
        print(
            "Please activate your virtual environment and try again.", file=sys.stderr
        )
        return 1

    parser = argparse.ArgumentParser(
        description="Manage Command Line Assistant releases"
    )
    parser.add_argument("version", help="New version number (format: X.Y.Z)")
    parser.add_argument(
        "-c",
        "--changelog",
        help="Path to GitHub-generated changelog markdown file",
        type=Path,
    )

    args = parser.parse_args()

    if not validate_version(args.version):
        print("Error: Version must be in format X.Y.Z")
        return 1

    try:
        current_version = parse_current_version()
        print(f"Current version: {current_version}")
        print(f"New version: {args.version}")

        changelog_entry = None
        if args.changelog and args.changelog.exists():
            changelog_entry = update_changelogs(args.changelog)
        elif args.changelog:
            print(f"Error: Changelog file {args.changelog} not found")
            return 1

        checkout_to_prepare_release_branch(args.version)
        print("✓ Branch created successfully")

        # Update all files
        update_constants_version(args.version)
        print("✓ Updated constants.py")

        update_selinux_version(args.version)
        print("✓ Updated SELinux policy module")

        update_spec_file(args.version, changelog_entry)
        print("✓ Updated spec file")

        update_pyproject_version(args.version)
        print("✓ Updated pyproject.toml")

        update_containerfile_version(args.version)
        print("✓ Updated Containerfile")

        update_docs_version(args.version)
        print("✓ Updated conf.py")

        update_makefile_version(args.version)
        print("✓ Updated Makefile")

        run_make_man()
        print("✓ Successfully updated man pages")

        print("\nRelease preparation complete!")
        print("\nPlease review the changes and commit them.")
        return 0

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
