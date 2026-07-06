#!/usr/bin/env python3
"""
Upload this Unity iOS Xcode export folder to GitHub.

Default repo:
  https://github.com/tuan2610/NSOJUNE-IPA-BUILD.git

Typical use:
  py upload_xcode_export.py

Optional:
  py upload_xcode_export.py --message "Update build 2026-07-06"
  py upload_xcode_export.py --tag update-xcode-export-2026-07-06
  py upload_xcode_export.py --no-push
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_REPO = "https://github.com/tuan2610/NSOJUNE-IPA-BUILD.git"
DEFAULT_BRANCH = "main"

GITATTRIBUTES = """*.a filter=lfs diff=lfs merge=lfs -text
*.resS filter=lfs diff=lfs merge=lfs -text
Data/resources.assets filter=lfs diff=lfs merge=lfs -text
"""

GITIGNORE = """# Xcode generated files
/build/
/DerivedData/
*.xcarchive
*.ipa
*.dSYM/
*.xcresult
*.moved-aside

# User-local Xcode state
xcuserdata/
*.xcuserstate
*.xcscmblueprint

# OS/editor files
.DS_Store
Thumbs.db
Desktop.ini
.vscode/
.idea/
.vs/
__pycache__/
*.pyc

# Signing secrets - never commit these
*.p12
*.cer
*.mobileprovision
*.provisionprofile
*.certSigningRequest
ExportOptions.plist

# Local archives/backups
*.zip
*.rar
*.7z
"""

WORKFLOW = """name: Build IPA from Xcode Export

on:
  workflow_dispatch:
    inputs:
      export_method:
        description: "IPA export method"
        required: true
        default: "ad-hoc"
        type: choice
        options:
          - ad-hoc
          - app-store
          - development

permissions:
  contents: read

