# Build IPA from this Xcode export

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
