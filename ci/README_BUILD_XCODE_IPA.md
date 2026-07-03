# Build IPA from this Xcode export

This folder is already a Unity iOS Xcode export. The GitHub Actions workflow builds the IPA directly from `Unity-iPhone.xcodeproj`, without rebuilding from the Unity client project.

## Important: use Git LFS

This export has files larger than GitHub's normal 100 MB file limit, including:

- `Data/resources.assets.resS`
- `Libraries/libiPhone-lib.a`

Those files are tracked by `.gitattributes`, but the repo must use Git LFS before pushing.

## Commit this folder

Commit this Xcode export folder with:

- `.gitattributes`
- `.gitignore`
- `.github/workflows/build-xcode-ipa.yml`
- `Unity-iPhone.xcodeproj/`
- `Classes/`
- `Data/`
- `Il2CppOutputProject/`
- `Libraries/`
- `Unity-iPhone/`
- `UnityFramework/`
- root plist/storyboard/png/shell files

Do not commit signing files such as `.p12` or `.mobileprovision`.

## Required GitHub Secrets

Add these in GitHub repository `Settings > Secrets and variables > Actions > Repository secrets`:

- `APPLE_TEAM_ID`
- `IOS_CERTIFICATE_BASE64`
- `IOS_CERTIFICATE_PASSWORD`
- `IOS_PROVISION_PROFILE_BASE64`

Optional repository variable:

- `IOS_BUNDLE_ID` - leave empty to use `com.NSOJUNE.NSOJUNE`

## Convert signing files to base64

PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\certificate.p12")) | Set-Clipboard
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\profile.mobileprovision")) | Set-Clipboard
```

macOS:

```bash
base64 -i certificate.p12 | pbcopy
base64 -i profile.mobileprovision | pbcopy
```

Paste the certificate value into `IOS_CERTIFICATE_BASE64`.
Paste the provisioning profile value into `IOS_PROVISION_PROFILE_BASE64`.

## Run the build

In GitHub, open `Actions`, choose `Build IPA from Xcode Export`, click `Run workflow`, then choose:

- `ad-hoc` for installing on registered devices
- `app-store` for App Store/TestFlight signing
- `development` for development profiles

The `.ipa` is uploaded as a workflow artifact.