jobs:
  build-ipa:
    name: Build IPA
    runs-on: macos-latest
    timeout-minutes: 120

    env:
      IOS_BUNDLE_ID: ${{ vars.IOS_BUNDLE_ID }}
      APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
      IOS_CERTIFICATE_BASE64: ${{ secrets.IOS_CERTIFICATE_BASE64 }}
      IOS_CERTIFICATE_PASSWORD: ${{ secrets.IOS_CERTIFICATE_PASSWORD }}
      IOS_PROVISION_PROFILE_BASE64: ${{ secrets.IOS_PROVISION_PROFILE_BASE64 }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          lfs: true

      - name: Validate required secrets
        shell: bash
        run: |
          set -euo pipefail

          if [ -z "${IOS_BUNDLE_ID:-}" ]; then
            IOS_BUNDLE_ID="com.NSOJUNE.NSOJUNE"
          fi
          echo "IOS_BUNDLE_ID=$IOS_BUNDLE_ID" >> "$GITHUB_ENV"

          missing=0
          for name in APPLE_TEAM_ID IOS_CERTIFICATE_BASE64 IOS_CERTIFICATE_PASSWORD IOS_PROVISION_PROFILE_BASE64; do
            if [ -z "${!name:-}" ]; then
              echo "::error::$name is not set in GitHub Secrets."
              missing=1
            fi
          done

          if [ "$missing" -ne 0 ]; then
            exit 1
          fi

      - name: Install Apple signing assets
        shell: bash
        run: |
          set -euo pipefail

          CERTIFICATE_PATH="$RUNNER_TEMP/build_certificate.p12"
          PROFILE_PATH="$RUNNER_TEMP/build_profile.mobileprovision"
          PROFILE_PLIST="$RUNNER_TEMP/build_profile.plist"
          KEYCHAIN_PATH="$RUNNER_TEMP/app-signing.keychain-db"
          KEYCHAIN_PASSWORD="$(uuidgen)"

          decode_base64() {
            local value="$1"
            local output="$2"
            echo "$value" | base64 --decode > "$output" 2>/dev/null || echo "$value" | base64 -D > "$output"
          }

          decode_base64 "$IOS_CERTIFICATE_BASE64" "$CERTIFICATE_PATH"
          decode_base64 "$IOS_PROVISION_PROFILE_BASE64" "$PROFILE_PATH"

          security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
          security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
          security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
          security import "$CERTIFICATE_PATH" -P "$IOS_CERTIFICATE_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN_PATH"
          security set-key-partition-list -S apple-tool:,apple: -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
          security list-keychain -d user -s "$KEYCHAIN_PATH"
          security find-identity -v -p codesigning "$KEYCHAIN_PATH"

          mkdir -p "$HOME/Library/MobileDevice/Provisioning Profiles"
          security cms -D -i "$PROFILE_PATH" > "$PROFILE_PLIST"
          PROFILE_UUID=$(/usr/libexec/PlistBuddy -c "Print UUID" "$PROFILE_PLIST")
          PROFILE_NAME=$(/usr/libexec/PlistBuddy -c "Print Name" "$PROFILE_PLIST")
          cp "$PROFILE_PATH" "$HOME/Library/MobileDevice/Provisioning Profiles/$PROFILE_UUID.mobileprovision"

          echo "PROFILE_NAME=$PROFILE_NAME" >> "$GITHUB_ENV"
          echo "KEYCHAIN_PATH=$KEYCHAIN_PATH" >> "$GITHUB_ENV"

      - name: Prepare Unity Xcode export
        shell: bash
        run: |
          set -euo pipefail

          find . -type f \\( -name "*.sh" -o -name "usymtool*" -o -name "il2cpp" -o -name "bee_backend" \\) -exec chmod +x {} \\;

          if [ -f "Podfile" ]; then
            sudo gem install cocoapods
            pod install
          fi

          if [ -d "Unity-iPhone.xcworkspace" ]; then
            echo "XCODE_CONTAINER_FLAG=-workspace" >> "$GITHUB_ENV"
            echo "XCODE_CONTAINER_PATH=Unity-iPhone.xcworkspace" >> "$GITHUB_ENV"
          else
            echo "XCODE_CONTAINER_FLAG=-project" >> "$GITHUB_ENV"
            echo "XCODE_CONTAINER_PATH=Unity-iPhone.xcodeproj" >> "$GITHUB_ENV"
          fi

      - name: Archive app
        shell: bash
        run: |
          set -euo pipefail

          xcodebuild \\
            "$XCODE_CONTAINER_FLAG" "$XCODE_CONTAINER_PATH" \\
            -scheme Unity-iPhone \\
            -configuration Release \\
            -sdk iphoneos \\
            -destination "generic/platform=iOS" \\
            -archivePath "$RUNNER_TEMP/NSOJUNE.xcarchive" \\
            DEVELOPMENT_TEAM="$APPLE_TEAM_ID" \\
            CODE_SIGN_STYLE=Manual \\
            PROVISIONING_PROFILE_SPECIFIER="$PROFILE_NAME" \\
            PRODUCT_BUNDLE_IDENTIFIER="$IOS_BUNDLE_ID" \\
            clean archive

      - name: Export IPA
        shell: bash
        run: |
          set -euo pipefail

          mkdir -p ipa
          cat > "$RUNNER_TEMP/ExportOptions.plist" <<EOF
          <?xml version="1.0" encoding="UTF-8"?>
          <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
          <plist version="1.0">
          <dict>
            <key>method</key>
            <string>${{ inputs.export_method }}</string>
            <key>teamID</key>
            <string>$APPLE_TEAM_ID</string>
            <key>signingStyle</key>
            <string>manual</string>
            <key>provisioningProfiles</key>
            <dict>
              <key>$IOS_BUNDLE_ID</key>
              <string>$PROFILE_NAME</string>
            </dict>
            <key>stripSwiftSymbols</key>
            <true/>
            <key>compileBitcode</key>
            <false/>
          </dict>
          </plist>
          EOF

          xcodebuild \\
            -exportArchive \\
            -archivePath "$RUNNER_TEMP/NSOJUNE.xcarchive" \\
            -exportOptionsPlist "$RUNNER_TEMP/ExportOptions.plist" \\
            -exportPath ipa

      - name: Upload IPA artifact
        uses: actions/upload-artifact@v4
        with:
          name: NSOJUNE-${{ inputs.export_method }}-ipa
          path: ipa/*.ipa
          if-no-files-found: error

      - name: Cleanup signing keychain
        if: always()
        shell: bash
        run: |
          if [ -n "${KEYCHAIN_PATH:-}" ]; then
            security delete-keychain "$KEYCHAIN_PATH" || true
          fi
"""

README = """# Build IPA from this Xcode export

This folder is a Unity iOS Xcode export. GitHub Actions builds the IPA directly
from `Unity-iPhone.xcodeproj`.

Large Unity export files are tracked through Git LFS:

- `Data/resources.assets.resS`
- `Libraries/*.a`
- `*.resS`

Required GitHub repository secrets:

- `APPLE_TEAM_ID`
- `IOS_CERTIFICATE_BASE64`
- `IOS_CERTIFICATE_PASSWORD`
- `IOS_PROVISION_PROFILE_BASE64`

Optional repository variable:

- `IOS_BUNDLE_ID` - defaults to `com.NSOJUNE.NSOJUNE`

The finished `.ipa` is uploaded as a GitHub Actions artifact.
"""


def find_git() -> str:
    env_git = os.environ.get("GIT_EXE")
    candidates = []
    if env_git:
        candidates.append(env_git)

    which_git = shutil.which("git")
    if which_git:
        candidates.append(which_git)

    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates.extend(
        glob.glob(
            os.path.join(
                local_app,
                "GitHubDesktop",
                "app-*",
                "resources",
                "app",
                "git",
                "cmd",
                "git.exe",
            )
        )
    )
    candidates.extend(
        [
            r"C:\Program Files\Git\cmd\git.exe",
            r"C:\Program Files\Git\bin\git.exe",
            r"C:\Program Files (x86)\Git\cmd\git.exe",
        ]
    )

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    raise SystemExit(
        "Khong tim thay git.exe. Hay cai Git for Windows hoac GitHub Desktop."
    )


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("\n$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd), text=True)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result


def write_if_changed(path: Path, content: str) -> None:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Updated helper file: {path}")


def ensure_helper_files(root: Path) -> None:
    write_if_changed(root / ".gitattributes", GITATTRIBUTES)
    write_if_changed(root / ".gitignore", GITIGNORE)
    write_if_changed(root / ".github" / "workflows" / "build-xcode-ipa.yml", WORKFLOW)
    write_if_changed(root / "ci" / "README_BUILD_XCODE_IPA.md", README)


def git_output(git: str, root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        [git, *args],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return (proc.stdout + proc.stderr).strip()


def ensure_repo(git: str, root: Path, repo_url: str, branch: str) -> None:
    if not (root / ".git").exists():
        run([git, "init"], root)

    run([git, "lfs", "install", "--local"], root)

    remotes = git_output(git, root, ["remote"])
    if "origin" not in remotes.split():
        run([git, "remote", "add", "origin", repo_url], root)
    else:
        run([git, "remote", "set-url", "origin", repo_url], root)

    current_branch = git_output(git, root, ["branch", "--show-current"])
    if current_branch != branch:
        run([git, "branch", "-M", branch], root)


def has_staged_changes(git: str, root: Path) -> bool:
    result = subprocess.run([git, "diff", "--cached", "--quiet"], cwd=str(root))
    return result.returncode == 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit and push this Unity iOS Xcode export to GitHub."
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository URL")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to push")
    parser.add_argument("--message", help="Commit message")
    parser.add_argument("--tag", help="Optional tag name to create/update")
    parser.add_argument("--no-push", action="store_true", help="Commit only, do not push")
    parser.add_argument(
        "--skip-helper-files",
        action="store_true",
        help="Do not rewrite .gitignore/.gitattributes/workflow helper files",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    git = find_git()

    print(f"Folder: {root}")
    print(f"Git: {git}")
    print(f"Repo: {args.repo}")

    if not (root / "Unity-iPhone.xcodeproj").exists():
        raise SystemExit(
            "Khong thay Unity-iPhone.xcodeproj. Hay dat file py trong folder Xcode export."
        )

    if not args.skip_helper_files:
        ensure_helper_files(root)

    ensure_repo(git, root, args.repo, args.branch)

    run([git, "add", "-A"], root)

    print("\nLFS files:")
    run([git, "lfs", "ls-files"], root, check=False)

    if not has_staged_changes(git, root):
        print("\nKhong co thay doi moi de commit.")
        if not args.no_push:
            run([git, "push", "origin", args.branch], root)
        return 0

    message = args.message or (
        "Update Unity iOS Xcode export "
        + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    run([git, "commit", "-m", message], root)

    if args.tag:
        run([git, "tag", "-f", args.tag], root)

    if args.no_push:
        print("\nDa commit local. Bo qua push vi co --no-push.")
        return 0

    run([git, "push", "origin", args.branch], root)
    if args.tag:
        run([git, "push", "origin", "-f", args.tag], root)

    print("\nXong. Da upload len GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
